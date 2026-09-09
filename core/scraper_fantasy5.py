"""天天樂(美國加州 Fantasy 5)開獎資料爬蟲。

加州彩券官網(calottery.com)以 volt-adc WAF 在 IP 層級硬性封鎖(403),
資料中心 IP 無法直連;因此改抓公開彙整站 lottolyzer.com,
其開獎號碼即為加州官方結果(僅第三方republish)。

玩法與今彩539 完全相同:39 選 5。
"""
from __future__ import annotations

import re

import pandas as pd

BASE = (
    "https://en.lottolyzer.com/history/united-states/"
    "fantasy-5-california/page/{page}/per-page/{per}/summary-view"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_ROW_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.S)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")


class ScrapeError(Exception):
    """爬蟲失敗。"""


def _parse_page(html: str) -> list[dict]:
    """從一頁 HTML 解析出 [{date, n1..n5}, ...]。

    lottolyzer 表格結構:第 0 欄期號、第 1 欄日期、第 2 欄為逗號分隔的 5 個開獎號。
    """
    rows = []
    for tr in _ROW_RE.findall(html):
        if not _DATE_RE.search(tr):
            continue
        cells = [_TAG_RE.sub("", c).strip() for c in _TD_RE.findall(tr)]
        # 找日期欄與其後的號碼欄
        date = None
        nums: list[int] = []
        for i, c in enumerate(cells):
            if _DATE_RE.fullmatch(c):
                date = c
                # 日期下一格通常是 "9,17,28,29,33"
                for nxt in cells[i + 1 : i + 3]:
                    cand = [int(x) for x in re.split(r"[,\s]+", nxt) if x.isdigit()]
                    cand = [n for n in cand if 1 <= n <= 39]
                    if len(cand) >= 5:
                        nums = sorted(set(cand))[:5]
                        break
                break
        if date and len(nums) == 5:
            rows.append({"date": pd.to_datetime(date), **{f"n{i+1}": nums[i] for i in range(5)}})
    return rows


def fetch_history(pages: int = 30, per_page: int = 50, timeout: int = 25) -> list[dict]:
    """抓取最近 pages 頁(每頁 per_page 期)的天天樂開獎資料。

    回傳合併、去重、依日期排序的 [{date, n1..n5}, ...]。失敗丟 ScrapeError。
    """
    try:
        import requests
    except ImportError as e:  # pragma: no cover
        raise ScrapeError("未安裝 requests,無法使用爬蟲功能") from e

    seen: dict = {}
    for page in range(1, pages + 1):
        url = BASE.format(page=page, per=per_page)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            if seen:
                break  # 已有資料,容忍中途失敗
            raise ScrapeError(f"無法取得天天樂資料:{e}") from e
        page_rows = _parse_page(resp.text)
        if not page_rows:
            break  # 沒有更多資料
        for r in page_rows:
            seen[r["date"]] = r

    if not seen:
        raise ScrapeError("解析不到天天樂開獎號(來源可能改版)。")
    return [seen[d] for d in sorted(seen)]
