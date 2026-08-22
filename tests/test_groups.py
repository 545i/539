"""二合下注「組」設定(backend.group_store)與快速上傳歸組 / 連碰補足。

group_store 的 DB 用 tmp_path 隔離;importer 讀組設定也走同一份,所以測試裡
改組設定(停用某組)就能驗到快速上傳的行為。
"""
from __future__ import annotations

import pytest

from backend import edition_store, group_store
from backend.routers import importer
from core.games import LOTTO539 as G


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    monkeypatch.setattr(group_store, "_db_path", lambda: tmp_path / "group.db")
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")


def _odds():
    """第一版今彩539 的預設盤口(= GameConfig,快速上傳成本計算用)。"""
    return edition_store.get_odds(1, G.key)


def test_defaults():
    groups = group_store.get_groups()
    assert [g["gid"] for g in groups] == [1, 2]
    assert groups[0]["mode"] == "single" and groups[0]["ball_count"] == 2
    assert groups[1]["mode"] == "multi" and groups[1]["ball_count"] == 3
    assert all(g["enabled"] for g in groups)


def test_set_and_reset():
    group_store.set_groups([{"gid": 1, "ball_count": 4, "enabled": False}], "tester")
    g1 = group_store.get_group(1)
    assert g1["ball_count"] == 4 and g1["enabled"] is False
    assert group_store.get_group(2)["ball_count"] == 3  # 只改到的那組
    assert group_store.mode_enabled("single") is False
    assert group_store.mode_enabled("multi") is True
    assert group_store.mode_enabled("combo") is True    # 非組的一律當啟用

    group_store.reset()
    assert group_store.get_group(1)["ball_count"] == 2


def test_set_rejects_bad():
    with pytest.raises(ValueError):
        group_store.set_groups([{"gid": 9, "ball_count": 2}], "x")
    with pytest.raises(ValueError):
        group_store.set_groups([{"gid": 1, "ball_count": 0}], "x")


# ── 快速上傳:依序歸組 ────────────────────────────────────
def test_parse_routes_by_order():
    text = "21_24x20車\n03_11_35x10車"
    items, errors = importer.parse(text, G, _odds())
    assert errors == []
    assert [it.mode for it in items] == ["single", "multi"]
    assert items[0].balls == [21, 24] and items[1].balls == [3, 11, 35]


def test_parse_third_erhe_line_errors():
    text = "01_02x5車\n03_04x5車\n05_06x5車"
    items, errors = importer.parse(text, G, _odds())
    assert [it.mode for it in items] == ["single", "multi"]
    assert len(errors) == 1 and "超過組數" in errors[0]["message"]


def test_parse_disabled_group_errors():
    group_store.set_groups([{"gid": 2, "enabled": False}], "x")
    text = "21_24x20車\n03_11_35x10車"
    items, errors = importer.parse(text, G, _odds())
    assert [it.mode for it in items] == ["single"]   # 2組停用 → 第二行變錯誤
    assert len(errors) == 1 and "停用" in errors[0]["message"]


# ── 快速上傳:連碰宣告顆數 + 向上補足 ─────────────────────
def test_combo_fills_upward_to_declared():
    text = ("21_24x20車\n03_11_35x10車\n 04_08_22\n八顆三星1500\n八顆四星1500")
    items, errors = importer.parse(text, G, _odds())
    assert errors == []
    combos = [it for it in items if it.mode == "combo"]
    assert len(combos) == 2
    # 補足 8 顆:04,08,22(最近選號)往上補 03,11,35,21,24
    assert set(combos[0].balls) == {4, 8, 22, 3, 11, 35, 21, 24}
    assert len(combos[0].balls) == 8
    from core import combo as cm
    assert combos[0].bets_count == cm.star_bets(3, 8)   # 三星 8 顆 = C(8,3) = 56
    assert combos[1].bets_count == cm.star_bets(4, 8)   # 四星 = C(8,4) = 70
    assert not combos[0].incomplete


def test_combo_incomplete_when_cannot_fill():
    text = "01_02_03\n八顆三星1500"
    items, _ = importer.parse(text, G, _odds())
    combos = [it for it in items if it.mode == "combo"]
    assert combos and combos[0].incomplete
    assert len(combos[0].balls) == 3   # 湊不到 8,有幾顆算幾顆


def test_cn_int():
    assert importer._cn_int("八") == 8
    assert importer._cn_int("十") == 10
    assert importer._cn_int("十二") == 12
    assert importer._cn_int("8") == 8
    assert importer._cn_int("") == 0


# ── 快速上傳:提交時後端重算成本 ─────────────────────────
def test_recost_erhe_and_combo():
    erhe = importer._recost(G, _odds(), "single", [5, 12], 3, 0)
    assert erhe.mode == "single"
    assert erhe.cost == round(importer._erhe_cost(_odds(), 2, 3))

    cb = importer._recost(G, _odds(), "combo", [1, 2, 3, 4, 5, 6, 7, 8], 12, 3)
    from core import combo as cm
    assert cb.bets_count == cm.star_bets(3, 8)

    with pytest.raises(ValueError):
        importer._recost(G, _odds(), "single", [999], 3, 0)   # 號碼超範圍
    with pytest.raises(ValueError):
        importer._recost(G, _odds(), "single", [5], 0, 0)      # 車數 0
