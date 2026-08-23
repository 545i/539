"""core.notify 推播韌性:分段、HTML 失敗退純文字、失敗原因記錄。

這些是「避免提醒發不出來」的三層防護,全走假的 _call,不會真的打 Telegram。
"""
from __future__ import annotations

import pytest

from core import notify


@pytest.fixture(autouse=True)
def _fake_creds(monkeypatch):
    monkeypatch.setattr(notify, "_token", lambda: "tok")
    monkeypatch.setattr(notify, "_chat_id", lambda: "123")
    notify._last_error = ""


# ── 分段 _split ──────────────────────────────────────────
def test_split_short_text_single_chunk():
    assert notify._split("hello", 4096) == ["hello"]


def test_split_keeps_each_chunk_within_limit_and_lossless():
    text = "\n".join(f"line {i:04d}" for i in range(1000))
    parts = notify._split(text, 4096)
    assert len(parts) > 1
    assert all(len(p) <= 4096 for p in parts)
    assert "\n".join(parts) == text


def test_split_hard_splits_overlong_single_line():
    parts = notify._split("x" * 9000, 4096)
    assert all(len(p) <= 4096 for p in parts)
    assert "".join(parts) == "x" * 9000


# ── 純文字退路 _strip_tags ────────────────────────────────
def test_strip_tags_removes_html_and_unescapes():
    assert notify._strip_tags("<b>今彩</b> &amp; &lt;3") == "今彩 & <3"


# ── send 三層防護 ─────────────────────────────────────────
def test_send_falls_back_to_plain_when_html_rejected(monkeypatch):
    calls = []

    def fake_call(method, params, timeout=8.0):
        calls.append(dict(params))
        if params.get("parse_mode") == "HTML":
            return {"ok": False, "description": "can't parse entities"}
        return {"ok": True}

    monkeypatch.setattr(notify, "_call", fake_call)
    assert notify.send("<b>壞HTML<") is True
    assert len(calls) == 2
    assert "parse_mode" not in calls[1]      # 第二次改純文字


def test_send_chunks_long_message(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "_call",
                        lambda m, p, timeout=8.0: calls.append(p) or {"ok": True})
    notify.send("\n".join(["x" * 500] * 50))  # 遠超 4096
    assert len(calls) > 1


def test_send_button_only_on_last_chunk(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "_call",
                        lambda m, p, timeout=8.0: calls.append(p) or {"ok": True})
    kb = {"inline_keyboard": [[{"text": "x", "callback_data": "c"}]]}
    notify.send("\n".join(["x" * 500] * 50), reply_markup=kb)
    assert "reply_markup" not in calls[0]
    assert "reply_markup" in calls[-1]


def test_send_records_last_error(monkeypatch):
    def fake_call(method, params, timeout=8.0):
        notify._last_error = "boom"
        return {"ok": False, "description": "boom"}

    monkeypatch.setattr(notify, "_call", fake_call)
    assert notify.send("hi", parse_mode="") is False
    assert notify.last_error() == "boom"


def test_send_noop_without_creds(monkeypatch):
    monkeypatch.setattr(notify, "_token", lambda: "")
    assert notify.send("hi") is False
