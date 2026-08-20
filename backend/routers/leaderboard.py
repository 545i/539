"""排行榜:把記帳流水彙總成「誰賺賠多少」與「哪種下法表現怎樣」。

資料只有一個來源 —— ledger_store 的流水帳,不是回測、也不是模擬。所以看得到
的都是**使用者實際記過帳的局**,沒人記帳就是空榜,不會生出假資料。

要登入才看得到(current_user):榜上有其他人的帳號與損益,不該對外開放。
自己那一列會標 is_me,前端拿來高亮。

勝率 = 賺錢的局 / 總局數;報酬率 = 總損益 / 總成本(成本為 0 時回 None,
不是 0 —— 「沒下過本金」和「打平」是兩回事)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend import ledger_store
from backend.deps import current_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

# 下法代號 → 顯示名稱(對應前端 DuoBetTab 的四個記帳分頁)
MODE_NAMES = {
    "single": "單顆下注",
    "multi": "多顆下注",
    "pillar1800": "三柱 1800碰",
    "combo": "連碰",
}


def _rate(part: float, whole: float) -> float:
    return part / whole if whole else 0.0


def _roi(agg: dict) -> float | None:
    cost = agg["total_cost"]
    return agg["total_pnl"] / cost if cost else None


def _row(name: str, agg: dict) -> dict:
    return {
        "name": name,
        "rounds": agg["rounds"],
        "wins": agg["wins"],
        "losses": agg["losses"],
        "win_rate": _rate(agg["wins"], agg["rounds"]),
        "total_pnl": round(agg["total_pnl"], 2),
        "total_cost": round(agg["total_cost"], 2),
        "total_payout": round(agg["total_payout"], 2),
        "roi": _roi(agg),
        "last_at": agg["last_at"],
    }


@router.get("")
def leaderboard(limit: int = Query(50, ge=1, le=500),
                user: str = Depends(current_user)):
    """使用者損益排行(高→低)+ 各下法的整體表現。

    users 依 total_pnl 由高到低;limit 只截 users(下法固定四種,不截)。
    """
    data = ledger_store.summary()

    users = [dict(_row(name, agg), username=name, is_me=(name == user))
             for name, agg in data["users"].items()]
    users.sort(key=lambda r: (-r["total_pnl"], -r["rounds"], r["username"]))
    users = users[:limit]
    for i, r in enumerate(users, start=1):
        r["rank"] = i

    modes = [_row(MODE_NAMES.get(k, k), agg) | {"mode": k}
             for k, agg in data["modes"].items()]
    modes.sort(key=lambda r: -r["rounds"])

    return {"me": user, "users": users, "modes": modes}
