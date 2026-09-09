"""開獎時刻表與「該不該抓」的判斷(core.drawtime)。

三個 CSV 存的都是**台灣日期**,所以時刻表也一律以台灣日期為準。
天天樂是加州 18:30 開獎、台灣已經隔天,day_offset=−1 —— 這裡把夏令/冬令
兩種情況都釘住,免得哪天改成寫死時差又踩回時區的坑。
"""
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from core import drawtime

TPE = drawtime.TAIPEI


def tpe(y, m, d, hh=0, mm=0):
    return dt.datetime(y, m, d, hh, mm, tzinfo=TPE)


# ── 時刻表本身 ───────────────────────────────────────────
def test_all_games_have_a_schedule():
    from core import games
    for key in games.GAMES:
        assert drawtime.get(key) is not None, f"{key} 沒有登記開獎時刻"


def test_unknown_game_has_no_schedule():
    assert drawtime.get("nope") is None
    assert drawtime.last_ready_draw("nope") is None
    assert drawtime.next_draw("nope") is None


def test_ready_buffer():
    """預設開獎後等 15 分鐘再抓;539 上架快 → 提前 5 分。"""
    assert drawtime.READY_BUFFER_MIN == 15
    assert drawtime.SCHEDULES["lotto539"].ready_min == 5
    assert drawtime.SCHEDULES["marksix"].ready_min == 15
    assert drawtime.SCHEDULES["fantasy5"].ready_min == 15


# ── 今彩539:週一~六 20:30 台灣 ──────────────────────────
def test_lotto539_draw_moment():
    assert drawtime.SCHEDULES["lotto539"].draw_moment(dt.date(2026, 8, 10)) \
        == tpe(2026, 8, 10, 20, 30)


def test_lotto539_no_draw_on_sunday():
    assert not drawtime.SCHEDULES["lotto539"].draws_on(dt.date(2026, 8, 9))  # 週日
    assert drawtime.SCHEDULES["lotto539"].draws_on(dt.date(2026, 8, 10))     # 週一


@pytest.mark.parametrize("now, expect", [
    (tpe(2026, 8, 10, 20, 29), dt.date(2026, 8, 8)),   # 還沒開 → 上一期(週六)
    (tpe(2026, 8, 10, 20, 33), dt.date(2026, 8, 8)),   # 開了但還在 5 分鐘緩衝內(ready 20:35)
    (tpe(2026, 8, 10, 20, 45), dt.date(2026, 8, 10)),  # 過了 5 分緩衝 → 抓得到當期
    (tpe(2026, 8, 11, 9, 0), dt.date(2026, 8, 10)),    # 隔天早上仍是週一那期
])
def test_lotto539_last_ready_draw(now, expect):
    assert drawtime.last_ready_draw("lotto539", now) == expect


def test_lotto539_next_draw_skips_sunday():
    # 週六 21:00(當期已開完)→ 下一期是週一
    assert drawtime.next_draw("lotto539", tpe(2026, 8, 8, 21, 0)) \
        == tpe(2026, 8, 10, 20, 30)


# ── 天天樂:加州 18:30,台灣日期 = 加州日期 + 1 ────────────
def test_fantasy5_summer_is_0930_taipei():
    """夏令(PDT, UTC−7):加州 8/9 18:30 → 台灣 8/10 09:30。"""
    moment = drawtime.SCHEDULES["fantasy5"].draw_moment(dt.date(2026, 8, 10))
    assert moment == tpe(2026, 8, 10, 9, 30)
    assert moment.astimezone(ZoneInfo("America/Los_Angeles")).date() \
        == dt.date(2026, 8, 9)


def test_fantasy5_winter_is_1030_taipei():
    """冬令(PST, UTC−8):加州 1/9 18:30 → 台灣 1/10 10:30。"""
    assert drawtime.SCHEDULES["fantasy5"].draw_moment(dt.date(2026, 1, 10)) \
        == tpe(2026, 1, 10, 10, 30)


def test_fantasy5_last_ready_draw_crosses_the_morning():
    # 台灣 8/10 09:40 —— 當天那期 09:30 開,還在 15 分鐘緩衝內(ready 09:45)
    assert drawtime.last_ready_draw("fantasy5", tpe(2026, 8, 10, 9, 40)) \
        == dt.date(2026, 8, 9)
    # 09:45 之後才算抓得到
    assert drawtime.last_ready_draw("fantasy5", tpe(2026, 8, 10, 9, 50)) \
        == dt.date(2026, 8, 10)


# ── 六合彩:週二/四/六/日 21:30 ───────────────────────────
def test_marksix_weekdays_include_sunday():
    """攪珠遇賽馬日會從週六挪到週日,兩天都當成可能開獎,才不會漏抓。"""
    sched = drawtime.SCHEDULES["marksix"]
    assert sched.draws_on(dt.date(2026, 8, 11))   # 週二
    assert sched.draws_on(dt.date(2026, 8, 13))   # 週四
    assert sched.draws_on(dt.date(2026, 8, 15))   # 週六
    assert sched.draws_on(dt.date(2026, 8, 16))   # 週日
    assert not sched.draws_on(dt.date(2026, 8, 10))   # 週一
    assert not sched.draws_on(dt.date(2026, 8, 12))   # 週三


def test_marksix_saturday_draw_means_sunday_is_not_stale():
    """週六已經開過就不會再開週日 —— 不該為了不存在的那期空抓一整輪。"""
    now = tpe(2026, 8, 16, 23, 0)              # 週日 23:00
    s = drawtime.staleness("marksix", dt.date(2026, 8, 15), now)   # 資料到週六
    assert s["target"] == dt.date(2026, 8, 16)
    assert s["stale"] is False


def test_marksix_sunday_draw_is_still_caught():
    """反過來:攪珠真的挪到週日時,資料停在週四就該去抓。"""
    now = tpe(2026, 8, 16, 23, 0)
    s = drawtime.staleness("marksix", dt.date(2026, 8, 13), now)   # 資料只到週四
    assert s["stale"] is True


def test_either_days_only_applies_to_the_alternate_day():
    """週六本身仍然照常判斷,不會被擇一規則放行。"""
    now = tpe(2026, 8, 15, 23, 0)              # 週六 23:00
    s = drawtime.staleness("marksix", dt.date(2026, 8, 13), now)
    assert s["target"] == dt.date(2026, 8, 15) and s["stale"] is True


def test_marksix_hong_kong_time_equals_taipei():
    """港台同為 UTC+8,21:30 就是 21:30。"""
    assert drawtime.SCHEDULES["marksix"].draw_moment(dt.date(2026, 8, 11)) \
        == tpe(2026, 8, 11, 21, 30)


# ── 落後判斷 ─────────────────────────────────────────────
def test_staleness_when_data_is_behind():
    s = drawtime.staleness("lotto539", dt.date(2026, 8, 5), tpe(2026, 8, 10, 22, 0))
    assert s["stale"] is True
    assert s["target"] == dt.date(2026, 8, 10)
    assert s["latest"] == dt.date(2026, 8, 5)


def test_staleness_when_data_is_current():
    s = drawtime.staleness("lotto539", dt.date(2026, 8, 10), tpe(2026, 8, 10, 22, 0))
    assert s["stale"] is False


def test_not_stale_before_todays_draw():
    """關鍵:當天還沒開獎時,資料停在昨天不算落後,不該整天空跑。"""
    s = drawtime.staleness("lotto539", dt.date(2026, 8, 8), tpe(2026, 8, 10, 15, 0))
    assert s["stale"] is False
    assert s["target"] == dt.date(2026, 8, 8)


def test_staleness_accepts_string_and_datetime():
    now = tpe(2026, 8, 10, 22, 0)
    assert drawtime.staleness("lotto539", "2026-08-10", now)["stale"] is False
    assert drawtime.staleness(
        "lotto539", dt.datetime(2026, 8, 10, 20, 30), now)["stale"] is False
    assert drawtime.staleness("lotto539", "壞掉的日期", now)["stale"] is True


def test_staleness_with_no_data_at_all():
    s = drawtime.staleness("lotto539", None, tpe(2026, 8, 10, 22, 0))
    assert s["stale"] is True


def test_staleness_reports_next_draw():
    s = drawtime.staleness("lotto539", dt.date(2026, 8, 10), tpe(2026, 8, 10, 22, 0))
    assert s["next_draw"] == tpe(2026, 8, 11, 20, 30)
