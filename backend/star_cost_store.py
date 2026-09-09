"""連碰星數盤口的持久化:每個星數一列 {每碰成本, 中一碰可得}。

core/combo.py 的 MARKET_COST / MARKET_PRIZE 是**出廠預設**,但組頭的價碼會變。
以前要改就得改程式再部署一次,所以這裡把它搬進 sqlite,後台改完立刻生效。

**這是全域設定,不是個人偏好**:同一個站上所有使用者用的是同一份成本,
不然試算、記帳、排行榜的損益就沒得比。所以表裡沒有 username 欄。

生效方式是「開站(以及每次寫入)時把設定灌進 core.combo 的覆寫層」——
見 apply_to_core()。core 不反過來讀資料庫,免得算式模組被綁上 sqlite。

資料庫檔放 data/star_cost.db(frozen 打包時放 exe 旁邊;*.db 已被 gitignore)。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

from core import combo

# 可設定的星數 —— 跟 core.combo 一致,後台不會冒出第四種星別
STARS = combo.STARS


def _db_path() -> Path:
    """資料庫路徑(frozen 時位於 exe 旁邊,否則專案 data/)。"""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "data" / "star_cost.db"


def _conn() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS star_costs (
            stars   INTEGER PRIMARY KEY,
            cost    REAL NOT NULL,
            prize   REAL NOT NULL,
            updated TEXT DEFAULT (datetime('now', 'localtime')),
            updated_by TEXT DEFAULT ''
        )
        """
    )
    return conn


def _stored() -> dict[int, dict]:
    """資料庫裡真的存過的那幾筆(沒存過的星數不會出現)。"""
    with _conn() as c:
        rows = c.execute(
            "SELECT stars, cost, prize, updated, updated_by FROM star_costs"
        ).fetchall()
    return {int(r[0]): {"cost": float(r[1]), "prize": float(r[2]),
                        "updated": r[3] or "", "updated_by": r[4] or ""}
            for r in rows}


def get_costs() -> dict[int, dict]:
    """目前生效的盤口:{星數: {cost, prize, updated, updated_by, custom}}。

    沒存過的星數回 core 的出廠預設(custom=False)—— 呼叫端永遠拿得到
    完整的三個星數,不必自己補洞。
    """
    stored = _stored()
    out: dict[int, dict] = {}
    for k in STARS:
        k = int(k)
        row = stored.get(k)
        if row is None:
            out[k] = {"cost": float(combo.MARKET_COST.get(k, 0.0)),
                      "prize": float(combo.MARKET_PRIZE.get(k, 0.0)),
                      "updated": "", "updated_by": "", "custom": False}
        else:
            out[k] = {**row, "custom": True}
    return out


def set_costs(costs: dict, updated_by: str = "") -> dict[int, dict]:
    """寫入(或更新)盤口,回傳寫完之後的完整設定。

    costs 形如 {3: {"cost": 63, "prize": 57000}, ...};只給部分星數就只改那幾個。
    成本 0 會讓返還率算出無限大、派彩 0 等於白買,所以兩者都要 > 0;
    星數不在 STARS 裡直接擋掉(打錯字不該偷偷寫進資料庫)。
    """
    rows = []
    for raw_k, v in (costs or {}).items():
        k = int(raw_k)
        if k not in STARS:
            raise ValueError(f"沒有這種星數:{k}(可設定的是 {list(STARS)})")
        cost = float(v["cost"] if isinstance(v, dict) else v[0])
        prize = float(v["prize"] if isinstance(v, dict) else v[1])
        if cost <= 0:
            raise ValueError(f"{combo.star_name(k)}的每碰成本要大於 0")
        if prize <= 0:
            raise ValueError(f"{combo.star_name(k)}的中一碰派彩要大於 0")
        rows.append((k, cost, prize, updated_by))

    with _conn() as c:
        c.executemany(
            """
            INSERT INTO star_costs (stars, cost, prize, updated, updated_by)
            VALUES (?, ?, ?, datetime('now', 'localtime'), ?)
            ON CONFLICT(stars) DO UPDATE SET
                cost = excluded.cost,
                prize = excluded.prize,
                updated = excluded.updated,
                updated_by = excluded.updated_by
            """,
            rows,
        )
    return get_costs()


def reset() -> dict[int, dict]:
    """清掉所有自訂,回到 core 的出廠預設。"""
    with _conn() as c:
        c.execute("DELETE FROM star_costs")
    return get_costs()


def apply_to_core() -> dict[int, dict]:
    """把目前的設定灌進 core.combo 的覆寫層 —— 之後所有試算都吃這份。

    開站時(backend/main.py 的 lifespan)呼叫一次,每次寫入後再呼叫一次。
    讀不到資料庫時**不擋啟動**:core 本來就有出廠預設,少了自訂值頂多是
    價碼舊一點,比整站起不來好。
    """
    try:
        current = get_costs()
    except Exception:       # noqa: BLE001 — 磁碟 / 資料庫壞掉不該讓整站起不來
        return {}
    combo.set_market_overrides(
        cost={k: v["cost"] for k, v in current.items()},
        prize={k: v["prize"] for k, v in current.items()},
    )
    return current
