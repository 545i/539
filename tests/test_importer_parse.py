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
