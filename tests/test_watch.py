"""區間組合斷檔的公共設定(backend.watch_store)與提醒計算(backend.reminders)。"""
from __future__ import annotations

import pytest

from backend import reminders, watch_store


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(watch_store, "_db_path", lambda: tmp_path / "watch.db")


def test_default_combo_is_bands():
    combos = watch_store.get_combos("lotto539")
    assert len(combos) == 1
    c = combos[0]
    assert len(c["groups"]) == 4                 # 0~3頭 四段
    assert c["groups"][0][:3] == [1, 2, 3]
    assert c["groups"][-1][-1] == 39
    assert c["threshold"] == watch_store.DEFAULT_THRESHOLD


def test_set_get_roundtrip_and_public():
    watch_store.set_combos("lotto539", [
        {"label": "自訂", "groups": [[1, 2], [10, 11]], "threshold": 3}])
    got = watch_store.get_combos("lotto539")
    assert got == [{"label": "自訂", "groups": [[1, 2], [10, 11]], "threshold": 3}]
    # 存空清單也要記住(不會又塞回預設)
    watch_store.set_combos("lotto539", [])
    assert watch_store.get_combos("lotto539") == []


def test_check_combo_watch_runs():
    # 用真實 CSV 計算,不該炸;回的是「達門檻」的清單(可能為空)
    al = reminders.check_combo_watch("lotto539")
    assert isinstance(al, list)


def test_notify_disabled_returns_false(monkeypatch):
    # 沒設 token/chat_id → notify.enabled() False → 不發、回 False
    from core import notify
    monkeypatch.setattr(notify, "_token", lambda: "")
    assert reminders.notify_combo_watch("lotto539") is False
