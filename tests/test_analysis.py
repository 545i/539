"""core.analysis 的統計檢定:確定性 + 各項數值合理性。

重點:同一份資料 + 同一範圍 → 同一結果(含變異數模擬的固定種子),因為使用者
要求「切回同一區間答案一致」。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core import analysis as an


def _make_df(periods: int = 60, num_max: int = 39, pick: int = 5,
             seed: int = 1) -> pd.DataFrame:
    """造一份假開獎資料(每期 pick 個不重複號 + 遞增日期 + 期號)。"""
    rng = np.random.default_rng(seed)
    rows = []
    base = pd.Timestamp("2026-01-01")
    for i in range(periods):
        draw = sorted(rng.choice(range(1, num_max + 1), size=pick, replace=False))
        row = {"date": base + pd.Timedelta(days=i), "issue": f"{100000 + i}"}
        for j, n in enumerate(draw, 1):
            row[f"n{j}"] = int(n)
        rows.append(row)
    return pd.DataFrame(rows)


def test_slice_range_periods():
    df = _make_df(60)
    assert len(an.slice_range(df, "periods", 30)) == 30
    assert len(an.slice_range(df, "periods", 999)) == 60   # 超過就全取


def test_slice_range_days():
    df = _make_df(60)   # 每天一期,60 天
    sub = an.slice_range(df, "days", 10)
    # 最後一天往回 10 天 → 11 期(含端點)
    assert 10 <= len(sub) <= 12


def test_counts_total_equals_periods_times_pick():
    df = _make_df(40, pick=5)
    c = an.counts(df, 39, 5)
    assert sum(c.values()) == 40 * 5


def test_analyze_is_deterministic():
    df = _make_df(50, seed=7)
    a = an.analyze(df, 39, 5, "periods", 50)
    b = an.analyze(df, 39, 5, "periods", 50)
    assert a == b, "同資料同範圍必須得到完全相同的結果(含變異數模擬)"


def test_uniformity_and_independence_valid_pvalues():
    df = _make_df(80, seed=3)
    u = an.uniformity(df, 39, 5)
    ind = an.independence(df, 39, 5)
    assert 0.0 <= u["p"] <= 1.0 and u["dof"] == 38
    assert 0.0 <= ind["p"] <= 1.0
    assert isinstance(ind["independent"], bool)   # 不能是 numpy bool(JSON 會壞)


def test_random_data_looks_uniform():
    # 大量真正隨機資料 → 均勻度檢定通常不會拒絕(p 偏大);偶爾誤判,放寬門檻
    df = _make_df(400, seed=11)
    u = an.uniformity(df, 39, 5)
    assert u["p"] > 0.001


def test_contribution_sorted_and_pct_sums_reasonable():
    df = _make_df(50, seed=5)
    con = an.contribution(df, 39, 5, top=39)
    contribs = [r["contrib"] for r in con["rows"]]
    assert contribs == sorted(contribs, reverse=True)   # 由大到小
    assert all(r["dir"] in ("熱", "冷", "平") for r in con["rows"])


def test_pearson_features_present():
    df = _make_df(50)
    pe = an.pearson_serial(df, 39, 5)
    names = {f["feature"] for f in pe["features"]}
    assert names == {"和值", "奇數個數", "大數個數"}
    assert all(-1.0 <= f["r"] <= 1.0 for f in pe["features"])


def test_variance_sim_percentile_in_range():
    df = _make_df(50, seed=9)
    v = an.variance_sim(df, 39, 5, runs=500)
    assert 0.0 <= v["percentile"] <= 100.0
    assert v["sim_lo"] <= v["sim_hi"]


def test_empty_df_no_crash():
    df = _make_df(0)
    res = an.analyze(df, 39, 5, "periods", 30)
    assert res["periods"] == 0
    assert res["uniformity"]["p"] == 1.0
