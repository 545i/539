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


# ── 特殊組合 combo_absence_alerts(整組缺席)──────────────
def test_combo_absence_whole_set_missing():
    # 三期都沒開到 {1,10,20,30} 任一顆 → 連續 3 期整組沒開
    df = _df([
        ("2024-01-01", 2, 3, 4, 5, 6),
        ("2024-01-02", 7, 8, 9, 11, 12),
        ("2024-01-03", 13, 14, 15, 16, 17),
    ])
    combos = [{"label": "01 10 20 30", "nums": [1, 10, 20, 30]}]
    res = stats.combo_absence_alerts(df, combos, threshold=3)
    assert res[0]["streak"] == 3 and res[0]["max_gap"] == 3
    assert res[0]["alert"] is True and res[0]["size"] == 4


def test_combo_absence_resets_when_any_member_drawn():
    # 最新一期開到 20(組內成員)→ streak 歸零,但歷史最長仍記到 2
    df = _df([
        ("2024-01-01", 2, 3, 4, 5, 6),
        ("2024-01-02", 7, 8, 9, 11, 12),
        ("2024-01-03", 20, 14, 15, 16, 17),
    ])
    combos = [{"label": "01 10 20 30", "nums": [1, 10, 20, 30]}]
    res = stats.combo_absence_alerts(df, combos, threshold=3)
    assert res[0]["streak"] == 0 and res[0]["max_gap"] == 2
    assert res[0]["alert"] is False


# ── 區間組合同時出現 combo_cooccurrence_alerts ────────────
_BANDS4 = [list(range(1, 10)), list(range(10, 20)),
           list(range(20, 30)), list(range(30, 40))]


def test_cooccurrence_streak_since_all_together():
    # 只有第一期四段同時開(1,10,20,30,其一補),之後兩期沒同時
    df = _df([
        ("2024-01-01", 1, 10, 20, 30, 5),   # 四段皆有 → 滿足
        ("2024-01-02", 1, 2, 3, 4, 5),      # 只有 01~09 → 不滿足
        ("2024-01-03", 11, 12, 13, 14, 15),  # 只有 10~19 → 不滿足
    ])
    combos = [{"label": "四段全開", "groups": _BANDS4}]
    res = stats.combo_cooccurrence_alerts(df, combos, threshold=2)
    assert res[0]["streak"] == 2       # 最近兩期沒全部同時
    assert res[0]["max_gap"] == 2
    assert res[0]["alert"] is True and res[0]["groups"] == 4


def test_cooccurrence_zero_when_latest_satisfies():
    df = _df([
        ("2024-01-01", 1, 2, 3, 4, 5),
        ("2024-01-02", 1, 10, 20, 30, 6),   # 最新一期四段皆有 → streak 0
    ])
    combos = [{"label": "四段全開", "groups": _BANDS4}]
    res = stats.combo_cooccurrence_alerts(df, combos, threshold=3)
    assert res[0]["streak"] == 0 and res[0]["alert"] is False


def test_cooccurrence_two_intervals():
    # 只看 10~19 與 30~39 是否同時出現
    df = _df([
        ("2024-01-01", 11, 31, 1, 2, 3),   # 兩段皆有 → 滿足
        ("2024-01-02", 11, 12, 13, 14, 15),  # 只有 10~19 → 不滿足
    ])
    combos = [{"label": "10~19+30~39",
               "groups": [list(range(10, 20)), list(range(30, 40))]}]
    res = stats.combo_cooccurrence_alerts(df, combos, threshold=1)
    assert res[0]["streak"] == 1 and res[0]["alert"] is True
