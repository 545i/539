"""scraper 範圍抓取邏輯測試(不打網路,用 monkeypatch 模擬 fetch_month)。"""
import pandas as pd
import pytest

from core import scraper


def test_iter_months_basic():
    assert list(scraper.iter_months((2026, 4), (2026, 6))) == [
        (2026, 4), (2026, 5), (2026, 6)
    ]


def test_iter_months_reversed_autoswap():
    # 起訖顛倒時自動對調,結果仍為遞增序列
    assert list(scraper.iter_months((2026, 6), (2026, 4))) == [
        (2026, 4), (2026, 5), (2026, 6)
    ]


def test_iter_months_cross_year():
    assert list(scraper.iter_months((2025, 11), (2026, 2))) == [
        (2025, 11), (2025, 12), (2026, 1), (2026, 2)
    ]


def test_iter_months_single():
    assert list(scraper.iter_months((2026, 5), (2026, 5))) == [(2026, 5)]


def _row(date, n):
    return {"date": pd.Timestamp(date), "n1": n, "n2": n + 1, "n3": n + 2,
            "n4": n + 3, "n5": n + 4}


def test_fetch_range_merges_months(monkeypatch):
    def fake_fetch_month(year, month, timeout=10):
        return [_row(f"{year}-{month:02d}-15", month)]

    monkeypatch.setattr(scraper, "fetch_month", fake_fetch_month)
    rows, failures = scraper.fetch_range((2026, 4), (2026, 6))
    assert len(rows) == 3
    assert failures == []


def test_fetch_range_tolerates_partial_failure(monkeypatch):
    def fake_fetch_month(year, month, timeout=10):
        if month == 5:
            raise scraper.ScrapeError("該月無資料")
        return [_row(f"{year}-{month:02d}-15", month)]

    monkeypatch.setattr(scraper, "fetch_month", fake_fetch_month)
    rows, failures = scraper.fetch_range((2026, 4), (2026, 6))
    assert len(rows) == 2  # 4 月、6 月成功
    assert [f[1] for f in failures] == [5]  # 5 月失敗被記錄


def test_fetch_range_all_fail_raises(monkeypatch):
    def fake_fetch_month(year, month, timeout=10):
        raise scraper.ScrapeError("壞掉")

    monkeypatch.setattr(scraper, "fetch_month", fake_fetch_month)
    with pytest.raises(scraper.ScrapeError):
        scraper.fetch_range((2026, 4), (2026, 5))
