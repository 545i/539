"""操作歷史:看得到自己做過什麼,而且每一筆都可以「作廢」(= 反轉)。

作廢不是刪歷史,是**補一筆反向操作**:原操作標記 voided 留在原地,反轉本身
另外記一筆(void_of 指回去)。所以「撤銷了一筆 → 事後作廢那個撤銷」會在歷史
上看到兩筆,而 ledger 裡那一局回來了 —— 這正是使用者要的。

反轉規則由 action 決定,對應 audit_store 裡存的 reverse_data:

    bet_add       {"entry_id": 3}                  → 刪掉 3
    bet_delete    {"entry": {id, mode, record, …}} → 用原 id 重新 insert 回去
    bet_clear     {"entries": [...]}               → 整批 insert 回去
    quick_import  {"entries": [...]}               → 整批刪掉

作廢動作(void)本身不可再作廢 —— 一路反轉回去語意會纏死,要復原就再作廢
原本那筆的下一次操作。已作廢的重複作廢回 400。

**反轉時發現目標已經不在了不算失敗**:紀錄可能早被清空端點掃掉,而作廢的目的
是「讓它不在」,結果已經達成。回傳的 reverted 會告訴前端實際動了幾筆。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend import audit_store, ledger_store
from backend.deps import current_user

router = APIRouter(prefix="/audit", tags=["audit"])


def _public(row: dict) -> dict:
    """回給前端的形狀:去掉 username 與 reverse_data(內部資料,沒必要外流)。"""
    return {k: v for k, v in row.items()
            if k not in ("username", "reverse_data")}


def _restore(user: str, entry: dict) -> int:
    """把一筆存在 reverse_data 裡的 ledger_entry 放回去,回傳放了幾筆(0/1)。"""
    if not isinstance(entry, dict) or not entry.get("mode"):
        return 0
    ledger_store.restore_entry(
        user, entry["mode"], entry.get("record") or {},
        entry_id=entry.get("id"), created=entry.get("created"),
    )
    return 1


def _revert(user: str, row: dict) -> int:
    """依 action 反轉一筆操作,回傳實際動到幾筆 ledger_entry。"""
    action, data = row["action"], row["reverse_data"]

    if action == "bet_add":
        entry_id = data.get("entry_id", row.get("target_id"))
        if entry_id is None:
            return 0
        return 1 if ledger_store.delete_entry(user, int(entry_id)) else 0

    if action == "bet_delete":
        return _restore(user, data.get("entry") or {})

    if action == "bet_clear":
        return sum(_restore(user, e) for e in (data.get("entries") or []))

    if action == "quick_import":
        done = 0
        for e in data.get("entries") or []:
            eid = e.get("id") if isinstance(e, dict) else None
            if eid is not None and ledger_store.delete_entry(user, int(eid)):
                done += 1
        return done

    raise HTTPException(status_code=400, detail=f"這種操作不能作廢:{action}")


@router.get("")
def list_logs(limit: int = Query(default=200, ge=1, le=1000),
              user: str = Depends(current_user)):
    """自己的操作歷史,新到舊。"""
    return [_public(r) for r in audit_store.list_logs(user, limit)]


@router.post("/{log_id}/void")
def void_log(log_id: int, user: str = Depends(current_user)):
    """作廢(反轉)一個操作;已作廢或不可作廢回 400,不是自己的回 404。"""
    row = audit_store.get(log_id)
    if row is None or row["username"] != user:
        raise HTTPException(status_code=404, detail="找不到這筆操作紀錄")
    if row["action"] == "void":
        raise HTTPException(status_code=400, detail="作廢動作本身不能再作廢")
    if row["voided"]:
        raise HTTPException(status_code=400, detail="這筆操作已經作廢過了")

    # 先標記再反轉:mark_voided 的 WHERE voided = 0 是這裡唯一的原子鎖,
    # 兩個分頁同時按作廢時只有一邊搶得到,不會反轉兩次(還原兩筆 / 刪兩次)。
    if not audit_store.mark_voided(log_id):
        raise HTTPException(status_code=400, detail="這筆操作已經作廢過了")
    reverted = _revert(user, row)

    entry = audit_store.log(
        user, "void", target_id=row["id"], void_of=row["id"],
        summary=f"作廢「{row['action_label']}」:{row['summary']}",
    )
    return {"ok": True, "voided": log_id, "reverted": reverted,
            "log": _public(entry)}
