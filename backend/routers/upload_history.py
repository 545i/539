"""快速上傳歷史 API(登入帳號綁定,存後端 SQL,跨裝置都在)。

前端 uploadHistory.ts 走這些端點;payload 是整個 entry 的 JSON,後端不解讀。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend import upload_history_store
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
    """新增一批;上限由後端維持(每人最多 HISTORY_CAP 筆)。"""
    return upload_history_store.add_entry(user, body.entry)


@router.patch("/{ts}")
def update_entry(ts: int, body: PatchIn, user: str = Depends(current_user)):
    """更新某批(ts)的欄位(例如保存對帳的 bill / recon / reconAt)。"""
    return upload_history_store.update_entry(user, ts, body.patch)


@router.delete("")
def clear(user: str = Depends(current_user)):
    """清空自己的上傳歷史。"""
    return {"deleted": upload_history_store.clear(user)}
