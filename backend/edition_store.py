"""下注「版」(edition)的持久化:每個版一份名稱,加上「版 × 遊戲」的整套盤口。

一個「版」= 一套組頭的價碼。第二版的成本 / 派彩可能跟第一版不同,所以每個版
對每款遊戲都能各自設定二合每車、1800碰每注、連碰各星數的成本與派彩。

**這是全站設定**(比照 star_cost_store):版清單與盤口全站共用一份,不綁使用者。

**第一版(eid=1)沒設定時 = 現有預設**:二合 / 1800碰 讀 GameConfig,連碰讀
core.combo 目前生效的盤口(含後台 star-cost 改過的值)—— 所以升級後第一版的
成本跟以前一模一樣,不會變。第二版才需要另外填。

盤口欄位(get_odds 一定回滿,呼叫端不必補洞):
    cost_per_car / win_payout          二合每車成本 / 中一顆可得
    bet_cost / bet_prize               1800碰每注成本 / 中一注可得
    combo_cost{2,3,4} / combo_prize{2,3,4}  連碰各星數每碰成本 / 中一碰可得

資料庫檔放 data/edition.db(frozen 打包時放 exe 旁邊;*.db 已被 gitignore)。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from core import combo
from core.games import get as game_by_key

# 連碰星數(與 core.combo 一致)
STARS = combo.STARS

# 全部盤口欄位名(get/set 都以這份為準)
FIELDS: tuple[str, ...] = (
    "cost_per_car", "win_payout", "bet_cost", "bet_prize",
    *(f"combo_cost{k}" for k in STARS),
    *(f"combo_prize{k}" for k in STARS),
)


def _db_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "edition.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS editions (
            eid     INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            sort    INTEGER NOT NULL DEFAULT 0,
            created TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS edition_odds (
            eid       INTEGER NOT NULL,
            game_key  TEXT NOT NULL,
            field     TEXT NOT NULL,
            value     REAL NOT NULL,
            PRIMARY KEY (eid, game_key, field)
        )
        """
    )
    # 第一版一定存在(沒有就補一筆 eid=1)
    row = conn.execute("SELECT COUNT(*) FROM editions").fetchone()
    if not row or int(row[0]) == 0:
        conn.execute("INSERT INTO editions (eid, name, sort) VALUES (1, '第一版', 0)")
        conn.commit()
    return conn


def list_editions() -> list[dict]:
    """全部版(依 sort, eid);至少有第一版。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT eid, name FROM editions ORDER BY sort, eid").fetchall()
    return [{"eid": int(r[0]), "name": r[1]} for r in rows]


def add_edition(name: str) -> dict:
    """新增一個版,回傳新版 {eid, name}。"""
    name = (name or "").strip() or "新版"
    with _conn() as c:
        nxt = c.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM editions").fetchone()[0]
        cur = c.execute(
            "INSERT INTO editions (name, sort) VALUES (?, ?)", (name, int(nxt)))
        eid = int(cur.lastrowid)
    return {"eid": eid, "name": name}


def rename_edition(eid: int, name: str) -> bool:
    name = (name or "").strip()
    if not name:
        raise ValueError("版名稱不能空白")
    with _conn() as c:
        cur = c.execute("UPDATE editions SET name = ? WHERE eid = ?", (name, int(eid)))
    return bool(cur.rowcount)


def delete_edition(eid: int) -> bool:
    """刪除一個版(第一版不給刪);連同它的盤口一起清掉。"""
    if int(eid) == 1:
        raise ValueError("第一版不能刪除")
    with _conn() as c:
        c.execute("DELETE FROM edition_odds WHERE eid = ?", (int(eid),))
        cur = c.execute("DELETE FROM editions WHERE eid = ?", (int(eid),))
    return bool(cur.rowcount)


def _defaults(game_key: str) -> dict:
    """某遊戲的出廠盤口:二合 / 1800碰 讀 GameConfig,連碰讀 core.combo 現行值。"""
    g = game_by_key(game_key)
    out = {
        "cost_per_car": float(g.default_cost_per_car),
        "win_payout": float(g.default_win_payout),
        "bet_cost": float(g.default_bet_cost),
        "bet_prize": float(g.default_bet_prize),
    }
    for k in STARS:
        # market_cost/prize 會吃到後台 star-cost 改過的值 —— 第一版沿用現況
        out[f"combo_cost{k}"] = float(combo.market_cost(k, combo.MARKET_COST[k]))
        out[f"combo_prize{k}"] = float(combo.market_prize(k, combo.MARKET_PRIZE[k]))
    return out


def _stored(eid: int, game_key: str) -> dict:
    with _conn() as c:
        rows = c.execute(
            "SELECT field, value FROM edition_odds WHERE eid = ? AND game_key = ?",
            (int(eid), game_key),
        ).fetchall()
    return {r[0]: float(r[1]) for r in rows}


def get_odds(eid: int, game_key: str) -> dict:
    """某版某遊戲目前生效的整套盤口(覆寫疊在預設上,一定回滿全部欄位)。"""
    out = _defaults(game_key)
    out.update({k: v for k, v in _stored(eid, game_key).items() if k in FIELDS})
    return out


def get_odds_detail(eid: int, game_key: str) -> dict:
    """設定頁用:每欄位回 {value, custom}(custom=是否有自訂,否則吃預設)。"""
    defaults = _defaults(game_key)
    stored = _stored(eid, game_key)
    return {k: {"value": stored.get(k, defaults[k]), "custom": k in stored}
            for k in FIELDS}


def set_odds(eid: int, game_key: str, values: dict) -> dict:
    """寫入某版某遊戲的盤口(只給的欄位才改);成本 / 派彩要 > 0。"""
    rows = []
    for k, v in (values or {}).items():
        if k not in FIELDS:
            continue
        fv = float(v)
        if fv <= 0:
            raise ValueError(f"{k} 要大於 0")
        rows.append((int(eid), game_key, k, fv))
    with _conn() as c:
        c.executemany(
            "INSERT INTO edition_odds (eid, game_key, field, value) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(eid, game_key, field) DO UPDATE SET value = excluded.value",
            rows,
        )
    return get_odds(int(eid), game_key)


def reset_odds(eid: int, game_key: str) -> dict:
    """清掉某版某遊戲的自訂,回到預設。"""
    with _conn() as c:
        c.execute("DELETE FROM edition_odds WHERE eid = ? AND game_key = ?",
                  (int(eid), game_key))
    return get_odds(int(eid), game_key)


def edition_exists(eid: int) -> bool:
    return any(e["eid"] == int(eid) for e in list_editions())
