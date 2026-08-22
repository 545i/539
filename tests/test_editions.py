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
    assert eds == [{"eid": 1, "name": "第一版"}]


def test_add_rename_delete():
    e2 = edition_store.add_edition("第二版")
    assert e2["eid"] == 2 and e2["name"] == "第二版"
    assert edition_store.rename_edition(2, "夜間版")
    assert edition_store.list_editions()[1]["name"] == "夜間版"
    assert edition_store.delete_edition(2)
    assert len(edition_store.list_editions()) == 1
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
