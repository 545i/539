"""週期性紀錄(cycle):每個帳號各自的記帳週期,手動開始 / 手動結算。

開了週期之後,新的下注與快速上傳都自動記上目前進行中(open)週期的 cycle_id
(後端在寫入前自動補,見 backend/routers/ledger.py 與 importer.py);結算後
新活動不再歸入它。summary 端點把該週期所有 ledger 紀錄的成本 / 派彩 / 淨損益
彙總出來,給總損益頁「週期」檢視用。

全部端點都綁 current_user —— 只看得到也只動得了自己的週期。語意與持久化都在
backend/cycle_store.py。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend import cycle_store, ledger_store
from backend.deps import current_user

router = APIRouter(prefix="/cycles", tags=["cycles"])


class CycleIn(BaseModel):
    name: str = ""


@router.get("")
def list_cycles(user: str = Depends(current_user)):
    """列出自己的所有週期(新→舊)。"""
    return cycle_store.list_cycles(user)


@router.get("/current")
def get_current(user: str = Depends(current_user)):
    """目前進行中的週期;沒有回 null。"""
    return cycle_store.current_cycle(user)


@router.post("")
def create_cycle(body: CycleIn, user: str = Depends(current_user)):
    """開一個新週期。同帳號同時只能一個 open —— 開新的會先把舊 open 自動結算。"""
    return cycle_store.create_cycle(user, body.name)


@router.post("/{cycle_id}/close")
def close_cycle(cycle_id: int, user: str = Depends(current_user)):
    """結算 / 保存某週期;之後的新活動不再歸入它。"""
    cyc = cycle_store.close_cycle(user, cycle_id)
    if cyc is None:
        raise HTTPException(status_code=404, detail="找不到這個週期")
    return cyc


@router.get("/{cycle_id}/summary")
def cycle_summary(cycle_id: int, user: str = Depends(current_user)):
    """某週期的損益彙總:成本 / 派彩 / 淨損益 / 筆數(從該用戶 ledger 加總)。

    只算 record.cycle_id == 這個週期 的紀錄;金額後端唯一權威解讀 payload 的
    cost / payout 兩欄,淨損益 = 派彩 − 成本。
    """
    if not cycle_store.cycle_exists(user, cycle_id):
        raise HTTPException(status_code=404, detail="找不到這個週期")
    cost = payout = 0.0
    n = 0
    for e in ledger_store.list_entries(user):
        rec = e.get("record") or {}
        cid = rec.get("cycle_id")
        if cid is None or int(cid) != int(cycle_id):
            continue
        cost += float(rec.get("cost", 0) or 0)
        payout += float(rec.get("payout", 0) or 0)
        n += 1
    return {"cycle_id": int(cycle_id), "cost": round(cost),
            "payout": round(payout), "pnl": round(payout - cost), "n": n}
