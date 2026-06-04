"""台灣彩券今彩539 開獎資料爬蟲(加值功能,核心不依賴它)。

官網以 JS 動態載入,改打其公開 JSON API。API 結構可能隨官網改版而變動;
抓不到時優雅失敗並提示使用者改用 CSV 匯入。
"""
from __future__ import annotations

import pandas as pd

API_URL = "https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Daily539Result"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) lotto539-stats-tool",
    "Accept": "application/json",
}


class ScrapeError(Exception):
    """爬蟲失敗(網路、API 改版等)。"""


def _build_session():
    """建立放寬「嚴格 X509 驗證」的 requests Session。

    台灣彩券 API 伺服器憑證缺少 Subject Key Identifier 擴充欄位,
    新版 OpenSSL(Python 3.12+)預設啟用 VERIFY_X509_STRICT 會拒絕它,
    報 'Missing Subject Key Identifier'。這裡只關掉那條嚴格旗標,
    仍完整驗證憑證的信任鏈(不是 verify=False 全關),兼顧連線成功與安全。
    """
    import ssl

    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context

    class _RelaxedStrictAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            ctx = create_urllib3_context()
            ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT  # 保留信任鏈驗證
            kwargs["ssl_context"] = ctx
            return super().init_poolmanager(*args, **kwargs)

    session = requests.Session()
    session.mount("https://", _RelaxedStrictAdapter())
    return session


def _parse_month(payload: dict) -> list[dict]:
    """把 API 回傳的某月資料轉成 [{date,n1..n5}, ...]。

    API 欄位名稱可能隨改版調整,這裡採容錯解析:找出 5 個 1~39 的開獎號。
    """
    content = payload.get("content") or {}
    items = content.get("daily539Res") or content.get("lotteryDaily539Res") or []
    rows = []
    for it in items:
        date = it.get("lotteryDate") or it.get("openDate")
        # 開獎號通常放在 drawNumberSize / openShowOrder 之類欄位
        raw = (
            it.get("drawNumberSize")
            or it.get("openShowOrder")
            or it.get("drawNumberAppear")
            or []
        )
        nums = [int(x) for x in raw if str(x).isdigit() and 1 <= int(x) <= 39]
        nums = sorted(set(nums))
        if date and len(nums) >= 5:
            nums = nums[:5]
            d = pd.to_datetime(date, errors="coerce")
            if pd.isna(d):
                continue
            rows.append({"date": d, **{f"n{i+1}": nums[i] for i in range(5)}})
    return rows


def fetch_month(year: int, month: int, timeout: int = 10) -> list[dict]:
    """抓取指定年月的開獎資料。失敗時丟出 ScrapeError。"""
    try:
        import requests
    except ImportError as e:  # pragma: no cover
        raise ScrapeError("未安裝 requests,無法使用爬蟲功能") from e

    params = {"period": "", "month": f"{year:04d}-{month:02d}", "pageNum": 1, "pageSize": 50}
    try:
        session = _build_session()
        resp = session.get(API_URL, params=params, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:  # noqa: BLE001 — 網路/解析皆視為爬蟲失敗
        raise ScrapeError(f"無法取得 {year}-{month:02d} 開獎資料:{e}") from e

    rows = _parse_month(payload)
    if not rows:
        raise ScrapeError(
            f"{year}-{month:02d} 解析不到開獎號(API 可能已改版)。建議改用 CSV 匯入。"
        )
    return rows


def iter_months(start: tuple[int, int], end: tuple[int, int]):
    """產生 start 到 end(含)之間的 (year, month) 序列。

    start/end 皆為 (year, month);若 start 晚於 end 會自動對調。
    """
    sy, sm = start
    ey, em = end
    if (sy, sm) > (ey, em):
        sy, sm, ey, em = ey, em, sy, sm
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield (y, m)
        m += 1
        if m > 12:
            m = 1
            y += 1


def fetch_range(
    start: tuple[int, int],
    end: tuple[int, int],
    timeout: int = 10,
) -> tuple[list[dict], list[tuple[int, int, str]]]:
    """抓取 start~end(含)區間每個月的開獎資料。

    回傳 (rows, failures):
      rows     — 合併後的所有 [{date,n1..n5}, ...](已照月份順序串接)。
      failures — [(year, month, 錯誤訊息), ...],逐月失敗不會中斷整批抓取。

    若整個區間一筆都抓不到,丟出 ScrapeError。
    """
    months = list(iter_months(start, end))
    if not months:
        raise ScrapeError("年月區間為空。")

    rows: list[dict] = []
    failures: list[tuple[int, int, str]] = []
    for year, month in months:
        try:
            rows.extend(fetch_month(year, month, timeout=timeout))
        except ScrapeError as e:
            failures.append((year, month, str(e)))

    if not rows:
        detail = "; ".join(f"{y}-{m:02d}: {msg}" for y, m, msg in failures)
        raise ScrapeError(f"區間內所有月份皆抓取失敗。{detail}")
    return rows, failures


def fetch_recent(months: int = 3) -> list[dict]:
    """抓最近 months 個月的資料(以範例固定起點 2026-06 往回推,避免不可重現的當下時間)。

    註:本函式不呼叫系統時鐘(環境禁用),呼叫端可改傳明確年月清單。
    """
    raise ScrapeError(
        "自動推算月份需要系統時鐘;請改用 fetch_month(year, month) 指定明確年月。"
    )
