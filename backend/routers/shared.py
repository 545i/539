"""佔比帳單(被連動者唯讀):版主設定損益佔比時把某分配對象「連動帳號」,
那個帳號登入後就能看該版主該版、自己佔比 > 0 那些日子的下注帳單。

只讀、只給符合條件的紀錄:版要對、日期要落在自己有佔比的生效區間;
其他合夥人名字遮掉(edition_store.partner_view_versions)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend import edition_store, ledger_store
from backend.deps import current_user

router = APIRouter(prefix="/shared", tags=["shared"])


def _ymd(record: dict) -> str:
    s = str(record.get("date") or "")
    return s[:10] if len(s) >= 10 and s[4] == "-" and s[7] == "-" else ""


def _edition(record: dict) -> int:
    try:
        return int(record.get("edition") or 1)
    except (TypeError, ValueError):
        return 1


def board_entries(owner: str, eid: int, account: str, versions: list[dict]) -> list[dict]:
    """版主該版、account 當天佔比 > 0 的紀錄(沒日期的不給)。"""
    out = []
    for e in ledger_store.list_entries(owner):
        r = e["record"] if isinstance(e["record"], dict) else {}
        if _edition(r) != eid:
            continue
        ymd = _ymd(r)
        if not ymd:
            continue
        v = edition_store.shares_on(versions, ymd)
        if any(s["account"] == account and s["pct"] > 0 for s in v["shares"]):
            out.append({"id": e["id"], "mode": e["mode"], "record": r})
    return out


@router.get("/boards")
def boards(user: str = Depends(current_user)):
    """我被連動的每個「版主 × 版」:佔比版本(遮名)+ 我看得到的帳單紀錄。"""
    names = {e["eid"]: e["name"] for e in edition_store.list_editions()}
    out = []
    for b in edition_store.linked_boards(user):
        versions = edition_store.get_share_versions(b["owner"], b["eid"])
        out.append({
            "owner": b["owner"],
            "eid": b["eid"],
            "edition_name": names.get(b["eid"], f"版{b['eid']}"),
            "versions": edition_store.partner_view_versions(versions, user),
            "entries": board_entries(b["owner"], b["eid"], user, versions),
        })
    return out
