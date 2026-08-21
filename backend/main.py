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

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.data import DATA_DIR, PROJECT_ROOT, all_games, game_data_path
from backend import star_cost_store
from backend.routers import (audit, auth, combo, erhe, export, games, history,
                             importer, ledger, leaderboard, pillar, predict,
                             settings, star_cost, stats)
from core import autoupdate

PREFIX = os.environ.get("APP_PREFIX", "").rstrip("/")
DIST_DIR = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 背景抓開獎資料(daemon thread,全行程只起一條)
    DATA_DIR.mkdir(exist_ok=True)
    # 把後台存的連碰盤口套進 core.combo(全域生效)
    star_cost_store.apply_to_core()
    autoupdate.start_scheduler(
        {g.key: game_data_path(g) for g in all_games()}, on_done=None)
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
          predict.router, importer.router, star_cost.router, audit.router):
    app.include_router(r, prefix=api_prefix)


@app.get(f"{PREFIX}/api/health")
def health():
    return {"ok": True}


# 前端靜態檔(build 後才有;dev 由 vite 提供,不掛)
if DIST_DIR.exists():
    app.mount(f"{PREFIX}/", StaticFiles(directory=str(DIST_DIR), html=True),
              name="frontend")
