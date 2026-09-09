import pytest

from core import backtest, loader, picker


@pytest.fixture(scope="module")
def df():
    return loader.generate_sample(800, seed=42)


def test_pick_returns_valid_sets(df):
    for strat in picker.STRATEGIES:
        tickets = picker.pick(df, strategy=strat, sets=5, seed=1)
        assert len(tickets) == 5
        for t in tickets:
            assert len(set(t)) == 5
            assert all(1 <= n <= 39 for n in t)


def test_pick_reproducible(df):
    a = picker.pick(df, "hot", sets=3, seed=99)
    b = picker.pick(df, "hot", sets=3, seed=99)
    assert a == b


def test_balanced_meets_constraints(df):
    tickets = picker.pick(df, "balanced", sets=10, seed=5)
    for t in tickets:
        odd = sum(1 for n in t if n % 2 == 1)
        assert 2 <= odd <= 3


def test_pick_unknown_strategy_raises(df):
    with pytest.raises(ValueError):
        picker.pick(df, "magic")


def test_backtest_hit_distribution_complete(df):
    r = backtest.run(df, "random", start_index=100, seed=1)
    assert sum(r.hit_dist.values()) == r.periods
    assert r.total_bet == r.periods * 50


def test_backtest_roi_converges_near_minus_44(df):
    # 大樣本下,隨機策略報酬率應靠近理論 -44%(允許樣本波動)
    r = backtest.run(df, "random", start_index=100, seed=1)
    assert -0.85 < r.roi < 0.2  # 寬鬆界線,避免頭獎/貳獎偶發造成大波動


def test_backtest_no_lookahead(df, monkeypatch):
    """驗證選號時傳給 picker 的資料不含當期(防 look-ahead)。"""
    seen_lengths = []
    orig = picker.pick

    def spy(passed_df, **kwargs):
        seen_lengths.append(len(passed_df))
        return orig(passed_df, **kwargs)

    monkeypatch.setattr(backtest, "pick", spy)
    backtest.run(df, "random", start_index=100, seed=1)
    # 第一次選號用的是前 100 期,長度應為 100(不含第 100 期本身)
    assert seen_lengths[0] == 100
