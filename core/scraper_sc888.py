"""天天樂(美國加州 Fantasy 5)開獎資料爬蟲 —— sc888 來源。

天天樂原本抓官方彙整站,常**慢一期**(最新一期還沒上架)。sc888
(https://sc888.net)的天天樂首頁開獎歷史更新較快、且已有最新期,期號體系
與本專案 CSV 一致、日期已是台灣日期,因此拿來當天天樂的**優先**來源;
抓不到時由 autoupdate 退回原本的官方彙整站。

**只用純 HTTP(curl_cffi impersonate chrome)抓 index 頁 HTML**:
  https://sc888.net/index.php?s=/LotteryFan/index
其 `getDownloadXls` 端點對純 HTTP 一律回空表(需真瀏覽器),不走那條。

index 頁的開獎歷史表格,每列結構(已確認):
    <tr class="LotteryFtn-tr-pc">
      <td class="time-td-pc">
        <p ...>第&nbsp;11981&nbsp;期</p>
        <p ...>2026-08-27&nbsp;星期四</p>
      </td>
      ... <div class="circle-item-539"><strong>02</strong></div> x5 ...
    </tr>
號碼球只在 class 含 circle-item-539 的元素裡,故精準定位、不整頁硬抽。
"""
from __future__ import annotations

import re

import pandas as pd

URL = "https://sc888.net/index.php?s=/LotteryFan/index"

# 玩法與今彩539 相同:39 選 5
_NUM_MIN, _NUM_MAX, _PICK = 1, 39, 5

# 一列開獎(桌面版表格)。手機版另有 class,這裡只吃桌面版即可,兩者號碼相同。
_ROW_RE = re.compile(
    r'<tr[^>]*class="[^"]*LotteryFtn-tr-pc[^"]*"[^>]*>(.*?)</tr>', re.S
)
_ISSUE_RE = re.compile(r"第(?:&nbsp;|&#160;|\s|\xa0)*(\d+)")
_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
# 只抓 circle-item-539 球裡的兩位數,避開整列其他統計欄位的數字
_BALL_RE = re.compile(
    r"circle-item-539[^>]*>\s*<strong>\s*(\d+)\s*</strong>", re.S
)


class ScrapeError(Exception):
    """爬蟲失敗(網路、來源改版等)。"""


def parse_history(html: str) -> list[dict]:
    """從 index 頁 HTML 解析出 [{date, issue, n1..n5}, ...](號碼升序)。

    date 為 pandas Timestamp(對齊 core.scraper_fantasy5 的回傳,讓 loader.merge
    直接吃);issue 為字串期號。解析不到任何一期會回空清單(由呼叫端決定是否報錯)。
    """
    rows: list[dict] = []
    for body in _ROW_RE.findall(html):
        m_issue = _ISSUE_RE.search(body)
        m_date = _DATE_RE.search(body)
        if not (m_issue and m_date):
            continue
        nums = [int(n) for n in _BALL_RE.findall(body)]
        nums = [n for n in nums if _NUM_MIN <= n <= _NUM_MAX]
        nums = sorted(set(nums))
        if len(nums) < _PICK:
            continue                       # 號碼不齊(超範圍/重複)→ 整期捨棄
        nums = nums[:_PICK]
        d = pd.to_datetime(m_date.group(1), errors="coerce")
        if pd.isna(d):
            continue
        rows.append({"date": d, "issue": m_issue.group(1),
                     **{f"n{i + 1}": nums[i] for i in range(_PICK)}})
    return rows


def fetch_fantasy5(timeout: int = 25) -> list[dict]:
    """抓取 sc888 天天樂 index 頁,回傳多期 [{date, issue, n1..n5}, ...]。

    表格有幾期就回幾期(依頁面順序,通常由新到舊)。抓取或解析失敗丟 ScrapeError。
    """
    try:
        from curl_cffi import requests as creq
    except ImportError as e:  # pragma: no cover
        raise ScrapeError("未安裝 curl_cffi,無法使用 sc888 爬蟲") from e

    try:
        resp = creq.get(URL, impersonate="chrome", timeout=timeout)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:  # noqa: BLE001 — 網路/HTTP 皆視為爬蟲失敗
        raise ScrapeError(f"無法取得 sc888 天天樂資料:{e}") from e

    rows = parse_history(html)
    if not rows:
        raise ScrapeError("解析不到 sc888 天天樂開獎號(來源可能改版)。")
    return rows
