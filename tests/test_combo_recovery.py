"""同一局同時下多款的回本試算(core.erhe.simultaneous_recovery)測試。

核心結論:要求「任一款中 1 顆就把虧損 + 本局總成本全部拿回」時,
成本係數 k = Σ(押幾顆 × 每車成本 ÷ 中獎可得) 必須 < 1,否則無解。
"""
import pytest

from core import erhe, games

# 使用者實際的盤口
S539 = (2755.0, 21200.0)     # (每車成本, 中獎可得)
SHK = (3528.0, 28500.0)


def _plans(n, *odds):
    return {f"g{i}": (n, c, w) for i, (c, w) in enumerate(odds)}


# ── k 係數 ───────────────────────────────────────────────
def test_k_matches_formula():
    plans = _plans(5, S539)
    assert erhe.combo_cost_ratio(plans) == pytest.approx(5 * 2755 / 21200)


def test_k_scales_linearly_with_numbers():
    k1 = erhe.combo_cost_ratio(_plans(1, S539, SHK))
    k5 = erhe.combo_cost_ratio(_plans(5, S539, SHK))
    assert k5 == pytest.approx(5 * k1)


def test_three_games_at_five_numbers_is_infeasible():
    """使用者目前設定(三款各押 5 顆)同時下 → k ≈ 1.92,無解。"""
    plans = _plans(5, S539, S539, SHK)
    k = erhe.combo_cost_ratio(plans)
    assert k > 1.0
    res = erhe.simultaneous_recovery(-52920, plans)
    assert res["feasible"] is False
    assert res["cars"] == {}


def test_single_game_at_five_numbers_is_feasible():
    plans = _plans(5, S539)
    res = erhe.simultaneous_recovery(-52920, plans, base_cars=3)
    assert res["feasible"] is True
    assert res["cars"]["g0"] == 8            # ⌈52920 / (21200 − 5×2755)⌉ = 8
    assert res["total_cost"] == pytest.approx(5 * 8 * 2755)
    assert res["worst_after"] >= 0


# ── 解出來的車數必須真的能回本 ────────────────────────────
@pytest.mark.parametrize("loss", [-10_000, -52_920, -250_000, -1_000_000])
@pytest.mark.parametrize("n", [1, 2, 3])
def test_solution_recovers_whatever_hits(loss, n):
    """任何一款中 1 顆,扣掉當天全部成本後都必須 >= 0。"""
    plans = _plans(n, S539, S539, SHK)
    res = erhe.simultaneous_recovery(loss, plans, base_cars=3)
    if not res["feasible"]:
        pytest.skip("此顆數下無解")
    total = res["total_cost"]
    for g, (_n, _c, w) in plans.items():
        after = loss + res["cars"][g] * w - total
        assert after >= 0, f"{g} 中 1 顆卻沒回本:{after}"
    assert res["worst_after"] >= 0


def test_total_cost_matches_cars():
    plans = _plans(2, S539, SHK)
    res = erhe.simultaneous_recovery(-100_000, plans, base_cars=3)
    expected = sum(n * res["cars"][g] * c for g, (n, c, _w) in plans.items())
    assert res["total_cost"] == pytest.approx(expected)


def test_recovered_returns_base_cars():
    plans = _plans(5, S539, SHK)
    res = erhe.simultaneous_recovery(+5000, plans, base_cars=3)
    assert res["recovered"] is True and res["feasible"] is True
    assert set(res["cars"].values()) == {3}


def test_empty_plans():
    res = erhe.simultaneous_recovery(-1000, {})
    assert res["feasible"] is True and res["cars"] == {}


# ── 可押顆數上限 ─────────────────────────────────────────
def test_max_numbers_for_combo():
    assert erhe.max_numbers_for_combo({"a": S539}) == 7
    assert erhe.max_numbers_for_combo({"a": S539, "b": SHK}) == 3
    assert erhe.max_numbers_for_combo({"a": S539, "b": S539, "c": SHK}) == 2


def test_max_numbers_is_actually_feasible():
    """回傳的顆數上限必須真的可解,再多一顆就不可解。"""
    odds = {"a": S539, "b": S539, "c": SHK}
    n_max = erhe.max_numbers_for_combo(odds)
    ok = {k: (n_max,) + v for k, v in odds.items()}
    bad = {k: (n_max + 1,) + v for k, v in odds.items()}
    assert erhe.simultaneous_recovery(-52920, ok)["feasible"] is True
    assert erhe.simultaneous_recovery(-52920, bad)["feasible"] is False


def test_real_game_defaults_are_wired_up():
    """用啟用中三款的實際預設盤口跑一次,確認接線正確。"""
    odds = {g.key: (g.default_cost_per_car, g.default_win_payout)
            for g in games.GAMES.values()}
    assert set(odds) == {"lotto539", "fantasy5", "marksix"}
    n = len(odds)
    assert erhe.max_numbers_for_combo(odds) == 2                       # 嚴格
    assert erhe.max_numbers_for_combo(odds, margin=n * 0.999) == 7      # 平攤(m=3)
    plans = {k: (2,) + v for k, v in odds.items()}
    res = erhe.simultaneous_recovery(-52920, plans, base_cars=3)
    assert res["feasible"] is True
    assert set(res["cars"]) == {"lotto539", "fantasy5", "marksix"}


# ── 固定部分款的車數(使用者自己填)後重解 ──────────────────
def test_fixed_game_lowers_others_cost():
    """把一款的車數壓低,當天總成本變小,其餘款的建議車數也跟著變少。"""
    plans = _plans(2, S539, S539, SHK)
    auto = erhe.simultaneous_recovery(-135_570, plans, base_cars=3)
    low = erhe.simultaneous_recovery(-135_570, plans, base_cars=3,
                                     fixed={"g0": 5})
    assert low["cars"]["g0"] == 5
    assert low["cars"]["g1"] < auto["cars"]["g1"]
    assert low["cars"]["g2"] < auto["cars"]["g2"]
    assert low["total_cost"] < auto["total_cost"]


def test_fixed_game_raises_others_cost():
    """把一款的車數拉高,當天成本變大,其餘款必須跟著加碼才追得回來。"""
    plans = _plans(2, S539, S539, SHK)
    auto = erhe.simultaneous_recovery(-135_570, plans, base_cars=3)
    high = erhe.simultaneous_recovery(-135_570, plans, base_cars=3,
                                      fixed={"g0": auto["cars"]["g0"] * 2})
    assert high["cars"]["g1"] > auto["cars"]["g1"]
    assert high["cars"]["g2"] > auto["cars"]["g2"]
    assert high["short"] == []          # 加碼後所有款仍都回得了本


def test_underfunded_fixed_game_reported_in_short():
    """自己把車數填太少的那款會被列進 short,其他款不受影響仍達標。"""
    plans = _plans(2, S539, S539, SHK)
    res = erhe.simultaneous_recovery(-135_570, plans, base_cars=3, fixed={"g0": 5})
    assert res["feasible"] is True
    assert res["short"] == ["g0"]
    for g in ("g1", "g2"):
        after = -135_570 + res["cars"][g] * plans[g][2] - res["total_cost"]
        assert after >= 0


def test_all_fixed_just_evaluates():
    """三款全部自己填時不需要解方程,只回報結果與哪幾款回不了本。"""
    plans = _plans(2, S539, S539, SHK)
    fixed = {"g0": 20, "g1": 20, "g2": 20}
    res = erhe.simultaneous_recovery(-135_570, plans, base_cars=3, fixed=fixed)
    assert res["feasible"] is True and res["cars"] == fixed
    assert res["total_cost"] == pytest.approx(
        sum(n * 20 * c for n, c, _w in plans.values()))
    assert set(res["short"]) == {"g0", "g1"}     # 539 兩款回收較低,回不了本


def test_fixed_game_does_not_make_combo_infeasible():
    """只有「未固定」的款才算進 k;把兩款固定住,剩一款就有解了。"""
    plans = _plans(5, S539, S539, SHK)           # 全自動時 k=1.92 無解
    assert erhe.simultaneous_recovery(-52_920, plans)["feasible"] is False
    res = erhe.simultaneous_recovery(-52_920, plans, fixed={"g0": 3, "g1": 3})
    assert res["feasible"] is True
    assert res["k"] == pytest.approx(5 * 3528 / 28500)   # 只剩六合彩進 k


def test_fixed_solution_still_recovers_free_games():
    """固定幾款之後,解出來的那些款仍必須真的回本。"""
    plans = _plans(2, S539, S539, SHK)
    for loss in (-10_000, -135_570, -800_000):
        res = erhe.simultaneous_recovery(loss, plans, base_cars=3, fixed={"g2": 7})
        total = res["total_cost"]
        for g in ("g0", "g1"):
            assert loss + res["cars"][g] * plans[g][2] - total >= 0


def test_fixed_ignores_unknown_keys():
    plans = _plans(2, S539)
    res = erhe.simultaneous_recovery(-50_000, plans, fixed={"不存在": 99})
    assert set(res["cars"]) == {"g0"}


# ── 責任分母 share:嚴格(m=1)vs 平攤(m=N)──────────────
def test_share_one_equals_strict():
    """share=1 就是原本的嚴格模式,結果必須完全相同。"""
    plans = _plans(2, S539, S539, SHK)
    a = erhe.simultaneous_recovery(-135_570, plans, base_cars=1)
    b = erhe.simultaneous_recovery(-135_570, plans, base_cars=1, share=1)
    assert a["cars"] == b["cars"] and a["total_cost"] == b["total_cost"]


def test_single_game_share_is_identical():
    """只下一款時 N=1,平攤與嚴格是同一條式子,也等於「單押回本」。"""
    plans = _plans(5, S539)
    strict = erhe.simultaneous_recovery(-41_325, plans, base_cars=1, share=1)
    share = erhe.simultaneous_recovery(-41_325, plans, base_cars=1, share=1)
    assert strict["cars"] == share["cars"]
    # 對照封閉解 ⌈L / (w − n·c)⌉
    per1 = erhe.per_car_one_hit_net(5, 2755.0, 21200.0)
    assert strict["cars"]["g0"] == -(-41_325 // int(per1))


def test_share_makes_infeasible_combo_solvable():
    """三款各押 5 顆時 k=1.92:嚴格無解,平攤(m=3)有解。"""
    plans = _plans(5, S539, S539, SHK)
    assert erhe.simultaneous_recovery(-135_570, plans, share=1)["feasible"] is False
    res = erhe.simultaneous_recovery(-135_570, plans, base_cars=1, share=3)
    assert res["feasible"] is True and res["k"] > 1.0
    assert res["share"] == 3


@pytest.mark.parametrize("loss", [-10_000, -135_570, -900_000])
def test_share_solution_meets_each_quota(loss):
    """平攤解出來的車數,每款中 1 顆都必須拿回自己那份 (L+T)/N。"""
    plans = _plans(2, S539, S539, SHK)
    n = len(plans)
    res = erhe.simultaneous_recovery(loss, plans, base_cars=1, share=n)
    quota = (-loss + res["total_cost"]) / n
    for g, (_n, _c, w) in plans.items():
        assert res["cars"][g] * w >= quota - 1e-6
    assert res["short"] == []


def test_share_all_hit_recovers_but_single_hit_does_not():
    """平攤的代價:全中才回本,只中一款會更慘 —— 這正是要誠實顯示的數字。"""
    plans = _plans(5, S539, S539, SHK)
    res = erhe.simultaneous_recovery(-135_570, plans, base_cars=1, share=3)
    assert res["all_hit_after"] >= 0          # 三款都中 1 顆 → 回本
    assert res["worst_after"] < -135_570      # 只中一款 → 比原本更差


def test_share_is_cheaper_than_strict():
    """平攤的總成本必定低於嚴格(責任被拆開了)。"""
    plans = _plans(2, S539, S539, SHK)
    strict = erhe.simultaneous_recovery(-135_570, plans, base_cars=1, share=1)
    share = erhe.simultaneous_recovery(-135_570, plans, base_cars=1, share=3)
    assert share["total_cost"] < strict["total_cost"]


def test_share_infeasible_when_k_exceeds_m():
    """k 大到超過款數時,連平攤都無解。"""
    plans = _plans(8, S539, S539, SHK)        # k = 8×0.384 ≈ 3.07 > 3
    res = erhe.simultaneous_recovery(-50_000, plans, share=3)
    assert res["feasible"] is False and res["k"] >= 3


def test_max_numbers_margin_follows_share():
    """可押顆數上限要跟著責任分母放寬。"""
    odds = {"a": S539, "b": S539, "c": SHK}
    assert erhe.max_numbers_for_combo(odds) == 2                    # 嚴格
    assert erhe.max_numbers_for_combo(odds, margin=3 * 0.999) == 7  # 平攤(m=3)
    plans = {k: (7,) + v for k, v in odds.items()}
    assert erhe.simultaneous_recovery(-50_000, plans, share=3)["feasible"] is True


def test_share_with_fixed_cars():
    """平攤時也能固定某幾款的車數,其餘款照樣重解。"""
    plans = _plans(2, S539, S539, SHK)
    res = erhe.simultaneous_recovery(-135_570, plans, base_cars=1, share=3,
                                     fixed={"g0": 30})
    assert res["cars"]["g0"] == 30
    quota = (135_570 + res["total_cost"]) / 3
    for g in ("g1", "g2"):
        assert res["cars"][g] * plans[g][2] >= quota - 1e-6
