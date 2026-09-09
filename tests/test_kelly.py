"""凱莉公式投報計算模組測試。"""
from math import log

from core import constants as C
from core import kelly


def test_kelly_binary_fair_double_or_nothing():
    # p=0.6、b=1.0(贏可拿 1 倍本金)→ f* = (1*0.6 - 0.4)/1 = 0.2
    assert abs(kelly.kelly_binary(0.6, 1.0) - 0.2) < 1e-9


def test_outcomes_539_shape_and_prob_sum():
    outcomes = kelly.outcomes_539()
    assert len(outcomes) == 6
    prob_sum = sum(prob for prob, _ in outcomes)
    assert abs(prob_sum - 1.0) < 1e-12


def test_outcomes_539_net_multiples():
    outcomes = kelly.outcomes_539()
    # k=2 剛好打平(net=0)
    assert abs(outcomes[2][1] - 0.0) < 1e-12
    # k<=1 本金全失(net=-1)
    assert abs(outcomes[0][1] - (-1.0)) < 1e-12
    assert abs(outcomes[1][1] - (-1.0)) < 1e-12


def test_analyze_539_says_do_not_bet():
    result = kelly.analyze_539()
    assert result.raw_fraction < 0.0
    assert result.fraction == 0.0
    assert abs(result.ev_return_rate - C.EXPECTED_RETURN) < 1e-3
    assert abs(result.ev_return_rate - (-0.4416)) < 1e-3
    assert result.growth_rate == 0.0
    # 誠實結論:必須點出比例為 0 / 不該下注
    assert "0" in result.recommendation


def test_simulate_bankroll_zero_fraction_is_constant():
    outcomes = kelly.outcomes_539()
    series = kelly.simulate_bankroll(0.0, outcomes, rounds=50, start=10000.0)
    assert len(series) == 51
    assert all(v == 10000.0 for v in series)


def test_simulate_bankroll_reproducible_with_same_seed():
    outcomes = kelly.outcomes_539()
    a = kelly.simulate_bankroll(0.01, outcomes, rounds=100, start=10000.0, seed=539)
    b = kelly.simulate_bankroll(0.01, outcomes, rounds=100, start=10000.0, seed=539)
    assert a == b
    # 起始值與長度正確
    assert a[0] == 10000.0
    assert len(a) == 101


def test_simulate_bankroll_different_seed_differs():
    outcomes = kelly.outcomes_539()
    a = kelly.simulate_bankroll(0.01, outcomes, rounds=200, start=10000.0, seed=1)
    b = kelly.simulate_bankroll(0.01, outcomes, rounds=200, start=10000.0, seed=2)
    assert a != b


def test_kelly_multi_matches_growth_definition():
    # 正期望、有利賭局時凱莉應給出正比例,且該比例確實提升成長率
    outcomes = [(0.5, 1.0), (0.5, -0.5)]  # 贏 +100% / 輸 -50%,EV 為正
    f = kelly.kelly_multi(outcomes)
    assert f > 0.0
    g_at_f = kelly._growth(f, outcomes)
    assert g_at_f >= kelly._growth(0.0, outcomes)
    assert g_at_f >= kelly._growth(f + 0.05, outcomes)
