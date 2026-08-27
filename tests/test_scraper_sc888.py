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
