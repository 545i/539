"""SQLite 持久化:二合買牌(策略1)的逐局下注紀錄與累積損益。

依遊戲(game_key)分開保存,重整頁面或重啟程式都不會遺失。
資料庫檔放在 data/ 下(frozen 打包時放 exe 旁邊)。
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
    return base / "data" / "erhe_state.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS erhe_rounds (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            game_key   TEXT NOT NULL,
            ts         TEXT DEFAULT (datetime('now', 'localtime')),
            numbers    INTEGER NOT NULL DEFAULT 5,
            cars       INTEGER NOT NULL,
            hits       INTEGER NOT NULL,
            net        REAL NOT NULL,
            cumulative REAL NOT NULL
        )
        """
    )
    # 舊資料遷移:若無 numbers 欄則補上
    cols = [r[1] for r in conn.execute("PRAGMA table_info(erhe_rounds)").fetchall()]
    if "numbers" not in cols:
        conn.execute("ALTER TABLE erhe_rounds ADD COLUMN numbers INTEGER NOT NULL DEFAULT 5")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS erhe_settings (
            game_key TEXT NOT NULL,
            key      TEXT NOT NULL,
            value    REAL NOT NULL,
            PRIMARY KEY (game_key, key)
        )
        """
    )
    return conn


def add_round(game_key: str, numbers: int, cars: int, hits: int,
              net: float, cumulative: float) -> None:
    """新增一局紀錄(numbers=每局押幾顆)。"""
    with _conn() as c:
        c.execute(
            "INSERT INTO erhe_rounds (game_key, numbers, cars, hits, net, cumulative) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (game_key, int(numbers), int(cars), int(hits), float(net), float(cumulative)),
        )


def load_rounds(game_key: str) -> list[dict]:
    """讀取某遊戲的所有局數紀錄(依時間順序)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, ts, numbers, cars, hits, net, cumulative FROM erhe_rounds "
            "WHERE game_key = ? ORDER BY id",
            (game_key,),
        ).fetchall()
    cols = ["id", "ts", "numbers", "cars", "hits", "net", "cumulative"]
    return [dict(zip(cols, r)) for r in rows]


def current_cumulative(game_key: str) -> float:
    """取得目前累積損益(最後一局的 cumulative;無紀錄回 0)。"""
    with _conn() as c:
        row = c.execute(
            "SELECT cumulative FROM erhe_rounds WHERE game_key = ? "
            "ORDER BY id DESC LIMIT 1",
            (game_key,),
        ).fetchone()
    return float(row[0]) if row else 0.0


def reset(game_key: str) -> None:
    """清除某遊戲的所有紀錄。"""
    with _conn() as c:
        c.execute("DELETE FROM erhe_rounds WHERE game_key = ?", (game_key,))


def get_setting(game_key: str, key: str, default: float) -> float:
    """讀取某遊戲的設定值(無則回傳 default)。"""
    with _conn() as c:
        row = c.execute(
            "SELECT value FROM erhe_settings WHERE game_key = ? AND key = ?",
            (game_key, key),
        ).fetchone()
    return float(row[0]) if row else float(default)


def set_setting(game_key: str, key: str, value: float) -> None:
    """寫入/更新某遊戲的設定值。"""
    with _conn() as c:
        c.execute(
            "INSERT INTO erhe_settings (game_key, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(game_key, key) DO UPDATE SET value = excluded.value",
            (game_key, key, float(value)),
        )
