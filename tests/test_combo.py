"""連碰 / 立柱 / 拖膽(core.combo)。

把民間那一套的規格釘死:
    注數 = C(拖幾顆, 星數 − 膽幾顆)  —— 三種下法只有這一條式子
    二星 1賠53、三星 1賠580、四星 1賠7500(倍率是幾倍,不是幾元)
    返還率 = 倍率 ÷ 公平賠率,**跟拖幾顆、幾顆膽、每注多少都無關**
機率一律用組合數列舉,並與「注數 × 單注中獎機率」交叉驗證。
"""
from math import comb

import pytest

from core import combo


# ── 注數:三種下法同一條式子 ──────────────────────────────
def test_combo_is_c_n_k():
    """連碰(沒有膽)= C(選幾顆, 星數)。"""
    assert combo.bets(3, 8) == comb(8, 3) == 56
    assert combo.bets(4, 8) == comb(8, 4) == 70
    assert combo.bets(2, 8) == comb(8, 2) == 28


def test_pillar_is_c_m_k_minus_1():
    """立柱(1 顆膽)= C(拖幾顆, 星數 − 1)。"""
    assert combo.bets(3, 7, 1) == comb(7, 2) == 21
    assert combo.bets(4, 7, 1) == comb(7, 3) == 35


def test_dan_is_c_m_k_minus_d():
    """拖膽(D 顆膽)= C(拖幾顆, 星數 − D)。"""
    assert combo.bets(4, 6, 2) == comb(6, 2) == 15
    assert combo.bets(4, 5, 3) == comb(5, 1) == 5


def test_the_three_plays_are_one_formula():
    """立柱就是 D=1、連碰就是 D=0 —— 同一條式子的特例。"""
    for k in combo.STARS:
        for m in range(1, 12):
            for d in range(0, k):
                assert combo.bets(k, m, d) == (comb(m, k - d) if m >= k - d else 0)


def test_impossible_combinations_are_zero():
    """拖不夠挑、或膽比星數還多,就是湊不出任何一注。"""
    assert combo.bets(4, 2) == 0            # 拖 2 顆挑不出 4 顆
    assert combo.bets(3, 0) == 0
    assert combo.bets(3, 8, 4) == 0         # 膽比星數多,一注塞不下


def test_dans_equal_to_stars_is_exactly_one_bet():
    """膽跟星數一樣多:你買的就是那一注,拖完全用不到。

    這裡 C(n,0)=1 是對的 —— 不要把它當成「湊不出來」而擋掉。
    (UI 上把膽限制在星數 − 1 顆,所以不會走到這條路;但算式本身要誠實。)
    """
    assert combo.bets(3, 8, 3) == 1
    assert combo.bets(3, 0, 3) == 1         # 拖幾顆都不影響


# ── 注單 ─────────────────────────────────────────────────
def test_bet_list_matches_the_count():
    for k, nums, dan in [(3, range(1, 9), ()), (3, range(1, 9), (1,)),
                         (4, range(1, 8), (1, 2))]:
        nums = list(nums)
        lst = combo.bet_list(k, nums, dan)
        assert len(lst) == combo.bets(k, len(set(nums) - set(dan)), len(dan))
        assert all(len(b) == k for b in lst)
        assert len(set(lst)) == len(lst), "不能有重複的注"


def test_bet_list_puts_the_dan_in_every_bet():
    lst = combo.bet_list(3, [1, 2, 3, 4], [1])
    assert lst == [(1, 2, 3), (1, 2, 4), (1, 3, 4)]
    assert all(1 in b for b in lst)


# ── 成本與打平 ───────────────────────────────────────────
def test_odds_are_a_multiplier_not_an_amount():
    """倍率乘的是每注成本,不是「中幾元」。"""
    assert combo.prize_per_bet(72.5, 53) == 3_842.5
    assert combo.prize_per_bet(63, 580) == 36_540
    assert combo.prize_per_bet(50, 7500) == 375_000


def test_each_star_level_has_its_own_cost():
    """二星 72.5、三星 63、四星 50 —— 三個價都不一樣,不能共用一個數字。"""
    assert combo.MARKET_COST == {2: 72.5, 3: 63.0, 4: 50.0}
    assert len(set(combo.MARKET_COST.values())) == 3


def test_total_cost_is_bets_times_per_bet():
    assert combo.total_cost(3, 8, 2) == 56 * 2
    assert combo.total_cost(3, 7, 2, 1) == 21 * 2


def test_breakeven_bets_ignores_the_stake():
    """打平注數 = 注數 ÷ 倍率 —— 每注下多少會約掉。"""
    assert combo.breakeven_bets(3, 8, 580) == pytest.approx(56 / 580)
    for per_bet in (1, 2, 50, 1000):
        cost = combo.total_cost(3, 8, per_bet)
        assert (cost / combo.prize_per_bet(per_bet, 580)
                == pytest.approx(combo.breakeven_bets(3, 8, 580)))


# ── 中獎 ─────────────────────────────────────────────────
@pytest.mark.parametrize("matched, got", [(0, 0), (2, 0), (3, 1), (4, 4), (5, 10)])
def test_three_star_hits(matched, got):
    """三星連碰:拖中 3 顆 → 1 注、4 顆 → 4 注、5 顆 → 10 注。"""
    assert combo.hits(3, matched) == got


def test_a_missed_dan_zeroes_the_whole_ticket():
    """膽沒全中就是 0,拖那邊中再多都沒用 —— 每一注都含膽。"""
    assert combo.hits(3, 5, dans=1, matched_dans=0) == 0
    assert combo.hits(3, 5, dans=1, matched_dans=1) == comb(5, 2) == 10
    assert combo.hits(4, 4, dans=2, matched_dans=1) == 0


def test_hits_of_reads_the_draw():
    picked = [1, 2, 3, 4, 5, 6, 7, 8]
    assert combo.hits_of(3, [1, 2, 3, 20, 21], picked) == 1
    assert combo.hits_of(3, [1, 2, 3, 4, 5], picked) == 10
    # 同一期、同一組號碼,把 09(沒開)指定成膽就整張歸零
    assert combo.hits_of(3, [1, 2, 3, 20, 21], picked + [9], [9]) == 0
    # 把 01(有開)指定成膽:剩下拖中 02、03,C(2,2) = 1 注
    assert combo.hits_of(3, [1, 2, 3, 20, 21], picked, [1]) == 1


def test_possible_hits_for_dropdowns():
    """下拉裡只該出現真的可能發生的注數。"""
    assert combo.possible_hits(3, 8) == [10, 4, 1, 0]
    assert combo.possible_hits(4, 8) == [5, 1, 0]
    assert 2 not in combo.possible_hits(3, 8), "三星不可能剛好中 2 注"


def test_result_text():
    assert combo.result_text(None) == "待開獎"
    assert combo.result_text(0) == "槓龜"
    assert combo.result_text(4) == "中 4 注"


# ── 機率 ─────────────────────────────────────────────────
@pytest.mark.parametrize("stars, drag, dans", [
    (2, 8, 0), (3, 8, 0), (4, 8, 0), (3, 7, 1), (4, 6, 2), (3, 12, 1), (2, 5, 1),
])
def test_hit_probs_sum_to_one(stars, drag, dans):
    assert sum(combo.hit_probs(stars, drag, dans).values()) == pytest.approx(1.0)


@pytest.mark.parametrize("stars, drag, dans", [
    (2, 8, 0), (3, 8, 0), (4, 8, 0), (3, 7, 1), (4, 6, 2), (3, 12, 1),
])
def test_expected_hits_two_independent_paths(stars, drag, dans):
    """列舉 hit_probs vs 注數 × 單注中獎機率 —— 兩條路徑必須一致。"""
    by_enumeration = sum(h * p for h, p in combo.hit_probs(stars, drag, dans).items())
    assert by_enumeration == pytest.approx(combo.expected_hits(stars, drag, dans),
                                           rel=1e-12)


def test_hit_probs_rejects_too_many_numbers():
    with pytest.raises(ValueError):
        combo.hit_probs(3, 39, 5)          # 膽 + 拖 超過 39 個號碼


def test_single_bet_prob_is_the_same_whatever_the_play():
    """一注中獎的機率只看星數,跟你買了幾注、有沒有膽無關。"""
    assert combo.single_bet_prob(3) == comb(5, 3) / comb(39, 3)


# ── 期望值:整個模組最該記住的一件事 ───────────────────────
def test_fair_odds():
    assert combo.fair_odds(2) == pytest.approx(comb(39, 2) / comb(5, 2))
    assert combo.fair_odds(2) == pytest.approx(74.1)
    assert combo.fair_odds(3) == pytest.approx(913.9)
    assert combo.fair_odds(4) == pytest.approx(16_450.2, abs=0.05)


def test_market_odds_are_all_below_fair():
    """實際盤口都低於公平賠率 —— 三種星別都是負期望。"""
    for k in combo.STARS:
        odds = combo.MARKET_PRIZE[k] / combo.MARKET_COST[k]
        assert odds < combo.fair_odds(k)
        assert combo.return_rate(k, odds) < 1.0


def test_star_return_reconciles_with_the_per_combo_probability():
    """返還率要用**單碰**中獎機率算,不是「至少重 K 顆的機率」。

    先前用後者(三星 4.91%)乘上中的碰數,算出 394% —— 那算的是「這一期
    有沒有中」,不是期望中幾碰,高估了 4 倍。改成一碰一碰算:
      三星 56 碰 × C(5,3)/C(39,3) = 0.06128 碰 × 57,000 ÷ 3,528 = 99.0%
      四星 70 碰 × C(5,4)/C(39,4) = 0.00426 碰 × 750,000 ÷ 3,500 = 91.2%
    兩者都剛好落在兩平點下面一點,那個差額就是組頭的抽成。
    """
    for k, n, want in ((3, 56, 0.990), (4, 70, 0.912)):
        cost = combo.MARKET_COST[k] * n
        e = combo.star_expected_hits(k, 8, bets_bought=n)
        assert e == pytest.approx(n * combo.single_bet_prob(k))
        rate = e * combo.MARKET_PRIZE[k] / cost
        assert rate == pytest.approx(want, abs=0.005), (k, rate)
        # 組頭報的每碰派彩低於兩平點,差額就是抽成
        assert combo.MARKET_PRIZE[k] < cost / e

def test_real_payouts_match_what_the_bookie_pays():
    """使用者的實際派彩:八顆三星中 5 碰共 285,000、四星中 4 碰共 3,000,000。

    這兩個數字同時釘住「中幾碰」與「每碰多少」—— 對得起來才代表星碰的
    碰數規則沒推錯。
    """
    assert combo.star_hits(3, 8, 3) * combo.MARKET_PRIZE[3] == 285_000
    assert combo.star_hits(4, 8, 4) * combo.MARKET_PRIZE[4] == 3_000_000


def test_return_rates_of_the_market_odds():
    assert combo.return_rate(2, 53) == pytest.approx(0.7152, abs=1e-4)
    assert combo.return_rate(3, 580) == pytest.approx(0.6346, abs=1e-4)
    assert combo.return_rate(4, 7500) == pytest.approx(0.4559, abs=1e-4)


def test_return_rate_does_not_depend_on_how_many_you_buy():
    """買越多注只是等比放大,返還率一動也不動 —— 這是整頁的重點。"""
    base = combo.return_rate(3, 580)
    for drag, dans, per_bet in [(6, 0, 2), (8, 0, 2), (15, 0, 50), (7, 1, 2),
                                (10, 2, 100)]:
        cost = combo.total_cost(3, drag, per_bet, dans)
        back = (combo.expected_hits(3, drag, dans)
                * combo.prize_per_bet(per_bet, 580))
        assert back / cost == pytest.approx(base, rel=1e-12)


def test_treating_odds_as_a_flat_amount_would_be_absurd():
    """把 580 當成 580 元的話返還率會差幾十倍 —— 記錄「為什麼是倍率」。"""
    absurd = combo.expected_hits(3, 8) * 580 / combo.total_cost(3, 8, 50)
    assert absurd < combo.return_rate(3, 580) / 40


def test_expected_net_is_negative_at_market_odds():
    assert combo.expected_net(3, 8, 2, 580) < 0
    assert combo.expected_net(2, 8, 2, 53) < 0


# ── 回本 ─────────────────────────────────────────────────
def test_net_per_sheet():
    """中 1 注每支淨利 = 中一注可得 − 這張的總成本。"""
    assert combo.net_per_sheet(1, 3, 8, 2, 580) == 2 * 580 - 56 * 2


def test_sheets_for_recovery_rounds_up():
    res = combo.sheets_for_recovery(10_000, 1, 3, 8, 2, 580)
    assert res["feasible"] and res["gain_per_sheet"] == 1_048
    assert res["sheets"] == 10                   # ⌈10000/1048⌉
    assert res["cost"] == 10 * 112


def test_sheets_for_recovery_never_below_base():
    assert combo.sheets_for_recovery(0, 1, 3, 8, 2, 580, base=3)["sheets"] == 3


def test_sheets_for_recovery_is_infeasible_when_a_win_loses_money():
    """倍率低到中 1 注還賠錢 —— 不是算不出來,是這個盤口回不了本。"""
    res = combo.sheets_for_recovery(10_000, 1, 3, 8, 2, 10)
    assert not res["feasible"] and res["sheets"] is None


# ── 歷史檢驗 ─────────────────────────────────────────────
_PICKED = [1, 2, 3, 4, 5, 6, 7, 8]


def test_history_stats_counts_hits_per_draw():
    draws = [[1, 2, 3, 20, 21],      # 拖中 3 → 1 注
             [10, 11, 12, 13, 14],   # 拖中 0 → 槓龜
             [1, 2, 3, 4, 5]]        # 拖中 5 → 10 注
    s = combo.history_stats(draws, 3, _PICKED)
    assert s["rounds"] == 3 and s["wins"] == 2
    assert s["total_hits"] == 11
    assert s["hit_counts"] == {0: 1, 1: 1, 10: 1}
    assert s["last_draw"] == [1, 2, 3, 4, 5] and s["last_hits"] == 10


def test_history_stats_skips_incomplete_draws():
    s = combo.history_stats([[1, 2, 3], [], [1, 2, 3, 20, 21]], 3, _PICKED)
    assert s["rounds"] == 1 and s["skipped"] == 2


def test_history_stats_streaks():
    miss, win = [10, 11, 12, 13, 14], [1, 2, 3, 20, 21]
    s = combo.history_stats([miss, miss, miss, win, miss, miss], 3, _PICKED)
    assert s["streak"] == 2 and s["max_streak"] == 3


def test_history_stats_of_an_empty_history():
    s = combo.history_stats([], 3, _PICKED)
    assert s["rounds"] == 0 and s["win_rate"] == 0.0 and s["last_draw"] == []


# ── 對照表 ───────────────────────────────────────────────
def test_bets_table_matches_bets():
    for row in combo.bets_table():
        for k in combo.STARS:
            assert (row[k] or 0) == combo.bets(k, row["drag"])
    for row in combo.bets_table(1):
        for k in combo.STARS:
            assert (row[k] or 0) == combo.bets(k, row["drag"], 1)


# ── 星碰(民間三星 / 四星碰)────────────────────────────────
# 使用者給的實例:下 05 11 13 15 20 23 31 35,開 05 11 13 15 27
#   重 4 顆 → 那 4 顆組成一組四星,剩下的 4 顆(20 23 31 35)各配一碰 = 4 碰
#   同一期三星是 5 碰 —— 一組三星 + 你剩下的 5 顆
_NUMS = [5, 11, 13, 15, 20, 23, 31, 35]
_DRAWN = [5, 11, 13, 15, 27]


def test_star_hits_matches_the_real_example():
    assert combo.star_hits_of(4, _DRAWN, _NUMS) == 4
    assert combo.star_hits_of(3, _DRAWN, _NUMS) == 5


def test_star_hits_is_picked_minus_stars_not_a_combination():
    """碰數 = 選幾顆 − 星數,**跟重了幾顆無關**(重到門檻就是那個數)。

    這是星碰跟連碰最容易搞混的地方:連碰是 C(重的顆數, 星數),
    重越多中越多;星碰重再多也還是同一組星配同樣那幾顆。
    """
    for m in (3, 4, 5):
        assert combo.star_hits(3, 8, m) == 5
    for m in (4, 5):
        assert combo.star_hits(4, 8, m) == 4
    assert combo.star_hits(3, 8, 2) == 0        # 重不到 3 顆就是槓龜
    assert combo.star_hits(4, 8, 3) == 0
    # 不是 C(重,星) × 剩餘 —— 重 4 顆的三星是 5 碰,不是 C(4,3)×4 = 16
    assert combo.star_hits(3, 8, 4) != comb(4, 3) * 4


def test_star_bets_is_the_number_of_star_groups():
    """一支買的碰數 = C(選幾顆, 星數) —— 選 8 顆時三星 56、四星 70。

    對應使用者給的單支成本:63 × 56 = 3,528、50 × 70 = 3,500。
    """
    assert combo.star_bets(3, 8) == comb(8, 3) == 56
    assert combo.star_bets(4, 8) == comb(8, 4) == 70
    assert 63 * combo.star_bets(3) == 3_528     # 預設就是 8 顆
    assert 50 * combo.star_bets(4) == 3_500
    assert combo.star_bets(3, 3) == 0


def test_star_hit_probs_sum_to_one():
    for k in (2, 3, 4):
        for n in (6, 8, 10):
            assert sum(combo.star_hit_probs(k, n).values()) == pytest.approx(1.0)


def test_star_win_prob_is_just_hitting_enough_numbers():
    """至少中一碰 = 重到星數以上 —— 中的碰數固定,所以兩者是同一件事。"""
    mp = combo.match_probs(8)
    assert combo.star_win_prob(3, 8) == pytest.approx(mp[3] + mp[4] + mp[5])
    assert combo.star_win_prob(4, 8) == pytest.approx(mp[4] + mp[5])


def test_star_joint_outcomes_links_the_star_levels():
    """三星 + 四星 一起下時,重幾顆同時決定兩邊中幾碰。"""
    rows = combo.star_joint_outcomes([3, 4], 8)
    assert sum(r["prob"] for r in rows) == pytest.approx(1.0)
    by_m = {r["matched"]: r["hits"] for r in rows}
    assert by_m[4] == {3: 5, 4: 4}      # 重 4 顆:三星 5 碰、四星 4 碰
    assert by_m[3] == {3: 5, 4: 0}      # 重 3 顆:只有三星中
    assert by_m[2] == {3: 0, 4: 0}
    # 邊際分布要跟各自算的一致
    for k in (3, 4):
        marg = {}
        for r in rows:
            marg[r["hits"][k]] = marg.get(r["hits"][k], 0) + r["prob"]
        ref = combo.star_hit_probs(k, 8)
        assert all(marg[h] == pytest.approx(ref[h]) for h in ref)
