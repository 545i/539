"""彩世界(tof)爬蟲與期號去重測試。

這個來源的價值在於:日期是**台灣日期**、而且帶**期號**。
天天樂原本抓 lottolyzer 記加州當地日期,同一期在台灣看是隔天 ——
光比對日期與號碼看不出這種錯位,有期號才驗得出來。
"""
import datetime as dt

import pandas as pd
import pytest

from core import loader, scraper_tof

# 取自實際頁面的片段(天天樂三期、六合彩一期)
F5_HTML = """
<div class="draw-section">
  <div class="draw-date"> 08/07(五) &nbsp;&nbsp;11961期 </div>
  <div class="numbers-container numbox lottery-numbers Fantasy5">
    <span class="number N08">08</span><span class="number N17">17</span>
    <span class="number N28">28</span><span class="number N32">32</span>
    <span class="number N34">34</span></div>
</div>
<div class="draw-section">
  <div class="draw-date"> 08/06(四) &nbsp;&nbsp;11960期 </div>
  <div class="numbers-container numbox lottery-numbers Fantasy5">
    <span class="number N04">04</span><span class="number N10">10</span>
    <span class="number N35">35</span><span class="number N37">37</span>
    <span class="number N39">39</span></div>
</div>
<div class="draw-section">
  <div class="draw-date"> 12/31(三) &nbsp;&nbsp;11800期 </div>
  <div class="numbers-container numbox lottery-numbers Fantasy5">
    <span class="number N01">01</span><span class="number N02">02</span>
    <span class="number N03">03</span><span class="number N04">04</span>
    <span class="number N05">05</span></div>
</div>
"""

MARKSIX_HTML = """
<div class="draw-section">
  <div class="draw-date"> 08/06(四) &nbsp;&nbsp;2026/085期 </div>
  <div class="numbers-container numbox lottery-numbers MARKSIX">
    <span class="number N42">42</span><span class="number N24">24</span>
    <span class="number N29">29</span><span class="number N48">48</span>
    <span class="number N13">13</span><span class="number N30">30</span>
    <span class="number N03">03</span></div>
</div>
"""

TODAY = dt.date(2026, 8, 7)


def test_parses_date_issue_and_numbers():
    rows = scraper_tof.parse_history(F5_HTML, 5, 39, today=TODAY)
    latest = rows[-1]
    assert latest["date"] == dt.date(2026, 8, 7)
    assert latest["issue"] == "11961"
    assert [latest[f"n{i}"] for i in range(1, 6)] == [8, 17, 28, 32, 34]


def test_rows_sorted_oldest_first():
    rows = scraper_tof.parse_history(F5_HTML, 5, 39, today=TODAY)
    assert [r["date"] for r in rows] == sorted(r["date"] for r in rows)


def test_year_rolls_back_across_new_year():
    """只有 MM/DD 沒有年份:晚於今天的日期要算成去年。"""
    rows = scraper_tof.parse_history(F5_HTML, 5, 39, today=TODAY)
    dec = next(r for r in rows if r["issue"] == "11800")
    assert dec["date"] == dt.date(2025, 12, 31)


def test_marksix_drops_special_number():
    """六合彩一列 7 個號碼,最後一個是特別號,只取前 6 個正選。"""
    rows = scraper_tof.parse_history(MARKSIX_HTML, 6, 49, today=TODAY)
    assert [rows[0][f"n{i}"] for i in range(1, 7)] == [13, 24, 29, 30, 42, 48]
    assert "n7" not in rows[0]
    assert rows[0]["issue"] == "2026/085"


def test_numbers_out_of_range_are_dropped():
    html = F5_HTML.replace('<span class="number N08">08</span>',
                           '<span class="number N99">99</span>')
    rows = scraper_tof.parse_history(html, 5, 39, today=TODAY)
    # 該期只剩 4 個合法號碼,整期捨棄
    assert all(r["issue"] != "11961" for r in rows)


def test_unknown_game_rejected():
    with pytest.raises(scraper_tof.ScrapeError, match="沒有對應的彩種"):
        scraper_tof.fetch_history("bogus", 5, 39)


# ── 合併:期號優先去重 ────────────────────────────────────
def _df(rows):
    d = pd.DataFrame(rows)
    d["date"] = pd.to_datetime(d["date"])
    return d


def test_merge_dedupes_by_issue():
    """同一期即使日期被記錯,也只能留一筆。"""
    old = _df([{"date": "2026-08-06", "issue": "11961",
                "n1": 8, "n2": 17, "n3": 28, "n4": 32, "n5": 34}])
    new = [{"date": dt.date(2026, 8, 7), "issue": "11961",
            "n1": 8, "n2": 17, "n3": 28, "n4": 32, "n5": 34}]
    merged = loader.merge(old, new)
    assert len(merged) == 1


def test_merge_drops_legacy_row_covered_by_issued_row():
    """舊資料沒有期號,同一天已經有帶期號的列時就不該再留一筆。"""
    old = _df([{"date": "2026-08-07", "issue": "",
                "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5}])
    new = [{"date": dt.date(2026, 8, 7), "issue": "11961",
            "n1": 8, "n2": 17, "n3": 28, "n4": 32, "n5": 34}]
    merged = loader.merge(old, new)
    assert len(merged) == 1
    assert merged.iloc[0]["issue"] == "11961"
    assert int(merged.iloc[0]["n1"]) == 8


def test_merge_keeps_distinct_issues_on_different_dates():
    old = _df([{"date": "2026-08-06", "issue": "11960",
                "n1": 4, "n2": 10, "n3": 35, "n4": 37, "n5": 39}])
    new = [{"date": dt.date(2026, 8, 7), "issue": "11961",
            "n1": 8, "n2": 17, "n3": 28, "n4": 32, "n5": 34}]
    merged = loader.merge(old, new)
    assert len(merged) == 2
    assert list(merged["issue"]) == ["11960", "11961"]


def test_merge_without_issue_column_still_works():
    """舊資料檔沒有 issue 欄時要照原本的日期去重,不能壞掉。"""
    old = _df([{"date": "2026-08-06", "n1": 4, "n2": 10, "n3": 35, "n4": 37, "n5": 39}])
    new = [{"date": dt.date(2026, 8, 6), "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5}]
    merged = loader.merge(old, new)
    assert len(merged) == 1
    assert int(merged.iloc[0]["n1"]) == 4      # 保留既有
