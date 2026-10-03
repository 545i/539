"""快速上傳 1800碰 自訂分柱:`20_29(去除24) / 30_39 / 其他100`。

前兩行是使用者指定的柱(起訖範圍,可去除號碼),「其他」= 剩下全部號碼(含被去除的)。
前兩行合計最多 19 顆;沒去除時 10+10=20 顆 → 錯誤碼 pillar_exclude_required,
前端據此彈窗要求使用者指定去除號碼。
"""
import pytest

from backend import edition_store, group_store, settle
from backend.data import get_game
from backend.routers import importer


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(group_store, "_db_path", lambda: tmp_path / "group.db")
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")
    g = get_game("lotto539")
    odds = edition_store.get_odds(1, "lotto539")
    return g, odds


def _parse(env, text):
    g, odds = env
    return importer.parse(text, g, odds)


def test_custom_pillars_with_exclusion(env):
    items, errors = _parse(env, "20_29(去除24)\n30_39\n其他100")
    assert errors == []
    assert len(items) == 1
    it = items[0]
    assert it.mode == "pillar1800"
    p1, p2, p3 = it.pillars
    assert p1 == [20, 21, 22, 23, 25, 26, 27, 28, 29]
    assert p2 == list(range(30, 40))
    assert p3 == list(range(1, 20)) + [24]
    assert it.bets_count == 1800
    assert it.units == 1
    _, odds = env
    assert it.cost == 1800 * float(odds["bet_cost"])


def test_fullwidth_paren_and_exclude_synonym(env):
    items, errors = _parse(env, "20_29（排除24）\n30_39\n其他100")
    assert errors == []
    assert 24 not in items[0].pillars[0]
    assert 24 in items[0].pillars[2]


def test_twenty_balls_requires_exclusion(env):
    items, errors = _parse(env, "20_29\n30_39\n其他100")
    assert items == []
    assert len(errors) == 1
    e = errors[0]
    assert e["code"] == "pillar_exclude_required"
    assert e["pillar_count"] == 20
    # 給前端彈窗用:兩行柱各自的行號與號碼
    assert [p["numbers"] for p in e["pillar_lines"]] == [list(range(20, 30)), list(range(30, 40))]
    assert [p["line_no"] for p in e["pillar_lines"]] == [1, 2]


def test_legacy_standard_format_unchanged(env):
    """舊格式 10_18 / 20_29 / 其他400 = 標準三柱,不存自訂柱(結算走固定分柱)。"""
    items, errors = _parse(env, "10_18\n20_29\n其他400")
    assert errors == []
    assert items[0].pillars == []
    assert items[0].units == 4
    assert items[0].bets_count == 4 * 1800


def test_exclusion_not_in_range_rejected(env):
    items, errors = _parse(env, "20_29(去除35)\n30_39\n其他100")
    assert items == []
    assert "35" in errors[0]["message"]


def test_overlapping_pillars_rejected(env):
    items, errors = _parse(env, "20_29(去除24)\n25_34\n其他100")
    assert items == []
    assert "重疊" in errors[0]["message"]


def test_record_carries_pillars_and_settles_with_them(env):
    g, _ = env
    items, _ = _parse(env, "20_29(去除24)\n30_39\n其他100")
    rec = importer.to_record(items[0], g, "2037-01-01", "")
    assert rec["pillars"] == items[0].pillars
    # 開 24、30、31、5、6:第一柱(去除24)沒中 → 斷柱
    out = settle.settle(rec, [24, 30, 31, 5, 6], g)
    assert out["payout"] == 0
    # 開 20、30、31、5、24:第一柱 1、第二柱 2、其他 2(5、24)→ 4 碰
    out = settle.settle(rec, [20, 30, 31, 5, 24], g)
    assert out["pillarDist"] == "1 × 2 × 2"


def test_recost_with_pillars(env):
    g, odds = env
    p1 = [20, 21, 22, 23, 25, 26, 27, 28, 29]
    p2 = list(range(30, 40))
    p3 = list(range(1, 20)) + [24]
    it = importer._recost(g, odds, "pillar1800", [], 2, 0, pillars=[p1, p2, p3])
    assert it.pillars == [p1, p2, p3]
    assert it.bets_count == 3600
    assert it.cost == 1800 * float(odds["bet_cost"]) * 2


def test_recost_rejects_twenty_ball_pillars(env):
    g, odds = env
    with pytest.raises(ValueError):
        importer._recost(g, odds, "pillar1800", [], 1, 0,
                         pillars=[list(range(20, 30)), list(range(30, 40)), list(range(1, 20))])
