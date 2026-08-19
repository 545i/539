"""FastAPI 相依:登入驗證。

沿用 core.auth 的無狀態自簽 token(等同 JWT),前端以
Authorization: Bearer <token> 帶回。
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from core import auth


def current_user(authorization: str = Header(default="")) -> str:
    """驗 Bearer token,回帳號;失敗回 401。受保護的 endpoint 依賴這個。"""
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="缺少登入憑證")
    user = auth.verify_token(authorization[len(prefix):])
    if not user:
        raise HTTPException(status_code=401, detail="登入已過期,請重新登入")
    return user
