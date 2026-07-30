"""包牌/牌型/加碼(core.wheel)與多遊戲設定(core.games)測試。"""
from math import comb

import pytest

from core import games, kelly, loader, wheel


# ── games ────────────────────────────────────────────────
def test_games_registry():
    assert set(games.GAMES) == {"fantasy5", "marksix"}          # 目前啟用的兩款
    assert games.get("fantasy5").key == "fantasy5"
    assert games.by_name("六合彩").key == "marksix"
    # 找不到回預設
    assert games.get("nope").key == games.DEFAULT_GAME.key
    assert games.DEFAULT_GAME.key == "fantasy5"


def test_retired_game_still_resolvable():
    """今彩539 已停用,但舊下注紀錄要能顯示正確名稱,不能被誤標成別款。"""
    assert "lotto539" not in games.GAMES
    assert games.get("lotto539").name == "今彩539"
    assert games.is_active("lotto539") is False
    assert games.is_active("marksix") is True


def test_all_games_negative_ev():
    for g in list(games.GAMES.values()) + list(games.RETIRED.values()):
        assert g.expected_return() < 0          # 三款都是負期望
        assert kelly.analyze(g).fraction == 0.0  # 凱莉建議皆為 0


def test_539_numbers_unchanged():
    g = games.LOTTO539
    assert abs(g.expected_return() - (-0.4416)) < 1e-3


# ── 六合彩(49 選 6)規格 ─────────────────────────────────
def test_marksix_spec():
    g = games.MARKSIX
    assert (g.num_max, g.pick) == (49, 6)
    assert g.total_comb == comb(49, 6) == 13_983_816
    assert g.notes_per_car == 48                      # 1 膽拖 48 號 = 1 車
    assert abs(g.dan_prob - 6 / 49) < 1e-12           # 膽中機率 6/49
    # 使用者指定的盤口:每車成本 3528(= 48 注 × 73.5)、中獎可得 28500
    assert g.default_cost_per_car == 3528.0
    assert g.default_win_payout == 28500.0
    # 中 k 碼組合數應與超幾何一致,且機率總和為 1
    assert g.ways(6) == 1 and g.ways(0) == comb(43, 6)
    assert abs(sum(g.prob(k) for k in range(7)) - 1.0) < 1e-12


def test_539_and_fantasy5_still_5_of_39():
    for g in (games.LOTTO539, games.FANTASY5):
        assert (g.num_max, g.pick) == (39, 5)
        assert g.notes_per_car == 38
        assert abs(g.dan_prob - 5 / 39) < 1e-12


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
