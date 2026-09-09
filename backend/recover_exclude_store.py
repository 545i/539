"""建議車數/支數「排除下注」清單(每個使用者一份,跨裝置)。

前端點卡片彈明細、逐筆勾選排除的紀錄 id 存這裡;換手機/電腦/重登都記得,
不再只留在單一瀏覽器的 localStorage。內容就是一組 ledger 紀錄 id(字串)。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path


def _db_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "recover_exclude.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recover_exclude (
            username TEXT PRIMARY KEY,
            ids      TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    return conn


def get_ids(username: str) -> list[str]:
    """回這個使用者排除的 ledger 紀錄 id 清單(字串);沒有回空。"""
    with _conn() as c:
        row = c.execute(
            "SELECT ids FROM recover_exclude WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return []
    try:
        return [str(x) for x in json.loads(row[0])]
    except Exception:       # noqa: BLE001 — 壞資料當空清單
        return []


def set_ids(username: str, ids: list[str]) -> list[str]:
    """覆寫這個使用者的排除清單;回存好的清單(去重、字串化)。"""
    clean = sorted({str(x) for x in ids})
    with _conn() as c:
        c.execute(
            "INSERT INTO recover_exclude(username, ids) VALUES(?, ?) "
            "ON CONFLICT(username) DO UPDATE SET ids = excluded.ids",
            (username, json.dumps(clean)),
        )
    return clean
