"""單顆 / 多顆分流(core.storage 的 mode 欄)測試。

重點:兩種下法**共用同一個損益池**(累積損益連續),但**紀錄與清除各自獨立** ——
清單顆不能動到多顆,而且清除前一定要有備份。
"""
import sqlite3

import pytest

from core import storage


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "erhe_state.db"
    monkeypatch.setattr(storage, "_db_path", lambda: path)
    return path


def _add(acct="u", game="lotto539", date="2026-08-01", n=5, cars=3, hits=0,
         cost=1000.0, rate=21200.0, mode=storage.MULTI):
    return storage.add_round(acct, game, date, n, cars, hits, cost, rate, mode=mode)


def test_mode_defaults_to_multi(db):
    _add()
    assert storage.load_rounds("u")[0]["mode"] == storage.MULTI


def test_rounds_split_by_mode(db):
    _add(date="2026-08-01", mode=storage.SINGLE, n=1, cost=1000.0)
    _add(date="2026-08-02", mode=storage.MULTI, cost=2000.0)
    assert len(storage.load_rounds("u")) == 2
    single = storage.load_rounds("u", storage.SINGLE)
    multi = storage.load_rounds("u", storage.MULTI)
    assert [r["cost"] for r in single] == [1000.0]
    assert [r["cost"] for r in multi] == [2000.0]


def test_totals_per_mode_and_combined(db):
    _add(mode=storage.SINGLE, n=1, cost=1000.0, hits=0)
    _add(mode=storage.MULTI, cost=3000.0, hits=0)
    assert storage.totals("u", storage.SINGLE)["cost"] == 1000.0
    assert storage.totals("u", storage.MULTI)["cost"] == 3000.0
    assert storage.totals("u")["cost"] == 4000.0          # 不指定 = 合計


def test_cumulative_is_shared_across_modes(db):
    """損益池共用:累積損益要把兩種下法一起累加。"""
    _add(date="2026-08-01", mode=storage.SINGLE, n=1, cost=1000.0)
    _add(date="2026-08-02", mode=storage.MULTI, cost=2000.0)
    rows = storage.load_rounds("u")
    assert [r["cumulative"] for r in rows] == [-1000.0, -3000.0]
    assert storage.current_cumulative("u") == -3000.0


def test_reset_one_mode_keeps_the_other(db):
    _add(date="2026-08-01", mode=storage.SINGLE, n=1, cost=1000.0)
    _add(date="2026-08-02", mode=storage.MULTI, cost=2000.0)
    n = storage.reset("u", storage.SINGLE)
    assert n == 1
    left = storage.load_rounds("u")
    assert len(left) == 1 and left[0]["mode"] == storage.MULTI
    assert left[0]["cumulative"] == -2000.0        # 剩下的要重新累加


def test_reset_all_modes(db):
    _add(mode=storage.SINGLE, n=1)
    _add(mode=storage.MULTI)
    assert storage.reset("u") == 2
    assert storage.load_rounds("u") == []


def test_reset_backs_up_first(db):
    """清除前一定要留下可還原的備份 —— 這是誤刪事故後補的保護。"""
    _add(mode=storage.SINGLE, n=1, cost=1234.0)
    assert storage.list_backups() == []
    storage.reset("u", storage.SINGLE)
    baks = storage.list_backups()
    assert len(baks) == 1 and "reset-single" in baks[0]["tag"]
    # 備份檔真的能開,而且裡面資料還在
    conn = sqlite3.connect(str(baks[0]["path"]))
    n, cost = conn.execute(
        "SELECT COUNT(*), SUM(cost) FROM erhe_rounds WHERE account='u'").fetchone()
    assert n == 1 and cost == 1234.0


def test_backup_keeps_only_recent(db, monkeypatch):
    monkeypatch.setattr(storage, "BACKUP_KEEP", 3)
    _add()
    for i in range(6):
        storage.backup(f"t{i}")
    assert len(storage.list_backups()) == 3


def test_undo_is_per_mode(db):
    _add(date="2026-08-01", mode=storage.SINGLE, n=1, cost=1000.0)
    _add(date="2026-08-02", mode=storage.MULTI, cost=2000.0)
    assert storage.undo_last_round("u", storage.SINGLE) is True
    left = storage.load_rounds("u")
    assert len(left) == 1 and left[0]["mode"] == storage.MULTI
    assert storage.undo_last_round("u", storage.SINGLE) is False   # 該模式已空


def test_pending_and_by_game_respect_mode(db):
    _add(date="2026-08-01", mode=storage.SINGLE, n=1, hits=None)
    _add(date="2026-08-02", mode=storage.MULTI, game="marksix", hits=None)
    assert len(storage.pending_rounds("u", storage.SINGLE)) == 1
    assert set(storage.totals_by_game("u", storage.MULTI)) == {"marksix"}
    assert len(storage.totals_by_date("u", storage.SINGLE)) == 1


def test_unknown_mode_rejected(db):
    with pytest.raises(ValueError, match="未知的下注模式"):
        _add(mode="bogus")
    with pytest.raises(ValueError, match="未知的下注模式"):
        storage.load_rounds("u", "bogus")


def test_migration_backfills_mode_from_numbers(db):
    """舊資料庫沒有 mode 欄:押 1 顆視為單顆,其餘視為多顆。"""
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE erhe_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT, game_key TEXT NOT NULL,
            ts TEXT, numbers INTEGER NOT NULL DEFAULT 5, cars INTEGER NOT NULL,
            hits INTEGER NOT NULL, net REAL NOT NULL, cumulative REAL NOT NULL,
            account TEXT, game TEXT, draw_date TEXT, cost REAL, payout REAL,
            payout_rate REAL);
        CREATE TABLE erhe_settings (game_key TEXT NOT NULL, key TEXT NOT NULL,
            value REAL NOT NULL, PRIMARY KEY (game_key, key));
        INSERT INTO erhe_rounds (game_key, account, game, draw_date, numbers, cars,
            hits, net, cumulative, cost, payout, payout_rate)
        VALUES ('u','u','lotto539','2026-08-01',1,50,0,-137750,-137750,137750,0,21200),
               ('u','u','lotto539','2026-08-02',5,3,0,-41325,-179075,41325,0,21200);
    """)
    conn.commit()
    conn.close()

    rows = storage.load_rounds("u")
    assert [r["mode"] for r in rows] == [storage.SINGLE, storage.MULTI]
    assert db.with_name(db.name + ".bak_v2").exists()      # 遷移前有備份
