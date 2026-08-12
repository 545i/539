"""三星 / 四星(core.star)。

把使用者給的規格釘死:
    三星  每碰 63、C(8,3)=56 碰 → 1 支 3,528;倍率 570 → 中一碰 35,910
    四星  每碰 50、C(8,4)=70 碰 → 1 支 3,500;倍率 7500 → 中一碰 375,000
    中獎金額 = 支數 × 中的碰數 × 每碰可得
機率一律用組合數列舉,並與「碰數 × 單碰中獎機率」交叉驗證。
"""
from math import comb

import pytest

from core import star


# ── 碰數與成本 ───────────────────────────────────────────
def test_combos_are_c8k():
    assert star.combos(3) == comb(8, 3) == 56
    assert star.combos(4) == comb(8, 4) == 70


def test_sheet_cost_matches_the_spec():
    """63 × 56 = 3,528 是一支成本;50 × 70 = 3,500。"""
    assert star.sheet_cost(63, 3) == 3_528
    assert star.sheet_cost(50, 4) == 3_500


def test_round_cost_scales_with_sheets():
    """可以下很多支,成本等比放大。"""
    assert star.round_cost(63, 3, sheets=1) == 3_528
    assert star.round_cost(63, 3, sheets=5) == 3_528 * 5
    assert star.round_cost(50, 4, sheets=3) == 3_500 * 3


def test_payout_per_combo_is_cost_times_odds():
    """倍率是「賠率幾倍」,不是「幾元」。"""
    assert star.payout_per_combo(63, 570) == 35_910
    assert star.payout_per_combo(50, 7500) == 375_000


# ── 中獎碰數 ─────────────────────────────────────────────
@pytest.mark.parametrize("matched, hits", [(0, 0), (2, 0), (3, 1), (4, 4), (5, 10)])
def test_three_star_hits(matched, hits):
    """三星:中 3 顆 → 1 碰、4 顆 → 4 碰、5 顆 → 10 碰。"""
    assert star.hits_for(matched, 3) == hits


@pytest.mark.parametrize("matched, hits", [(0, 0), (3, 0), (4, 1), (5, 5)])
def test_four_star_hits(matched, hits):
    assert star.hits_for(matched, 4) == hits


def test_possible_hits_for_dropdowns():
    assert star.possible_hits(3) == [10, 4, 1, 0]
    assert star.possible_hits(4) == [5, 1, 0]


def test_round_payout_is_sheets_times_hits_times_per_combo():
    """中獎金額 = 支數 × 中的碰數 × 每碰可得 —— 使用者給的算式。"""
    assert star.round_payout(4, 63, 570, sheets=2) == 2 * 4 * 35_910


@pytest.mark.parametrize("hits, net", [
    (0, -3_528), (1, 35_910 - 3_528), (4, 4 * 35_910 - 3_528),
])
def test_settle_three_star(hits, net):
    assert star.settle(hits, 63, 570, 3)["net"] == net


def test_settle_scales_with_sheets():
    one = star.settle(4, 63, 570, 3, sheets=1)
    three = star.settle(4, 63, 570, 3, sheets=3)
    assert three["cost"] == one["cost"] * 3
    assert three["payout"] == one["payout"] * 3


# ── 機率 ─────────────────────────────────────────────────
def test_match_probs_sum_to_one():
    assert sum(star.match_probs().values()) == pytest.approx(1.0)


def test_hit_probs_sum_to_one():
    for k in star.STARS:
        assert sum(star.hit_probs(k).values()) == pytest.approx(1.0)


@pytest.mark.parametrize("stars", star.STARS)
def test_expected_hits_two_independent_paths(stars):
    """列舉對中顆數 vs 碰數 × 單碰中獎機率 —— 兩條路徑必須一致。"""
    by_enumeration = star.expected_hits(stars)
    by_combo = star.combos(stars) * comb(39 - stars, 5 - stars) / comb(39, 5)
    assert by_enumeration == pytest.approx(by_combo, rel=1e-12)


def test_breakeven_odds_are_the_fair_odds_of_one_combo():
    """兩平倍率 = 單碰公平賠率,與每碰成本無關。"""
    assert star.breakeven_odds(3) == pytest.approx(comb(39, 3) / comb(5, 3))
    assert star.breakeven_odds(3) == pytest.approx(913.9)
    assert star.breakeven_odds(4) == pytest.approx(comb(39, 4) / comb(5, 4))
    assert star.breakeven_odds(4) == pytest.approx(16_450.2, abs=0.05)


def test_the_odds_on_offer_are_below_breakeven():
    """570 < 913.9、7500 < 16,450.2 —— 都是負期望,沒有變成穩賺。"""
    assert 570 < star.breakeven_odds(3)
    assert 7500 < star.breakeven_odds(4)
    assert star.return_rate(63, 570, 3) < 1.0
    assert star.return_rate(50, 7500, 4) < 1.0


def test_return_rates_of_the_real_odds():
    assert star.return_rate(63, 570, 3) == pytest.approx(0.6237, abs=1e-4)
    assert star.return_rate(50, 7500, 4) == pytest.approx(0.4559, abs=1e-4)


def test_treating_odds_as_a_flat_amount_would_be_absurd():
    """把 570 當成 570 元的話返還率只有 0.99% —— 那種盤口不存在。

    這個測試存在的意義是記錄「為什麼 570 是倍率而不是金額」。
    """
    e = star.expected_hits(3)
    absurd = e * 570 / star.sheet_cost(63, 3)
    assert absurd < 0.01


def test_win_prob_three_star_is_higher_than_four_star():
    assert star.win_prob(3) > star.win_prob(4)
    assert star.win_prob(3) == pytest.approx(0.04909, abs=1e-5)
    assert star.win_prob(4) == pytest.approx(0.0038658, abs=1e-6)


def test_best_case_net_per_sheet():
    """三星全中(5 顆)= 10 碰;四星全中 = 5 碰。"""
    assert star.best_case_net_per_sheet(63, 570, 3) == 10 * 35_910 - 3_528
    assert star.best_case_net_per_sheet(50, 7500, 4) == 5 * 375_000 - 3_500


# ── UI 要用的:星別反推、對獎、回本、歷史檢驗 ───────────────
class _Game:
    def __init__(self, num_max, pick):
        self.num_max, self.pick = num_max, pick


def test_supports_only_39_pick_5():
    """盤口與機率都是照 39 選 5 報的,六合彩(49 選 6)不開放。"""
    assert star.supports(_Game(39, 5))
    assert not star.supports(_Game(49, 6))
    assert not star.supports(object())


def test_stars_of_combos_recovers_the_star_level():
    """流水只存碰數,顯示星別時要能反推回來。"""
    assert star.stars_of_combos(56) == 3
    assert star.stars_of_combos(70) == 4
    assert star.stars_of_combos(999) == 0      # 對不上就回 0,不硬猜


def test_matched_count_and_hits_of():
    picked = [1, 2, 3, 4, 5, 6, 7, 8]
    assert star.matched_count(picked, [1, 2, 3, 20, 21]) == 3
    assert star.hits_of(picked, [1, 2, 3, 20, 21], 3) == 1     # C(3,3)
    assert star.hits_of(picked, [1, 2, 3, 20, 21], 4) == 0     # 對中 3 顆買四星不中
    assert star.hits_of(picked, [1, 2, 3, 4, 5], 3) == 10      # C(5,3)


def test_result_text():
    assert star.result_text(None) == "待開獎"
    assert star.result_text(0) == "槓龜"
    assert star.result_text(4) == "中 4 碰"
    assert star.result_text(4, 3) == "三星中 4 碰"


def test_net_per_sheet_matches_best_case():
    assert star.net_per_sheet(1, 63, 570, 3) == 35_910 - 3_528
    assert star.net_per_sheet(10, 63, 570, 3) == star.best_case_net_per_sheet(63, 570, 3)


def test_sheets_for_recovery_rounds_up():
    """支數 = ⌈虧損 ÷ 中 hits 碰每支淨利⌉。"""
    res = star.sheets_for_recovery(100_000, 1, 63, 570, 3)
    assert res["feasible"] and res["gain_per_sheet"] == 32_382
    assert res["sheets"] == 4                       # ⌈100000/32382⌉
    assert res["cost"] == 4 * 3_528


def test_sheets_for_recovery_never_below_base():
    """沒有虧損(或虧一點點)時至少下起始支數。"""
    assert star.sheets_for_recovery(0, 1, 63, 570, 3, base=2)["sheets"] == 2
    assert star.sheets_for_recovery(100, 1, 63, 570, 3, base=2)["sheets"] == 2


def test_sheets_for_recovery_is_infeasible_when_a_win_loses_money():
    """倍率低到中 1 碰還賠錢 —— 那不是算不出來,是這個盤口回不了本。"""
    res = star.sheets_for_recovery(100_000, 1, 63, 10, 3)
    assert not res["feasible"] and res["sheets"] is None
    assert res["gain_per_sheet"] < 0


# ── 歷史檢驗 ─────────────────────────────────────────────
_PICKED = [1, 2, 3, 4, 5, 6, 7, 8]


def test_history_stats_counts_hits_per_draw():
    draws = [[1, 2, 3, 20, 21],      # 對中 3 → 1 碰
             [10, 11, 12, 13, 14],   # 對中 0 → 槓龜
             [1, 2, 3, 4, 5]]        # 對中 5 → 10 碰
    s = star.history_stats(draws, _PICKED, 3)
    assert s["rounds"] == 3 and s["wins"] == 2
    assert s["total_hits"] == 1 + 0 + 10
    assert s["hit_counts"] == {0: 1, 1: 1, 10: 1}
    assert s["last_draw"] == [1, 2, 3, 4, 5]
    assert s["last_matched"] == 5 and s["last_hits"] == 10


def test_history_stats_skips_incomplete_draws():
    """顆數不齊的期不該被算成槓龜(資料還沒補齊而已)。"""
    s = star.history_stats([[1, 2, 3], [], [1, 2, 3, 20, 21]], _PICKED, 3)
    assert s["rounds"] == 1 and s["skipped"] == 2


def test_history_stats_streaks():
    """streak 是「目前」連幾期沒中,max_streak 是史上最長。"""
    miss, win = [10, 11, 12, 13, 14], [1, 2, 3, 20, 21]
    s = star.history_stats([miss, miss, miss, win, miss, miss], _PICKED, 3)
    assert s["streak"] == 2 and s["max_streak"] == 3


def test_history_stats_of_an_empty_history():
    s = star.history_stats([], _PICKED, 3)
    assert s["rounds"] == 0 and s["win_rate"] == 0.0 and s["last_draw"] == []
