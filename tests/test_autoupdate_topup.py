"""catch_up 的「官方 top-up」:彩世界(tof)慢一期時,最新一期仍由官方補上。

2026-08 曾因彩世界只到 8/25、程式採信它而不再問官方,漏掉官方已有的 8/26。
這裡把兩個來源都換成假的:tof 停在 8/25、官方有 8/26,驗 catch_up 會補上 8/26。
"""
import datetime as dt

import pytest

from core import autoupdate, loader


def _row(date: str, issue: str, nums):
    # 真實 scraper 回的 date 是日期物件(catch_up 會拿它跟 date 比較),測試比照
    return {"date": dt.date.fromisoformat(date), "issue": issue,
            **{f"n{i + 1}": nums[i] for i in range(5)}}


@pytest.fixture()
def csv_to_25(tmp_path):
    """初始資料到 8/25(206)。"""
    p = tmp_path / "history.csv"
    p.write_text(
        "date,issue,n1,n2,n3,n4,n5\n"
        "2026-06-01,115000150,1,2,3,4,5\n"     # 夠舊的錨點,讓 tof「涵蓋得到落差」
        "2026-08-22,115000204,9,10,29,30,34\n"
        "2026-08-24,115000205,9,10,19,23,26\n"
        "2026-08-25,115000206,8,21,23,30,35\n"
    )
    return p


def test_official_topup_adds_latest_when_tof_lags(csv_to_25, monkeypatch):
    # 彩世界:涵蓋落差區間但**只到 8/25**(慢一期)
    tof_rows = [
        _row("2026-06-01", "115000150", [1, 2, 3, 4, 5]),   # 夠舊,oldest<=start
        _row("2026-08-24", "115000205", [9, 10, 19, 23, 26]),
        _row("2026-08-25", "115000206", [8, 21, 23, 30, 35]),
    ]
    monkeypatch.setattr(autoupdate.scraper_tof, "fetch_history",
                        lambda *a, **k: tof_rows)
    # 官方台彩月 API:有 8/26(207)
    official = [
        _row("2026-08-25", "115000206", [8, 21, 23, 30, 35]),
        _row("2026-08-26", "115000207", [13, 19, 23, 35, 38]),
    ]
    monkeypatch.setattr(autoupdate.scraper, "fetch_month",
                        lambda y, m, **k: official)

    res = autoupdate.catch_up("lotto539", csv_to_25)

    assert res["latest"] == dt.date(2026, 8, 26)     # top-up 補上了最新期
    assert res["added"] == 1
    df = loader.load_history(csv_to_25, 5, 39)
    assert "115000207" in set(df["issue"].astype(str))


def test_topup_failure_does_not_break(csv_to_25, monkeypatch):
    """官方 top-up 掛掉不能拖垮整個更新 —— 至少保住彩世界那份。"""
    tof_rows = [
        _row("2026-06-01", "115000150", [1, 2, 3, 4, 5]),
        _row("2026-08-25", "115000206", [8, 21, 23, 30, 35]),
    ]
    monkeypatch.setattr(autoupdate.scraper_tof, "fetch_history",
                        lambda *a, **k: tof_rows)

    def _boom(*a, **k):
        raise autoupdate.scraper.ScrapeError("官方掛了")
    monkeypatch.setattr(autoupdate.scraper, "fetch_month", _boom)

    res = autoupdate.catch_up("lotto539", csv_to_25)   # 不應拋例外
    assert res["latest"] == dt.date(2026, 8, 25)       # 沿用既有最新,不倒
