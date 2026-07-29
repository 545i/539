"""SQLite 持久化:二合買牌(策略1)的逐局下注流水與合併累積損益。

資料模型(v2):**一個帳號一個損益池**,三款遊戲的下注全部串成同一條流水。
每筆紀錄記下「日期 / 遊戲 / 車數 / 押幾顆 / 重幾顆 / 成本 / 回收」,
累積損益依 (下注日期, 寫入順序) 重新累加 —— 所以補登過去日期的紀錄也會排到正確位置。

資料庫檔放在 data/ 下(frozen 打包時放 exe 旁邊)。
舊版(v1:依「帳號::遊戲」分池)的紀錄會在第一次開啟時自動遷移並保留,
遷移前會先備份一份 erhe_state.db.bak_v1。
"""
from __future__ import annotations

import datetime as dt
import shutil
import sqlite3
import sys
from pathlib import Path

# 中獎顆數尚未回填(還沒開獎 / 還沒對獎)的哨兵值。
# 用 -1 而非 NULL,是因為舊資料庫的 hits 欄位有 NOT NULL 約束,SQLite 無法事後移除。
PENDING = -1

# v1 舊資料遷移時,推不出成本的紀錄用的每車成本(僅供回填,不影響損益)
_FALLBACK_COST_PER_CAR = {"lotto539": 2755.0, "fantasy5": 2755.0, "marksix": 3528.0}
_FALLBACK_PAYOUT = {"lotto539": 21200.0, "fantasy5": 21200.0, "marksix": 28500.0}
_V2_COLUMNS = {
    "account": "TEXT",
    "game": "TEXT",
    "draw_date": "TEXT",
    "cost": "REAL",
    "payout": "REAL",
    "payout_rate": "REAL",   # 下注當時的「每車中獎可得」,供事後回填中獎顆數時結算
}


def _db_path() -> Path:
    """資料庫路徑(frozen 時位於 exe 旁邊,否則專案 data/)。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "erhe_state.db"


def today_str() -> str:
    """今天的日期字串(YYYY-MM-DD),供下注日期預設值。"""
    return dt.date.today().isoformat()


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
            cumulative REAL NOT NULL,
            account    TEXT,
            game       TEXT,
            draw_date  TEXT,
            cost       REAL,
            payout     REAL,
            payout_rate REAL
        )
        """
    )
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
    _migrate(conn, path)
    return conn


# ── v1 → v2 遷移 ─────────────────────────────────────────
def _migrate(conn: sqlite3.Connection, path: Path) -> None:
    """補齊 v2 欄位,並把舊的「帳號::遊戲」分池紀錄併成單一流水。

    可重複執行:只處理 account 仍為 NULL 的舊列。
    """
    cols = [r[1] for r in conn.execute("PRAGMA table_info(erhe_rounds)").fetchall()]
    if "numbers" not in cols:  # v0 → v1
        conn.execute("ALTER TABLE erhe_rounds ADD COLUMN numbers INTEGER NOT NULL DEFAULT 5")
    missing = [c for c in _V2_COLUMNS if c not in cols]
    legacy = conn.execute(
        "SELECT COUNT(*) FROM erhe_rounds WHERE account IS NULL" if not missing else
        "SELECT COUNT(*) FROM erhe_rounds"
    ).fetchone()[0]
    if not missing and legacy == 0:
        return  # 已是 v2 且無待遷移列

    if missing and legacy > 0 and path.exists():
        backup = path.with_name(path.name + ".bak_v1")
        if not backup.exists():
            shutil.copy2(path, backup)  # 遷移前備份一次,出事可還原
    for col in missing:
        conn.execute(f"ALTER TABLE erhe_rounds ADD COLUMN {col} {_V2_COLUMNS[col]}")

    rows = conn.execute(
        "SELECT id, game_key, ts, numbers, cars, net FROM erhe_rounds "
        "WHERE account IS NULL ORDER BY id"
    ).fetchall()
    if not rows:
        return

    accounts = set()
    for rid, game_key, ts, numbers, cars, net in rows:
        account, _, game = (game_key or "").partition("::")
        if not game:                      # 舊資料未綁帳號:整串視為預設遊戲
            account, game = "", "lotto539"
        game = game.split("::")[0]        # 容忍「帳號::遊戲::策略」這種舊格式
        draw_date = (ts or "")[:10] or today_str()
        cost = _legacy_cost(conn, account, game, numbers, cars)
        rate = _legacy_payout_rate(conn, account, game)
        conn.execute(
            "UPDATE erhe_rounds SET account=?, game=?, draw_date=?, cost=?, payout=?, "
            "payout_rate=? WHERE id=?",
            (account, game, draw_date, cost, (net or 0.0) + cost, rate, rid),
        )
        accounts.add(account)
    for account in accounts:
        _recompute(conn, account)


def _legacy_cost(conn, account: str, game: str, numbers, cars) -> float:
    """回填舊紀錄的本局成本 = 押幾顆 × 車數 × 每車成本(取該帳號存過的設定)。

    只用來拆出「成本 / 回收」兩個統計欄位;每局損益(net)完全不動。
    """
    row = conn.execute(
        "SELECT value FROM erhe_settings WHERE game_key=? AND key='cost_per_car'",
        (f"{account}::{game}",),
    ).fetchone()
    per_car = float(row[0]) if row else _FALLBACK_COST_PER_CAR.get(game, 2755.0)
    return int(numbers or 5) * int(cars or 0) * per_car


def _legacy_payout_rate(conn, account: str, game: str) -> float:
    """回填舊紀錄的「每車中獎可得」(取該帳號存過的設定,沒有就用該遊戲預設)。"""
    row = conn.execute(
        "SELECT value FROM erhe_settings WHERE game_key=? AND key='win_payout'",
        (f"{account}::{game}",),
    ).fetchone()
    return float(row[0]) if row else _FALLBACK_PAYOUT.get(game, 21200.0)


# ── 累積損益重算 ─────────────────────────────────────────
def _recompute(conn: sqlite3.Connection, account: str) -> None:
    """依 (下注日期, 寫入順序) 重新累加該帳號的累積損益。

    補登過去日期、撤銷任一筆之後都呼叫它,累積值永遠與流水一致。
    """
    running = 0.0
    for rid, net in conn.execute(
        "SELECT id, net FROM erhe_rounds WHERE account=? ORDER BY draw_date, id",
        (account,),
    ).fetchall():
        running += float(net or 0.0)
        conn.execute("UPDATE erhe_rounds SET cumulative=? WHERE id=?", (running, rid))


# ── 寫入 / 讀取 ──────────────────────────────────────────
def add_round(account: str, game: str, draw_date: str, numbers: int, cars: int,
              hits: int | None, cost: float, payout_rate: float) -> int:
    """新增一筆下注流水,回傳該筆 id。

    account   帳號(整個帳號共用一個損益池)
    game      遊戲代號(lotto539 / fantasy5 / marksix)
    draw_date 下注日期 YYYY-MM-DD
    numbers   每局押幾顆;cars 車數
    hits      重幾顆;傳 None 代表「還沒開獎 / 待回填」
    cost        本局成本
    payout_rate 下注當時的「每車中獎可得」;回收 = 中幾顆 × 車數 × payout_rate

    待回填的紀錄一樣把成本計入累積損益(錢已經花出去了),
    等回填中獎顆數時再依當初的 payout_rate 把回收加回來。
    """
    pending = hits is None
    hits_val = PENDING if pending else int(hits)
    payout = 0.0 if pending else int(hits) * int(cars) * float(payout_rate)
    net = payout - float(cost)
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO erhe_rounds "
            "(game_key, account, game, draw_date, numbers, cars, hits, cost, payout, "
            " payout_rate, net, cumulative) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (account, account, game, str(draw_date), int(numbers), int(cars), hits_val,
             float(cost), payout, float(payout_rate), net),
        )
        rid = int(cur.lastrowid)
        _recompute(c, account)
    return rid


def update_round_result(round_id: int, hits: int, payout: float | None = None) -> bool:
    """回填(或修正)某筆紀錄的中獎顆數;找不到該筆回 False。

    payout 留空時,依下注當時存的 payout_rate 結算:
    回收 = 中幾顆 × 車數 × 每車中獎可得。
    """
    with _conn() as c:
        row = c.execute(
            "SELECT account, cost, cars, payout_rate FROM erhe_rounds WHERE id = ?",
            (round_id,),
        ).fetchone()
        if row is None:
            return False
        account, cost, cars, rate = row[0], float(row[1] or 0.0), int(row[2] or 0), row[3]
        if payout is None:
            payout = int(hits) * cars * float(rate or 0.0)
        c.execute(
            "UPDATE erhe_rounds SET hits = ?, payout = ?, net = ? WHERE id = ?",
            (int(hits), float(payout), float(payout) - cost, int(round_id)),
        )
        _recompute(c, account)
    return True


def set_round_date(round_id: int, draw_date: str) -> bool:
    """修改某筆紀錄的下注日期(補登打錯時用);會重排流水順序。"""
    with _conn() as c:
        row = c.execute("SELECT account FROM erhe_rounds WHERE id = ?", (round_id,)).fetchone()
        if row is None:
            return False
        c.execute("UPDATE erhe_rounds SET draw_date = ? WHERE id = ?",
                  (str(draw_date), int(round_id)))
        _recompute(c, row[0])
    return True


def delete_round(round_id: int) -> bool:
    """刪除指定的一筆紀錄(流水表上的逐筆刪除);找不到回 False。"""
    with _conn() as c:
        row = c.execute("SELECT account FROM erhe_rounds WHERE id = ?", (round_id,)).fetchone()
        if row is None:
            return False
        c.execute("DELETE FROM erhe_rounds WHERE id = ?", (int(round_id),))
        _recompute(c, row[0])
    return True


_ROW_COLS = ["id", "ts", "draw_date", "game", "numbers", "cars", "hits",
             "cost", "payout", "payout_rate", "net", "cumulative"]


def load_rounds(account: str) -> list[dict]:
    """該帳號的完整下注流水(依下注日期、寫入順序);pending 欄標示是否待回填。"""
    with _conn() as c:
        rows = c.execute(
            f"SELECT {', '.join(_ROW_COLS)} FROM erhe_rounds "
            "WHERE account = ? ORDER BY draw_date, id",
            (account,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(zip(_ROW_COLS, r))
        d["pending"] = int(d["hits"] or 0) < 0
        out.append(d)
    return out


def pending_rounds(account: str) -> list[dict]:
    """尚未回填中獎顆數的紀錄(待對獎清單)。"""
    return [r for r in load_rounds(account) if r["pending"]]


def current_cumulative(account: str) -> float:
    """目前合併累積損益(流水最後一筆的累積值;無紀錄回 0)。"""
    with _conn() as c:
        row = c.execute(
            "SELECT cumulative FROM erhe_rounds WHERE account = ? "
            "ORDER BY draw_date DESC, id DESC LIMIT 1",
            (account,),
        ).fetchone()
    return float(row[0]) if row else 0.0


def totals(account: str) -> dict:
    """該帳號的合計:總成本、總回收、總損益、局數、中獎局數。"""
    with _conn() as c:
        row = c.execute(
            "SELECT COALESCE(SUM(cost),0), COALESCE(SUM(payout),0), "
            "       COALESCE(SUM(net),0), COUNT(*), "
            "       COALESCE(SUM(CASE WHEN hits > 0 THEN 1 ELSE 0 END),0), "
            "       COALESCE(SUM(CASE WHEN hits < 0 THEN 1 ELSE 0 END),0) "
            "FROM erhe_rounds WHERE account = ?",
            (account,),
        ).fetchone()
    cost, payout, net, rounds, wins, pending = row
    settled = int(rounds) - int(pending)   # 勝率只看已對獎的局
    return {
        "cost": float(cost), "payout": float(payout), "net": float(net),
        "rounds": int(rounds), "wins": int(wins), "pending": int(pending),
        "settled": settled,
        "win_rate": (wins / settled) if settled else 0.0,
        "roi": (net / cost) if cost else 0.0,
    }


def totals_by_game(account: str) -> dict[str, dict]:
    """依遊戲拆開的合計(給「哪一款賺賠最多」用)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT game, COALESCE(SUM(cost),0), COALESCE(SUM(payout),0), "
            "       COALESCE(SUM(net),0), COUNT(*), "
            "       COALESCE(SUM(CASE WHEN hits > 0 THEN 1 ELSE 0 END),0), "
            "       COALESCE(SUM(CASE WHEN hits < 0 THEN 1 ELSE 0 END),0) "
            "FROM erhe_rounds WHERE account = ? GROUP BY game",
            (account,),
        ).fetchall()
    return {
        r[0]: {"cost": float(r[1]), "payout": float(r[2]), "net": float(r[3]),
               "rounds": int(r[4]), "wins": int(r[5]), "pending": int(r[6])}
        for r in rows
    }


def totals_by_date(account: str) -> list[dict]:
    """依下注日期彙總的流水(同一天三款一起看)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT draw_date, COUNT(*), COALESCE(SUM(cost),0), "
            "       COALESCE(SUM(payout),0), COALESCE(SUM(net),0), MAX(cumulative) "
            "FROM erhe_rounds WHERE account = ? GROUP BY draw_date ORDER BY draw_date",
            (account,),
        ).fetchall()
    out = []
    for d, n, cost, payout, net, _cum in rows:
        out.append({"draw_date": d, "rounds": int(n), "cost": float(cost),
                    "payout": float(payout), "net": float(net)})
    # 累積值要照日期順序重新取(MAX(cumulative) 在同日多筆時才是當日收盤值)
    running = 0.0
    for row in out:
        running += row["net"]
        row["cumulative"] = running
    return out


def undo_last_round(account: str) -> bool:
    """撤銷「最後輸入」的那一筆(不是最後日期的那筆);無紀錄回 False。"""
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM erhe_rounds WHERE account = ? ORDER BY id DESC LIMIT 1",
            (account,),
        ).fetchone()
        if row is None:
            return False
        c.execute("DELETE FROM erhe_rounds WHERE id = ?", (row[0],))
        _recompute(c, account)
    return True


def reset(account: str) -> None:
    """清除該帳號的所有下注流水。"""
    with _conn() as c:
        c.execute("DELETE FROM erhe_rounds WHERE account = ?", (account,))


def latest_cumulatives() -> list[dict]:
    """每個帳號的合併累積損益與局數(供排行榜)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT account, COALESCE(SUM(net),0), COUNT(*), COALESCE(SUM(cost),0) "
            "FROM erhe_rounds GROUP BY account"
        ).fetchall()
    return [
        {"account": r[0] or "", "cumulative": float(r[1]), "rounds": int(r[2]),
         "cost": float(r[3])}
        for r in rows
    ]


# ── 盤口設定(仍依「帳號::遊戲」分開存)────────────────────
def get_setting(game_key: str, key: str, default: float) -> float:
    """讀取某帳號某遊戲的設定值(無則回傳 default)。"""
    with _conn() as c:
        row = c.execute(
            "SELECT value FROM erhe_settings WHERE game_key = ? AND key = ?",
            (game_key, key),
        ).fetchone()
    return float(row[0]) if row else float(default)


def set_setting(game_key: str, key: str, value: float) -> None:
    """寫入/更新某帳號某遊戲的設定值。"""
    with _conn() as c:
        c.execute(
            "INSERT INTO erhe_settings (game_key, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(game_key, key) DO UPDATE SET value = excluded.value",
            (game_key, key, float(value)),
        )
