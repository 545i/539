"""操作歷史(audit log):每個會改到資料的動作都留一筆痕跡,而且**可以反轉**。

記帳流水本身只看得到「現在有哪些紀錄」,看不到「誰在什麼時候做了什麼」。
撤銷更是不可逆 —— 手滑按下去,那一局的號碼、成本、期別就沒了。這張表把
「反轉這個動作所需要的全部資料」跟動作本身一起存下來,所以撤銷可以被撤銷。

**四種動作與各自的反轉**:

    bet_add       單筆下注寫進 ledger    → 反轉 = 刪掉那筆 ledger_entry
    bet_delete    撤銷一筆(刪除)        → 反轉 = 把整筆 record 重新 insert 回去
    bet_clear     清空某下法的全部紀錄     → 反轉 = 把那一批 record 全部放回去
    quick_import  快速上傳一次多筆        → 反轉 = 刪掉那一批
    void          作廢(反轉)某個操作     → 本身也是一筆紀錄,不能再被作廢

關鍵在 bet_delete:**刪之前**要先把整筆內容塞進 reverse_data,不然事後拿不
回來。所以 ledger_store.delete_entry 改成回傳被刪的那一筆(見該檔)。

作廢是「補一筆反向操作」而不是「把歷史抹掉」—— 原操作留著只是標記 voided,
作廢本身另外記一筆(void_of 指回去)。歷史只會往前長,不會被改寫。

資料庫檔放 data/audit.db(frozen 打包時放 exe 旁邊;*.db 已被 gitignore)。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

# 動作類型 → 中文標籤(前端直接顯示,不用自己維護一份對照表)
ACTION_LABELS = {
    "bet_add": "新增下注",
    "bet_delete": "撤銷下注",
    "bet_clear": "清空紀錄",
    "bet_settle": "改期數對獎",
    "quick_import": "快速上傳",
    "void": "作廢操作",
}

ACTIONS = tuple(ACTION_LABELS)

# 下注模式 → 中文(摘要用;與前端各分頁的名稱一致)
MODE_LABELS = {
    "single": "1組",       # 二合買牌第一組(舊「單顆」的 mode key)
    "multi": "2組",        # 二合買牌第二組(舊「多顆」的 mode key)
    "pillar1800": "三柱1800碰",
    "combo9000": "9000碰",
    "combo": "連碰",
}


def _db_path() -> Path:
    """資料庫路徑(frozen 時位於 exe 旁邊,否則專案 data/)。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "audit.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            action       TEXT NOT NULL,
            target_id    INTEGER,
            summary      TEXT NOT NULL DEFAULT '',
            reverse_data TEXT NOT NULL DEFAULT '{}',
            voided       INTEGER NOT NULL DEFAULT 0,
            void_of      INTEGER,
            created      TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log (username, id)"
    )
    return conn


_COLS = ("id, username, action, target_id, summary, reverse_data, "
         "voided, void_of, created")


def _row(r: tuple) -> dict:
    """資料庫列 → API 形狀;reverse_data 壞掉就當空的(不讓整份歷史讀不出來)。"""
    try:
        reverse = json.loads(r[5])
    except (ValueError, TypeError):
        reverse = {}
    if not isinstance(reverse, dict):
        reverse = {}
    action = r[2]
    voided = bool(r[6])
    return {
        "id": int(r[0]),
        "username": r[1],
        "action": action,
        "action_label": ACTION_LABELS.get(action, action),
        "target_id": int(r[3]) if r[3] is not None else None,
        "summary": r[4] or "",
        "reverse_data": reverse,
        "voided": voided,
        "void_of": int(r[7]) if r[7] is not None else None,
        "created": r[8],
        # 作廢動作本身不可再作廢(不然一路反轉回去語意會纏死);已作廢的也不行
        "reversible": action != "void" and not voided,
    }


def log(username: str, action: str, target_id: int | None = None,
        summary: str = "", reverse_data: dict | None = None,
        void_of: int | None = None) -> dict:
    """記一筆操作,回傳寫進去的那筆(含 id)。

    reverse_data 是「反轉這個動作要用到的東西」,形狀由 action 決定
    (見 backend/routers/audit.py 的 _revert)。
    """
    if action not in ACTIONS:
        raise ValueError(f"未知的操作類型:{action}")
    payload = json.dumps(reverse_data or {}, ensure_ascii=False)
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO audit_log (username, action, target_id, summary, "
            "reverse_data, void_of) VALUES (?, ?, ?, ?, ?, ?)",
            (username, action,
             int(target_id) if target_id is not None else None,
             summary, payload,
             int(void_of) if void_of is not None else None),
        )
        row = c.execute(
            f"SELECT {_COLS} FROM audit_log WHERE id = ?", (int(cur.lastrowid),)
        ).fetchone()
    return _row(row)


def list_logs(username: str, limit: int = 200) -> list[dict]:
    """某使用者的操作歷史,**新到舊**(歷史頁最關心的是剛剛做了什麼)。"""
    with _conn() as c:
        rows = c.execute(
            f"SELECT {_COLS} FROM audit_log WHERE username = ? "
            "ORDER BY id DESC LIMIT ?",
            (username, max(1, int(limit))),
        ).fetchall()
    return [_row(r) for r in rows]


def get(log_id: int) -> dict | None:
    """取一筆(含 username,呼叫端自己比對是不是本人的操作)。"""
    with _conn() as c:
        row = c.execute(
            f"SELECT {_COLS} FROM audit_log WHERE id = ?", (int(log_id),)
        ).fetchone()
    return _row(row) if row else None


def mark_voided(log_id: int) -> bool:
    """標記成已作廢;本來就已作廢(或不存在)回 False —— 擋重複作廢用這個回傳值。"""
    with _conn() as c:
        cur = c.execute(
            "UPDATE audit_log SET voided = 1 WHERE id = ? AND voided = 0",
            (int(log_id),),
        )
    return (cur.rowcount or 0) > 0


# ── 摘要 ────────────────────────────────────────────────────
# 歷史頁要看得懂「作廢的是哪一筆」,光有 id 沒有用。這裡把前端的 BetRecord
# 擠成一行字;欄位缺了就跳過那一段(舊紀錄 / 別的形狀都不能讓摘要爆掉)。
def summarize_record(mode: str, record: dict) -> str:
    """一筆下注 → 一行摘要,例如「單顆下注 · 今彩539 · 單顆 3 車 · 成本 8,265」。"""
    rec = record if isinstance(record, dict) else {}
    parts = [MODE_LABELS.get(mode, mode)]
    for key in ("game", "playType"):
        v = rec.get(key)
        if isinstance(v, str) and v:
            parts.append(v)
    issue = rec.get("issue")
    if isinstance(issue, str) and issue:
        parts.append(f"第 {issue} 期")
    cost = rec.get("cost")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        parts.append(f"成本 {round(cost):,}")
    return " · ".join(parts)
