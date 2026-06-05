"""包牌/牌型/加碼(core.wheel)與雙遊戲設定(core.games)測試。"""
from math import comb

import pytest

from core import games, kelly, loader, wheel


# ── games ────────────────────────────────────────────────
def test_games_registry():
    assert set(games.GAMES) == {"lotto539", "fantasy5"}
    assert games.get("lotto539").name == "今彩539"
    assert games.by_name("今彩539").key == "lotto539"
    # 找不到回預設
    assert games.get("nope").key == games.DEFAULT_GAME.key


def test_both_games_negative_ev():
    for g in games.GAMES.values():
        assert g.expected_return() < 0          # 兩款都是負期望
        assert kelly.analyze(g).fraction == 0.0  # 凱莉建議皆為 0


def test_539_numbers_unchanged():
    g = games.LOTTO539
    assert abs(g.expected_return() - (-0.4416)) < 1e-3


# ── wheel:包牌 ───────────────────────────────────────────
def test_wheel_car_count_is_combination():
    g = games.LOTTO539
    for n in (5, 6, 7, 10):
        plan = wheel.wheel_plan(n, g)
        assert plan.cars == comb(n, 5)
        assert plan.cost == comb(n, 5) * g.ticket_price


def test_wheel_unit_rounds_up():
    g = games.LOTTO539
    plan = wheel.wheel_plan(7, g, unit=3)  # 21 車 / 3 = 7 單位
    assert plan.cars == 21 and plan.units == 7
    plan2 = wheel.wheel_plan(8, g, unit=3)  # 56 車 / 3 = 18.67 → 19
    assert plan2.cars == 56 and plan2.units == 19


def test_wheel_expected_return_unchanged():
    # 包牌不改變期望報酬率
    g = games.LOTTO539
    assert abs(wheel.wheel_plan(10, g).expected_return - g.expected_return()) < 1e-12


def test_wheel_rejects_too_few():
    with pytest.raises(ValueError):
        wheel.wheel_plan(4, games.LOTTO539)


# ── wheel:牌型 ───────────────────────────────────────────
def test_pattern_distribution():
    df = loader.generate_sample(200)
    rows = wheel.pattern_distribution(df, top=5)
    assert 1 <= len(rows) <= 5
    # 比例介於 0~1,次數為正
    for _desc, cnt, ratio in rows:
        assert cnt > 0 and 0 < ratio <= 1


# ── wheel:加碼回本破產示範 ───────────────────────────────
def test_martingale_ruins_in_negative_ev():
    g = games.LOTTO539
    res = wheel.martingale_demo(g, base_cars=3, rounds=40, start_capital=100000, trials=100)
    # 負期望 + 加碼 → 破產率應極高
    assert res.ruin_rate > 0.8
    assert res.peak_bet_cars >= 3


def test_martingale_reproducible():
    g = games.FANTASY5
    a = wheel.martingale_demo(g, base_cars=3, rounds=30, trials=50, seed=7)
    b = wheel.martingale_demo(g, base_cars=3, rounds=30, trials=50, seed=7)
    assert a.ruin_rate == b.ruin_rate
    assert a.capital_curve == b.capital_curve
