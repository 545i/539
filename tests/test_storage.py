"""SQLite 持久化 core.storage 測試(用臨時 DB,不碰正式檔)。"""
import sqlite3

import pytest

from core import storage


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "test_erhe.db"
    monkeypatch.setattr(storage, "_db_path", lambda: db)
    return db


def test_add_and_load(temp_db):
    assert storage.current_cumulative("fantasy5") == 0.0
    storage.add_round("fantasy5", 3, 0, -41325, -41325)
    storage.add_round("fantasy5", 6, 1, 44550, 3225)
    rows = storage.load_rounds("fantasy5")
    assert len(rows) == 2
    assert rows[0]["cars"] == 3 and rows[1]["hits"] == 1
    assert storage.current_cumulative("fantasy5") == 3225.0


def test_games_separated(temp_db):
    storage.add_round("fantasy5", 3, 0, -41325, -41325)
    storage.add_round("lotto539", 5, 2, 1000, 1000)
    assert len(storage.load_rounds("fantasy5")) == 1
    assert len(storage.load_rounds("lotto539")) == 1
    assert storage.current_cumulative("fantasy5") == -41325.0
    assert storage.current_cumulative("lotto539") == 1000.0


def test_reset(temp_db):
    storage.add_round("fantasy5", 3, 0, -100, -100)
    storage.reset("fantasy5")
    assert storage.load_rounds("fantasy5") == []
    assert storage.current_cumulative("fantasy5") == 0.0


def test_persists_across_connections(temp_db):
    storage.add_round("fantasy5", 3, 1, 22275, 22275)
    # 直接用新連線讀,驗證真的寫入磁碟
    conn = sqlite3.connect(str(temp_db))
    n = conn.execute("SELECT COUNT(*) FROM erhe_rounds WHERE game_key='fantasy5'").fetchone()[0]
    conn.close()
    assert n == 1
