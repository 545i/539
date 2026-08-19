"""區間組合提醒 stats.tens_pair_alerts 的邊界測試。

十位分四段:band0=01~09、band1=10~19、band2=20~29、band3=30~39。
判定:兩段連續幾期都沒開;streak >= threshold 才 alert。
"""
from __future__ import annotations

import pandas as pd

from core import stats


def _df(rows: list[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["date", "n1", "n2", "n3", "n4", "n5"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def _pair(res: list[dict], a: str, b: str) -> dict:
    want = {a, b}
    return next(r for r in res if set(r["labels"]) == want)


def test_six_pairs_and_labels():
    # 4 段 → C(4,2)=6 組配對,標籤為 01/11/21/31
    df = _df([("2024-01-01", 1, 12, 23, 34, 5)])
    res = stats.tens_pair_alerts(df)
    assert len(res) == 6
    labels = {tuple(sorted(r["labels"])) for r in res}
    assert ("01", "11") in labels and ("21", "31") in labels


def test_streak_counts_consecutive_double_absence():
    # 三期都只開 band0(01~09)→ band1/band2/band3 兩兩都連續 3 期缺席
    df = _df([
        ("2024-01-01", 1, 2, 3, 4, 5),
        ("2024-01-02", 1, 2, 3, 4, 5),
        ("2024-01-03", 1, 2, 3, 4, 5),
    ])
    res = stats.tens_pair_alerts(df, threshold=3)
    assert _pair(res, "11", "21")["streak"] == 3
    assert _pair(res, "11", "21")["alert"] is True
    # 含 band0 的配對每期都有 band0 → streak 0
    assert _pair(res, "01", "11")["streak"] == 0
    assert _pair(res, "01", "11")["alert"] is False


def test_threshold_boundary_two_not_alerted_three_alerted():
    two = _df([("2024-01-01", 1, 2, 3, 4, 5), ("2024-01-02", 1, 2, 3, 4, 5)])
    assert _pair(stats.tens_pair_alerts(two), "21", "31")["streak"] == 2
    assert _pair(stats.tens_pair_alerts(two), "21", "31")["alert"] is False

    three = _df([("2024-01-01", 1, 2, 3, 4, 5)] * 3)
    three["date"] = pd.to_datetime(
        ["2024-01-01", "2024-01-02", "2024-01-03"])
    assert _pair(stats.tens_pair_alerts(three), "21", "31")["alert"] is True


def test_streak_resets_on_appearance():
    # 最新一期 band2 有開(23)→ 含 band2 的配對 streak 歸零
    df = _df([
        ("2024-01-01", 1, 2, 3, 4, 5),
        ("2024-01-02", 1, 2, 3, 4, 5),
        ("2024-01-03", 1, 2, 3, 4, 23),
    ])
    res = stats.tens_pair_alerts(df)
    assert _pair(res, "21", "31")["streak"] == 0
    # band1、band3 仍連續 3 期缺席
    assert _pair(res, "11", "31")["streak"] == 3
