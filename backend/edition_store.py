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

from core import combo, combo9000
from core.games import get as game_by_key

# 連碰星數(與 core.combo 一致)
STARS = combo.STARS

# 全部盤口欄位名(get/set 都以這份為準)。
# 二合成本以「每注基礎 pair_bet_cost」為單一真相(可存/可改);每車成本 cost_per_car
# 一律**導出** = pair_bet_cost × (num_max-1),所以不在 FIELDS 裡(不直接存/改),但
# get_odds / get_odds_detail 仍會回它,給下游(GroupBetTab / settle / erhe)照舊使用。
FIELDS: tuple[str, ...] = (
    "pair_bet_cost", "win_payout", "bet_cost", "bet_prize",
    *(f"combo_cost{k}" for k in STARS),
    *(f"combo_prize{k}" for k in STARS),
    "combo9000_prize",   # 9000碰專屬派彩(每碰),跟星碰四星分開
)


def _notes_per_car(game_key: str) -> int:
    """二合一車的注數 = num_max − 1(拖 1 膽配其餘號碼);539/天天樂 38、六合彩 48。"""
    return max(1, game_by_key(game_key).num_max - 1)


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
    """某遊戲的出廠盤口:二合 / 1800碰 讀 GameConfig,連碰讀 core.combo 現行值。

    二合的預設「每注基礎」= 出廠每車成本 ÷ 注數(2755 ÷ 38 = 72.5、六合彩 3528 ÷ 48
    = 73.5),讓「基礎 × 注數」還原成原本的每車成本,升級後金額不變。
    """
    g = game_by_key(game_key)
    out = {
        "pair_bet_cost": float(g.default_cost_per_car) / _notes_per_car(game_key),
        "win_payout": float(g.default_win_payout),
        "bet_cost": float(g.default_bet_cost),
        "bet_prize": float(g.default_bet_prize),
    }
    for k in STARS:
        # market_cost/prize 會吃到後台 star-cost 改過的值 —— 第一版沿用現況
        out[f"combo_cost{k}"] = float(combo.market_cost(k, combo.MARKET_COST[k]))
        out[f"combo_prize{k}"] = float(combo.market_prize(k, combo.MARKET_PRIZE[k]))
    out["combo9000_prize"] = float(combo9000.PRIZE_PER_BET)   # 9000碰專屬派彩(預設 800,000)
    return out


def _stored(eid: int, game_key: str) -> dict:
    with _conn() as c:
        rows = c.execute(
            "SELECT field, value FROM edition_odds WHERE eid = ? AND game_key = ?",
            (int(eid), game_key),
        ).fetchall()
    return {r[0]: float(r[1]) for r in rows}


def _base_of(raw: dict, defaults: dict, notes: int) -> tuple[float, bool]:
    """二合每注基礎 + 是否自訂:優先讀新欄位 pair_bet_cost,退而讀舊 cost_per_car
    (每車 ÷ 注數換算),都沒有就吃預設。回 (base, custom)。"""
    if "pair_bet_cost" in raw:
        return raw["pair_bet_cost"], True
    if "cost_per_car" in raw:            # 舊資料只存過每車成本 → 換算回每注基礎
        return raw["cost_per_car"] / notes, True
    return defaults["pair_bet_cost"], False


def get_odds(eid: int, game_key: str) -> dict:
    """某版某遊戲目前生效的整套盤口(覆寫疊在預設上,一定回滿全部欄位)。

    二合每車成本 cost_per_car 一律導出 = 每注基礎 × 注數,額外附在回傳裡供下游使用。
    """
    notes = _notes_per_car(game_key)
    out = _defaults(game_key)
    raw = _stored(eid, game_key)
    out.update({k: v for k, v in raw.items() if k in FIELDS})
    base, _ = _base_of(raw, out, notes)
    out["pair_bet_cost"] = base
    out["cost_per_car"] = base * notes          # 衍生:給 settle / erhe / GroupBetTab
    return out


def get_odds_detail(eid: int, game_key: str) -> dict:
    """設定頁用:每欄位回 {value, custom}(custom=是否有自訂,否則吃預設)。

    額外回衍生唯讀的 cost_per_car(= 每注基礎 × 注數),讓 GroupBetTab 等消費者照舊
    讀得到每車成本;它不在 FIELDS(不可直接改),改基礎即連動。
    """
    notes = _notes_per_car(game_key)
    defaults = _defaults(game_key)
    stored = _stored(eid, game_key)
    out = {k: {"value": stored.get(k, defaults[k]), "custom": k in stored}
           for k in FIELDS}
    base, custom = _base_of(stored, defaults, notes)
    out["pair_bet_cost"] = {"value": base, "custom": custom}
    out["cost_per_car"] = {"value": base * notes, "custom": custom}   # 衍生唯讀
    return out


def set_odds(eid: int, game_key: str, values: dict) -> dict:
    """寫入某版某遊戲的盤口(只給的欄位才改);成本 / 派彩要 > 0。

    向後相容:若傳入舊的 cost_per_car(每車成本),自動換算成 pair_bet_cost
    (每注基礎 = 每車 ÷ 注數)—— 二合成本只存基礎這一個真相。
    """
    values = dict(values or {})
    if "cost_per_car" in values and "pair_bet_cost" not in values:
        values["pair_bet_cost"] = float(values.pop("cost_per_car")) / _notes_per_car(game_key)
    rows = []
    for k, v in values.items():
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
