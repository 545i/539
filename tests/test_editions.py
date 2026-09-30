"""下注「版」設定(backend.edition_store):版清單、版×遊戲的整套盤口與回退。"""
from __future__ import annotations

import pytest

from backend import edition_store
from core.games import LOTTO539 as G


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")


def test_default_edition():
    eds = edition_store.list_editions()
    real = [e for e in eds if not e["simulated"]]
    assert real == [{"eid": 1, "name": "第一版", "simulated": False}]
    # 內建「模擬」版一定存在(不計總損益)
    assert any(e["simulated"] and e["name"] == "模擬" for e in eds)


def test_add_rename_delete():
    e2 = edition_store.add_edition("第二版")
    assert e2["name"] == "第二版"
    eid = e2["eid"]
    assert edition_store.rename_edition(eid, "夜間版")
    assert next(x for x in edition_store.list_editions() if x["eid"] == eid)["name"] == "夜間版"
    assert edition_store.delete_edition(eid)
    assert all(x["eid"] != eid for x in edition_store.list_editions())
    with pytest.raises(ValueError):
        edition_store.delete_edition(1)   # 第一版不能刪


def test_odds_defaults_match_gameconfig():
    o = edition_store.get_odds(1, G.key)
    assert o["cost_per_car"] == G.default_cost_per_car   # 2755
    assert o["win_payout"] == G.default_win_payout       # 21200
    assert o["bet_cost"] == G.default_bet_cost
    assert o["bet_prize"] == G.default_bet_prize
    # 全部欄位都回滿
    for f in edition_store.FIELDS:
        assert f in o


def test_set_odds_per_edition_game_independent():
    e2 = edition_store.add_edition("第二版")["eid"]
    edition_store.set_odds(e2, G.key, {"cost_per_car": 3000, "win_payout": 25000})
    o2 = edition_store.get_odds(e2, G.key)
    assert o2["cost_per_car"] == 3000 and o2["win_payout"] == 25000
    # 第一版不受影響
    o1 = edition_store.get_odds(1, G.key)
    assert o1["cost_per_car"] == G.default_cost_per_car
    # 別款遊戲不受影響(版×遊戲獨立)
    assert edition_store.get_odds(e2, "fantasy5")["cost_per_car"] != 3000

    edition_store.reset_odds(e2, G.key)
    assert edition_store.get_odds(e2, G.key)["cost_per_car"] == G.default_cost_per_car


def test_set_odds_rejects_nonpositive():
    with pytest.raises(ValueError):
        edition_store.set_odds(1, G.key, {"cost_per_car": 0})


def test_pair_bet_cost_derives_cost_per_car():
    """二合每注基礎 pair_bet_cost 是單一真相;cost_per_car 導出 = 基礎 × (num_max-1)。"""
    notes = G.num_max - 1               # lotto539 → 38
    o = edition_store.get_odds(1, G.key)
    assert o["pair_bet_cost"] == G.default_cost_per_car / notes   # 預設 72.5
    assert o["cost_per_car"] == o["pair_bet_cost"] * notes        # 2755
    e2 = edition_store.add_edition("基礎版")["eid"]
    edition_store.set_odds(e2, G.key, {"pair_bet_cost": 80})
    o2 = edition_store.get_odds(e2, G.key)
    assert o2["pair_bet_cost"] == 80 and o2["cost_per_car"] == 80 * notes
    det = edition_store.get_odds_detail(e2, G.key)
    assert det["pair_bet_cost"]["value"] == 80 and det["pair_bet_cost"]["custom"] is True
    assert det["cost_per_car"]["value"] == 80 * notes             # 衍生唯讀


def _cur(eid=1, since=""):
    return next(v["shares"] for v in edition_store.get_share_versions(eid) if v["since"] == since)


def test_shares_default_self_100():
    assert edition_store.get_share_versions(1) == [
        {"since": "", "shares": [{"name": "本人", "pct": 100.0, "self": True}]}]


def test_shares_conserve_to_100():
    edition_store.set_shares(1, [{"name": "阿閔", "pct": 33.33}, {"name": "阿姨", "pct": 33.33}])
    out = _cur()
    assert [s["name"] for s in out] == ["本人", "阿閔", "阿姨"]
    assert out[0]["pct"] == 33.34
    assert round(sum(s["pct"] for s in out) * 100) == 10000
    edition_store.set_shares(1, [{"name": "A", "pct": 100}])
    assert _cur()[0]["pct"] == 0
    edition_store.set_shares(1, [])
    assert _cur()[0]["pct"] == 100


def test_shares_versions_by_since():
    # 週三才開始分:最早起仍是本人 100%
    vs = edition_store.set_shares(1, [{"name": "阿閔", "pct": 40}], since="2026-09-30")
    assert [v["since"] for v in vs] == ["", "2026-09-30"]
    assert vs[0]["shares"][0]["pct"] == 100
    assert vs[1]["shares"][0]["pct"] == 60
    vs = edition_store.delete_share_version(1, "2026-09-30")
    assert [v["since"] for v in vs] == [""]
    with pytest.raises(ValueError):
        edition_store.set_shares(1, [], since="9/30")


def test_shares_migrate_old_table(tmp_path):
    import sqlite3
    db = tmp_path / "edition.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE edition_shares (eid INTEGER, pos INTEGER, name TEXT, bps INTEGER, PRIMARY KEY (eid, pos))")
    con.execute("INSERT INTO edition_shares VALUES (1, 0, 'A', 2500)")
    con.commit(); con.close()
    assert _cur()[1] == {"name": "A", "pct": 25.0, "self": False}


@pytest.mark.parametrize("others", [
    [{"name": "A", "pct": 60}, {"name": "B", "pct": 40.01}],   # 合計超過 100
    [{"name": "A", "pct": 0}],                                  # 0%
    [{"name": "A", "pct": -5}],
    [{"name": "A", "pct": 1.234}],                              # 超過兩位小數
    [{"name": "本人", "pct": 10}],
    [{"name": "A", "pct": 10}, {"name": "A", "pct": 10}],
    [{"name": " ", "pct": 10}],
])
def test_shares_reject(others):
    edition_store.set_shares(1, [{"name": "keep", "pct": 20}])
    with pytest.raises(ValueError):
        edition_store.set_shares(1, others)
    assert _cur()[1] == {"name": "keep", "pct": 20.0, "self": False}


def test_delete_edition_clears_shares():
    eid = edition_store.add_edition("X")["eid"]
    edition_store.set_shares(eid, [{"name": "A", "pct": 50}], since="2026-09-30")
    edition_store.delete_edition(eid)
    assert eid not in edition_store.all_shares()
