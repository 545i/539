"""開獎前提醒的排程觸發(core.autoupdate._check_pre_draw)與文字(backend.reminders）。

重點是**只在對的時間、且每期只推一次**:跨過「開獎前 PRE_DRAW_MIN 分」後的寬限窗
內推一次,過了寬限(例如行程在窗內才啟動)就不補推過時提醒;同一次開獎重複檢查
不會連推。時鐘與下次開獎時刻都換成假的,測的是決策不是真的等時間。
"""
import datetime as dt

import pytest

from core import autoupdate, drawtime

TPE = drawtime.TAIPEI
GAME = "lotto539"
DRAW = dt.datetime(2026, 9, 18, 20, 30, tzinfo=TPE)   # 假設下次開獎
LEAD = DRAW - dt.timedelta(minutes=autoupdate.PRE_DRAW_MIN)  # 開獎前 2 小時 = 18:30


@pytest.fixture
def clock(monkeypatch):
    """把 next_draw 固定成 DRAW,now 由測試設定;每次清掉去重狀態。"""
    autoupdate._prefired.clear()
    state = {"now": LEAD}
    monkeypatch.setattr(drawtime, "next_draw", lambda *a, **k: DRAW)
    monkeypatch.setattr(drawtime, "now_taipei", lambda: state["now"])
    return state


def _fires_at(clock, now):
    clock["now"] = now
    hits = []
    autoupdate._check_pre_draw(GAME, hits.append)
    return hits


def test_fires_once_when_crossing_lead(clock):
    assert _fires_at(clock, LEAD + dt.timedelta(seconds=30)) == [GAME]


def test_dedups_same_draw(clock):
    assert _fires_at(clock, LEAD + dt.timedelta(seconds=30)) == [GAME]
    # 同一次開獎、窗還沒過,再檢查一次不該重推
    assert _fires_at(clock, LEAD + dt.timedelta(minutes=3)) == []


def test_not_before_lead(clock):
    assert _fires_at(clock, LEAD - dt.timedelta(minutes=1)) == []


def test_not_after_grace_window(clock):
    # 行程在「開獎前 30 分」才啟動:早過了寬限窗 → 不補推過時的「開獎前」提醒
    late = LEAD + dt.timedelta(seconds=autoupdate._PRE_FIRE_GRACE + 60)
    assert _fires_at(clock, late) == []


def test_no_callback_is_safe(clock):
    clock["now"] = LEAD + dt.timedelta(seconds=30)
    autoupdate._check_pre_draw(GAME, None)   # 不該爆
    assert autoupdate._prefired == {}        # 沒 callback 就不佔用去重


def test_no_next_draw_is_safe(clock, monkeypatch):
    monkeypatch.setattr(drawtime, "next_draw", lambda *a, **k: None)
    assert _fires_at(clock, LEAD + dt.timedelta(seconds=30)) == []


def test_lead_text_formats():
    from backend import reminders
    assert reminders._lead_text(120) == "2 小時"
    assert reminders._lead_text(90) == "1.5 小時"
    assert reminders._lead_text(40) == "40 分鐘"


def test_push_pre_draw_without_creds_returns_false(monkeypatch):
    from core import notify
    from backend import reminders
    monkeypatch.setattr(notify, "enabled", lambda: False)
    assert reminders.push_pre_draw(GAME) is False
