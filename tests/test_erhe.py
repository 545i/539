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


def test_progression_sim_basics():
    r = erhe.progression_sim(progression=(3, 5, 7.5, 10), win_prob=erhe.DAN_PROB,
                             cost_per_car=2755, win_payout=21200, rounds=200,
                             start_capital=100000, trials=200)
    # 每局期望報酬率約 -1.34%
    assert abs(r.per_round_ev - (-0.0134)) < 0.005
    # 進程內至少中一次 = 1-(1-p)^4
    p = erhe.DAN_PROB
    assert abs(r.p_win_in_progression - (1 - (1 - p) ** 4)) < 1e-9
    # 期望幾局才中 = 1/p
    assert abs(r.expected_rounds_to_win - 1 / p) < 1e-9
    # 負期望下破產率高
    assert r.ruin_rate > 0.5


def test_progression_sim_reproducible():
    a = erhe.progression_sim(trials=100, seed=11)
    b = erhe.progression_sim(trials=100, seed=11)
    assert a.ruin_rate == b.ruin_rate and a.curve == b.curve


def test_round_net():
    # 下13車、押5顆、重0顆 → 損益 = 13×(0 - 5×2755) = -179,075
    assert erhe.round_net(13, 0, 5, 2755, 21200) == 13 * (0 - 5 * 2755)
    # 重1顆 → 13×(21200 - 13775) = +96,525
    assert erhe.round_net(13, 1, 5, 2755, 21200) == 13 * (21200 - 5 * 2755)


def test_per_car_one_hit_net():
    assert erhe.per_car_one_hit_net(5, 2755, 21200) == 21200 - 5 * 2755  # 7425


def test_next_cars_for_recovery():
    # 虧 179,075 → 下一局 ceil(179075/7425)=25 車
    rec = erhe.next_cars_for_recovery(-179075, 5, 2755, 21200, base_cars=3)
    assert rec["next_cars"] == 25 and not rec["recovered"]
    # 已獲利 → 回到起始車數
    rec2 = erhe.next_cars_for_recovery(50000, 5, 2755, 21200, base_cars=3)
    assert rec2["next_cars"] == 3 and rec2["recovered"]
    # 中1顆淨利<=0 → 無法靠中1顆回本
    rec3 = erhe.next_cars_for_recovery(-1000, 5, 2755, 10000, base_cars=3)
    assert rec3["next_cars"] == float("inf") and not rec3["can_recover_1hit"]


def test_hit_distribution_sums_to_one():
    d = erhe.hit_distribution(5)
    assert abs(sum(d.values()) - 1.0) < 1e-12
    # 中0顆機率 = C(34,5)/C(39,5)
    from math import comb
    assert abs(d[0] - comb(34, 5) / comb(39, 5)) < 1e-12


def test_progression_table_multi_costs():
    rows = erhe.progression_table_multi((3, 5, 7, 10, 13), 5, 2755, 21200, 500000)
    # 第1局成本 = 5顆 × 3車 × 2755
    assert rows[0].round_cost == 5 * 3 * 2755
    # 累積遞增
    assert rows[-1].cumulative_cost > rows[0].cumulative_cost
    # 50萬資金在第5局破產
    assert rows[-1].busted


def test_progression_sim_multi_capital_affects_ruin():
    low = erhe.progression_sim_multi((3, 5, 7, 10, 13), 5, 2755, 21200,
                                     capital=200000, rounds=200, trials=200)
    high = erhe.progression_sim_multi((3, 5, 7, 10, 13), 5, 2755, 21200,
                                      capital=3000000, rounds=200, trials=200)
    # 資金越大破產率越低
    assert low.ruin_rate > high.ruin_rate
    # 負期望 → 平均最終資金 < 起始
    assert low.avg_final_capital < 200000


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
