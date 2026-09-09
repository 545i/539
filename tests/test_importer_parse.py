"""快速上傳文字解析(importer.parse)的邊界容錯。

重點:號碼行裡多打的底線 / 空白(手滑很常見)不該讓整行「看不懂」被丟掉。
2026-08 真實案例:`03_21_28_×50`(號碼與 x 之間多一個底線)整行判讀失敗。
"""
import pytest

from backend import edition_store, group_store
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


def test_stray_underscore_before_x(env):
    """`03_21_28_×50` —— 號碼與 x 間多一個底線,仍要正確解析成 3 顆 × 50 車。"""
    items, errors = _parse(env, "03_21_28_×50")
    assert errors == []
    assert len(items) == 1
    assert items[0].balls == [3, 21, 28]
    assert items[0].units == 50


def test_double_underscore_between_numbers(env):
    """號碼間連續底線 `03__21_28×50` 也要吸收掉。"""
    items, errors = _parse(env, "03__21_28×50")
    assert errors == []
    assert items[0].balls == [3, 21, 28]


def test_full_block_second_line_no_longer_fails(env):
    """使用者回報的整段:第二組(03_21_28_×50)以前判讀失敗,現在應成功。"""
    text = ("12_16×60\n"
            "03_21_28_×50\n"
            "_____\n"
            "07_33_36\n"
            "八顆三星1500\n"
            "八顆四星1500\n"
            "10_18\n"
            "20_29\n"
            "其他400")
    items, errors = _parse(env, text)
    # 兩個下注行(single/multi)都要在,且沒有「看不懂」錯誤
    assert not any("看不懂" in e["message"] for e in errors)
    balls_sets = [it.balls for it in items]
    assert [12, 16] in balls_sets
    assert [3, 21, 28] in balls_sets


def test_pick_line_trailing_underscore(env):
    """純選號行結尾多底線 `07_33_36_` 仍算一行選號(不報錯)。"""
    items, errors = _parse(env, "07_33_36_\n八顆三星1500")
    assert not any("看不懂" in e["message"] for e in errors)


def test_genuinely_bad_line_still_flagged(env):
    """容錯不能矯枉過正:真的亂打的行還是要報「看不懂」。"""
    items, errors = _parse(env, "這是一行亂七八糟的字")
    assert any("看不懂" in e["message"] for e in errors)


def test_combo9000_x_form(env):
    """9000碰x10 → 0.1 支(數字/100=支數)、900 碰、mode=combo9000。"""
    items, errors = _parse(env, "9000碰x10")
    assert errors == []
    assert len(items) == 1
    it = items[0]
    assert it.mode == "combo9000"
    assert it.units == 0.1
    assert it.bets_count == 900
    assert it.balls == []


def test_combo9000_full_and_fullwidth(env):
    """9000碰X100 → 1 支(全包一支);全形 Ｘ 與空白也認。"""
    items, _ = _parse(env, "9000碰Ｘ100")
    assert items[0].units == 1.0 and items[0].bets_count == 9000
    items2, _ = _parse(env, "9000碰 x 250")
    assert items2[0].units == 2.5


def test_combo9000_decimal_multiplier(env):
    """乘數本身可小數:9000碰x0.5 → 0.005 支。"""
    items, errors = _parse(env, "9000碰x0.5")
    assert errors == [] and items[0].units == 0.005


def test_combo9000_zero_rejected(env):
    items, errors = _parse(env, "9000碰x0")
    assert items == [] and errors and "大於 0" in errors[0]["message"]


def test_combo9000_marksix_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(group_store, "_db_path", lambda: tmp_path / "group.db")
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")
    g = get_game("marksix")
    odds = edition_store.get_odds(1, "marksix")
    items, errors = importer.parse("9000碰x10", g, odds)
    assert items == [] and errors and "六合彩不支援9000碰" in errors[0]["message"]


def test_recost_base_override_per_record(env):
    """逐筆基礎成本覆蓋:base 傳入就用它重算,不動版盤口。"""
    g, odds = env
    notes = g.num_max - 1
    # 二合:base 是每注,cost = 顆×車×(base×38)
    it = importer._recost(g, odds, "single", [3, 4], 380, 0, base=80)
    assert it.base_cost == 80 and it.cost == 2 * 380 * (80 * notes)
    # 不傳 base → 吃版預設(72.5)
    it0 = importer._recost(g, odds, "single", [3, 4], 380, 0)
    assert it0.base_cost == odds["pair_bet_cost"] == 72.5
    # 1800碰:base 每注直接套
    itp = importer._recost(g, odds, "pillar1800", [], 1, 0, base=60)
    assert itp.base_cost == 60 and itp.cost == 1800 * 60
    # 9000碰:base 每碰直接套(0.2支)
    itc = importer._recost(g, odds, "combo9000", [], 0.2, 0, base=48)
    assert itc.base_cost == 48 and abs(itc.cost - 9000 * 48 * 0.2) < 1e-6


def test_recost_base_none_uses_edition(env):
    """base=None(沒覆蓋)→ to_record 帶出版盤口的基礎成本供前端顯示。"""
    g, odds = env
    it = importer._recost(g, odds, "combo9000", [], 1, 0)
    rec = importer.to_record(it, g, "2026-08-29", "", 1)
    assert rec["baseCost"] == odds["combo_cost4"]
