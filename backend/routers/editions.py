"""下注「版」(edition):版清單 + 版×遊戲的整套盤口(全站共用)。

讀是公開的(下注頁 / 快速上傳都要知道有哪些版、各版盤口);改要登入。
語意與持久化都在 backend/edition_store.py。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend import edition_store
from backend.deps import current_user

router = APIRouter(prefix="/editions", tags=["editions"])


class EditionIn(BaseModel):
    name: str = ""


class OddsIn(BaseModel):
    game: str
    values: dict = Field(default_factory=dict)


@router.get("")
def list_editions():
    return edition_store.list_editions()


@router.post("")
def add_edition(body: EditionIn, user: str = Depends(current_user)):
    return edition_store.add_edition(body.name)


@router.put("/{eid}")
def rename_edition(eid: int, body: EditionIn, user: str = Depends(current_user)):
    try:
        if not edition_store.rename_edition(eid, body.name):
            raise HTTPException(status_code=404, detail="找不到這個版")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.delete("/{eid}")
def delete_edition(eid: int, user: str = Depends(current_user)):
    try:
        if not edition_store.delete_edition(eid):
            raise HTTPException(status_code=404, detail="找不到這個版")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/{eid}/odds")
def get_odds(eid: int, game: str = Query(...)):
    """某版某遊戲的整套盤口(每欄位含 value 與 custom)。"""
    if not edition_store.edition_exists(eid):
        raise HTTPException(status_code=404, detail="找不到這個版")
    return {"eid": eid, "game": game, "fields": edition_store.get_odds_detail(eid, game)}


@router.put("/{eid}/odds")
def set_odds(eid: int, body: OddsIn, user: str = Depends(current_user)):
    if not edition_store.edition_exists(eid):
        raise HTTPException(status_code=404, detail="找不到這個版")
    try:
        return edition_store.set_odds(eid, body.game, body.values)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{eid}/odds")
def reset_odds(eid: int, game: str = Query(...), user: str = Depends(current_user)):
    return edition_store.reset_odds(eid, game)
