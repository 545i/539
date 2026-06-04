import pandas as pd

from core import stats


def _df(draws):
    rows = []
    d = pd.Timestamp("2024-01-01")
    for nums in draws:
        rows.append({"date": d, **{f"n{i+1}": nums[i] for i in range(5)}})
        d += pd.Timedelta(days=1)
    return pd.DataFrame(rows)


def test_frequency_counts():
    df = _df([[1, 2, 3, 4, 5], [1, 2, 3, 4, 6]])
    freq = stats.frequency(df)
    assert freq[1] == 2
    assert freq[5] == 1
    assert freq[6] == 1
    assert freq[39] == 0


def test_missing_current_gap():
    # 號碼 1 只在第一期出現,共 3 期 → 目前遺漏 2 期
    df = _df([[1, 2, 3, 4, 5], [6, 7, 8, 9, 10], [6, 7, 8, 9, 11]])
    miss = stats.missing(df)
    assert miss[1]["current"] == 2


def test_parity_and_sum():
    df = _df([[1, 3, 5, 7, 9]])  # 全奇數,和=25
    odd, big, sums = stats.parity_size_sum(df)
    assert odd[5] == 1
    assert sums == [25]
    assert big[0] == 1  # 全部 < 20


def test_consecutive_ratio():
    df = _df([[1, 2, 10, 20, 30], [5, 8, 15, 25, 35]])
    gaps, ratio = stats.gaps_consecutive(df)
    assert ratio == 0.5  # 只有第一期有連號(1,2)


def test_chi_square_dof_is_38():
    from core import loader
    df = loader.generate_sample(300, seed=11)
    r = stats.chi_square(df)
    assert r.dof == 38
    assert r.enough_data is True


def test_chi_square_flags_insufficient_data():
    from core import loader
    df = loader.generate_sample(10, seed=1)
    r = stats.chi_square(df)
    assert r.enough_data is False


def test_cooccurrence():
    df = _df([[1, 2, 3, 4, 5]])
    co = stats.cooccurrence(df)
    assert co[(1, 2)] == 1
    assert co[(4, 5)] == 1
