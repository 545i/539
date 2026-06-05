"""二合(策略1)買牌試算 core.erhe 測試。"""
from core import erhe


def test_pair_prob():
    # 二合單組中獎機率 = C(37,3)/C(39,5) ≈ 1/74.1
    assert abs(erhe.PAIR_PROB - 7770 / 575757) < 1e-12
    assert abs(erhe.BREAKEVEN_ODDS - 74.10) < 0.05


def test_dan_prob():
    # 膽中機率 = 5/39
    assert abs(erhe.DAN_PROB - 5 / 39) < 1e-12


def test_car_ev_matches_user_numbers():
    # 每車成本 2755、中獎可得 21200 → 期望報酬率約 -1.34%
    ev = erhe.car_ev_rate(2755, 21200)
    assert abs(ev - (-0.0134)) < 0.005
    assert ev < 0


def test_car_kelly_zero_when_negative_ev():
    assert erhe.car_kelly_fraction(2755, 21200) == 0.0


def test_car_kelly_positive_when_positive_ev():
    # 若中獎金額拉高到遠超損益兩平,凱莉應給正比例
    fair = 2755 / erhe.DAN_PROB  # 損益兩平中獎金額
    f = erhe.car_kelly_fraction(2755, fair * 1.5)
    assert f > 0


def test_breakeven_payout():
    # 中獎金額 = 損益兩平時,期望報酬率為 0
    fair = 2755 / erhe.DAN_PROB
    assert abs(erhe.car_ev_rate(2755, fair)) < 1e-9


def test_martingale_explodes_and_busts():
    t = erhe.martingale_table(base_cars=3, multiplier=2, rounds=8,
                              cost_per_car=2755, win_payout=21200, capital=100000)
    # 車數倍增
    assert [s.cars for s in t.steps][:4] == [3, 6, 12, 24]
    # 累積成本遞增、會破產
    assert t.bust_round is not None
    assert t.steps[-1].cumulative_cost > t.steps[0].cumulative_cost
    # 打平需中車數隨累積成本上升
    assert t.steps[-1].cars_to_break_even > t.steps[0].cars_to_break_even
