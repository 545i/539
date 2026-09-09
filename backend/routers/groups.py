"""二合下注「組」的設定:固定顆數與啟用開關(全站共用)。

讀是公開的(前端每個分頁 / 快速上傳都要知道有幾組、各組幾顆、開沒開);
寫要登入。設定的語意與持久化都在 backend/group_store.py。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import group_store
from backend.deps import current_user

router = APIRouter(prefix="/groups", tags=["groups"])


class GroupIn(BaseModel):
    gid: int
    ball_count: int | None = None
    enabled: bool | None = None


class GroupsIn(BaseModel):
    groups: list[GroupIn] = Field(default_factory=list)


@router.get("")
def list_groups():
    """兩組的目前設定(gid / mode / name / ball_count / enabled)。"""
    return group_store.get_groups()


@router.put("")
def update_groups(body: GroupsIn, user: str = Depends(current_user)):
    """改組設定(固定顆數 / 啟用),回傳寫完之後的完整兩組。"""
    try:
        return group_store.set_groups(
            [g.model_dump(exclude_none=True) for g in body.groups], updated_by=user)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
