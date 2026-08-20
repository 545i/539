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


# ── 自訂區間 interval_pair_alerts ─────────────────────────
def test_interval_pairs_custom_groups():
    # 三期都只開 01~09 → 自訂「10~20」與「21~39」兩區間連續 3 期都沒開
    df = _df([("2024-01-01", 1, 2, 3, 4, 5)] * 3)
    df["date"] = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
    groups = [
        {"label": "01~09", "nums": list(range(1, 10))},
        {"label": "10~20", "nums": list(range(10, 21))},
        {"label": "21~39", "nums": list(range(21, 40))},
    ]
    res = stats.interval_pair_alerts(df, groups, threshold=3)
    assert len(res) == 3  # C(3,2)
    pair = next(r for r in res if set(r["labels"]) == {"10~20", "21~39"})
    assert pair["streak"] == 3 and pair["alert"] is True
    # 含 01~09 的配對每期都有 01~09 → streak 0
    p2 = next(r for r in res if set(r["labels"]) == {"01~09", "10~20"})
    assert p2["streak"] == 0 and p2["alert"] is False


def test_interval_pairs_overlapping_allowed():
    # 區間可重疊(自訂):單號 vs 大號,只要當期兩者都沒開才累計
    df = _df([("2024-01-01", 2, 4, 6, 8, 10)])  # 全偶數、全小
    groups = [
        {"label": "單號", "nums": list(range(1, 40, 2))},
        {"label": "大號", "nums": list(range(20, 40))},
    ]
    res = stats.interval_pair_alerts(df, groups, threshold=1)
    assert res[0]["streak"] == 1 and res[0]["alert"] is True
