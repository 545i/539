"""快速上傳的 5 項防呆邊界:1 個 🔴 拒絕(六合彩×特殊下法)+ 4 個 🟡 警告
(期號格式 / 大車支 / 舊日期 / 重複)。

- errors:那一筆不寫入(六合彩星碰/三柱 在 parse、_recost 都要擋)。
- warnings:提示但可上傳,由 importer._collect_warnings 逐項組出。
"""
from datetime import date

import pytest

from backend import edition_store, group_store
from backend.data import get_game
from backend.routers import importer


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(group_store, "_db_path", lambda: tmp_path / "group.db")
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")

    def _odds(key):
        return edition_store.get_odds(1, key)

    return _odds


# ── 1. 遊戲×下法不合 → 🔴 拒絕 ──────────────────────────────
def test_marksix_star_rejected_in_parse(env):
    """六合彩收到星碰 → 進 errors「六合彩不支援星碰」,不產出 combo 筆。"""
    g = get_game("marksix")
    items, errors = importer.parse("07_33_36\n八顆三星1200", g, env("marksix"))
    assert any("六合彩不支援星碰" in e["message"] for e in errors)
    assert not any(it.mode == "combo" for it in items)


def test_marksix_pillar_rejected_in_parse(env):
    """六合彩收到 1800碰(三柱)→ errors「六合彩不支援三柱」。"""
    g = get_game("marksix")
    items, errors = importer.parse("10_18\n20_29\n其他400", g, env("marksix"))
    assert any("六合彩不支援三柱" in e["message"] for e in errors)
    assert not any(it.mode == "pillar1800" for it in items)


def test_marksix_star_rejected_in_recost(env):
    """_recost 也要擋:六合彩×星碰直接 raise(commit 端點收成 error)。"""
    g = get_game("marksix")
    with pytest.raises(ValueError, match="六合彩不支援星碰"):
        importer._recost(g, env("marksix"), "combo", [7, 33, 36], 1, 3)


def test_lotto539_star_still_ok(env):
    """防呆別誤傷:今彩539 的星碰照常解析成功。"""
    g = get_game("lotto539")
    items, errors = importer.parse("07_33_36\n八顆三星1200", g, env("lotto539"))
    assert any(it.mode == "combo" for it in items)


# ── 2. 期號格式 × 遊戲不符 → 🟡 警告 ────────────────────────
def test_issue_format_fantasy5_got_539_issue():
    """天天樂收到 9 碼(539 期號)→ 警告(踩過的真實 bug)。"""
    g = get_game("fantasy5")
    assert importer._issue_format_warning(g, "115000207") is not None
    assert importer._issue_format_warning(g, "11981") is None


def test_issue_format_lotto539_got_marksix_issue():
    """今彩539 收到 2026/093(六合彩期號)→ 警告。"""
    g = get_game("lotto539")
    assert importer._issue_format_warning(g, "2026/093") is not None
    assert importer._issue_format_warning(g, "115000207") is None


def test_issue_format_marksix_ok():
    g = get_game("marksix")
    assert importer._issue_format_warning(g, "2026/093") is None
    assert importer._issue_format_warning(g, "11981") is not None


# ── 3. 車/支數異常大 → 🟡 警告 ─────────────────────────────
@pytest.mark.parametrize("mode,big,ok", [
    ("single", 200, 100),
    ("multi", 200, 100),
    ("combo", 40, 20),
    ("pillar1800", 20, 10),
    ("combo9000", 15, 8),
])
def test_units_warning(mode, big, ok):
    assert importer._units_warning({"mode": mode, "units": big}) is not None
    assert importer._units_warning({"mode": mode, "units": ok}) is None


# ── 4. 日期異常(比最新開獎早超過 14 天)→ 🟡 警告 ──────────
def test_date_warning(monkeypatch):
    g = get_game("lotto539")
    monkeypatch.setattr(importer, "_latest_draw_date", lambda _g: date(2026, 8, 26))
    assert importer._date_warning(g, "2026-08-01") is not None   # 25 天 > 14
    assert importer._date_warning(g, "2026-08-20") is None       # 6 天


def test_date_warning_silent_when_no_data(monkeypatch):
    g = get_game("lotto539")
    monkeypatch.setattr(importer, "_latest_draw_date", lambda _g: None)
    assert importer._date_warning(g, "2000-01-01") is None


# ── 5. 重複上傳 → 🟡 警告 ──────────────────────────────────
def _rec(**kw):
    base = {"edition": 1, "issue": "115000207", "mode": "single",
            "selectedBalls": [2], "units": 50}
    base.update(kw)
    return base


def test_duplicate_warning():
    g = get_game("lotto539")
    existing = [{"record": _rec()}]
    warnings = importer._collect_warnings(
        g, "2026-08-26", "115000207", [(1, _rec())], existing)
    assert any("重複" in w["message"] for w in warnings)


def test_not_duplicate_when_units_differ():
    g = get_game("lotto539")
    existing = [{"record": _rec(units=50)}]
    warnings = importer._collect_warnings(
        g, "2026-08-26", "115000207", [(1, _rec(units=60))], existing)
    assert not any("重複" in w["message"] for w in warnings)
