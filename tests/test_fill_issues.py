"""loader.fill_sequential_issues:六合彩缺期號依前一期 +1 自動補。"""
from __future__ import annotations

import pandas as pd

from core import loader


def _df(rows):
    """rows = [(date, issue), …] → DataFrame(含 n1..n6 佔位)。"""
    data = {"date": [pd.Timestamp(d) for d, _ in rows],
            "issue": [i for _, i in rows]}
    for j in range(1, 7):
        data[f"n{j}"] = [j for _ in rows]
    return pd.DataFrame(data)


def test_fills_missing_with_prev_plus_one():
    df = _df([("2026-08-22", "2026/092"), ("2026-08-25", "2026/093"),
              ("2026-08-27", ""), ("2026-08-29", "")])
    out = loader.fill_sequential_issues(df)
    assert out["issue"].tolist() == ["2026/092", "2026/093", "2026/094", "2026/095"]


def test_keeps_existing_issue_untouched():
    df = _df([("2026-08-25", "2026/093"), ("2026-08-27", "2026/999")])
    out = loader.fill_sequential_issues(df)
    assert out["issue"].tolist() == ["2026/093", "2026/999"]


def test_preserves_zero_pad_width():
    df = _df([("2026-08-25", "2026/007"), ("2026-08-27", "")])
    out = loader.fill_sequential_issues(df)
    assert out["issue"].tolist()[-1] == "2026/008"


def test_year_rollover_resets_to_001():
    df = _df([("2026-12-30", "2026/150"), ("2027-01-02", "")])
    out = loader.fill_sequential_issues(df)
    assert out["issue"].tolist()[-1] == "2027/001"


def test_leading_missing_stays_empty():
    # 開頭沒有任何可依的期號 → 補不了,留空(不亂編)
    df = _df([("2026-08-25", ""), ("2026-08-27", "2026/093")])
    out = loader.fill_sequential_issues(df)
    assert out["issue"].tolist() == ["", "2026/093"]


def test_idempotent():
    df = _df([("2026-08-25", "2026/093"), ("2026-08-27", "")])
    once = loader.fill_sequential_issues(df)
    twice = loader.fill_sequential_issues(once)
    assert once["issue"].tolist() == twice["issue"].tolist()
