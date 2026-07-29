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
    """用 GameConfig 的實際預設盤口跑一次,確認接線正確。"""
    odds = {g.key: (g.default_cost_per_car, g.default_win_payout)
            for g in games.GAMES.values()}
    assert erhe.max_numbers_for_combo(odds) == 2
    plans = {k: (2,) + v for k, v in odds.items()}
    res = erhe.simultaneous_recovery(-52920, plans, base_cars=3)
    assert res["feasible"] is True
    assert set(res["cars"]) == {"lotto539", "fantasy5", "marksix"}
