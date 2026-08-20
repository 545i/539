"""設定頁:開獎資料的更新狀態,以及「立即抓取」的手動備援。

狀態是**算出來的**,不是排程回報的:各款依 core.drawtime 的開獎時刻表算出
「到現在為止最後一期應該抓得到的是哪一天」,再跟 CSV 的最新日期比 —— 所以
就算排程剛重啟、什麼都還沒跑過,這頁也看得出資料到底追上了沒。
autoupdate.status() 的內容(上次跑的訊息 / 錯誤 / 試了幾次)另外附在 status 欄。

「立即抓取」直接同步跑 autoupdate.catch_up:與背景排程共用同一段程式,
但不受「同一期最多試 12 次」的限制(手動就是要能硬抓)。單款抓失敗不會拖垮
其他款,錯誤放進該款的 error 欄回給前端。
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.data import all_games, game_data_path, get_game
from backend.deps import current_user
from core import autoupdate, drawtime

router = APIRouter(prefix="/settings", tags=["settings"])


def _iso(d) -> str | None:
    return d.isoformat() if d is not None else None


def _status_of(game) -> dict:
    """單款的更新狀態(給設定頁顯示用)。"""
    path = game_data_path(game)
    latest = autoupdate.latest_date(path, game.key)
    state = drawtime.staleness(game.key, latest)
    sched = drawtime.get(game.key)
    st = autoupdate.status(game.key)
    done_ts = st.get("done_ts")

    return {
        "key": game.key,
        "name": game.name,
        "short_name": game.label,
        "data_file": game.data_file,
        "scheduled": sched is not None,     # 沒登記時刻表的款不自動更新
        "note": sched.note if sched else "",
        "latest": _iso(latest),
        "target": _iso(state["target"]),
        "stale": state["stale"],
        "next_draw": _iso(state["next_draw"]),
        "status": {
            "running": bool(st.get("running")),
            "msg": st.get("msg", ""),
            "error": st.get("error", ""),
            "attempts": int(st.get("attempts", 0) or 0),
            "added": int(st.get("added", 0) or 0),
            "done_at": (dt.datetime.fromtimestamp(done_ts).isoformat(timespec="seconds")
                        if done_ts else None),
        },
    }


@router.get("/autoupdate")
def autoupdate_status():
    """各款的開獎更新狀態 + 排程執行緒是否活著。"""
    return {
        "scheduler_running": autoupdate.scheduler_running(),
        "tick_seconds": autoupdate.TICK_SECONDS,
        "max_attempts": autoupdate.MAX_ATTEMPTS,
        "checked_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": [_status_of(g) for g in all_games()],
    }


class FetchNowIn(BaseModel):
    game: str | None = None     # 不給就抓全部有登記時刻表的款


@router.post("/fetch-now")
def fetch_now(body: FetchNowIn | None = None, user: str = Depends(current_user)):
    """立即補抓開獎資料(同步,抓完才回);單款失敗不影響其他款。"""
    key = body.game if body else None
    games = [get_game(key)] if key else [g for g in all_games()
                                         if drawtime.get(g.key) is not None]

    results = []
    for g in games:
        row = {"key": g.key, "name": g.name, "ok": False,
               "fetched": 0, "added": 0, "latest": None, "error": ""}
        try:
            res = autoupdate.catch_up(g.key, game_data_path(g))
            row.update(ok=True, fetched=res["fetched"], added=res["added"],
                       latest=_iso(res["latest"]))
        except Exception as e:      # noqa: BLE001 — 抓取失敗要顯示給使用者,不是 500
            row["error"] = str(e)
        results.append(row)

    return {"results": results, "games": [_status_of(g) for g in all_games()]}
