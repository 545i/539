"""排行榜:把記帳流水彙總成「誰賺賠多少」與「哪種下法表現怎樣」。

資料只有一個來源 —— ledger_store 的流水帳,不是回測、也不是模擬。所以看得到
的都是**使用者實際記過帳的局**,沒人記帳就是空榜,不會生出假資料。

要登入才看得到(current_user):榜上有其他人的帳號與損益,不該對外開放。
自己那一列會標 is_me,前端拿來高亮。

勝率 = 賺錢的局 / 總局數;報酬率 = 總損益 / 總成本(成本為 0 時回 None,
不是 0 —— 「沒下過本金」和「打平」是兩回事)。

`GET /leaderboard/{username}/ledger` 是榜上那一列的展開:同一批流水,只是不彙總
而是逐筆列出。放在這個 router 而不是 /ledger,因為 /ledger 的語意是「我自己的
記帳」(每個端點都綁 current_user 只動自己的),這裡的語意是「榜上這個人的公開
成績單」—— 兩者權限模型不同,混在一起遲早有人改壞。
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


# 展開某帳號流水時,前端要顯示的欄位。後端只挑這些欄位出來,不是整包 record
# 原封不動丟出去 —— 榜上看得到別人的帳號,沒必要連內部欄位(cumPnl / id /
# drawBalls …)都一起外流,而且欄位固定前端才好排表。
_TEXT_FIELDS = ("date", "issue", "game", "playType", "result")
_NUM_FIELDS = ("units", "cars", "betsCount", "cost", "payout", "pnl")


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


def _text(record: dict, key: str) -> str:
    v = record.get(key)
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _number(record: dict, key: str) -> float | None:
    """數字欄位;不是數字(含 None / 布林 / 字串)就回 None,不是 0。

    「沒有這個欄位」和「這局成本 0」在表格上要長得不一樣,所以不補 0。
    """
    v = record.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _balls(record: dict) -> list[int]:
    """選號;非整數的元素直接丟掉(舊紀錄可能是字串,能轉就轉)。"""
    raw = record.get("selectedBalls")
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        if isinstance(x, bool):
            continue
        if isinstance(x, (int, float)):
            out.append(int(x))
        elif isinstance(x, str) and x.strip().isdigit():
            out.append(int(x))
    return out


def _entry_view(entry: dict) -> dict:
    record = entry.get("record")
    if not isinstance(record, dict):
        record = {}
    mode = entry.get("mode", "")
    view = {
        "id": entry.get("id"),
        "mode": mode,
        "mode_name": MODE_NAMES.get(mode, mode),
        "created": entry.get("created") or "",
        "selectedBalls": _balls(record),
    }
    view.update({k: _text(record, k) for k in _TEXT_FIELDS})
    view.update({k: _number(record, k) for k in _NUM_FIELDS})
    return view


@router.get("/{username}/ledger")
def user_ledger(username: str, user: str = Depends(current_user)):
    """某帳號的下注流水(新→舊)—— 排行榜點開一列時看的明細。

    只要登入就看得到**任何人**的流水,跟排行榜本身一樣:榜上已經公開了各帳號
    的累積損益,明細是同一批資料的展開,再擋一層意義不大。要改成只能看自己的
    話,在這裡比對 username == user 即可。

    帳號不存在(或還沒記過帳)回空陣列而不是 404 —— 前端只要處理「沒有紀錄」
    一種狀況,不用再分「查無此人」。
    """
    entries = ledger_store.list_entries(username)
    entries.reverse()  # list_entries 是舊→新,明細表要新的在上面
    views = [_entry_view(e) for e in entries]
    return {"username": username, "count": len(views), "entries": views}


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
