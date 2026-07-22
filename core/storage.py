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


def undo_last_round(game_key: str) -> bool:
    """撤銷最後一局紀錄(刪除該 game_key 最大 id 那筆);無紀錄回 False。

    累積損益不需重算:每局的 cumulative 都存在各自那筆,刪掉最後一筆後,
    current_cumulative() 自然回到前一局的值。
    """
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM erhe_rounds WHERE game_key = ? ORDER BY id DESC LIMIT 1",
            (game_key,),
        ).fetchone()
        if row is None:
            return False
        c.execute("DELETE FROM erhe_rounds WHERE id = ?", (row[0],))
    return True


def reset(game_key: str) -> None:
    """清除某遊戲的所有紀錄。"""
    with _conn() as c:
        c.execute("DELETE FROM erhe_rounds WHERE game_key = ?", (game_key,))


def latest_cumulatives() -> list[dict]:
    """每個 game_key 的「最新累積損益」與「總局數」(供排行榜彙整)。

    game_key 由上層以「帳號::遊戲代號」命名空間寫入;本函式只回傳原始字串,
    由呼叫端解析帳號與遊戲。回傳 [{game_key, cumulative, rounds}, ...]。
    """
    with _conn() as c:
        rows = c.execute(
            "SELECT e.game_key, e.cumulative, "
            "  (SELECT COUNT(*) FROM erhe_rounds x WHERE x.game_key = e.game_key) AS rounds "
            "FROM erhe_rounds e "
            "WHERE e.id IN (SELECT MAX(id) FROM erhe_rounds GROUP BY game_key)",
        ).fetchall()
    return [
        {"game_key": r[0], "cumulative": float(r[1]), "rounds": int(r[2])}
        for r in rows
    ]


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
