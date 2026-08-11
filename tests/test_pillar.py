"""三柱 1800碰(core.pillar)。

這一組測試的用途是把 539-SPEC.md 第 3、4 章的數字釘住:分柱是完全劃分、
1800 注、hits 只有 {0,3,4}、過關率 55.3619%、E[hits] 1.96958、兩平 913.9。
機率一律用「列舉組合數」與「三合包牌」兩條互不相依的路徑交叉驗證 ——
只要有人動了分柱邊界或算式,這裡就會先炸。
"""
from math import comb

import pytest

from core import games, pillar


# ── 分柱 ─────────────────────────────────────────────────
def test_pillar_sizes_and_partition():
    c1, c2, c3 = pillar.pillars(39)
    assert (len(c1), len(c2), len(c3)) == (9, 10, 20)
    assert set(c1) | set(c2) | set(c3) == set(range(1, 40))   # 窮盡
    assert not (set(c1) & set(c2)) and not (set(c2) & set(c3))
    assert not (set(c1) & set(c3))                            # 互斥


def test_nineteen_belongs_to_third_pillar():
    """19 歸第三柱是刻意的不對稱(SPEC §3.1),不是筆誤。"""
    assert pillar.pillar_of(18) == 1
    assert pillar.pillar_of(19) == 3
    assert pillar.pillar_of(20) == 2


def test_pillar_counts():
    assert pillar.pillar_counts([5, 12, 18, 23, 31]) == (2, 1, 2)
    assert pillar.pillar_counts([]) == (0, 0, 0)


def test_total_bets_is_1800():
    assert pillar.total_bets(39) == 9 * 10 * 20 == 1800


# ── 命中 ─────────────────────────────────────────────────
@pytest.mark.parametrize("draw, counts, hits", [
    ([5, 12, 18, 23, 31], (2, 1, 2), 4),      # {1,2,2} → 中四碰
    ([12, 23, 31, 35, 38], (1, 1, 3), 3),     # {1,1,3} → 中三碰
    ([1, 2, 3, 4, 5], (0, 0, 5), 0),          # 第一、二柱斷 → 槓龜
    ([10, 11, 12, 20, 21], (3, 2, 0), 0),     # 第三柱斷 → 槓龜
])
def test_hits_of(draw, counts, hits):
    assert pillar.pillar_counts(draw) == counts
    assert pillar.hits_of(draw) == hits


def test_hits_value_domain_is_only_0_3_4():
    """n1+n2+n3=5 且每項 ≥1 的整數分割只有 {1,2,2} 與 {1,1,3}。"""
    assert set(pillar.hit_ways(39, 5)) == {0, 3, 4}


def test_broken_pillars():
    assert pillar.broken_pillars((3, 2, 0)) == [3]
    assert pillar.broken_pillars((0, 0, 5)) == [1, 2]
    assert pillar.broken_pillars((1, 2, 2)) == []


# ── 機率:對照 SPEC §4.5 的組合數表 ───────────────────────
def test_outcome_ways_matches_spec_table():
    ways = pillar.outcome_ways(39, 5)
    assert ways[(1, 1, 3)] == 102_600
    assert ways[(1, 3, 1)] == 21_600
    assert ways[(3, 1, 1)] == 16_800
    assert ways[(1, 2, 2)] == 76_950
    assert ways[(2, 1, 2)] == 68_400
    assert ways[(2, 2, 1)] == 32_400


def test_ways_sum_to_total_combinations():
    assert sum(pillar.outcome_ways(39, 5).values()) == comb(39, 5) == 575_757


def test_hit_ways_aggregate():
    ways = pillar.hit_ways(39, 5)
    assert ways[4] == 177_750
    assert ways[3] == 141_000
    assert ways[0] == 257_007
    assert ways[3] + ways[4] == 318_750


def test_pass_prob_is_5536_percent():
    assert pillar.pass_prob(39, 5) == pytest.approx(0.553619, abs=1e-6)


def test_expected_hits_two_independent_paths():
    """列舉柱分佈 vs 三合包牌 —— 兩條路徑必須算出同一個數。"""
    by_enumeration = pillar.expected_hits(39, 5)
    by_packet = pillar.total_bets(39) * comb(5, 3) / comb(39, 3)
    assert by_enumeration == pytest.approx(by_packet, rel=1e-12)
    assert by_enumeration == pytest.approx(1.96958, abs=1e-5)


# ── 損益 ─────────────────────────────────────────────────
def test_breakeven_prize_equals_fair_odds_of_one_three_combo():
    """1800碰 的兩平點恆等於單注三合的公平賠率 C(39,3)/C(5,3) = 913.9。"""
    assert pillar.breakeven_prize(1.0) == pytest.approx(comb(39, 3) / comb(5, 3))
    assert pillar.breakeven_prize(1.0) == pytest.approx(913.9, abs=1e-9)
    # 線性:每注成本 25 時兩平派彩就是 25 倍
    assert pillar.breakeven_prize(25.0) == pytest.approx(913.9 * 25)


def test_official_odds_are_negative_ev():
    c, p = pillar.OFFICIAL_COST_PER_BET, pillar.OFFICIAL_PRIZE_PER_BET
    assert pillar.round_cost(c) == 45_000
    assert pillar.return_rate(c, p) == pytest.approx(0.4924, abs=1e-4)
    assert pillar.expected_net(c, p) == pytest.approx(-22_842, abs=1.0)


def test_spec_default_odds_are_absurd():
    """SPEC §8.1:原站預設 1 / 5700 會算出 623.7% 返還率,不可能存在。"""
    assert pillar.return_rate(1.0, 5700.0) == pytest.approx(6.237, abs=1e-3)
    assert pillar.expected_net(1.0, 5700.0) == pytest.approx(9_426.6, abs=1.0)


@pytest.mark.parametrize("hits, net", [(4, 0), (3, -11_250), (0, -45_000)])
def test_settle_official(hits, net):
    r = pillar.settle(hits, pillar.OFFICIAL_COST_PER_BET,
                      pillar.OFFICIAL_PRIZE_PER_BET)
    assert r["net"] == pytest.approx(net)


def test_settle_scales_with_multiplier():
    one = pillar.settle(4, 25, 11_250, multiplier=1)
    three = pillar.settle(4, 25, 11_250, multiplier=3)
    assert three["cost"] == one["cost"] * 3
    assert three["payout"] == one["payout"] * 3


def test_recovery_is_infeasible_at_official_odds():
    """官方盤口下中四碰剛好打平,所以永遠追不回過去的虧損。"""
    assert pillar.best_case_net_per_multiple(25, 11_250) == 0
    res = pillar.multiplier_for_recovery(100_000, 25, 11_250)
    assert res["feasible"] is False


def test_recovery_multiplier_when_payout_is_better():
    """中四碰每倍淨利 5,000 時,追 12,000 的虧損要 3 倍。"""
    gain = pillar.best_case_net_per_multiple(25, 12_500)
    assert gain == 4 * 12_500 - 45_000 == 5_000
    res = pillar.multiplier_for_recovery(12_000, 25, 12_500)
    assert res["feasible"] and res["multiplier"] == 3
    assert res["cost"] == 3 * 45_000


def test_recovery_uses_base_when_nothing_to_chase():
    res = pillar.multiplier_for_recovery(0, 25, 12_500, base=2)
    assert res["multiplier"] == 2


# ── 適用範圍 ─────────────────────────────────────────────
def test_supports_only_39_pick_5():
    assert pillar.supports(games.LOTTO539)
    assert pillar.supports(games.FANTASY5)
    assert not pillar.supports(games.MARKSIX)      # 49選6,結構完全不同


# ── 歷史檢驗 ─────────────────────────────────────────────
def test_history_stats_basic():
    draws = [
        [1, 2, 3, 4, 5],            # 槓龜(第一、二柱斷)
        [5, 12, 18, 23, 31],        # 中四碰
        [12, 23, 31, 35, 38],       # 中三碰
        [10, 11, 12, 20, 21],       # 槓龜(第三柱斷)
    ]
    s = pillar.history_stats(draws)
    assert s["rounds"] == 4
    assert s["passes"] == 2
    assert s["pass_rate"] == 0.5
    assert s["hit_counts"] == {0: 2, 3: 1, 4: 1}
    assert s["streak"] == 1                 # 最新那期槓龜
    assert s["max_streak"] == 1
    assert s["last_broken"] == [3]


def test_history_stats_streak_counts_back_from_newest():
    draws = [[5, 12, 18, 23, 31]] + [[1, 2, 3, 4, 5]] * 3
    s = pillar.history_stats(draws)
    assert s["streak"] == 3 and s["max_streak"] == 3


def test_history_stats_skips_incomplete_rows_without_losing_last_broken():
    """SPEC §8.9:原站最近一期資料不完整就記不到斷柱;這裡不該有那個洞。"""
    draws = [[5, 12, 18, 23, 31], [10, 11, 12, 20, 21], [1, 2, 3]]
    s = pillar.history_stats(draws)
    assert s["rounds"] == 2 and s["skipped"] == 1
    assert s["last_broken"] == [3]          # 取最後一筆「有效」期
    assert s["streak"] == 1


def test_history_stats_empty():
    s = pillar.history_stats([])
    assert s["rounds"] == 0 and s["pass_rate"] == 0.0 and s["last_broken"] == []


# ── 流水表的欄位對應 ─────────────────────────────────────
# 1800碰 沒有自己的資料表,是借用二合的 erhe_rounds:
#   numbers → 總注數(1800)   cars → 倍數   hits → 命中注數(0/3/4)
#   payout_rate → 每注派彩,回收 = hits × cars × payout_rate
# 整個設計成立與否就靠這個對應,所以在這裡釘死。
@pytest.fixture()
def db(tmp_path, monkeypatch):
    from core import storage
    monkeypatch.setattr(storage, "_db_path", lambda: tmp_path / "erhe_state.db")
    return storage


def _bet(storage, hits, mult=1, cost_per_bet=25.0, prize=11_250.0):
    return storage.add_round(
        "u", "lotto539", "2026-08-01", pillar.total_bets(39), mult, hits,
        pillar.round_cost(cost_per_bet, mult), prize, mode=storage.PILLAR)


@pytest.mark.parametrize("hits, mult, net", [
    (4, 1, 0), (3, 1, -11_250), (0, 1, -45_000), (4, 3, 0), (3, 2, -22_500),
])
def test_ledger_matches_pillar_settlement(db, hits, mult, net):
    _bet(db, hits, mult)
    row = db.load_rounds("u", db.PILLAR)[0]
    expect = pillar.settle(hits, 25.0, 11_250.0, mult)
    assert row["cost"] == expect["cost"]
    assert row["payout"] == expect["payout"]
    assert row["net"] == expect["net"] == net


def test_pending_round_settles_on_fill(db):
    """待開獎先記成本;回填時依當初存的每注派彩結算,不必再帶價碼進來。"""
    rid = _bet(db, None, mult=2)
    row = db.load_rounds("u", db.PILLAR)[0]
    assert row["pending"] and row["net"] == -90_000
    db.update_round_result(rid, 3)
    row = db.load_rounds("u", db.PILLAR)[0]
    assert row["payout"] == 3 * 2 * 11_250 == 67_500
    assert row["net"] == 67_500 - 90_000


def test_pillar_ledger_is_separate_from_erhe(db):
    """清 1800碰 不能動到單顆 / 多顆的紀錄,但累積損益是共用池。"""
    _bet(db, 0)
    db.add_round("u", "lotto539", "2026-08-02", 5, 3, 0, 41_325.0, 21_200.0,
                 mode=db.MULTI)
    assert len(db.load_rounds("u", db.PILLAR)) == 1
    assert len(db.load_rounds("u", db.MULTI)) == 1
    assert db.current_cumulative("u") == -45_000 - 41_325     # 共用池
    db.reset("u", db.PILLAR)
    assert db.load_rounds("u", db.PILLAR) == []
    assert len(db.load_rounds("u", db.MULTI)) == 1
