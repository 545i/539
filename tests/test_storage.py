"""SQLite 持久化 core.storage 測試(用臨時 DB,不碰正式檔)。

v2 資料模型:一個帳號一個損益池,三款遊戲串成同一條流水,
累積損益依 (下注日期, 寫入順序) 重算。
"""
import sqlite3

import pytest

from core import storage

COST_539 = 5 * 3 * 2755.0        # 押5顆 × 3車 × 每車2755
PAY_539 = 21200.0
COST_HK = 5 * 3 * 3528.0
PAY_HK = 28500.0


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "test_erhe.db"
    monkeypatch.setattr(storage, "_db_path", lambda: db)
    return db


def _bet(account="a", game="lotto539", date="2026-07-29", numbers=5, cars=3,
         hits=0, cost=COST_539, rate=PAY_539):
    return storage.add_round(account, game, date, numbers, cars, hits, cost, rate)


# ── 基本寫入 / 讀取 ──────────────────────────────────────
def test_add_and_load(temp_db):
    assert storage.current_cumulative("a") == 0.0
    _bet(hits=0)                      # 沒中 → 淨損 = −成本
    _bet(hits=1)                      # 中1顆 → 回收 = 1 × 3車 × 21200
    rows = storage.load_rounds("a")
    assert len(rows) == 2
    assert rows[0]["net"] == -COST_539
    assert rows[1]["payout"] == 1 * 3 * PAY_539
    assert rows[1]["net"] == 3 * PAY_539 - COST_539
    assert storage.current_cumulative("a") == rows[1]["cumulative"]
    assert storage.current_cumulative("a") == sum(r["net"] for r in rows)


def test_three_games_share_one_pool(temp_db):
    _bet(game="lotto539", hits=0, cost=COST_539, rate=PAY_539)
    _bet(game="fantasy5", hits=0, cost=COST_539, rate=PAY_539)
    _bet(game="marksix", hits=0, cost=COST_HK, rate=PAY_HK)
    rows = storage.load_rounds("a")
    assert len(rows) == 3
    assert [r["game"] for r in rows] == ["lotto539", "fantasy5", "marksix"]
    # 合併累積 = 三款成本相加(全部沒中)
    assert storage.current_cumulative("a") == pytest.approx(-(COST_539 * 2 + COST_HK))
    tot = storage.totals("a")
    assert tot["rounds"] == 3 and tot["wins"] == 0
    assert tot["cost"] == pytest.approx(COST_539 * 2 + COST_HK)
    assert tot["payout"] == 0.0


def test_accounts_isolated(temp_db):
    _bet(account="a", hits=0)
    _bet(account="b", hits=1)
    assert len(storage.load_rounds("a")) == 1
    assert len(storage.load_rounds("b")) == 1
    assert storage.current_cumulative("a") == -COST_539
    assert storage.current_cumulative("b") == 3 * PAY_539 - COST_539


# ── 日期流水:補登過去日期會排到正確位置 ───────────────────
def test_backdated_entry_reorders_cumulative(temp_db):
    _bet(date="2026-07-29", hits=0)              # 後輸入但日期較新
    _bet(date="2026-07-27", hits=1)              # 補登較早的一天
    rows = storage.load_rounds("a")
    assert [r["draw_date"] for r in rows] == ["2026-07-27", "2026-07-29"]
    # 累積依日期順序重算:先中獎那天,再槓龜那天
    assert rows[0]["cumulative"] == pytest.approx(3 * PAY_539 - COST_539)
    assert rows[1]["cumulative"] == pytest.approx(3 * PAY_539 - COST_539 * 2)
    assert storage.current_cumulative("a") == pytest.approx(rows[1]["cumulative"])


def test_totals_by_date_groups_three_games(temp_db):
    for g, cost, rate in (("lotto539", COST_539, PAY_539),
                          ("fantasy5", COST_539, PAY_539),
                          ("marksix", COST_HK, PAY_HK)):
        _bet(game=g, date="2026-07-29", hits=0, cost=cost, rate=rate)
    _bet(game="lotto539", date="2026-07-30", hits=1)
    daily = storage.totals_by_date("a")
    assert [d["draw_date"] for d in daily] == ["2026-07-29", "2026-07-30"]
    assert daily[0]["rounds"] == 3
    assert daily[0]["cost"] == pytest.approx(COST_539 * 2 + COST_HK)
    assert daily[1]["cumulative"] == pytest.approx(daily[0]["net"] + daily[1]["net"])


def test_totals_by_game(temp_db):
    _bet(game="marksix", hits=0, cost=COST_HK, rate=PAY_HK)
    _bet(game="marksix", hits=2, cost=COST_HK, rate=PAY_HK)
    _bet(game="lotto539", hits=0)
    by_game = storage.totals_by_game("a")
    assert by_game["marksix"]["rounds"] == 2 and by_game["marksix"]["wins"] == 1
    assert by_game["marksix"]["payout"] == pytest.approx(2 * 3 * PAY_HK)
    assert by_game["lotto539"]["rounds"] == 1


# ── 待回填(中獎顆數可後填)────────────────────────────────
def test_pending_counts_cost_only(temp_db):
    rid = _bet(hits=None)
    rows = storage.load_rounds("a")
    assert rows[0]["pending"] is True
    assert rows[0]["payout"] == 0.0
    assert rows[0]["net"] == -COST_539          # 錢已經花出去,先計成本
    tot = storage.totals("a")
    assert tot["pending"] == 1 and tot["settled"] == 0
    assert tot["win_rate"] == 0.0               # 沒有已對獎的局,不算勝率
    assert storage.pending_rounds("a")[0]["id"] == rid


def test_fill_pending_uses_original_odds(temp_db):
    rid = _bet(hits=None, rate=PAY_539)
    assert storage.update_round_result(rid, 1) is True
    row = storage.load_rounds("a")[0]
    assert row["pending"] is False
    assert row["hits"] == 1
    assert row["payout"] == pytest.approx(1 * 3 * PAY_539)   # 依當初的 payout_rate
    assert row["net"] == pytest.approx(3 * PAY_539 - COST_539)
    assert storage.totals("a")["wins"] == 1


def test_fill_pending_can_be_corrected(temp_db):
    rid = _bet(hits=2)
    storage.update_round_result(rid, 0)          # 對錯獎,改回 0 顆
    row = storage.load_rounds("a")[0]
    assert row["hits"] == 0 and row["payout"] == 0.0
    assert storage.current_cumulative("a") == -COST_539


def test_update_missing_round_returns_false(temp_db):
    assert storage.update_round_result(999, 1) is False
    assert storage.delete_round(999) is False
    assert storage.set_round_date(999, "2026-01-01") is False


# ── 撤銷 / 刪除 / 改日期 / 重置 ───────────────────────────
def test_undo_removes_last_written_row(temp_db):
    _bet(date="2026-07-29", hits=0)
    _bet(date="2026-07-20", hits=0)              # 較早日期但最後寫入
    assert storage.undo_last_round("a") is True
    rows = storage.load_rounds("a")
    assert len(rows) == 1 and rows[0]["draw_date"] == "2026-07-29"
    assert storage.current_cumulative("a") == -COST_539
    storage.undo_last_round("a")
    assert storage.undo_last_round("a") is False  # 空了


def test_delete_and_set_date_recompute(temp_db):
    r1 = _bet(date="2026-07-29", hits=0)
    _bet(date="2026-07-30", hits=1)
    storage.set_round_date(r1, "2026-08-01")     # 把第一筆挪到最後
    rows = storage.load_rounds("a")
    assert [r["draw_date"] for r in rows] == ["2026-07-30", "2026-08-01"]
    assert rows[1]["cumulative"] == pytest.approx(sum(r["net"] for r in rows))
    storage.delete_round(r1)
    rows = storage.load_rounds("a")
    assert len(rows) == 1
    assert rows[0]["cumulative"] == pytest.approx(rows[0]["net"])


def test_reset_only_current_account(temp_db):
    _bet(account="a", hits=0)
    _bet(account="b", hits=0)
    storage.reset("a")
    assert storage.load_rounds("a") == []
    assert storage.current_cumulative("a") == 0.0
    assert len(storage.load_rounds("b")) == 1


def test_latest_cumulatives_one_row_per_account(temp_db):
    _bet(account="a", game="lotto539", hits=0)
    _bet(account="a", game="marksix", hits=0, cost=COST_HK, rate=PAY_HK)
    _bet(account="b", hits=1)
    rows = {r["account"]: r for r in storage.latest_cumulatives()}
    assert set(rows) == {"a", "b"}
    assert rows["a"]["rounds"] == 2                       # 兩款併成一列
    assert rows["a"]["cumulative"] == pytest.approx(-(COST_539 + COST_HK))
    assert rows["b"]["cumulative"] == pytest.approx(3 * PAY_539 - COST_539)


# ── 設定(仍依「帳號::遊戲」分開)──────────────────────────
def test_settings_persist(temp_db):
    assert storage.get_setting("a::marksix", "cost_per_car", 3528) == 3528
    storage.set_setting("a::marksix", "cost_per_car", 3600)
    assert storage.get_setting("a::marksix", "cost_per_car", 3528) == 3600
    # 依帳號/遊戲分開
    assert storage.get_setting("a::lotto539", "cost_per_car", 2755) == 2755
    assert storage.get_setting("b::marksix", "cost_per_car", 3528) == 3528


def test_persists_across_connections(temp_db):
    _bet(hits=1)
    conn = sqlite3.connect(str(temp_db))
    n = conn.execute("SELECT COUNT(*) FROM erhe_rounds WHERE account='a'").fetchone()[0]
    conn.close()
    assert n == 1


# ── v1 → v2 遷移(舊的分池紀錄併成一條流水)────────────────
def _make_v1_db(path):
    """建一個 v1 結構的資料庫(game_key = 帳號::遊戲,沒有 v2 欄位)。"""
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE erhe_rounds (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "game_key TEXT NOT NULL, ts TEXT, numbers INTEGER NOT NULL DEFAULT 5, "
        "cars INTEGER NOT NULL, hits INTEGER NOT NULL, net REAL NOT NULL, "
        "cumulative REAL NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE erhe_settings (game_key TEXT NOT NULL, key TEXT NOT NULL, "
        "value REAL NOT NULL, PRIMARY KEY (game_key, key))"
    )
    conn.executemany(
        "INSERT INTO erhe_rounds (game_key, ts, numbers, cars, hits, net, cumulative) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("a::lotto539", "2026-07-20 10:00:00", 5, 3, 0, -41325.0, -41325.0),
            ("a::marksix", "2026-07-21 10:00:00", 5, 3, 0, -52920.0, -52920.0),
            ("a::lotto539", "2026-07-22 10:00:00", 5, 6, 1, 44550.0, 3225.0),
        ],
    )
    conn.commit()
    conn.close()


def test_v1_migration_merges_into_single_ledger(temp_db):
    _make_v1_db(temp_db)
    rows = storage.load_rounds("a")
    assert len(rows) == 3
    assert [r["game"] for r in rows] == ["lotto539", "marksix", "lotto539"]
    assert [r["draw_date"] for r in rows] == ["2026-07-20", "2026-07-21", "2026-07-22"]
    # 每局損益原封不動,但累積改成三款合併後依日期重算
    assert [r["net"] for r in rows] == [-41325.0, -52920.0, 44550.0]
    assert rows[-1]["cumulative"] == pytest.approx(-41325.0 - 52920.0 + 44550.0)
    assert storage.current_cumulative("a") == pytest.approx(-49695.0)


def test_v1_migration_backfills_cost_and_payout(temp_db):
    _make_v1_db(temp_db)
    rows = storage.load_rounds("a")
    for r in rows:
        # 回收 − 成本 必須等於原本的每局損益(拆欄位不能改變損益)
        assert r["payout"] - r["cost"] == pytest.approx(r["net"])
    assert rows[0]["cost"] == pytest.approx(5 * 3 * 2755.0)     # 539 預設盤口
    assert rows[1]["cost"] == pytest.approx(5 * 3 * 3528.0)     # 六合彩預設盤口


def test_v1_migration_backs_up_and_is_idempotent(temp_db):
    _make_v1_db(temp_db)
    storage.load_rounds("a")                       # 觸發遷移
    backup = temp_db.with_name(temp_db.name + ".bak_v1")
    assert backup.exists()                         # 遷移前有備份
    before = storage.load_rounds("a")
    storage.load_rounds("a")                       # 再跑一次不應重複處理
    assert storage.load_rounds("a") == before


def test_v1_migration_keeps_accounts_separate(temp_db):
    _make_v1_db(temp_db)
    conn = sqlite3.connect(str(temp_db))
    conn.execute(
        "INSERT INTO erhe_rounds (game_key, ts, numbers, cars, hits, net, cumulative) "
        "VALUES ('b::lotto539', '2026-07-20 10:00:00', 5, 3, 0, -41325.0, -41325.0)"
    )
    conn.commit()
    conn.close()
    assert len(storage.load_rounds("a")) == 3
    assert len(storage.load_rounds("b")) == 1
    assert storage.current_cumulative("b") == pytest.approx(-41325.0)
