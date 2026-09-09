"""三柱部分包牌 pillar.partial_bets 測試。

三柱:第一柱 10~18(9)、第二柱 20~29(10)、第三柱 其餘(20)。
注數 = 三柱各選幾顆的乘積;任一柱掛 0 → 組不出注(buyable=False)。
"""
from __future__ import annotations

from core import pillar


def test_bets_is_product_of_pillar_counts():
    # 第一柱 2 顆(10,11)、第二柱 2 顆(20,21)、第三柱 2 顆(1,2)→ 2×2×2=8
    res = pillar.partial_bets([10, 11, 20, 21, 1, 2])
    assert res["counts"] == (2, 2, 2)
    assert res["bets"] == 8
    assert res["buyable"] is True
    assert res["total"] == 1800
    assert abs(res["coverage"] - 8 / 1800) < 1e-9


def test_missing_a_pillar_is_not_buyable():
    res = pillar.partial_bets([10, 20])  # 第三柱空
    assert res["counts"] == (1, 1, 0)
    assert res["bets"] == 0
    assert res["buyable"] is False


def test_full_selection_reproduces_1800():
    c1, c2, c3 = pillar.pillars(39)
    res = pillar.partial_bets(c1 + c2 + c3)
    assert res["bets"] == 1800
    assert res["coverage"] == 1.0


def test_19_belongs_to_third_pillar():
    # 19 刻意歸第三柱(非第一/第二)
    res = pillar.partial_bets([19, 10, 20])
    assert res["pillars"][2] == [19]
    assert res["counts"] == (1, 1, 1)
    assert res["bets"] == 1


def test_dedupe_and_out_of_pillar_ints():
    res = pillar.partial_bets([10, 10, 11, 20, 5])  # 重複 10 去重
    assert res["counts"] == (2, 1, 1)
    assert res["bets"] == 2
