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

# 下注模式:單顆(每款固定押 1 顆)/ 多顆。兩者共用同一個損益池,但紀錄與重置分開。
SINGLE = "single"
MULTI = "multi"
MODES = (SINGLE, MULTI)
MODE_NAMES = {SINGLE: "單顆", MULTI: "多顆"}

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
            payout_rate REAL,
            mode       TEXT NOT NULL DEFAULT 'multi',
            picked     TEXT,
            issue      TEXT
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS predictions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            game         TEXT NOT NULL,
            target_issue TEXT NOT NULL,
            target_date  TEXT,
            strategy     TEXT NOT NULL,
            numbers      TEXT NOT NULL,
            created_at   TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE (game, target_issue, strategy)
        )
        """
    )
    _migrate(conn, path)
    return conn


def _migrate_predictions(conn: sqlite3.Connection) -> None:
    """預測表:從「以日期為鍵」改成「以期數為鍵」。

    一開始用 target_date 當識別,但日期不等於一期 —— 同一天可能剛開完
    11964、接著要下的是 11965,兩者都落在同一天就會撞在一起、後者存不進去。
    改用 target_issue(期號)當識別;沒有期號的款(六合彩)就拿日期字串當期號用。

    SQLite 不能直接改 UNIQUE 約束,所以重建表再把舊資料搬過去。
    """
    cols = [r[1] for r in conn.execute("PRAGMA table_info(predictions)").fetchall()]
    if not cols or "target_issue" in cols:
        return                                   # 沒這張表 或 已經是新版
    conn.execute(
        """
        CREATE TABLE predictions_v2 (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            game         TEXT NOT NULL,
            target_issue TEXT NOT NULL,
            target_date  TEXT,
            strategy     TEXT NOT NULL,
            numbers      TEXT NOT NULL,
            created_at   TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE (game, target_issue, strategy)
        )
        """
    )
    # 舊資料有期號就用期號,沒有就沿用日期當期號(識別方式不變,不會消失)
    conn.execute(
        "INSERT OR IGNORE INTO predictions_v2 "
        "(game, target_issue, target_date, strategy, numbers, created_at) "
        "SELECT game, COALESCE(NULLIF(TRIM(COALESCE(issue, '')), ''), target_date), "
        "       target_date, strategy, numbers, created_at FROM predictions"
    )
    conn.execute("DROP TABLE predictions")
    conn.execute("ALTER TABLE predictions_v2 RENAME TO predictions")


# ── v1 → v2 遷移 ─────────────────────────────────────────
def _migrate(conn: sqlite3.Connection, path: Path) -> None:
    """補齊 v2 欄位,並把舊的「帳號::遊戲」分池紀錄併成單一流水。

    可重複執行:只處理 account 仍為 NULL 的舊列。
    """
    _migrate_predictions(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(erhe_rounds)").fetchall()]
    if "numbers" not in cols:  # v0 → v1
        conn.execute("ALTER TABLE erhe_rounds ADD COLUMN numbers INTEGER NOT NULL DEFAULT 5")
    if "picked" not in cols:   # v3 → v4:記下實際圈選的號碼(選號盤)
        conn.execute("ALTER TABLE erhe_rounds ADD COLUMN picked TEXT")
        cols.append("picked")
    if "issue" not in cols:    # v4 → v5:記下期號,才能跟預測對得起來
        conn.execute("ALTER TABLE erhe_rounds ADD COLUMN issue TEXT")
        cols.append("issue")
    if "mode" not in cols:     # v2 → v3:單顆 / 多顆分流
        if path.exists():
            bak = path.with_name(path.name + ".bak_v2")
            if not bak.exists():
                shutil.copy2(path, bak)
        conn.execute("ALTER TABLE erhe_rounds ADD COLUMN mode TEXT")
        # 舊紀錄沒有模式欄:押 1 顆的就是單顆下法,其餘歸多顆
        conn.execute(
            f"UPDATE erhe_rounds SET mode = CASE WHEN numbers = 1 THEN '{SINGLE}' "
            f"ELSE '{MULTI}' END WHERE mode IS NULL"
        )
        cols.append("mode")
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


# ── 模式過濾 / 備份 ──────────────────────────────────────
def _mode_clause(mode: str | None) -> tuple[str, tuple]:
    """回傳 (附加的 SQL 條件, 參數);mode 傳 None 代表單顆多顆都要。"""
    if mode is None:
        return "", ()
    if mode not in MODES:
        raise ValueError(f"未知的下注模式:{mode}")
    return " AND mode = ?", (mode,)


BACKUP_KEEP = 30          # 自動備份保留幾份(超過就砍最舊的)


def backup(tag: str = "manual") -> Path | None:
    """把資料庫另存一份到 data/backups/,回傳備份路徑(沒有資料庫則回 None)。

    刪除類操作前一定會呼叫它 —— 誤刪時可以直接把檔案複製回去,
    不必再從磁碟殘骸雕紀錄。
    """
    path = _db_path()
    if not path.exists():
        return None
    out_dir = path.parent / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = out_dir / f"erhe_state.{stamp}.{tag}.db"
    shutil.copy2(path, dest)
    olds = sorted(out_dir.glob("erhe_state.*.db"))
    for stale in olds[:-BACKUP_KEEP]:
        stale.unlink(missing_ok=True)
    return dest


def list_backups() -> list[dict]:
    """現有的自動備份(新到舊):路徑、時間戳、標記、大小。"""
    out_dir = _db_path().parent / "backups"
    if not out_dir.exists():
        return []
    out = []
    for p in sorted(out_dir.glob("erhe_state.*.db"), reverse=True):
        parts = p.name.split(".")
        out.append({"path": p, "stamp": parts[1] if len(parts) > 2 else "",
                    "tag": parts[2] if len(parts) > 3 else "", "size": p.stat().st_size})
    return out


# ── 選號的字串化(資料庫存 "5,12,18,23,31",空的存 NULL)──
def dump_picked(nums: list[int] | None) -> str | None:
    """把選號存成逗號字串;沒選號(填數量模式)回 None。"""
    if not nums:
        return None
    return ",".join(str(int(n)) for n in sorted(set(nums)))


def parse_picked(raw) -> list[int]:
    """把資料庫欄位讀回號碼清單;空值或格式壞掉都回空清單。"""
    if not raw:
        return []
    out = []
    for part in str(raw).split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return sorted(set(out))


# ── 寫入 / 讀取 ──────────────────────────────────────────
def add_round(account: str, game: str, draw_date: str, numbers: int, cars: int,
              hits: int | None, cost: float, payout_rate: float,
              mode: str = MULTI, picked: list[int] | None = None,
              issue: str | None = None) -> int:
    """新增一筆下注流水,回傳該筆 id。

    account   帳號(整個帳號共用一個損益池)
    game      遊戲代號(lotto539 / fantasy5 / marksix)
    draw_date 下注日期 YYYY-MM-DD
    numbers   每局押幾顆;cars 車數
    hits      重幾顆;傳 None 代表「還沒開獎 / 待回填」
    cost        本局成本
    payout_rate 下注當時的「每車中獎可得」;回收 = 中幾顆 × 車數 × payout_rate
    mode        single(單顆)/ multi(多顆);兩者共用損益池,但紀錄與重置分開
    picked      實際圈選的號碼;用選號盤下注才有,填數量的話留 None

    待回填的紀錄一樣把成本計入累積損益(錢已經花出去了),
    等回填中獎顆數時再依當初的 payout_rate 把回收加回來。
    """
    if mode not in MODES:
        raise ValueError(f"未知的下注模式:{mode}")
    pending = hits is None
    hits_val = PENDING if pending else int(hits)
    payout = 0.0 if pending else int(hits) * int(cars) * float(payout_rate)
    net = payout - float(cost)
    picked_str = dump_picked(picked)
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO erhe_rounds "
            "(game_key, account, game, draw_date, numbers, cars, hits, cost, payout, "
            " payout_rate, net, cumulative, mode, picked, issue) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
            (account, account, game, str(draw_date), int(numbers), int(cars), hits_val,
             float(cost), payout, float(payout_rate), net, mode, picked_str,
             (str(issue).strip() or None) if issue else None),
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
             "cost", "payout", "payout_rate", "net", "cumulative", "mode", "picked",
             "issue"]


def load_rounds(account: str, mode: str | None = None) -> list[dict]:
    """該帳號的下注流水(依下注日期、寫入順序);pending 欄標示是否待回填。

    mode 傳 single / multi 只取該模式的紀錄,None(預設)則兩種都取。

    **指定 mode 時,cumulative 會就地重算成「該下法自己的累積」**,
    這樣單顆頁看到的累積就只含單顆的盈虧,追虧損的車數才不會被另一種下法帶偏。
    資料庫裡存的仍是整個帳號共用池的值(不指定 mode 時回傳的就是它)。
    """
    where, params = _mode_clause(mode)
    with _conn() as c:
        rows = c.execute(
            f"SELECT {', '.join(_ROW_COLS)} FROM erhe_rounds "
            f"WHERE account = ?{where} ORDER BY draw_date, id",
            (account, *params),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(zip(_ROW_COLS, r))
        d["pending"] = int(d["hits"] or 0) < 0
        d["mode"] = d["mode"] or MULTI
        d["picked"] = parse_picked(d.get("picked"))
        out.append(d)
    if mode is not None:
        running = 0.0
        for d in out:
            running += float(d["net"] or 0.0)
            d["cumulative"] = running
    return out


def pending_rounds(account: str, mode: str | None = None) -> list[dict]:
    """尚未回填中獎顆數的紀錄(待對獎清單)。"""
    return [r for r in load_rounds(account, mode) if r["pending"]]


def current_cumulative(account: str, mode: str | None = None) -> float:
    """目前累積損益(無紀錄回 0)。

    mode 傳 single / multi 則只算該下法自己的累積 —— 兩種下法的追虧損進程
    各自獨立,建議車數才不會被另一種的盈虧帶偏。
    """
    if mode is not None:
        return totals(account, mode)["net"]
    with _conn() as c:
        row = c.execute(
            "SELECT cumulative FROM erhe_rounds WHERE account = ? "
            "ORDER BY draw_date DESC, id DESC LIMIT 1",
            (account,),
        ).fetchone()
    return float(row[0]) if row else 0.0


def totals(account: str, mode: str | None = None) -> dict:
    """該帳號的合計:總成本、總回收、總損益、局數、中獎局數。

    mode 傳 single / multi 則只算該模式(用來顯示各自的小計)。
    """
    where, params = _mode_clause(mode)
    with _conn() as c:
        row = c.execute(
            "SELECT COALESCE(SUM(cost),0), COALESCE(SUM(payout),0), "
            "       COALESCE(SUM(net),0), COUNT(*), "
            "       COALESCE(SUM(CASE WHEN hits > 0 THEN 1 ELSE 0 END),0), "
            "       COALESCE(SUM(CASE WHEN hits < 0 THEN 1 ELSE 0 END),0) "
            f"FROM erhe_rounds WHERE account = ?{where}",
            (account, *params),
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


def totals_by_game(account: str, mode: str | None = None) -> dict[str, dict]:
    """依遊戲拆開的合計(給「哪一款賺賠最多」用)。"""
    where, params = _mode_clause(mode)
    with _conn() as c:
        rows = c.execute(
            "SELECT game, COALESCE(SUM(cost),0), COALESCE(SUM(payout),0), "
            "       COALESCE(SUM(net),0), COUNT(*), "
            "       COALESCE(SUM(CASE WHEN hits > 0 THEN 1 ELSE 0 END),0), "
            "       COALESCE(SUM(CASE WHEN hits < 0 THEN 1 ELSE 0 END),0) "
            f"FROM erhe_rounds WHERE account = ?{where} GROUP BY game",
            (account, *params),
        ).fetchall()
    return {
        r[0]: {"cost": float(r[1]), "payout": float(r[2]), "net": float(r[3]),
               "rounds": int(r[4]), "wins": int(r[5]), "pending": int(r[6])}
        for r in rows
    }


def totals_by_date(account: str, mode: str | None = None) -> list[dict]:
    """依下注日期彙總的流水(同一天三款一起看)。"""
    where, params = _mode_clause(mode)
    with _conn() as c:
        rows = c.execute(
            "SELECT draw_date, COUNT(*), COALESCE(SUM(cost),0), "
            "       COALESCE(SUM(payout),0), COALESCE(SUM(net),0), MAX(cumulative) "
            f"FROM erhe_rounds WHERE account = ?{where} "
            "GROUP BY draw_date ORDER BY draw_date",
            (account, *params),
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


def undo_last_round(account: str, mode: str | None = None) -> bool:
    """撤銷「最後輸入」的那一筆(不是最後日期的那筆);無紀錄回 False。

    mode 傳 single / multi 則只撤銷該模式最後輸入的那筆。
    """
    where, params = _mode_clause(mode)
    with _conn() as c:
        row = c.execute(
            f"SELECT id FROM erhe_rounds WHERE account = ?{where} ORDER BY id DESC LIMIT 1",
            (account, *params),
        ).fetchone()
        if row is None:
            return False
        c.execute("DELETE FROM erhe_rounds WHERE id = ?", (row[0],))
        _recompute(c, account)
    return True


def reset(account: str, mode: str | None = None) -> int:
    """清除該帳號的下注流水,回傳刪掉幾筆。

    mode 傳 single / multi 只清該模式,None 則清該帳號全部。
    **刪除前一定先整份備份**(data/backups/),誤刪時可直接還原檔案。
    """
    where, params = _mode_clause(mode)
    backup(f"reset-{mode or 'all'}-{account or 'anon'}")
    with _conn() as c:
        cur = c.execute(
            f"DELETE FROM erhe_rounds WHERE account = ?{where}", (account, *params))
        n = cur.rowcount
        _recompute(c, account)      # 只清一種模式時,剩下那種的累積要重排
    return int(n)


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


# ── 策略預測(不分帳號:系統依固定 seed 產生的客觀紀錄)──────
_PRED_COLS = ["id", "game", "target_issue", "target_date", "strategy",
              "numbers", "created_at"]


def add_predictions(game: str, target_issue: str, rows: dict[str, list[int]],
                    target_date: str | None = None) -> int:
    """存下某一期各策略的預測號碼,回傳實際新增的筆數。

    target_issue 是這一期的識別(期號;沒有期號的款用日期字串)。
    rows 形如 {"hot": [5,12,...], "cold": [...]}。
    同一期同一策略已經存過就跳過(不覆蓋)—— 預測一旦寫下就不該再改,
    否則「事前預測」的意義就沒了。
    """
    added = 0
    with _conn() as c:
        for strategy, nums in rows.items():
            if not nums:
                continue
            cur = c.execute(
                "INSERT OR IGNORE INTO predictions "
                "(game, target_issue, target_date, strategy, numbers) "
                "VALUES (?, ?, ?, ?, ?)",
                (game, str(target_issue), (target_date or None), strategy,
                 dump_picked(nums)),
            )
            added += cur.rowcount or 0
    return added


def load_predictions(game: str | None = None,
                     target_issue: str | None = None) -> list[dict]:
    """讀預測紀錄(新的期在前);numbers 已轉回號碼清單。"""
    where, params = [], []
    if game:
        where.append("game = ?")
        params.append(game)
    if target_issue:
        where.append("target_issue = ?")
        params.append(str(target_issue))
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    with _conn() as c:
        rows = c.execute(
            f"SELECT {', '.join(_PRED_COLS)} FROM predictions{clause} "
            "ORDER BY target_issue DESC, strategy",
            params,
        ).fetchall()
    out = []
    for r in rows:
        d = dict(zip(_PRED_COLS, r))
        d["numbers"] = parse_picked(d["numbers"])
        out.append(d)
    return out


def prediction_issues(game: str) -> list[str]:
    """該遊戲有預測紀錄的期別(新到舊)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT DISTINCT target_issue FROM predictions WHERE game = ? "
            "ORDER BY target_issue DESC", (game,),
        ).fetchall()
    return [r[0] for r in rows]


def delete_predictions(game: str, target_issue: str) -> int:
    """刪掉某一期的全部預測(輸錯期別時用);回傳刪除筆數。"""
    with _conn() as c:
        cur = c.execute(
            "DELETE FROM predictions WHERE game = ? AND target_issue = ?",
            (game, str(target_issue)),
        )
        return cur.rowcount or 0
