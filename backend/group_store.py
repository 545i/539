"""二合下注「組」的設定持久化:每組一列 {固定顆數, 是否啟用}。

以前二合買牌只有寫死的「單顆 / 多顆」兩種下法。現在改成兩個可設定的「組」:
**1組**(原單顆,預設固定 2 顆)、**2組**(原多顆,預設固定 3 顆)。每組可以改
固定顆數、可以停用。

**這是全站設定,不是個人偏好**(比照 backend/star_cost_store.py):同一個站上
所有人看到的組設定是同一份,不然分頁、快速上傳、排行榜就對不起來,所以表裡
沒有 username 欄。

**gid 與 ledger mode 的對應只寫在這裡一個地方**(GID_TO_MODE):組化只是換張皮,
底層流水仍存在既有的 single / multi 兩個 mode key,所以線上舊紀錄不用搬 ——
single 那批就是 1組、multi 那批就是 2組。

資料庫檔放 data/group.db(frozen 打包時放 exe 旁邊;*.db 已被 gitignore)。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# gid → 底層 ledger mode key(唯一對應點)。1組=single、2組=multi。
GID_TO_MODE: dict[int, str] = {1: "single", 2: "multi"}
MODE_TO_GID: dict[str, int] = {v: k for k, v in GID_TO_MODE.items()}

# 出廠預設:1組固定 2 顆、2組固定 3 顆,都啟用。
_DEFAULTS: dict[int, dict] = {
    1: {"name": "1組", "ball_count": 2, "enabled": True},
    2: {"name": "2組", "ball_count": 3, "enabled": True},
}


def _db_path() -> Path:
    """資料庫路徑(frozen 時位於 exe 旁邊,否則專案 data/)。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "group.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bet_groups (
            gid        INTEGER PRIMARY KEY,
            ball_count INTEGER NOT NULL,
            enabled    INTEGER NOT NULL DEFAULT 1,
            updated    TEXT DEFAULT (datetime('now', 'localtime')),
            updated_by TEXT DEFAULT ''
        )
        """
    )
    return conn


def _stored() -> dict[int, dict]:
    """資料庫裡真的存過的那幾組(沒存過的 gid 不會出現)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT gid, ball_count, enabled, updated, updated_by FROM bet_groups"
        ).fetchall()
    return {int(r[0]): {"ball_count": int(r[1]), "enabled": bool(r[2]),
                        "updated": r[3] or "", "updated_by": r[4] or ""}
            for r in rows}


def get_groups() -> list[dict]:
    """目前生效的兩組設定(依 gid 排序)。

    沒存過的 gid 回出廠預設 —— 呼叫端永遠拿得到完整兩組,不必自己補洞。
    每筆含 gid / mode / name / ball_count / enabled。
    """
    stored = _stored()
    out: list[dict] = []
    for gid in sorted(GID_TO_MODE):
        d = _DEFAULTS[gid]
        row = stored.get(gid)
        out.append({
            "gid": gid,
            "mode": GID_TO_MODE[gid],
            "name": d["name"],
            "ball_count": row["ball_count"] if row else d["ball_count"],
            "enabled": row["enabled"] if row else d["enabled"],
        })
    return out


def get_group(gid: int) -> dict | None:
    """單組設定;沒有這個 gid 回 None。"""
    return next((g for g in get_groups() if g["gid"] == int(gid)), None)


def mode_enabled(mode: str) -> bool:
    """某 ledger mode 對應的組是否啟用(非組的 mode 一律當啟用)。"""
    gid = MODE_TO_GID.get(mode)
    if gid is None:
        return True
    g = get_group(gid)
    return bool(g and g["enabled"])


def set_groups(items: list[dict], updated_by: str = "") -> list[dict]:
    """寫入(或更新)組設定,回傳寫完之後的完整兩組。

    items 形如 [{"gid": 1, "ball_count": 2, "enabled": True}, ...];只給部分組
    就只改那幾組。固定顆數要 >= 1(0 顆下注沒有意義);gid 不在 GID_TO_MODE
    裡直接擋掉(打錯不該偷偷寫進資料庫)。
    """
    rows = []
    for it in (items or []):
        gid = int(it["gid"])
        if gid not in GID_TO_MODE:
            raise ValueError(f"沒有這個組:{gid}(可設定的是 {list(GID_TO_MODE)})")
        cur = get_group(gid) or {}
        ball_count = int(it.get("ball_count", cur.get("ball_count", 1)))
        if ball_count < 1:
            raise ValueError(f"{_DEFAULTS[gid]['name']}的固定顆數要至少 1 顆")
        enabled = 1 if bool(it.get("enabled", cur.get("enabled", True))) else 0
        rows.append((gid, ball_count, enabled, updated_by))

    with _conn() as c:
        c.executemany(
            """
            INSERT INTO bet_groups (gid, ball_count, enabled, updated, updated_by)
            VALUES (?, ?, ?, datetime('now', 'localtime'), ?)
            ON CONFLICT(gid) DO UPDATE SET
                ball_count = excluded.ball_count,
                enabled    = excluded.enabled,
                updated    = excluded.updated,
                updated_by = excluded.updated_by
            """,
            rows,
        )
    return get_groups()


def reset() -> list[dict]:
    """清掉所有自訂,回到出廠預設。"""
    with _conn() as c:
        c.execute("DELETE FROM bet_groups")
    return get_groups()
