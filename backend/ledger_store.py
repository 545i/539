"""記帳流水的持久化:一個使用者、一種下法、一筆 JSON。

前端各下注分頁的「流水帳紀錄」原本只活在 React state,重整就沒了。這裡用一張
極簡的通用表把它存起來,登入後跨裝置 / 跨重整都在。

**為什麼不用 core.storage?**
core.storage 的 erhe_rounds 是為二合買牌量身訂做的(numbers / cars / hits /
payout_rate 這些欄位有各自的語意,還要跟著算累積損益、對獎、追虧損)。前端的
BetRecord 是另一套形狀(selectedBalls / drawBalls / pillarDist / result …),
硬塞進去會兩邊都變形。這張表只負責「原封不動地存下前端記了什麼」,
累積損益由前端依順序重算 —— 兩套資料各自獨立,互不干擾。

資料庫檔放 data/ledger.db(frozen 打包時放 exe 旁邊;*.db 已被 gitignore)。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# 允許的下法(對應前端 DuoBetTab 的四個記帳分頁)
MODES = ("single", "multi", "pillar1800", "combo")


def _db_path() -> Path:
    """資料庫路徑(frozen 時位於 exe 旁邊,否則專案 data/)。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "ledger.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            mode     TEXT NOT NULL,
            payload  TEXT NOT NULL,
            created  TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ledger_user_mode "
        "ON ledger_entries (username, mode, id)"
    )
    return conn


def _row(r: tuple) -> dict:
    """資料庫列 → API 回傳形狀;payload 壞掉就當空紀錄(不讓整包讀不出來)。"""
    try:
        record = json.loads(r[2])
    except (ValueError, TypeError):
        record = {}
    return {"id": int(r[0]), "mode": r[1], "record": record, "created": r[3]}


def list_entries(username: str, mode: str | None = None) -> list[dict]:
    """某使用者的紀錄(寫入順序,舊→新);mode 傳 None 代表四種下法全取。"""
    where, params = "", [username]
    if mode is not None:
        where = " AND mode = ?"
        params.append(mode)
    with _conn() as c:
        rows = c.execute(
            "SELECT id, mode, payload, created FROM ledger_entries "
            f"WHERE username = ?{where} ORDER BY id",
            params,
        ).fetchall()
    return [_row(r) for r in rows]


def add_entry(username: str, mode: str, record: dict) -> dict:
    """新增一筆,回傳寫進去的那筆(含資料庫給的 id)。"""
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO ledger_entries (username, mode, payload) VALUES (?, ?, ?)",
            (username, mode, json.dumps(record, ensure_ascii=False)),
        )
        row = c.execute(
            "SELECT id, mode, payload, created FROM ledger_entries WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _row(row)


def delete_entry(username: str, entry_id: int) -> bool:
    """刪一筆(撤銷用);不是自己的紀錄或不存在都回 False。"""
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM ledger_entries WHERE id = ? AND username = ?",
            (int(entry_id), username),
        )
    return (cur.rowcount or 0) > 0


def _num(record: dict, key: str) -> float:
    """從紀錄裡取一個數字欄位;缺欄位 / 型別不對都當 0。

    這是後端唯一會「解讀」payload 的地方 —— 排行榜非得知道損益不可。
    只碰 pnl / cost / payout 三個數字欄,其餘欄位仍然原封不動。
    """
    v = record.get(key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def _blank_agg() -> dict:
    return {"rounds": 0, "wins": 0, "losses": 0, "total_pnl": 0.0,
            "total_cost": 0.0, "total_payout": 0.0, "last_at": ""}


def _fold(agg: dict, record: dict, created: str) -> None:
    pnl = _num(record, "pnl")
    agg["rounds"] += 1
    agg["wins"] += 1 if pnl > 0 else 0
    agg["losses"] += 1 if pnl < 0 else 0
    agg["total_pnl"] += pnl
    agg["total_cost"] += _num(record, "cost")
    agg["total_payout"] += _num(record, "payout")
    if created and created > agg["last_at"]:
        agg["last_at"] = created


def summary() -> dict:
    """全站流水的彙總:依使用者、依下法各一份(排行榜用)。

    回傳 {"users": {帳號: 彙總}, "modes": {下法: 彙總}},彙總含
    rounds / wins / losses / total_pnl / total_cost / total_payout / last_at。
    勝率與報酬率由呼叫端換算(這裡不決定分母要用成本還是注數)。
    """
    with _conn() as c:
        rows = c.execute(
            "SELECT username, mode, payload, created FROM ledger_entries ORDER BY id"
        ).fetchall()

    users: dict[str, dict] = {}
    modes: dict[str, dict] = {}
    for username, mode, payload, created in rows:
        try:
            record = json.loads(payload)
        except (ValueError, TypeError):
            record = {}
        if not isinstance(record, dict):
            record = {}
        _fold(users.setdefault(username, _blank_agg()), record, created or "")
        _fold(modes.setdefault(mode, _blank_agg()), record, created or "")
    return {"users": users, "modes": modes}


def clear(username: str, mode: str | None = None) -> int:
    """清空某使用者的紀錄,回傳刪掉幾筆;mode 傳 None 代表清光四種下法。"""
    where, params = "", [username]
    if mode is not None:
        where = " AND mode = ?"
        params.append(mode)
    with _conn() as c:
        cur = c.execute(f"DELETE FROM ledger_entries WHERE username = ?{where}", params)
    return int(cur.rowcount or 0)
