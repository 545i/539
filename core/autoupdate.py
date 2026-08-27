"""開獎資料的自動補抓:一條背景排程執行緒,依各款的開獎時刻表定時檢查。

**觸發方式**:定時檢查,不再由使用者操作(記帳)觸發。以前是「回報下注時
順便去抓」,結果是沒下注的日子不會更新、下注頻繁的日子又一直打對方站台。
現在改成排程:每 5 分鐘看一次「到現在為止最後一期應該抓得到的是哪一天」
(core.drawtime),資料比它舊才去抓。

這樣的好處是不必精準地在 20:30 醒來 —— 服務重啟、錯過時間點、放了幾天沒開,
下一次檢查都會自動補上。

**同一期最多試幾次**:抓了但沒有新資料(對方還沒上架、或那天其實沒開獎,
例如六合彩的攪珠從週六挪到週日)就等一段時間再試,同一期試滿
MAX_ATTEMPTS 次就停手,等下一期的時間到了才重新開始 —— 不會因為某天沒開獎
就整天狂打對方站台。手動按「立即抓取」永遠不受這個限制。

補抓範圍:從 min(資料最新日, 今天 − 9 天) 所在月份抓到本月,依日期去重合併
—— 9 個日曆天必含 ≥7 個開獎日(今彩539 週一~六開獎),避免日期對不上。

執行緒是 daemon,跑在 Streamlit 伺服器行程內,使用者關掉網頁也會繼續。
注意:行程重啟後要有人開過一次頁面,排程才會起來(Streamlit 沒有開機鉤子)。
"""
from __future__ import annotations

import datetime as dt
import threading
import time
from pathlib import Path

import pandas as pd

from core import (drawtime, games, loader, scraper, scraper_fantasy5,
                  scraper_marksix, scraper_tof)

MIN_DRAWS = 7        # 每次補抓至少涵蓋的期數(去重合併,不會重複寫入)
_MIN_SPAN_DAYS = 9   # 今彩539 週一~六開獎:9 個日曆天必含 >=7 個開獎日
_MARKSIX_PER_PAGE = 23   # 六合彩來源站每頁期數
_MARKSIX_PER_WEEK = 3    # 六合彩每週開獎次數(二/四/六)

TICK_SECONDS = 300       # 排程多久檢查一次
MAX_ATTEMPTS = 12        # 同一期最多自動試幾次(手動抓取不受限)
_COOLDOWN_OK = 600       # 有抓到新資料後的冷卻秒數
_COOLDOWN_IDLE = 1800    # 抓了但沒新資料(對方還沒上架 / 那天沒開獎)
_COOLDOWN_ERR = 300      # 抓取失敗後的冷卻秒數

_lock = threading.Lock()
_status: dict[str, dict] = {}  # game_key -> {running, msg, error, done_ts, added, ...}
_scheduler = None              # 排程執行緒(全行程只起一條)


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


def latest_date(data_path: str | Path, game_key: str) -> dt.date | None:
    """檔案裡的最新開獎日期;讀不到回 None。"""
    game = games.get(game_key)
    try:
        df = loader.load_history(Path(data_path), game.pick, game.num_max)
        if df.empty:
            return None
        return pd.to_datetime(df["date"]).max().date()
    except Exception:      # noqa: BLE001 — 檔案壞掉/不存在都當作「不知道」
        return None


def _official_latest(game_key: str, today: dt.date) -> list[dict]:
    """該款**官方**來源的最新一批開獎,給「彩世界落後」時 top-up 用。

    彩世界(tof)一站三款很省請求,但常**慢官方約一期** —— 用它回補後,最新一期
    一律再向各款官方來源抓一次,保證不缺最新期(2026-08 因此漏過 539 的 8/26)。
    best-effort:任何抓取失敗都回空清單,不影響已經拿到的彩世界資料。
    """
    try:
        if game_key == "fantasy5":
            return scraper_fantasy5.fetch_history(pages=1)
        if game_key == "marksix":
            return scraper_marksix.fetch_history(pages=1)
        # lotto539:官方台彩「月」API。月初幾天把上個月也抓一次,免得漏掉月底那期。
        rows = list(scraper.fetch_month(today.year, today.month))
        if today.day <= 3:
            py, pm = ((today.year - 1, 12) if today.month == 1
                      else (today.year, today.month - 1))
            rows.extend(scraper.fetch_month(py, pm))
        return rows
    except Exception:
        return []


def catch_up(game_key: str, data_path: str | Path) -> dict:
    """把這一款的開獎資料補到最新;回傳 {fetched, added, latest}。

    抓取失敗會直接拋出例外(讓呼叫端決定要顯示還是記進狀態)。
    背景排程與「立即抓取」按鈕共用這一段,兩邊的行為保證一致。
    """
    data_path = Path(data_path)
    today = dt.date.today()
    game = games.get(game_key)
    df = loader.load_history(data_path, game.pick, game.num_max)
    latest = pd.to_datetime(df["date"]).max().date()
    # 從資料最新日與「今天 − 9 天」較早者開始抓,保證至少重抓 7 期
    start = min(latest, today - dt.timedelta(days=_MIN_SPAN_DAYS))

    # 先試彩世界(tof):一站三款、日期是台灣日期、附期號,而且只要一次請求。
    # 它只留最近 100 期,不夠補的時候才退回各自的原始來源。
    new_rows = []
    try:
        tof_rows = scraper_tof.fetch_history(game_key, game.pick, game.num_max)
        oldest = min(r["date"] for r in tof_rows)
        if oldest <= start:          # 這 100 期涵蓋得到落差區間才夠用
            new_rows = tof_rows
    except scraper_tof.ScrapeError:
        new_rows = []

    if new_rows:
        # 用了彩世界(它慢官方約一期)→ 最新一期再用官方來源 top-up,保證不缺最新期。
        new_rows = new_rows + _official_latest(game_key, today)
    elif game_key == "fantasy5":
        # 天天樂每日開獎:每頁約 50 期,依落差天數換算頁數
        gap_days = (today - start).days
        pages = min(60, max(1, -(-(gap_days + MIN_DRAWS) // 50)))
        new_rows = scraper_fantasy5.fetch_history(pages=pages)
    elif game_key == "marksix":
        # 六合彩每週開三次:把落差天數換算成期數,再換算頁數
        gap_draws = (today - start).days * _MARKSIX_PER_WEEK / 7
        pages = min(20, max(1, -(-int(gap_draws + MIN_DRAWS) // _MARKSIX_PER_PAGE)))
        new_rows = scraper_marksix.fetch_history(pages=pages)
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
    return {"fetched": len(new_rows), "added": added,
            "latest": pd.to_datetime(merged["date"]).max().date()}


def _run(game_key: str, data_path: Path, on_done, on_added=None) -> None:
    """背景執行緒:補抓一次,把結果寫進狀態。"""
    try:
        res = catch_up(game_key, data_path)
        added = res["added"]
        _set(game_key, running=False, error="", done_ts=time.time(), added=added,
             idle=added == 0,
             msg=f"自動補抓完成:重抓 {res['fetched']} 期、新增 {added} 期,"
                 f"資料已到 {res['latest']}。")
        if added > 0 and on_done is not None:
            try:
                on_done()  # 清 load_df 快取,讓各頁面下次 rerun 讀到新資料
            except Exception:
                pass
        if added > 0 and on_added is not None:
            try:
                on_added(game_key)  # 有新開獎 → 檢查斷檔提醒等(見 backend.reminders)
            except Exception:
                pass
    except Exception as e:  # noqa: BLE001 — 背景執行緒,任何錯誤都記進狀態
        _set(game_key, running=False, error=str(e), done_ts=time.time(), idle=False,
             msg=f"自動補抓失敗:{e}")


def kick(game_key: str, data_path: str | Path, latest=None, on_done=None,
         on_added=None) -> bool:
    """資料落後就觸發背景補抓;回傳是否真的啟動。

    是否落後由 core.drawtime 依開獎時刻表判斷 —— 「今天還沒到開獎時間」
    不算落後,不會整天空跑。
    """
    data_path = Path(data_path)
    if latest is None:
        latest = latest_date(data_path, game_key)
    state = drawtime.staleness(game_key, latest)
    if not state["stale"]:
        return False
    target = state["target"].isoformat()

    with _lock:
        s = _status.setdefault(game_key, {})
        if s.get("running"):
            return False
        if s.get("target") != target:      # 換一期了 → 重新開始算次數
            s["target"], s["attempts"] = target, 0
        if s.get("attempts", 0) >= MAX_ATTEMPTS:
            return False
        if s.get("error"):
            cooldown = _COOLDOWN_ERR
        elif s.get("idle"):
            cooldown = _COOLDOWN_IDLE
        else:
            cooldown = _COOLDOWN_OK
        if s.get("done_ts") and time.time() - s["done_ts"] < cooldown:
            return False
        s.update(running=True, msg="背景補抓開獎資料中…", error="",
                 attempts=s.get("attempts", 0) + 1)
    threading.Thread(
        target=_run, args=(game_key, data_path, on_done, on_added), daemon=True
    ).start()
    return True


def _loop(paths: dict[str, Path], on_done, on_added=None) -> None:
    while True:
        for game_key, path in paths.items():
            if drawtime.get(game_key) is None:
                continue                   # 沒登記開獎時刻的款不自動更新
            try:
                kick(game_key, path, on_done=on_done, on_added=on_added)
            except Exception:              # noqa: BLE001 — 排程不能被單款拖垮
                pass
        time.sleep(TICK_SECONDS)


def start_scheduler(paths: dict[str, Path], on_done=None, on_added=None) -> bool:
    """啟動背景排程(整個行程只會起一條);回傳這次是否真的啟動。

    on_added(game_key):有新開獎期被寫入時呼叫(斷檔提醒等)。
    可以重複呼叫 —— Streamlit 每次 rerun 都會走到,第二次以後直接回 False。
    """
    global _scheduler
    with _lock:
        if _scheduler is not None and _scheduler.is_alive():
            return False
        _scheduler = threading.Thread(
            target=_loop,
            args=({k: Path(v) for k, v in paths.items()}, on_done, on_added),
            daemon=True, name="lotto-autoupdate")
        _scheduler.start()
    return True


def scheduler_running() -> bool:
    with _lock:
        return _scheduler is not None and _scheduler.is_alive()
