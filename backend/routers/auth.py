"""登入 / 註冊。沿用 core.auth 的邀請碼註冊與自簽 token。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.deps import current_user
from core import auth

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    invite_code: str


@router.post("/login")
def login(body: LoginIn):
    if not auth.verify(body.username, body.password):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    return {"token": auth.make_token(body.username), "username": body.username}


@router.post("/register")
def register(body: RegisterIn):
    ok, msg = auth.register(body.username, body.password, body.invite_code)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.get("/me")
def me(user: str = Depends(current_user)):
    return {"username": user}
