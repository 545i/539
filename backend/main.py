"""FastAPI 進入點:取代舊的 Streamlit app.py。

- 路由前綴 APP_PREFIX(正式環境 "/539"),讓整包掛在 taiwansilver.shop/539/ 下,
  nginx / cloudflared 不用動。
- startup 掛 autoupdate 背景排程 —— 不再需要「有人開過頁面才會起來」。
- 前端 build 產物(frontend/dist)由 StaticFiles 同源提供。

啟動(dev):APP_PREFIX=/539 uvicorn backend.main:app --port 8540 --reload
啟動(prod):uvicorn backend.main:app --host 127.0.0.1 --port 8539 --root-path /539
           (systemd 帶 Environment=APP_PREFIX=/539)
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.data import DATA_DIR, PROJECT_ROOT, all_games, game_data_path
from backend import autosettle, bot, reminders, star_cost_store, ws
from backend.routers import (audit, auth, combo, cycles, editions, erhe, export,
                             games, groups, history, importer, ledger,
                             leaderboard, pillar, predict, settings, star_cost,
                             stats, upload_history)
from core import autoupdate, notify

PREFIX = os.environ.get("APP_PREFIX", "").rstrip("/")
DIST_DIR = PROJECT_ROOT / "frontend" / "dist"

# 開獎/推播事件寫進 journal(uvicorn 的 stdout → systemd),供事後稽核
# 「某期到底有沒有推成 Telegram」。以前這條路徑完全沒 log,查不到。
# uvicorn 預設不給 root logger 掛 handler,自訂 logger 的 INFO 不會輸出 —— 這裡
# 自己掛一個 stdout handler(INFO 也印),避免只看得到 WARNING 以上。
log = logging.getLogger("lotto")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s: %(name)s: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def _on_new_draw(game_key: str) -> None:
    """排程抓到新開獎時:先自動對獎(結算待開獎),廣播給前端,再推 Telegram。

    每一步在 journal 留痕(draw 偵測 → 對獎筆數 → 推播 ok/fail),方便事後查
    「這期到底有沒有推成」。推播失敗會連 notify.last_error() 一起印出來。
    """
    log.info("[draw] 偵測到新開獎:game=%s", game_key)
    settled = 0
    try:
        settled = autosettle.settle_pending(game_key)   # 開獎時自動對獎(跨所有人 / 版)
    except Exception:       # noqa: BLE001 — 對獎失敗不影響提醒與排程
        log.exception("[draw] 自動對獎失敗:game=%s", game_key)
    try:
        ws.hub.publish({"type": "draw", "game": game_key, "settled": settled})
    except Exception:       # noqa: BLE001
        log.exception("[draw] WebSocket 廣播失敗:game=%s", game_key)
    try:
        pushed = reminders.on_new_draw(game_key)
        if pushed:
            log.info("[draw] Telegram 推播成功:game=%s settled=%d", game_key, settled)
        elif not notify.enabled():
            log.warning("[draw] 未推播:未設定 TELEGRAM_BOT_TOKEN/CHAT_ID game=%s",
                        game_key)
        else:
            log.error("[draw] Telegram 推播失敗:game=%s reason=%s",
                      game_key, notify.last_error() or "(無資料或空提醒)")
    except Exception:       # noqa: BLE001
        log.exception("[draw] 推播流程例外:game=%s", game_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 背景抓開獎資料(daemon thread,全行程只起一條)
    DATA_DIR.mkdir(exist_ok=True)
    # WebSocket 廣播要用主事件迴圈(背景排程從別的執行緒丟訊息回來)
    ws.hub.bind_loop(asyncio.get_running_loop())
    # 把後台存的連碰盤口套進 core.combo(全域生效)
    star_cost_store.apply_to_core()
    # 啟動先掃一次:補上停機期間錯過、卻已經開了的待開獎紀錄
    try:
        autosettle.settle_pending()
    except Exception:       # noqa: BLE001
        pass
    # 有新開獎 → 自動對獎 + 檢查斷檔推 Telegram(見 _on_new_draw)
    autoupdate.start_scheduler(
        {g.key: game_data_path(g) for g in all_games()},
        on_done=None, on_added=_on_new_draw)
    # Telegram bot 收訊(/提醒 + 清除按鈕);沒設 token/chat_id 就不起
    bot.start()
    yield


app = FastAPI(title="今彩539 統計分析系統", lifespan=lifespan)

# dev 時前端跑 3000 埠、後端 8540,需要 CORS;正式同源可省但留著無害
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = f"{PREFIX}/api"
for r in (auth.router, games.router, history.router, stats.router,
          pillar.router, combo.router, erhe.router, ledger.router,
          leaderboard.router, export.router, settings.router,
          predict.router, importer.router, star_cost.router, audit.router,
          groups.router, editions.router, upload_history.router,
          cycles.router):
    app.include_router(r, prefix=api_prefix)


@app.get(f"{PREFIX}/api/health")
def health():
    return {"ok": True}


@app.websocket(f"{PREFIX}/api/ws")
async def ws_endpoint(websocket: WebSocket):
    """前端連這條就會收到「開獎 / 自動對獎」等資料變動通知,收到就重抓資料。

    只做保活:收到什麼都忽略,斷線就移除。真正的訊息一律由後端 hub.publish 推出。
    """
    await ws.hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()   # 保活;內容忽略(斷線會拋例外)
    except Exception:       # noqa: BLE001 — 斷線 / 任何錯 → 收掉這條連線
        pass
    finally:
        ws.hub.disconnect(websocket)


class SpaStaticFiles(StaticFiles):
    """SPA 靜態檔:index.html 不快取(每次重新驗證 → 部署後自動拿到新版),
    帶 hash 的 assets 長快取(檔名一變就自動失效,可放心 immutable)。

    先前 index.html 沒有 Cache-Control,手機瀏覽器會啟發式快取,導致部署後
    使用者一直看到舊版前端。
    """
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        ctype = resp.headers.get("content-type", "")
        if "text/html" in ctype:
            resp.headers["Cache-Control"] = "no-cache"
        elif path.startswith("assets/") or "/assets/" in path:
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp


# 前端靜態檔(build 後才有;dev 由 vite 提供,不掛)
if DIST_DIR.exists():
    app.mount(f"{PREFIX}/", SpaStaticFiles(directory=str(DIST_DIR), html=True),
              name="frontend")
