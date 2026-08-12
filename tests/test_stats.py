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


# ── 直柱(選號單上的直行)遺漏提醒 ────────────────────────
def _df(draws):
    """把幾期開獎號碼包成 DataFrame(舊 → 新)。"""
    return pd.DataFrame([
        {"date": f"2026-01-{i + 1:02d}", **{f"n{j + 1}": n for j, n in enumerate(d)}}
        for i, d in enumerate(draws)
    ])


def test_columns_are_the_units_digit_groups():
    """選號單一列 10 格,所以一個直行就是尾數相同的那一群。"""
    cols = stats.columns(39)
    assert cols[1] == [1, 11, 21, 31]
    assert cols[0] == [10, 20, 30]
    assert cols[9] == [9, 19, 29, 39]
    assert stats.column_label(1, 39) == "01 11 21 31"


def test_columns_cover_every_number_exactly_once():
    cols = stats.columns(39)
    flat = [n for nums in cols.values() for n in nums]
    assert sorted(flat) == list(range(1, 40))


def test_columns_scale_to_marksix():
    cols = stats.columns(49)
    assert cols[1] == [1, 11, 21, 31, 41]
    assert cols[0] == [10, 20, 30, 40]


def test_column_missing_counts_consecutive_draws():
    """整行都沒中才累計;那一行有任何一個號碼開出就歸零。"""
    draws = [
        [1, 2, 3, 4, 5],        # 尾數 1 有開(01)
        [2, 3, 4, 5, 6],
        [2, 3, 4, 5, 6],
        [2, 3, 4, 5, 6],
        [2, 3, 4, 5, 6],
    ]
    got = stats.column_missing(_df(draws), 39)
    assert got[1]["current"] == 4      # 最後四期尾數 1 那行都沒開
    assert got[2]["current"] == 0      # 每期都有 02


def test_column_missing_resets_on_any_number_in_the_column():
    draws = [[2, 3, 4, 5, 6]] * 3 + [[31, 2, 3, 4, 5]] + [[2, 3, 4, 5, 6]] * 2
    got = stats.column_missing(_df(draws), 39)
    assert got[1]["current"] == 2      # 31 之後才過兩期
    assert got[1]["max_gap"] == 3      # 31 之前那三期是歷史最長


def test_column_alerts_fire_at_four_draws():
    """需求就是這條:連續四期整行沒開要跳提醒。"""
    draws = [[1, 2, 3, 4, 5]] + [[2, 3, 4, 5, 6]] * 4
    alerts = stats.column_alerts(_df(draws), 39)
    cols = {a["col"] for a in alerts}
    assert 1 in cols
    hit = next(a for a in alerts if a["col"] == 1)
    assert hit["current"] == 4
    assert hit["label"] == "01 11 21 31"


def test_column_alerts_quiet_at_three_draws():
    draws = [[1, 2, 3, 4, 5]] + [[2, 3, 4, 5, 6]] * 3
    assert 1 not in {a["col"] for a in stats.column_alerts(_df(draws), 39)}


def test_column_alerts_sorted_by_how_long():
    draws = [[1, 2, 3, 4, 5], [2, 3, 4, 5, 6]] + [[3, 4, 5, 6, 7]] * 5
    alerts = stats.column_alerts(_df(draws), 39)
    assert [a["current"] for a in alerts] == sorted(
        [a["current"] for a in alerts], reverse=True)


def test_column_alerts_threshold_is_adjustable():
    draws = [[1, 2, 3, 4, 5]] + [[2, 3, 4, 5, 6]] * 2
    assert 1 in {a["col"] for a in stats.column_alerts(_df(draws), 39, threshold=2)}
