"""預先記錄(期號未定)+ 依日期校正結算,以及日期→期號 resolver。

情境:那一天還沒開時就先上傳下注(期號留空),等這天真的開了,對獎要能
依**下注日期**反查真實開獎號 + 期號回填結算(見 backend.autosettle 與
backend.routers.history.resolve_issue)。

關鍵不可回歸:**有期號時一律以期號為準,絕不退回用日期查**(同一天可能記了
兩期,用日期會拿錯的號碼結算 —— 見 test_app_smoke 的同名警示)。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from backend import autosettle, edition_store
from backend.routers import history
from core.games import LOTTO539 as G


@pytest.fixture(autouse=True)
def _isolate_edition(tmp_path, monkeypatch):
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")


def _pending(**kw) -> dict:
    base = {"result": "待開獎", "game": G.name, "mode": "single",
            "selectedBalls": [12], "cars": 1, "units": 1, "cost": 1000}
    base.update(kw)
    return base


# ── settle_record_if_drawn 的三條路徑 ─────────────────────────────
def test_empty_issue_settles_by_date_and_backfills(monkeypatch):
    """期號留空 + 那天已開 → 依日期反查、回填真實期號並結算。"""
    monkeypatch.setattr(autosettle.data, "draw_by_date",
                        lambda k, d: ([12, 5, 6, 7, 8], "115000200"))
    out = autosettle.settle_record_if_drawn(
        _pending(issue="", date="2026-08-18"), G)
    assert out["result"] != "待開獎"          # 有結算
    assert out["issue"] == "115000200"         # 回填真實期號
    assert out["date"] == "2026-08-18"


def test_empty_issue_undrawn_date_stays_pending(monkeypatch):
    """期號留空 + 那天還沒開 → 維持待開獎。"""
    monkeypatch.setattr(autosettle.data, "draw_by_date", lambda k, d: None)
    out = autosettle.settle_record_if_drawn(
        _pending(issue="", date="2099-01-01"), G)
    assert out["result"] == "待開獎"


def test_issue_present_never_falls_back_to_date(monkeypatch):
    """有期號但那期還沒開 → 維持待開獎,**不准**退回用日期查(防同日多期誤配)。"""
    called = {"date": False}

    def _no_date(k, d):
        called["date"] = True
        return ([1, 2, 3, 4, 5], "wrong")

    monkeypatch.setattr(autosettle.data, "draw_by_issue", lambda k, i: None)
    monkeypatch.setattr(autosettle.data, "draw_by_date", _no_date)
    out = autosettle.settle_record_if_drawn(
        _pending(issue="115000208", date="2026-08-18"), G)
    assert out["result"] == "待開獎"
    assert not called["date"], "有期號就不該去用日期查"


def test_issue_present_settles_by_issue(monkeypatch):
    """有期號且已開 → 依期號結算(維持原行為)。"""
    monkeypatch.setattr(autosettle.data, "draw_by_issue",
                        lambda k, i: ([12, 5, 6, 7, 8], "2026-08-18"))
    out = autosettle.settle_record_if_drawn(
        _pending(issue="115000200", date="whatever"), G)
    assert out["result"] != "待開獎"
    assert out["issue"] == "115000200"
    assert out["date"] == "2026-08-18"          # 用期號查到的日期覆蓋


# ── resolve_issue:日期 → 期號狀態 ────────────────────────────────
def _fake_df(rows: list[tuple[str, str, list[int]]]) -> pd.DataFrame:
    """rows = [(date_str, issue, [n1..n5]), …](舊→新)。"""
    data = {"date": [pd.Timestamp(d) for d, _, _ in rows],
            "issue": [i for _, i, _ in rows]}
    for j in range(5):
        data[f"n{j + 1}"] = [nums[j] for _, _, nums in rows]
    return pd.DataFrame(data)


def test_resolve_drawn(monkeypatch):
    df = _fake_df([("2026-08-18", "115000200", [1, 2, 3, 4, 5])])
    monkeypatch.setattr(history, "load_df", lambda g: df)
    r = history.resolve_issue("lotto539", "2026-08-18")
    assert r["status"] == "drawn" and r["issue"] == "115000200"


def test_resolve_pending_predicts_numeric(monkeypatch):
    # 最新 8/18(週二),下一個 539 開獎日 8/19(週三)→ 預估 +1
    df = _fake_df([("2026-08-18", "115000200", [1, 2, 3, 4, 5])])
    monkeypatch.setattr(history, "load_df", lambda g: df)
    r = history.resolve_issue("lotto539", "2026-08-19")
    assert r["status"] == "pending"
    assert r["issue"] == ""                      # 期號留空(依日期校正)
    assert r["predicted"] == "115000201"         # 顯示用預估


def test_resolve_closed_non_draw_day(monkeypatch):
    df = _fake_df([("2026-08-18", "115000200", [1, 2, 3, 4, 5])])
    monkeypatch.setattr(history, "load_df", lambda g: df)
    # 539 週日不開獎(2026-08-23 為週日)
    assert dt.date(2026, 8, 23).weekday() == 6
    r = history.resolve_issue("lotto539", "2026-08-23")
    assert r["status"] == "closed"
