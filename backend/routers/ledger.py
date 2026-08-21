"""記帳流水帳:登入後各下注分頁的紀錄存後端,重整 / 換裝置都還在。

每個端點都靠 current_user 綁定帳號,只看得到也只動得了自己的紀錄。
紀錄內容(前端的 BetRecord)原封不動以 JSON 存,後端不解讀 ——
累積損益由前端依順序重算,盤口算法改版時舊紀錄不會壞掉。

每個會改到資料的端點都會往 audit_store 記一筆操作歷史,而且**先讀後刪**,
把被刪的內容留在 audit 的 reverse_data 裡 —— 手滑撤銷 / 清空之後還救得回來
(見 backend/routers/audit.py 的作廢)。記歷史失敗不影響記帳本身。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend import audit_store, ledger_store
from backend.deps import current_user

router = APIRouter(prefix="/ledger", tags=["ledger"])


def _check_mode(mode: str) -> str:
    if mode not in ledger_store.MODES:
        raise HTTPException(status_code=400, detail=f"未知的下注模式:{mode}")
    return mode


class EntryIn(BaseModel):
    mode: str
    record: dict = Field(default_factory=dict)


@router.get("")
def list_entries(mode: str | None = Query(default=None),
                 user: str = Depends(current_user)):
    """列出自己的紀錄;不帶 mode 就回四種下法全部(總損益頁彙整用)。"""
    if mode is not None:
        _check_mode(mode)
    return ledger_store.list_entries(user, mode)


@router.post("")
def add_entry(body: EntryIn, user: str = Depends(current_user)):
    """新增一筆,回傳含資料庫 id 的那筆(前端拿 id 才刪得掉)。"""
    _check_mode(body.mode)
    entry = ledger_store.add_entry(user, body.mode, body.record)
    audit_store.log(
        user, "bet_add", target_id=entry["id"],
        summary=audit_store.summarize_record(body.mode, entry["record"]),
        reverse_data={"entry_id": entry["id"]},
    )
    return entry


@router.delete("/{entry_id}")
def delete_entry(entry_id: int, user: str = Depends(current_user)):
    """刪一筆(撤銷上一筆);不是自己的紀錄回 404。

    刪掉的內容整筆進 audit,所以「撤銷」這個動作事後也能被作廢還原。
    """
    entry = ledger_store.delete_entry(user, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="找不到這筆紀錄")
    audit_store.log(
        user, "bet_delete", target_id=entry["id"],
        summary=audit_store.summarize_record(entry["mode"], entry["record"]),
        reverse_data={"entry": entry},
    )
    return {"ok": True, "deleted": 1}


@router.delete("")
def clear_entries(mode: str | None = Query(default=None),
                  user: str = Depends(current_user)):
    """清空某種下法的紀錄;不帶 mode 就清光自己的全部。

    這是最不可逆的一個動作,所以清之前先把整批讀出來存進 audit ——
    整批清空一樣可以作廢還原。
    """
    if mode is not None:
        _check_mode(mode)
    entries = ledger_store.list_entries(user, mode)
    deleted = ledger_store.clear(user, mode)
    if deleted:
        scope = audit_store.MODE_LABELS.get(mode, mode) if mode else "全部下法"
        audit_store.log(
            user, "bet_clear",
            summary=f"清空{scope}的 {deleted} 筆紀錄",
            reverse_data={"entries": entries},
        )
    return {"ok": True, "deleted": deleted}
