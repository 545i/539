"""快速上傳歷史 API(登入帳號綁定,存後端 SQL,跨裝置都在)。

前端 uploadHistory.ts 走這些端點;payload 是整個 entry 的 JSON,後端不解讀。
"""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import audit_store, ledger_store, upload_history_store
from backend.deps import current_user

router = APIRouter(prefix="/upload-history", tags=["upload-history"])


class EntryIn(BaseModel):
    entry: dict = Field(default_factory=dict)


class PatchIn(BaseModel):
    patch: dict = Field(default_factory=dict)


@router.get("")
def list_entries(user: str = Depends(current_user)):
    """自己的全部上傳歷史(新→舊)。"""
    return upload_history_store.list_entries(user)


@router.post("")
def add_entry(body: EntryIn, user: str = Depends(current_user)):
    """新增一批;不設筆數上限(卡片與流水要一路對得上,見 upload_history_store)。"""
    return upload_history_store.add_entry(user, body.entry)


@router.patch("/{ts}")
def update_entry(ts: int, body: PatchIn, user: str = Depends(current_user)):
    """更新某批(ts)的欄位(例如保存對帳的 bill / recon / reconAt)。"""
    return upload_history_store.update_entry(user, ts, body.patch)


def _delete_bets_of(user: str, entry: dict) -> list[dict]:
    """刪掉某批上傳建立的 ledger 下注,回傳被刪的整筆(給 audit 還原用)。

    優先用上傳當下存的 entryIds 精準刪(一對一);舊資料沒存 id 的,退回用
    (game+issue+edition+mode+cost)簽名比對,每個簽名**最多刪該批 items 記的
    筆數**——避免把之後同號重下的紀錄一起誤刪。
    """
    deleted: list[dict] = []

    ids = entry.get("entryIds")
    if isinstance(ids, list) and ids:
        for eid in ids:
            try:
                row = ledger_store.delete_entry(user, int(eid))
            except (TypeError, ValueError):
                row = None
            if row:
                deleted.append(row)
        return deleted

    # 沒有 entryIds:簽名比對(舊上傳)
    game = entry.get("gameName")
    issue = str(entry.get("issue") or "")
    edition = entry.get("eid")
    want: Counter = Counter()
    for it in entry.get("items") or []:
        want[(it.get("mode"), round(float(it.get("cost") or 0)))] += 1
    if not want:
        return deleted

    for r in ledger_store.list_entries(user):     # 舊→新
        rec = r.get("record") or {}
        key = (r.get("mode"), round(float(rec.get("cost") or 0)))
        same = (rec.get("game") == game
                and str(rec.get("issue") or "") == issue
                and rec.get("edition") == edition)
        if same and want.get(key, 0) > 0:
            row = ledger_store.delete_entry(user, r["id"])
            if row:
                deleted.append(row)
                want[key] -= 1
    return deleted


@router.delete("/{ts}")
def void_entry(ts: int, user: str = Depends(current_user)):
    """作廢某一批上傳:刪掉它建立的 ledger 下注 + 刪這筆上傳歷史紀錄。

    被刪的 ledger 整批進 audit(bet_clear),手滑作廢之後還能還原。找不到這批回 404。
    """
    target = next(
        (e for e in upload_history_store.list_entries(user)
         if int(e.get("ts") or 0) == int(ts)),
        None,
    )
    if target is None:
        raise HTTPException(status_code=404, detail="找不到這批上傳")

    deleted = _delete_bets_of(user, target)
    if deleted:
        label = f"第 {target.get('issue')} 期" if target.get("issue") else ""
        audit_store.log(
            user, "bet_clear",
            summary=f"作廢上傳:{target.get('gameName', '')} {label} 共 {len(deleted)} 筆下注",
            reverse_data={"entries": deleted},
        )
    removed = upload_history_store.delete_entry(user, ts)
    return {"deleted_bets": len(deleted), "deleted_upload": removed}


@router.delete("")
def clear(user: str = Depends(current_user)):
    """清空自己的上傳歷史(僅刪歷史紀錄,不動 ledger 下注)。"""
    return {"deleted": upload_history_store.clear(user)}
