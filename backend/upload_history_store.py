"""快速上傳歷史的持久化:一個使用者、一批上傳、一筆 JSON(SQLite)。

前端原本把「快速上傳歷史」存在瀏覽器 localStorage,換裝置 / 換瀏覽器就不見。這裡
比照 backend.ledger_store 用一張極簡表存起來,登入後跨裝置都在。

業務鍵用 entry 內的 ts(前端一直拿 ts 當 React key 與更新鍵),payload 原封不動存
整個 entry 的 JSON(gameName / editionName / eid / issue / text / items / bill / recon …)。
後端不解讀內容,只負責存 / 取 / 改 / 清,以及維持每人最多 HISTORY_CAP 筆。

資料庫檔放 data/upload_history.db(frozen 打包時放 exe 旁邊;*.db 已被 gitignore)。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

HISTORY_CAP = 30       # 每人最多留幾批(與前端一致)


def _db_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "upload_history.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS upload_history (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            ts       INTEGER NOT NULL,
            payload  TEXT NOT NULL,
            created  TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_uh_user_ts ON upload_history (username, ts)"
    )
    return conn


def _entry(payload: str) -> dict:
    """payload JSON → entry dict;壞掉回空 dict(不讓整包讀不出來)。"""
    try:
        e = json.loads(payload)
    except (ValueError, TypeError):
        e = {}
    return e if isinstance(e, dict) else {}


def list_entries(username: str) -> list[dict]:
    """某使用者的全部上傳歷史,新→舊(ts 大的在前)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT payload FROM upload_history WHERE username = ? "
            "ORDER BY ts DESC, id DESC",
            (username,),
        ).fetchall()
    return [_entry(r[0]) for r in rows]


def _prune(c: sqlite3.Connection, username: str) -> None:
    """留最新 HISTORY_CAP 筆,其餘刪掉(依 ts 由新到舊)。"""
    c.execute(
        "DELETE FROM upload_history WHERE username = ? AND id NOT IN ("
        "  SELECT id FROM upload_history WHERE username = ? "
        "  ORDER BY ts DESC, id DESC LIMIT ?)",
        (username, username, HISTORY_CAP),
    )


def add_entry(username: str, entry: dict) -> dict:
    """新增一批;回傳存入的 entry。維持每人最多 HISTORY_CAP 筆。"""
    ts = int(entry.get("ts") or 0)
    with _conn() as c:
        c.execute(
            "INSERT INTO upload_history (username, ts, payload) VALUES (?, ?, ?)",
            (username, ts, json.dumps(entry, ensure_ascii=False)),
        )
        _prune(c, username)
    return entry


def update_entry(username: str, ts: int, patch: dict) -> dict | None:
    """把某批(ts 相符)的 payload 合併 patch 後覆寫;回傳更新後 entry。找不到回 None。"""
    with _conn() as c:
        row = c.execute(
            "SELECT id, payload FROM upload_history WHERE username = ? AND ts = ? "
            "ORDER BY id DESC LIMIT 1",
            (username, int(ts)),
        ).fetchone()
        if row is None:
            return None
        merged = {**_entry(row[1]), **(patch or {})}
        c.execute(
            "UPDATE upload_history SET payload = ? WHERE id = ?",
            (json.dumps(merged, ensure_ascii=False), int(row[0])),
        )
    return merged


def update_issue_by_entry_id(username: str, entry_id: int, new_issue: str) -> int:
    """把「entryIds 含 entry_id」的那批上傳歷史,期號改成 new_issue;回傳更新幾批。

    ledger 明細改期數時同步呼叫,快速上傳歷史的盈虧才會抓對期(它拿 entry.issue
    去查該期派彩)。只認有存 entryIds 的批次 —— 舊批次沒 id 無從連動(直接改資料庫)。
    """
    n = 0
    with _conn() as c:
        rows = c.execute(
            "SELECT id, payload FROM upload_history WHERE username = ?", (username,)
        ).fetchall()
        for rid, payload in rows:
            e = _entry(payload)
            ids = e.get("entryIds")
            if not isinstance(ids, list):
                continue
            has = any(isinstance(x, (int, float)) and int(x) == int(entry_id)
                      for x in ids)
            if has and str(e.get("issue") or "") != str(new_issue):
                e["issue"] = str(new_issue)
                c.execute(
                    "UPDATE upload_history SET payload = ? WHERE id = ?",
                    (json.dumps(e, ensure_ascii=False), int(rid)),
                )
                n += 1
    return n


def clear(username: str) -> int:
    """清空某使用者的上傳歷史,回傳刪了幾筆。"""
    with _conn() as c:
        cur = c.execute("DELETE FROM upload_history WHERE username = ?", (username,))
    return int(cur.rowcount or 0)


def delete_entry(username: str, ts: int) -> int:
    """刪掉某一批(ts 相符),回傳刪了幾筆。"""
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM upload_history WHERE username = ? AND ts = ?",
            (username, int(ts)),
        )
    return int(cur.rowcount or 0)
