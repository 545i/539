"""六合彩(香港)開獎資料爬蟲。

香港馬會官網(hkjc.com)對非香港 IP 與自動化請求相當敏感,故改抓公開彙整站
「樂透彩幸運發財網」(pilio.idv.tw),其開獎號碼即為香港六合彩官方結果。

玩法:49 選 6(另有特別號,本工具的二合拖牌只看 6 個正選號,故不收錄)。

來源頁面結構(list.asp?indexpage=N&orderby=new,每頁約 23 期,最舊可回溯到 2002 年):
    <td class="date-cell">07/28<br>26(二)</td>
    <td class="number-cell">04,&nbsp;07,&nbsp;14,&nbsp;20,&nbsp;21,&nbsp;30</td>
    <td class="bonus-cell">34</td>
"""
from __future__ import annotations

import re

import pandas as pd

BASE = "https://www.pilio.idv.tw/ltohk/list.asp?indexpage={page}&orderby=new"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

PICK = 6
NUM_MAX = 49

_ROW_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.S)
_DATE_CELL_RE = re.compile(
    r'<td[^>]*class="date-cell"[^>]*>\s*(\d{1,2})/(\d{1,2})\s*<br\s*/?>\s*(\d{2})', re.S
)
_NUM_CELL_RE = re.compile(r'<td[^>]*class="number-cell"[^>]*>(.*?)</td>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")


class ScrapeError(Exception):
    """爬蟲失敗。"""


def _parse_page(html: str) -> list[dict]:
    """從一頁 HTML 解析出 [{date, n1..n6}, ...];解析不到的列直接略過。"""
    rows = []
    for tr in _ROW_RE.findall(html):
        m_date = _DATE_CELL_RE.search(tr)
        m_nums = _NUM_CELL_RE.search(tr)
        if not (m_date and m_nums):
            continue
        month, day, yy = (int(x) for x in m_date.groups())
        text = _TAG_RE.sub(" ", m_nums.group(1)).replace("&nbsp;", " ")
        nums = sorted({int(x) for x in re.findall(r"\d{1,2}", text) if 1 <= int(x) <= NUM_MAX})
        if len(nums) != PICK:
            continue
        date = pd.to_datetime(f"{2000 + yy:04d}-{month:02d}-{day:02d}", errors="coerce")
        if pd.isna(date):
            continue
        rows.append({"date": date, **{f"n{i + 1}": nums[i] for i in range(PICK)}})
    return rows


def fetch_history(pages: int = 5, timeout: int = 25) -> list[dict]:
    """抓取最近 pages 頁(每頁約 23 期)的六合彩開獎資料。

    回傳合併、去重、依日期排序的 [{date, n1..n6}, ...]。整批失敗才丟 ScrapeError;
    中途某頁失敗時保留已抓到的資料(來源站偶爾逾時)。
    """
    try:
        import requests
    except ImportError as e:  # pragma: no cover
        raise ScrapeError("未安裝 requests,無法使用爬蟲功能") from e

    seen: dict = {}
    for page in range(1, pages + 1):
        try:
            resp = requests.get(BASE.format(page=page), headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            if seen:
                break  # 已有資料,容忍中途失敗
            raise ScrapeError(f"無法取得六合彩資料:{e}") from e
        resp.encoding = "utf-8"
        page_rows = _parse_page(resp.text)
        if not page_rows:
            break  # 沒有更多資料(或已超過最後一頁)
        for r in page_rows:
            seen[r["date"]] = r

    if not seen:
        raise ScrapeError("解析不到六合彩開獎號(來源可能改版)。")
    return [seen[d] for d in sorted(seen)]
