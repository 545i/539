"""sc888 開獎資料爬蟲 —— 天天樂、今彩539、六合彩共用。

各款原本的官方/彙整來源常**慢一期**(最新一期還沒上架)。sc888
(https://sc888.net)的開獎歷史首頁更新較快、且已有最新期,期號體系與本專案
CSV 一致、日期已是台灣日期,因此拿來當**優先**來源;抓不到時由 autoupdate
退回各款原本的來源。

**只用純 HTTP(curl_cffi impersonate chrome)抓 index 頁 HTML**:
  天天樂  https://sc888.net/index.php?s=/LotteryFan/index
  今彩539 https://sc888.net/index.php?s=/LotteryFtn/index
  六合彩  https://sc888.net/index.php?s=/LotterySix/index
其 `getDownloadXls` 端點對純 HTTP 一律回空表(需真瀏覽器),不走那條。

三款 index 頁的開獎列都是 `<tr class="LotteryFtn-tr-pc">`,期號「第&nbsp;N&nbsp;期」、
日期 `YYYY-MM-DD`。差別在號碼球的 class:

- 天天樂 / 今彩539:號碼球在 `circle-item-539`。同一列會出現兩組(開獎順序 5 顆
  + 由小到大重排 5 顆),另有 `circle-item-539 grey-bingo` 的**統計欄**(球數/大小/
  單雙,非開獎號)。故用結尾為 `539"` 的精準 class 只吃開獎球、避開 grey-bingo,
  再 set 去重成 5 顆。

- 六合彩(49 選 6 + 1 特別號):號碼球在
  `circle-item-blt LotterySix-number-color-<顏色>`。同一列依序是「開獎順序 6 顆 →
  重排 6 顆 → 特別號 1 顆」共 **13 顆**,之後才是 `circle-item-blt grey-bingo` 統計欄。
  特別號固定在**最後一顆(第 13 顆)**。已用實抓 100 列驗證:每列前 6 顆 set 後 == 中
  間 6 顆 set(同一組正選號),第 13 顆為特別號;且與本專案既有 CSV 完全吻合。
  **本專案六合彩 CSV 只存 6 顆正選號(date,n1..n6,無期號、無特別號欄)**,故解析時
  取前 6 顆正選、丟掉特別號,對齊 CSV。
"""
from __future__ import annotations

import re

import pandas as pd

URL = "https://sc888.net/index.php?s=/LotteryFan/index"          # 天天樂
URL_539 = "https://sc888.net/index.php?s=/LotteryFtn/index"      # 今彩539
URL_MARKSIX = "https://sc888.net/index.php?s=/LotterySix/index"  # 六合彩

# 玩法與今彩539 相同:39 選 5
_NUM_MIN, _NUM_MAX, _PICK = 1, 39, 5
# 六合彩:49 選 6(+ 1 特別號,不收錄)
_SIX_NUM_MAX, _SIX_PICK = 49, 6

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
# 今彩539:精準吃 class 結尾為 `539"` 的開獎球,避開 `circle-item-539 grey-bingo`
# 統計欄與 `circle-item-539-pc` 等其他容器。
_BALL_539_RE = re.compile(
    r'circle-item-539"[^>]*>\s*<strong>\s*(\d+)\s*</strong>', re.S
)
# 六合彩:號碼球 class 為 `circle-item-blt LotterySix-number-color-<顏色>`。
# 要求顏色後緊接 `"`,避開頁面裡以 JS 樣板字串拼出的假 class 與 grey-bingo 統計欄。
_BALL_MARKSIX_RE = re.compile(
    r'circle-item-blt LotterySix-number-color-\w+"[^>]*>\s*'
    r'<strong>\s*(\d+)\s*</strong>', re.S
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


def _get_html(url: str, timeout: int) -> str:
    """用 curl_cffi impersonate chrome 抓 index 頁 HTML;失敗一律丟 ScrapeError。"""
    try:
        from curl_cffi import requests as creq
    except ImportError as e:  # pragma: no cover
        raise ScrapeError("未安裝 curl_cffi,無法使用 sc888 爬蟲") from e
    try:
        resp = creq.get(url, impersonate="chrome", timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:  # noqa: BLE001 — 網路/HTTP 皆視為爬蟲失敗
        raise ScrapeError(f"無法取得 sc888 資料:{e}") from e


def parse_539(html: str) -> list[dict]:
    """從今彩539 index 頁 HTML 解析出 [{date, issue, n1..n5}, ...](號碼升序)。

    每列的開獎球會出現兩組(開獎順序 + 重排),另有 grey-bingo 統計欄;用結尾為
    `539"` 的精準 class 只吃開獎球,set 去重後取 5 顆。號碼不齊/超範圍整期捨棄。
    """
    rows: list[dict] = []
    for body in _ROW_RE.findall(html):
        m_issue = _ISSUE_RE.search(body)
        m_date = _DATE_RE.search(body)
        if not (m_issue and m_date):
            continue
        nums = [int(n) for n in _BALL_539_RE.findall(body)]
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


def parse_marksix(html: str) -> list[dict]:
    """從六合彩 index 頁 HTML 解析出 [{date, n1..n6}, ...](6 顆正選,升序)。

    每列的顏色號碼球依序是「開獎順序 6 顆 → 重排 6 顆 → 特別號 1 顆」,取**前 6 顆**
    即為正選號(特別號固定在最後、被排除);對齊本專案六合彩 CSV `date,n1..n6`(不含
    期號、不含特別號)。號碼不齊(前 6 顆去重後不足 6)整期捨棄。
    """
    rows: list[dict] = []
    for body in _ROW_RE.findall(html):
        m_date = _DATE_RE.search(body)
        if not m_date:
            continue
        balls = [int(n) for n in _BALL_MARKSIX_RE.findall(body)]
        # 前 6 顆為開獎順序的正選號;丟掉第 13 顆特別號與後面統計欄。
        picks = sorted({n for n in balls[:_SIX_PICK]
                        if _NUM_MIN <= n <= _SIX_NUM_MAX})
        if len(picks) != _SIX_PICK:
            continue                       # 正選號不齊 → 整期捨棄
        d = pd.to_datetime(m_date.group(1), errors="coerce")
        if pd.isna(d):
            continue
        rows.append({"date": d,
                     **{f"n{i + 1}": picks[i] for i in range(_SIX_PICK)}})
    return rows


def fetch_539(timeout: int = 25) -> list[dict]:
    """抓取 sc888 今彩539 index 頁,回傳多期 [{date, issue, n1..n5}, ...]。

    表格有幾期就回幾期(依頁面順序,通常由新到舊)。抓取或解析失敗丟 ScrapeError。
    """
    rows = parse_539(_get_html(URL_539, timeout))
    if not rows:
        raise ScrapeError("解析不到 sc888 今彩539 開獎號(來源可能改版)。")
    return rows


def fetch_marksix(timeout: int = 25) -> list[dict]:
    """抓取 sc888 六合彩 index 頁,回傳多期 [{date, n1..n6}, ...](6 顆正選)。

    表格有幾期就回幾期(依頁面順序,通常由新到舊)。抓取或解析失敗丟 ScrapeError。
    """
    rows = parse_marksix(_get_html(URL_MARKSIX, timeout))
    if not rows:
        raise ScrapeError("解析不到 sc888 六合彩開獎號(來源可能改版)。")
    return rows
