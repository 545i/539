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

from backend import audit_store, data, ledger_store, settle
from backend.deps import current_user
from core import games

router = APIRouter(prefix="/ledger", tags=["ledger"])


def _check_mode(mode: str) -> str:
    if mode not in ledger_store.MODES:
        raise HTTPException(status_code=400, detail=f"未知的下注模式:{mode}")
    return mode


def _resettle(record: dict, issue: str) -> dict:
    """把一筆紀錄對到指定期數的開獎號:更新期數 / 日期 / 開獎號 / 損益。

    money 規則全在 backend.settle;查不到該期(未開)就退回待開獎。登入與未登入
    兩條路共用這裡,結算邏輯只有一份。
    """
    g = games.by_name(str(record.get("game", "")))
    found = data.draw_by_issue(g.key, issue)
    out = settle.settle(record, found[0] if found else None, g)
    out["issue"] = str(issue)
    if found:
        out["date"] = found[1]
    return out


class EntryIn(BaseModel):
    mode: str
    record: dict = Field(default_factory=dict)


class SettleIn(BaseModel):
    issue: str


class PreviewIn(BaseModel):
    record: dict = Field(default_factory=dict)
    issue: str


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


@router.post("/settle-preview")
def settle_preview(body: PreviewIn):
    """把一筆紀錄對到某期開獎號後長怎樣 —— 不寫 DB(未登入的核對列表用)。

    未登入沒有後端流水,紀錄只活在瀏覽器;這裡只回「對過獎的那筆」讓前端更新
    自己的暫存,不需要登入也不動任何人的資料。
    """
    return _resettle(body.record, body.issue)


@router.put("/{entry_id}")
def resettle_entry(entry_id: int, body: SettleIn, user: str = Depends(current_user)):
    """改一筆的期數並重新對獎:抓該期真實開獎號,重算中獎狀態與損益後存回。

    先讀後寫,舊的整筆進 audit 的 reverse_data —— 改錯期數也能作廢還原。
    """
    entries = ledger_store.list_entries(user)
    cur = next((e for e in entries if e["id"] == entry_id), None)
    if cur is None:
        raise HTTPException(status_code=404, detail="找不到這筆紀錄")

    updated_record = _resettle(cur["record"], body.issue)
    res = ledger_store.update_entry(user, entry_id, updated_record)
    if res is None:
        raise HTTPException(status_code=404, detail="找不到這筆紀錄")
    new_entry, old_entry = res
    audit_store.log(
        user, "bet_settle", target_id=entry_id,
        summary=f"改期數對獎 → {body.issue}:"
                f"{audit_store.summarize_record(new_entry['mode'], new_entry['record'])}",
        reverse_data={"entry": old_entry},
    )
    return new_entry


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
