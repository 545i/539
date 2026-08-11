"""自動補抓的觸發條件(core.autoupdate.kick)。

重點是**什麼時候不該去抓**:當天還沒開獎、剛抓完還在冷卻、同一期已經試過
太多次(例如六合彩那天其實沒開獎)。抓錯時間只是浪費,一直重試卻會變成
對來源站台的騷擾,所以這幾條界線要釘死。

執行緒在這裡被換成「當場跑完」的假物件,測的是決策不是併發。
"""
import datetime as dt

import pytest

from core import autoupdate, drawtime

TPE = drawtime.TAIPEI
GAME = "lotto539"


class _InlineThread:
    """把背景執行緒換成當場執行,測試才不用等。"""

    def __init__(self, target, args=(), **kw):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)

    def is_alive(self):
        return False


class _Env:
    """測試當下的世界:現在幾點、資料到哪天、抓取會拿回幾筆新資料。"""

    def __init__(self):
        self.calls: list[str] = []
        self.added = 1
        self.latest = dt.date(2026, 8, 5)
        self.now = dt.datetime(2026, 8, 10, 22, 0, tzinfo=TPE)


@pytest.fixture()
def env(monkeypatch):
    """把時間、抓取、執行緒都換掉,只留下 kick 的判斷邏輯。"""
    autoupdate._status.clear()
    e = _Env()
    monkeypatch.setattr(autoupdate.threading, "Thread", _InlineThread)

    def fake_catch_up(game_key, data_path):
        e.calls.append(game_key)
        return {"fetched": 5, "added": e.added, "latest": dt.date(2026, 8, 10)}

    monkeypatch.setattr(autoupdate, "catch_up", fake_catch_up)
    monkeypatch.setattr(autoupdate, "latest_date", lambda p, k: e.latest)
    monkeypatch.setattr(drawtime, "now_taipei", lambda: e.now)
    yield e
    autoupdate._status.clear()


def test_kicks_when_data_is_behind(env, tmp_path):
    assert autoupdate.kick(GAME, tmp_path / "h.csv") is True
    assert env.calls == [GAME]


def test_does_not_kick_before_the_draw(env, tmp_path):
    """當天 15:00 還沒開獎,資料停在上一期不算落後。"""
    env.now = dt.datetime(2026, 8, 10, 15, 0, tzinfo=TPE)
    env.latest = dt.date(2026, 8, 8)
    assert autoupdate.kick(GAME, tmp_path / "h.csv") is False
    assert env.calls == []


def test_does_not_kick_when_current(env, tmp_path):
    env.latest = dt.date(2026, 8, 10)
    assert autoupdate.kick(GAME, tmp_path / "h.csv") is False


def test_cooldown_blocks_immediate_retry(env, tmp_path):
    autoupdate.kick(GAME, tmp_path / "h.csv")
    assert autoupdate.kick(GAME, tmp_path / "h.csv") is False
    assert len(env.calls) == 1


def test_idle_result_uses_longer_cooldown(env, tmp_path):
    """抓到了但沒有新資料 → 記成 idle,下次要等更久。"""
    env.added = 0
    autoupdate.kick(GAME, tmp_path / "h.csv")
    s = autoupdate.status(GAME)
    assert s["idle"] is True and s["added"] == 0


def test_gives_up_after_max_attempts_on_the_same_draw(env, tmp_path, monkeypatch):
    """同一期試滿次數就停手 —— 那天其實沒開獎時不會整天狂打對方站台。"""
    env.added = 0
    monkeypatch.setattr(autoupdate.time, "time", lambda: 0.0)  # 冷卻永遠算「已過」
    for _ in range(autoupdate.MAX_ATTEMPTS):
        assert autoupdate.kick(GAME, tmp_path / "h.csv") is True
    assert autoupdate.kick(GAME, tmp_path / "h.csv") is False
    assert len(env.calls) == autoupdate.MAX_ATTEMPTS


def test_new_draw_resets_the_attempt_counter(env, tmp_path, monkeypatch):
    env.added = 0
    monkeypatch.setattr(autoupdate.time, "time", lambda: 0.0)
    for _ in range(autoupdate.MAX_ATTEMPTS):
        autoupdate.kick(GAME, tmp_path / "h.csv")
    assert autoupdate.kick(GAME, tmp_path / "h.csv") is False

    env.now = dt.datetime(2026, 8, 11, 22, 0, tzinfo=TPE)   # 下一期開完了
    assert autoupdate.kick(GAME, tmp_path / "h.csv") is True


def test_failure_is_recorded_and_retried_sooner(env, tmp_path, monkeypatch):
    def boom(game_key, data_path):
        raise RuntimeError("來源站掛了")

    monkeypatch.setattr(autoupdate, "catch_up", boom)
    autoupdate.kick(GAME, tmp_path / "h.csv")
    s = autoupdate.status(GAME)
    assert "來源站掛了" in s["error"]
    assert s["running"] is False


def test_unscheduled_game_is_never_kicked(env, tmp_path):
    assert autoupdate.kick("nope", tmp_path / "h.csv") is False
