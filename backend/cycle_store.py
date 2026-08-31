"""週期性紀錄(cycle)的持久化:把一段時間的所有下注 / 快速上傳歸到一個「週期」。

一個「週期」= 使用者手動開始、手動結算的一段記帳區間(例:「8月W4」)。開了週期
之後,新的下注與快速上傳都自動記上這個週期的 cycle_id;結算後狀態改 closed,
之後的新活動不再歸入它(要再開新的)。

**每個帳號各自的週期**(綁 username,跟 edition 的全站共用不同)。同一帳號同時
只有一個「進行中(open)」週期 —— 開新的之前,先把舊的 open 自動結算掉。

cycle_id 只是塞進 ledger record 的 payload(自由 JSON),不用改 ledger 的表;
沒有進行中週期時 cycle_id 留空,一切行為跟以前完全一樣。

資料庫檔放 data/cycle.db(frozen 打包時放 exe 旁邊;*.db 已被 gitignore)。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def _db_path() -> Path:
    """資料庫路徑(frozen 時位於 exe 旁邊,否則專案 data/)。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "cycle.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cycles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT NOT NULL,
            name       TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'open',
            started_at TEXT DEFAULT (datetime('now', 'localtime')),
            closed_at  TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cycles_user "
        "ON cycles (username, status, id)"
    )
    return conn


def _row(r: tuple) -> dict:
    """資料庫列 → API 回傳形狀。"""
    return {
        "id": int(r[0]),
        "name": r[1],
        "status": r[2],
        "started_at": r[3],
        "closed_at": r[4],
    }


def list_cycles(username: str) -> list[dict]:
    """某使用者的所有週期(新→舊,進行中的排最前面才好找)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, name, status, started_at, closed_at FROM cycles "
            "WHERE username = ? ORDER BY id DESC",
            (username,),
        ).fetchall()
    return [_row(r) for r in rows]


def current_cycle(username: str) -> dict | None:
    """目前進行中(open)的週期;沒有回 None。同帳號同時只會有一個。"""
    with _conn() as c:
        row = c.execute(
            "SELECT id, name, status, started_at, closed_at FROM cycles "
            "WHERE username = ? AND status = 'open' ORDER BY id DESC LIMIT 1",
            (username,),
        ).fetchone()
    return _row(row) if row else None


def create_cycle(username: str, name: str) -> dict:
    """開一個新週期。同帳號同時只能有一個 open —— 開新的之前先把舊 open 自動結算。"""
    name = (name or "").strip() or "新週期"
    with _conn() as c:
        # 先把該帳號還開著的舊週期結算掉(同時只留一個 open)
        c.execute(
            "UPDATE cycles SET status = 'closed', "
            "closed_at = datetime('now', 'localtime') "
            "WHERE username = ? AND status = 'open'",
            (username,),
        )
        cur = c.execute(
            "INSERT INTO cycles (username, name, status) VALUES (?, ?, 'open')",
            (username, name),
        )
        row = c.execute(
            "SELECT id, name, status, started_at, closed_at FROM cycles WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _row(row)


def close_cycle(username: str, cycle_id: int) -> dict | None:
    """結算 / 保存某週期(狀態改 closed、記 closed_at);之後新活動不再歸入它。

    不是自己的週期或不存在回 None。已經 closed 的再結算一次無妨(冪等)。
    """
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM cycles WHERE id = ? AND username = ?",
            (int(cycle_id), username),
        ).fetchone()
        if row is None:
            return None
        c.execute(
            "UPDATE cycles SET status = 'closed', "
            "closed_at = COALESCE(closed_at, datetime('now', 'localtime')) "
            "WHERE id = ?",
            (int(cycle_id),),
        )
        new = c.execute(
            "SELECT id, name, status, started_at, closed_at FROM cycles WHERE id = ?",
            (int(cycle_id),),
        ).fetchone()
    return _row(new)


def cycle_exists(username: str, cycle_id: int) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM cycles WHERE id = ? AND username = ?",
            (int(cycle_id), username),
        ).fetchone()
    return row is not None
