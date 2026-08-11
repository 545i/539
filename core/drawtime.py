"""三款遊戲的開獎時刻表,以及「現在該不該去抓資料」的判斷。

各款的開獎時間(2026-08 查證,來源見下方 SOURCES):
  今彩539    週一~週六 20:30(台灣)
  六合彩      週二、週四,以及非賽馬日的週六或週日 21:30(香港,與台灣同為 UTC+8)
  天天樂      加州每天 18:30(America/Los_Angeles)

**日期基準一律是台灣日期** —— 三個 CSV 存的都是台灣日期(天天樂先前已用
tools/fix_fantasy5_dates.py 從加州日期改成台灣日期)。加州 18:30 開的那期,
台灣已經是隔天早上(夏令 09:30、冬令 10:30),所以天天樂的 day_offset 是 −1:
台灣日期 D 的那一期,是加州 D−1 日 18:30 開的。用 zoneinfo 換算,夏令/冬令
自動處理,不必寫死時差。

判斷「資料過期」不是用「幾點到了就抓」,而是問:**到現在為止,最後一期
應該已經開完並且抓得到的是哪一天?** 資料比它舊就是過期。這樣服務重啟、
錯過時間點、補登舊資料都不會漏抓,不需要精準地在某個時刻醒來。
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")

# 往回/往前找開獎日時最多掃幾天(六合彩最長間隔 3 天,14 天綽綽有餘)
_SCAN_DAYS = 14

# 開獎後等多久才去抓。開完到來源站上架有時間差,太早抓只會抓到舊資料、
# 白白耗掉「同一期最多試幾次」的額度。寧可晚半小時拿到,也不要空跑。
READY_BUFFER_MIN = 30

SOURCES = {
    "lotto539": "台灣彩券官網開獎時間表(每週一至週六 20:30)",
    "marksix": "香港賽馬會六合彩(每週二、四,及非賽馬日的週六/週日 21:30)",
    "fantasy5": "California State Lottery — Fantasy 5(每日 18:30 太平洋時間)",
}


@dataclass(frozen=True)
class DrawSchedule:
    """一款遊戲的開獎時刻表。

    weekdays   會開獎的星期(以**台灣日期**計,0=週一 … 6=週日)
    tz         開獎時刻所在的時區
    at         該時區的開獎時刻
    day_offset 開獎當地日期 = 台灣日期 + day_offset(天天樂為 −1)
    ready_min  開獎後幾分鐘,資料來源才穩定抓得到(留給對方站台上架的時間)
    note       顯示給使用者看的說明
    """
    weekdays: tuple[int, ...]
    tz: str
    at: dt.time
    day_offset: int = 0
    ready_min: int = READY_BUFFER_MIN
    note: str = ""
    # 「擇一開獎」的星期配對 (主要日, 備用日):兩天只會開其中一天。
    # 六合彩遇賽馬日會把攪珠從週六挪到週日,所以兩天都得當成可能開獎;
    # 但資料裡已經有主要日那期的話,備用日就不必再等 ——
    # 否則沒開的那天會整輪空抓。
    either_days: tuple[tuple[int, int], ...] = ()

    def draws_on(self, taipei_date: dt.date) -> bool:
        return taipei_date.weekday() in self.weekdays

    def draw_moment(self, taipei_date: dt.date) -> dt.datetime:
        """台灣日期 taipei_date 那一期的開獎時刻(回傳台灣時間)。"""
        local_date = taipei_date + dt.timedelta(days=self.day_offset)
        local = dt.datetime.combine(local_date, self.at, tzinfo=ZoneInfo(self.tz))
        return local.astimezone(TAIPEI)

    def ready_moment(self, taipei_date: dt.date) -> dt.datetime:
        """那一期「應該抓得到」的時刻 = 開獎時刻 + 上架緩衝。"""
        return self.draw_moment(taipei_date) + dt.timedelta(minutes=self.ready_min)


# 六合彩把週六與週日都列進來:賽馬日時攪珠會從週六挪到週日,兩天都當成
# 「可能開獎」比較不會漏抓。真的沒開的那天會連抓幾次抓不到東西,
# 由 autoupdate 的「同一期最多試幾次」擋下來,不會無限重試。
SCHEDULES: dict[str, DrawSchedule] = {
    "lotto539": DrawSchedule(
        weekdays=(0, 1, 2, 3, 4, 5),          # 週一~週六
        tz="Asia/Taipei", at=dt.time(20, 30),
        note="每週一至週六 20:30 開獎",
    ),
    "marksix": DrawSchedule(
        weekdays=(1, 3, 5, 6),                # 週二、四、六、日
        tz="Asia/Hong_Kong", at=dt.time(21, 30),
        either_days=((5, 6),),                # 週六 / 週日 擇一
        note="每週二、四,及非賽馬日的週六或週日 21:30 開獎(港台同時區)",
    ),
    "fantasy5": DrawSchedule(
        weekdays=(0, 1, 2, 3, 4, 5, 6),       # 每天
        tz="America/Los_Angeles", at=dt.time(18, 30), day_offset=-1,
        note="加州每天 18:30 開獎;台灣時間是隔天早上(夏令 09:30、冬令 10:30)",
    ),
}


def get(game_key: str) -> DrawSchedule | None:
    """取得該款的時刻表;沒有登記的款回 None(代表不做自動更新)。"""
    return SCHEDULES.get(game_key)


def now_taipei() -> dt.datetime:
    return dt.datetime.now(TAIPEI)


def last_ready_draw(game_key: str, now: dt.datetime | None = None) -> dt.date | None:
    """到 now 為止,最後一期「已經開完且應該抓得到」的台灣日期。

    找不到(例如時刻表未登記,或往回掃 14 天都沒有開獎日)回 None。
    """
    sched = get(game_key)
    if sched is None:
        return None
    now = now or now_taipei()
    day = now.astimezone(TAIPEI).date()
    for _ in range(_SCAN_DAYS + 1):
        if sched.draws_on(day) and sched.ready_moment(day) <= now:
            return day
        day -= dt.timedelta(days=1)
    return None


def next_draw(game_key: str, now: dt.datetime | None = None) -> dt.datetime | None:
    """下一次開獎的時刻(台灣時間);找不到回 None。"""
    sched = get(game_key)
    if sched is None:
        return None
    now = now or now_taipei()
    day = now.astimezone(TAIPEI).date()
    for _ in range(_SCAN_DAYS + 1):
        if sched.draws_on(day):
            moment = sched.draw_moment(day)
            if moment > now:
                return moment
        day += dt.timedelta(days=1)
    return None


def _as_date(value) -> dt.date | None:
    """把各種日期表示法轉成 date;轉不動回 None。"""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def staleness(game_key: str, latest_date, now: dt.datetime | None = None) -> dict:
    """這一款的資料是不是落後了。

    回傳 {stale, target, latest, next_draw}:
      stale     True 代表該去抓了
      target    現在應該已經有的最新一期(台灣日期);None 代表無從判斷
      latest    目前資料的最新日期
      next_draw 下一次開獎時刻
    """
    target = last_ready_draw(game_key, now)
    latest = _as_date(latest_date)
    stale = bool(target and (latest is None or latest < target))

    # 擇一開獎:target 落在備用日,而資料已經有同一輪主要日那期 → 那天沒開,不算落後
    sched = get(game_key)
    if stale and target and latest and sched:
        for primary, alt in sched.either_days:
            if target.weekday() == alt and latest == target - dt.timedelta(
                    days=alt - primary):
                stale = False
                break

    return {"stale": stale, "target": target, "latest": latest,
            "next_draw": next_draw(game_key, now)}
