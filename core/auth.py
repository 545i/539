"""帳號系統:註冊(需邀請碼)/ 登入 / 密碼雜湊。

每個帳號獨立;登入後二合的「累積損益」「倍頭進程」「凱莉對照」設定都以
帳號命名空間(帳號::game_key)隔離,互不干擾。

密碼以 PBKDF2-HMAC-SHA256 + 每人隨機 salt 雜湊保存,資料庫不存明碼。
資料庫檔放在 data/users.db(frozen 打包時放 exe 旁邊;*.db 已被 gitignore)。
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import sys
from pathlib import Path

# 註冊邀請碼:沒有此碼無法註冊新帳號。
INVITE_CODE = "055574471"
_ITERATIONS = 200_000


def _db_path() -> Path:
    """使用者資料庫路徑(frozen 時位於 exe 旁邊,否則專案 data/)。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "users.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            salt     TEXT NOT NULL,
            pw_hash  TEXT NOT NULL,
            created  TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    return conn


def _hash(password: str, salt: str) -> str:
    """以 salt(hex)對密碼做 PBKDF2-HMAC-SHA256,回傳 hex。"""
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS
    )
    return dk.hex()


def user_exists(username: str) -> bool:
    """帳號是否已存在。"""
    with _conn() as c:
        return c.execute(
            "SELECT 1 FROM users WHERE username = ?", ((username or "").strip(),)
        ).fetchone() is not None


def register(username: str, password: str, invite_code: str) -> tuple[bool, str]:
    """註冊新帳號;需正確邀請碼。回傳 (是否成功, 訊息)。"""
    username = (username or "").strip()
    if (invite_code or "").strip() != INVITE_CODE:
        return False, "邀請碼錯誤,無法註冊。"
    if len(username) < 2:
        return False, "帳號至少 2 個字元。"
    if len(password or "") < 4:
        return False, "密碼至少 4 個字元。"
    if user_exists(username):
        return False, "此帳號已存在,請改用其他帳號或直接登入。"
    salt = secrets.token_hex(16)
    pw_hash = _hash(password, salt)
    with _conn() as c:
        c.execute(
            "INSERT INTO users (username, salt, pw_hash) VALUES (?, ?, ?)",
            (username, salt, pw_hash),
        )
    return True, "註冊成功,請切到「登入」分頁登入。"


def verify(username: str, password: str) -> bool:
    """驗證帳號密碼是否正確。"""
    username = (username or "").strip()
    with _conn() as c:
        row = c.execute(
            "SELECT salt, pw_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return False
    salt, pw_hash = row
    return hmac.compare_digest(_hash(password or "", salt), pw_hash)
