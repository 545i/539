"""sc888 天天樂爬蟲測試(離線,mock 掉 curl_cffi,不打網路)。

HTML 取自實際 index 頁的表格片段(前 3 期),用來驗:
  - 期號、台灣日期、5 個號碼都解析正確
  - 號碼升序排序
  - 超範圍/不齊的期整期捨棄
  - fetch_fantasy5 走 curl_cffi(被 mock)並回傳解析結果
"""
import pandas as pd
import pytest

from core import scraper_sc888

# 真實 index 頁的三列(第 11981/11980/11979 期),保留關鍵 class 與結構。
SAMPLE_HTML = """
<table><thead><th>尾數9</th></thead><tbody>
<tr class="LotteryFtn-tr-pc">
  <td class="time-td-pc"><p class="mb-0">第&nbsp;11981&nbsp;期</p>
    <p class="mb-0">2026-08-27&nbsp;星期四</p></td>
  <td><div class="recordChoice">
    <div class="record-item-539"><div class="circle-item-539"><strong>02</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>07</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>17</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>23</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>38</strong></div></div>
  </div></td>
  <td>3</td><td>2</td><td>87</td>
</tr>
<tr class="LotteryFtn-tr-pc">
  <td class="time-td-pc"><p class="mb-0">第&nbsp;11980&nbsp;期</p>
    <p class="mb-0">2026-08-26&nbsp;星期三</p></td>
  <td><div class="recordChoice">
    <div class="record-item-539"><div class="circle-item-539"><strong>39</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>02</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>35</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>24</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>27</strong></div></div>
  </div></td>
  <td>1</td>
</tr>
<tr class="LotteryFtn-tr-pc">
  <td class="time-td-pc"><p class="mb-0">第&nbsp;11979&nbsp;期</p>
    <p class="mb-0">2026-08-25&nbsp;星期二</p></td>
  <td><div class="recordChoice">
    <div class="record-item-539"><div class="circle-item-539"><strong>09</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>11</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>14</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>16</strong></div></div>
    <div class="record-item-539"><div class="circle-item-539"><strong>34</strong></div></div>
  </div></td>
  <td>2</td>
</tr>
</tbody></table>
"""


def test_parses_issue_date_and_numbers():
    rows = scraper_sc888.parse_history(SAMPLE_HTML)
    assert len(rows) == 3
    first = rows[0]
    assert first["issue"] == "11981"
    assert pd.Timestamp(first["date"]) == pd.Timestamp("2026-08-27")
    assert [first[f"n{i}"] for i in range(1, 6)] == [2, 7, 17, 23, 38]


def test_numbers_sorted_ascending():
    """來源號碼可能非升序(如 11980 的 39,02,35,24,27),要排成升序。"""
    rows = scraper_sc888.parse_history(SAMPLE_HTML)
    row = next(r for r in rows if r["issue"] == "11980")
    nums = [row[f"n{i}"] for i in range(1, 6)]
    assert nums == sorted(nums)
    assert nums == [2, 24, 27, 35, 39]


def test_date_is_taiwan_date_string_parsed():
    rows = scraper_sc888.parse_history(SAMPLE_HTML)
    row = next(r for r in rows if r["issue"] == "11979")
    assert pd.Timestamp(row["date"]) == pd.Timestamp("2026-08-25")
    assert [row[f"n{i}"] for i in range(1, 6)] == [9, 11, 14, 16, 34]


def test_out_of_range_number_drops_whole_row():
    """把 11981 的 38 改成 99(超出 1~39)→ 只剩 4 個合法號 → 整期捨棄。"""
    html = SAMPLE_HTML.replace("<strong>38</strong>", "<strong>99</strong>")
    rows = scraper_sc888.parse_history(html)
    assert all(r["issue"] != "11981" for r in rows)
    assert len(rows) == 2


def test_empty_html_returns_no_rows():
    assert scraper_sc888.parse_history("<html><body>no table</body></html>") == []


def test_fetch_fantasy5_uses_curl_cffi(monkeypatch):
    """fetch_fantasy5 應透過 curl_cffi 取得 HTML 並回傳解析結果(不打網路)。"""
    from curl_cffi import requests as creq

    calls = {}

    class _Resp:
        text = SAMPLE_HTML

        def raise_for_status(self):
            pass

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls["impersonate"] = kwargs.get("impersonate")
        return _Resp()

    monkeypatch.setattr(creq, "get", fake_get)
    rows = scraper_sc888.fetch_fantasy5()
    assert calls["impersonate"] == "chrome"
    assert calls["url"] == scraper_sc888.URL
    assert len(rows) == 3
    assert rows[0]["issue"] == "11981"


def test_fetch_fantasy5_raises_on_empty_parse(monkeypatch):
    from curl_cffi import requests as creq

    class _Resp:
        text = "<html>nothing</html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(creq, "get", lambda url, **kw: _Resp())
    with pytest.raises(scraper_sc888.ScrapeError):
        scraper_sc888.fetch_fantasy5()


def test_fetch_fantasy5_wraps_network_error(monkeypatch):
    from curl_cffi import requests as creq

    def boom(url, **kw):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(creq, "get", boom)
    with pytest.raises(scraper_sc888.ScrapeError):
        scraper_sc888.fetch_fantasy5()


# ---------------------------------------------------------------------------
# 今彩539(LotteryFtn):結構同天天樂,但每列多了「重排 5 顆」與 grey-bingo 統計欄。
# 下面的片段忠實重現 sc888 實抓的一列(draw 5 顆 + 排序 5 顆 + grey-bingo 4 欄),
# 用來驗證精準 class 只吃開獎球、grey-bingo(含在範圍內的假號)被排除。
# ---------------------------------------------------------------------------

def _ftn_ball(n, grey=False):
    cls = "circle-item-539 grey-bingo" if grey else "circle-item-539"
    return f'<div class="{cls}"><strong>{n}</strong></div>'


def _ftn_row(issue, date, draw, grey):
    balls = "".join(_ftn_ball(n) for n in draw)            # 開獎順序
    balls += "".join(_ftn_ball(n) for n in sorted(draw))  # 重排
    stats = "".join(_ftn_ball(n, grey=True) for n in grey)  # 統計欄(非開獎號)
    return (f'<tr class="LotteryFtn-tr-pc">'
            f'<td class="time-td-pc"><p>第&nbsp;{issue}&nbsp;期</p>'
            f'<p>{date}&nbsp;星期一</p></td>'
            f'<td><div class="recordChoice">{balls}</div>'
            f'<div class="statistic">{stats}</div></td></tr>')


# 第一列取自實抓 115000207(2026-08-26):draw 13,35,23,38,19;grey-bingo 39,93,35,58
# ——其中 39 落在 1~39 範圍內,若誤把 grey-bingo 也當號碼會多一顆 → 專門測試排除。
SAMPLE_539_HTML = (
    "<table><tbody>"
    + _ftn_row("115000207", "2026-08-26", [13, 35, 23, 38, 19], [39, 93, 35, 58])
    + _ftn_row("115000206", "2026-08-25", [5, 20, 11, 30, 2], [30, 88, 12, 40])
    + "</tbody></table>"
)


def test_539_parses_issue_date_numbers():
    rows = scraper_sc888.parse_539(SAMPLE_539_HTML)
    assert len(rows) == 2
    first = rows[0]
    assert first["issue"] == "115000207"
    assert pd.Timestamp(first["date"]) == pd.Timestamp("2026-08-26")
    # draw 非升序 → 升序;grey-bingo 的 39 必須被排除(否則會變 [13,19,23,35,39])
    assert [first[f"n{i}"] for i in range(1, 6)] == [13, 19, 23, 35, 38]


def test_539_grey_bingo_stats_excluded():
    """grey-bingo 統計欄含範圍內數字(30/12/40)也不能被當成開獎號。"""
    row = scraper_sc888.parse_539(SAMPLE_539_HTML)[1]
    assert row["issue"] == "115000206"
    assert [row[f"n{i}"] for i in range(1, 6)] == [2, 5, 11, 20, 30]


def test_539_out_of_range_drops_row():
    html = SAMPLE_539_HTML.replace(
        _ftn_ball(38), _ftn_ball(99))  # 把 115000207 的正選 38 改成超範圍 99
    rows = scraper_sc888.parse_539(html)
    assert all(r["issue"] != "115000207" for r in rows)
    assert len(rows) == 1


def test_fetch_539_uses_curl_cffi(monkeypatch):
    from curl_cffi import requests as creq
    calls = {}

    class _Resp:
        text = SAMPLE_539_HTML

        def raise_for_status(self):
            pass

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls["impersonate"] = kwargs.get("impersonate")
        return _Resp()

    monkeypatch.setattr(creq, "get", fake_get)
    rows = scraper_sc888.fetch_539()
    assert calls["impersonate"] == "chrome"
    assert calls["url"] == scraper_sc888.URL_539
    assert rows[0]["issue"] == "115000207"


# ---------------------------------------------------------------------------
# 六合彩(LotterySix):每列 13 顆顏色球 = 開獎 6 + 重排 6 + 特別號 1,之後 grey-bingo。
# 對齊本專案 CSV:只取前 6 顆正選(升序),丟掉特別號與統計欄。片段取自實抓資料。
# ---------------------------------------------------------------------------

def _six_ball(n, color="red", grey=False):
    cls = ("circle-item-blt grey-bingo" if grey
           else f"circle-item-blt LotterySix-number-color-{color}")
    return f'<div class="{cls}"><strong>{n:02d}</strong></div>'


def _six_row(issue, date, draw, special, grey):
    balls = "".join(_six_ball(n) for n in draw)            # 開獎順序 6 顆
    balls += "".join(_six_ball(n) for n in sorted(draw))  # 重排 6 顆
    balls += _six_ball(special, color="blue")             # 特別號 1 顆(最後)
    stats = "".join(_six_ball(n, grey=True) for n in grey)
    return (f'<tr class="LotteryFtn-tr-pc">'
            f'<td class="time-td-pc"><p>第&nbsp;{issue}&nbsp;期</p>'
            f'<p>{date}&nbsp;星期一</p></td>'
            f'<td><div class="recordChoice">{balls}</div>'
            f'<div class="statistic">{stats}</div></td></tr>')


# 取自實抓:026093(2026-08-25)draw 34,01,25,19,18,38、特別號 07;
#           026092(2026-08-24)draw 07,09,12,25,34,40、特別號 29。
# 兩期特別號(07 / 29)都不是最小/最大值 —— 專門驗證它是靠「位置在最後」被排除,
# 不是靠數值大小,且不會被誤當成正選。
SAMPLE_MARKSIX_HTML = (
    "<table><tbody>"
    + _six_row("026093", "2026-08-25", [34, 1, 25, 19, 18, 38], 7,
               [18, 89, 95, 54, 48])
    + _six_row("026092", "2026-08-24", [7, 9, 12, 25, 34, 40], 29,
               [22, 77, 60, 41, 55])
    + "</tbody></table>"
)


def test_marksix_parses_six_normals_ascending():
    rows = scraper_sc888.parse_marksix(SAMPLE_MARKSIX_HTML)
    assert len(rows) == 2
    first = rows[0]
    assert pd.Timestamp(first["date"]) == pd.Timestamp("2026-08-25")
    nums = [first[f"n{i}"] for i in range(1, 7)]
    assert nums == [1, 18, 19, 25, 34, 38]        # 6 顆正選、升序
    assert nums == sorted(nums)
    assert "n7" not in first and "issue" not in first  # 無第 7 欄、無期號欄


def test_marksix_special_number_excluded():
    """特別號固定在最後(第 13 顆),必須被排除、且不出現在正選裡。"""
    rows = scraper_sc888.parse_marksix(SAMPLE_MARKSIX_HTML)
    second = rows[1]
    nums = [second[f"n{i}"] for i in range(1, 7)]
    assert nums == [7, 9, 12, 25, 34, 40]
    assert 29 not in nums                          # 特別號 29 未混入正選


def test_marksix_grey_bingo_excluded():
    """grey-bingo 統計欄(含範圍內數字)不得被當成正選號。"""
    rows = scraper_sc888.parse_marksix(SAMPLE_MARKSIX_HTML)
    assert [rows[0][f"n{i}"] for i in range(1, 7)] == [1, 18, 19, 25, 34, 38]


def test_marksix_incomplete_row_dropped():
    """前 6 顆正選去重後不足 6(把 026093 的正選 34 也改成 18)→ 整期捨棄。"""
    broken = _six_row("026093", "2026-08-25", [18, 1, 25, 19, 18, 38], 7,
                      [18, 89, 95, 54, 48])
    html = SAMPLE_MARKSIX_HTML.replace(
        _six_row("026093", "2026-08-25", [34, 1, 25, 19, 18, 38], 7,
                 [18, 89, 95, 54, 48]), broken)
    rows = scraper_sc888.parse_marksix(html)
    assert len(rows) == 1
    assert pd.Timestamp(rows[0]["date"]) == pd.Timestamp("2026-08-24")


def test_fetch_marksix_uses_curl_cffi(monkeypatch):
    from curl_cffi import requests as creq
    calls = {}

    class _Resp:
        text = SAMPLE_MARKSIX_HTML

        def raise_for_status(self):
            pass

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls["impersonate"] = kwargs.get("impersonate")
        return _Resp()

    monkeypatch.setattr(creq, "get", fake_get)
    rows = scraper_sc888.fetch_marksix()
    assert calls["impersonate"] == "chrome"
    assert calls["url"] == scraper_sc888.URL_MARKSIX
    assert [rows[0][f"n{i}"] for i in range(1, 7)] == [1, 18, 19, 25, 34, 38]


def test_fetch_539_and_marksix_raise_on_empty(monkeypatch):
    from curl_cffi import requests as creq

    class _Resp:
        text = "<html>nothing</html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(creq, "get", lambda url, **kw: _Resp())
    with pytest.raises(scraper_sc888.ScrapeError):
        scraper_sc888.fetch_539()
    with pytest.raises(scraper_sc888.ScrapeError):
        scraper_sc888.fetch_marksix()
