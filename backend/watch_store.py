"""區間組合「斷檔提醒」的公共設定:每款遊戲一份「要盯的組合」清單(全站共用)。

以前這份設定存在前端 localStorage(每個瀏覽器各一份、私人),所以每個人看到的
提醒不一樣、也沒辦法給提醒機器人用。搬進 sqlite 後變成**全站共用**(公共),
UI 改一次全站生效,Telegram 排程提醒也讀同一份。

一筆組合 = {label, groups, threshold}:
    label      顯示名稱(例:「0~3頭 四段同開」)
    groups     數個區間,各自的號碼清單 [[1..9],[10..19],[20..29],[30..39]]
    threshold  連續幾期「沒有全部同時開出」就算斷檔(alert)

出廠預設:每款種一筆「全段同開」(539/天天樂 四段=0~3頭、六合彩 五段),
threshold=5 —— 對應使用者要的「0頭到3頭 四個組合一起沒開幾期」。

資料庫檔放 data/watch.db(*.db 已被 gitignore)。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from core.games import get as game_by_key

DEFAULT_THRESHOLD = 5


def _db_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "watch.db"


def _bands(num_max: int) -> list[list[int]]:
    """十位區段:0頭=1~9、1頭=10~19、…直到涵蓋 num_max。"""
    out: list[list[int]] = []
    hi = num_max // 10
    for i in range(hi + 1):
        lo = 1 if i == 0 else i * 10
        nums = [n for n in range(lo, i * 10 + 10) if 1 <= n <= num_max]
        if nums:
            out.append(nums)
    return out


def _default_combos(game_key: str) -> list[dict]:
    g = game_by_key(game_key)
    bands = _bands(g.num_max)
    label = f"0~{len(bands) - 1}頭 {len(bands)} 段同開"
    return [{"label": label, "groups": bands, "threshold": DEFAULT_THRESHOLD}]


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS combo_watch (
            game_key  TEXT NOT NULL,
            idx       INTEGER NOT NULL,
            label     TEXT NOT NULL,
            groups    TEXT NOT NULL,
            threshold INTEGER NOT NULL DEFAULT 5,
            PRIMARY KEY (game_key, idx)
        )
        """
    )
    return conn


def _has_seen_table(c: sqlite3.Connection) -> bool:
    return bool(c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='combo_watch_seen'"
    ).fetchone())


def get_combos(game_key: str) -> list[dict]:
    """這款目前盯的組合清單;沒設定過回出廠預設(不寫入,呼叫端讀得到即可)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT label, groups, threshold FROM combo_watch "
            "WHERE game_key = ? ORDER BY idx", (game_key,),
        ).fetchall()
        seen = _has_seen_table(c) and c.execute(
            "SELECT 1 FROM combo_watch_seen WHERE game_key = ?", (game_key,)
        ).fetchone()
    if not rows and not seen:
        return _default_combos(game_key)
    out = []
    for label, groups, thr in rows:
        try:
            grp = json.loads(groups)
        except (ValueError, TypeError):
            grp = []
        out.append({"label": label, "groups": grp, "threshold": int(thr)})
    return out


def set_combos(game_key: str, combos: list[dict]) -> list[dict]:
    """整組覆寫這款的組合清單(可為空 = 這款不盯任何組合)。"""
    rows = []
    for i, c in enumerate(combos or []):
        groups = [[int(n) for n in g] for g in (c.get("groups") or []) if g]
        thr = int(c.get("threshold", DEFAULT_THRESHOLD))
        rows.append((game_key, i, str(c.get("label", "") or f"組合{i+1}"),
                     json.dumps(groups), max(1, thr)))
    with _conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS combo_watch_seen (game_key TEXT PRIMARY KEY)")
        conn.execute("DELETE FROM combo_watch WHERE game_key = ?", (game_key,))
        conn.executemany(
            "INSERT INTO combo_watch (game_key, idx, label, groups, threshold) "
            "VALUES (?, ?, ?, ?, ?)", rows)
        conn.execute("INSERT OR IGNORE INTO combo_watch_seen (game_key) VALUES (?)",
                     (game_key,))
    return get_combos(game_key)
