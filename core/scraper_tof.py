"""彩世界開獎網(tof.988cp.net)爬蟲 —— 一個站台同時供應三款開獎資料。

為什麼加這個來源:
  原本天天樂抓 lottolyzer,它記的是**加州當地日期**;加州晚上開獎時台灣已經隔天,
  所以站上顯示 08/07 的那期,我們的檔案裡是 08-06,看起來像少了一天。
  這個站是中文站,日期本來就是**台灣日期**,對台灣使用者才對得起來。
  今彩539 與六合彩本來就沒有時差問題,兩邊日期一致(已實測比對)。

頁面結構(/history?g=<gtype>):
  <div class="draw-section">
    <div class="draw-date"> 08/06(四) &nbsp;&nbsp;11960期 </div>
    <div class="numbers-container ... "><span class="number N04">04</span>…</div>

注意事項:
  - 日期只有 MM/DD 沒有年份,依「不晚於今天」推斷(跨年時自動退一年)。
  - 每頁只有最近 100 期,適合**補最新**;要建整份歷史仍需原本的來源。
  - 六合彩一列有 7 個號碼,最後一個是特別號,我們只取前 6 個正選號。
  - 純 HTML,一般 GET 就拿得到(實測 HTTP 200),不需要反爬工具。
"""
from __future__ import annotations

import datetime as dt
import re

import requests

BASE = "https://tof.988cp.net/history?g={gtype}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

# 本專案的遊戲代號 → 這個站的 gtype
GTYPE = {
    "lotto539": "DayLotto",
    "fantasy5": "Fantasy5",
    "marksix": "MARKSIX",
}

_SECTION_RE = re.compile(
    r'<div class="draw-section">\s*'
    r'<div class="draw-date">\s*(.*?)\s*</div>\s*'
    r'<div class="[^"]*numbers-container[^"]*">(.*?)</div>',
    re.S,
)
_MMDD_RE = re.compile(r"(\d{1,2})/(\d{1,2})")
_NUM_RE = re.compile(r">(\d+)</span>")
# 期號:天天樂是純數字(11961)、今彩539 是 115000190、六合彩是 2026/085
_ISSUE_RE = re.compile(r"([\d/]+)\s*期")


class ScrapeError(Exception):
    """爬蟲失敗。"""


def _year_for(month: int, day: int, today: dt.date) -> int:
    """把只有 MM/DD 的日期補上年份:取「不晚於今天」的那一年。"""
    try:
        if dt.date(today.year, month, day) <= today:
            return today.year
    except ValueError:      # 2/29 之類
        pass
    return today.year - 1


def parse_history(html: str, pick: int, num_max: int,
                  today: dt.date | None = None) -> list[dict]:
    """解析歷史頁,回傳 [{date, issue, n1..n{pick}}, ...](由舊到新)。

    pick    每期取幾個號碼(539/天天樂 5、六合彩 6;六合彩第 7 個是特別號,捨去)
    num_max 號碼上限,用來擋掉解析到的雜訊

    issue 是站上標的期號 —— 光比對日期與號碼看不出「中間漏了一期」,
    有期號才驗得出連續性。
    """
    today = today or dt.date.today()
    out = []
    for date_text, nums_html in _SECTION_RE.findall(html):
        m = _MMDD_RE.search(date_text)
        if not m:
            continue
        month, day = int(m.group(1)), int(m.group(2))
        nums = [int(x) for x in _NUM_RE.findall(nums_html)]
        nums = [n for n in nums if 1 <= n <= num_max]
        if len(nums) < pick:
            continue
        try:
            date = dt.date(_year_for(month, day, today), month, day)
        except ValueError:
            continue
        issue = _ISSUE_RE.search(date_text)
        row = {"date": date, "issue": issue.group(1) if issue else ""}
        for i, n in enumerate(sorted(nums[:pick]), 1):
            row[f"n{i}"] = n
        if len(row) == pick + 2:          # date + issue + pick 個號碼都齊了
            out.append(row)
    out.sort(key=lambda r: r["date"])
    return out


def fetch_history(game_key: str, pick: int, num_max: int,
                  timeout: int = 25, today: dt.date | None = None) -> list[dict]:
    """抓某一款的最近 100 期。game_key 為本專案代號(lotto539/fantasy5/marksix)。"""
    gtype = GTYPE.get(game_key)
    if not gtype:
        raise ScrapeError(f"這個站沒有對應的彩種:{game_key}")
    url = BASE.format(gtype=gtype)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ScrapeError(f"連線失敗:{e}") from e
    rows = parse_history(resp.text, pick, num_max, today=today)
    if not rows:
        raise ScrapeError(f"{url} 解析不到任何開獎資料(頁面結構可能改了)")
    return rows
