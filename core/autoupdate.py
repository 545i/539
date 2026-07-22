"""背景自動補抓開獎資料(回報策略結果時觸發)。

規則:
- 比對「系統日期」與「資料最新日期」:相同 → 不補抓;有落差才補。
- 補抓時從 min(資料最新日, 今天 − 9 天) 所在月份抓到本月,依日期去重合併
  —— 9 個日曆天必含 ≥7 個開獎日(今彩539 週一~六開獎),避免日期對不上。
- 跑在 daemon 執行緒(Streamlit 伺服器行程內),使用者關閉網頁也會繼續補完。
- 同一遊戲同時只跑一條;成功後 10 分鐘內、失敗後 60 秒內不重複觸發。
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from pathlib import Path

import pandas as pd

from core import loader, scraper, scraper_fantasy5

MIN_DRAWS = 7        # 每次補抓至少涵蓋的期數(去重合併,不會重複寫入)
_MIN_SPAN_DAYS = 9   # 今彩539 週一~六開獎:9 個日曆天必含 >=7 個開獎日
_COOLDOWN_OK = 600   # 補抓成功後的冷卻秒數(避免每回報一局就打一次 API)
_COOLDOWN_ERR = 60   # 補抓失敗後的冷卻秒數

_lock = threading.Lock()
_status: dict[str, dict] = {}  # game_key -> {running, msg, error, done_ts, added}


def status(game_key: str) -> dict:
    """目前補抓狀態(給頁面顯示用);無紀錄回空 dict。"""
    with _lock:
        return dict(_status.get(game_key, {}))


def _set(game_key: str, **kw) -> None:
    with _lock:
        _status.setdefault(game_key, {}).update(kw)


def _months_between(start: dt.date, end: dt.date):
    """產生 start 到 end(含)之間的 (year, month) 序列。"""
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            y, m = y + 1, 1


def _run(game_key: str, data_path: Path, on_done) -> None:
    today = dt.date.today()
    try:
        df = loader.load_history(data_path)
        latest = pd.to_datetime(df["date"]).max().date()
        # 從資料最新日與「今天 − 9 天」較早者開始抓,保證至少重抓 7 期
        start = min(latest, today - dt.timedelta(days=_MIN_SPAN_DAYS))

        if game_key == "fantasy5":
            # 天天樂每日開獎:每頁約 50 期,依落差天數換算頁數
            gap_days = (today - start).days
            pages = min(60, max(1, -(-(gap_days + MIN_DRAWS) // 50)))
            new_rows = scraper_fantasy5.fetch_history(pages=pages)
        else:
            new_rows, failures = [], []
            for y, m in _months_between(start, today):
                try:
                    new_rows.extend(scraper.fetch_month(y, m))
                except scraper.ScrapeError as e:
                    failures.append(f"{y}-{m:02d}: {e}")
            if not new_rows:
                raise scraper.ScrapeError("; ".join(failures) or "區間內無資料")

        merged = loader.merge(df, new_rows)
        added = len(merged) - len(df)
        if added > 0:
            loader.save(merged, data_path)
        new_latest = pd.to_datetime(merged["date"]).max().date()
        _set(game_key, running=False, error="", done_ts=time.time(), added=added,
             msg=f"自動補抓完成:重抓 {len(new_rows)} 期、新增 {added} 期,"
                 f"資料已到 {new_latest}。")
        if added > 0 and on_done is not None:
            try:
                on_done()  # 清 load_df 快取,讓各頁面下次 rerun 讀到新資料
            except Exception:
                pass
    except Exception as e:  # noqa: BLE001 — 背景執行緒,任何錯誤都記進狀態
        _set(game_key, running=False, error=str(e), done_ts=time.time(),
             msg=f"自動補抓失敗:{e}")


def kick(game_key: str, data_path: str | Path, latest_date, on_done=None) -> bool:
    """觸發背景補抓;回傳是否真的啟動。

    latest_date — 目前資料的最新日期(date/Timestamp);與系統日期相同則不補。
    on_done     — 補抓有新增資料時的回呼(例如清 Streamlit 快取)。
    """
    today = dt.date.today()
    if latest_date is not None and pd.to_datetime(latest_date).date() >= today:
        return False  # 資料已是今天 → 不補充
    with _lock:
        s = _status.get(game_key, {})
        if s.get("running"):
            return False
        cooldown = _COOLDOWN_ERR if s.get("error") else _COOLDOWN_OK
        if s.get("done_ts") and time.time() - s["done_ts"] < cooldown:
            return False
        _status[game_key] = {"running": True, "msg": "背景補抓開獎資料中…", "error": ""}
    threading.Thread(
        target=_run, args=(game_key, Path(data_path), on_done), daemon=True
    ).start()
    return True
