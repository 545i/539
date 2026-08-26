"""9000碰(core.combo9000)。

釘住玩法規格:四段依十位頭切成 0/1/2/3 頭(9/10/10/10)、全包 9000 碰、
四段各開 ≥ 1 顆(必為 {2,1,1,1} 分布)→ 過關固定中 2 碰,否則 0。
"""
from itertools import combinations
from math import comb

from core import combo9000, games


# ── 分段 ─────────────────────────────────────────────────
def test_segment_sizes_and_partition():
    s0, s1, s2, s3 = combo9000.segments(39)
    assert (len(s0), len(s1), len(s2), len(s3)) == (9, 10, 10, 10)
    assert set(s0) | set(s1) | set(s2) | set(s3) == set(range(1, 40))   # 窮盡
    assert s0 == list(range(1, 10)) and s3 == list(range(30, 40))


def test_seg_of_by_tens_head():
    assert combo9000.seg_of(1) == 0 and combo9000.seg_of(9) == 0
    assert combo9000.seg_of(10) == 1 and combo9000.seg_of(19) == 1
    assert combo9000.seg_of(20) == 2 and combo9000.seg_of(30) == 3


def test_seg_counts():
    assert combo9000.seg_counts([5, 11, 12, 22, 34]) == (1, 2, 1, 1)
    assert combo9000.seg_counts([]) == (0, 0, 0, 0)


def test_total_bets_is_9000():
    assert combo9000.total_bets(39) == 9 * 10 * 10 * 10 == 9000


# ── 命中 ─────────────────────────────────────────────────
def test_pass_is_fixed_two_carries():
    # 四段都有開 → 中 2 碰(不看乘積)
    assert combo9000.hits_of([5, 11, 12, 22, 34]) == 2
    assert combo9000.hits_of([9, 10, 20, 30, 31]) == 2


def test_broken_head_is_zero():
    # 缺 0頭 → 槓龜
    assert combo9000.hits_of([10, 11, 22, 34, 35]) == 0
    # 全部落 3頭 → 槓龜
    assert combo9000.hits_of([30, 31, 32, 33, 34]) == 0


def test_pass_hits_matches_brute_force_wheel():
    """過關固定中 2 碰,拿全包 9000 碰逐碰對一次開獎交叉驗證。

    一碰 = 四段各取一號;中 = 該碰四顆全在開出的 5 顆裡。{2,1,1,1} 分布下
    只有那多開 1 顆的段能二選一,故恰好 2 碰全中。
    """
    s0, s1, s2, s3 = combo9000.segments(39)
    draw = {5, 11, 12, 22, 34}   # (1,2,1,1)
    won = sum(1 for a in s0 for b in s1 for c in s2 for d in s3
              if {a, b, c, d} <= draw)
    assert won == 2 == combo9000.hits_of(draw)


def test_all_pass_distributions_are_2111():
    """列舉所有 39 選 5 開獎:過關者的段分布一定是 {2,1,1,1}。"""
    passes = 0
    for draw in combinations(range(1, 40), 5):
        counts = combo9000.seg_counts(draw)
        if combo9000.passed(counts):
            passes += 1
            assert sorted(counts) == [1, 1, 1, 2]
            assert combo9000.hits_from_counts(counts) == 2
        else:
            assert combo9000.hits_from_counts(counts) == 0
    # 過關組合數 = C(9,2)C(10,1)^3 + [C(10,2) 出現在 1/2/3 頭三種] × ...
    # 直接用列舉數對照:0頭多開 + 其他三段各多開
    expect = (comb(9, 2) * 10 * 10 * 10
              + 9 * comb(10, 2) * 10 * 10
              + 9 * 10 * comb(10, 2) * 10
              + 9 * 10 * 10 * comb(10, 2))
    assert passes == expect


# ── 損益 ─────────────────────────────────────────────────
def test_round_cost_and_payout():
    # 每碰成本 50、每碰派彩 750,000(四星盤口)、1 支
    assert combo9000.round_cost(50.0, 1, 39) == 9000 * 50.0 == 450_000
    assert combo9000.round_payout(2, 750_000.0, 1) == 1_500_000
    res = combo9000.settle(2, 50.0, 750_000.0, 1, 39)
    assert res == {"hits": 2, "cost": 450_000, "payout": 1_500_000,
                   "net": 1_050_000}


# ── 適用遊戲 ─────────────────────────────────────────────
def test_supports_only_39_pick5():
    assert combo9000.supports(games.LOTTO539)
    assert combo9000.supports(games.FANTASY5)
    assert not combo9000.supports(games.MARKSIX)
