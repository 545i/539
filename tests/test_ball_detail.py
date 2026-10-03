"""二合(1組/2組)逐顆車數 / 每注成本(ballDetail):成本、對獎、相容、編輯器換算。

ballDetail = [{n, cars, base}]:每顆號碼各自的車數與每注成本(絕對值)。
成本 = Σ 車數 × 每注 × (num_max−1);派彩 = Σ 中獎號碼各自車數 × win_payout。
各顆車數與每注都相同時收斂成一般紀錄(不存 ballDetail),沒有 ballDetail 的舊紀錄行為不變。
"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import (audit_store, data, edition_store, group_store,  # noqa: E402
                     ledger_store, reconcile, settle)
from backend.data import get_game  # noqa: E402
from backend.routers import audit, importer, ledger  # noqa: E402
from core import auth  # noqa: E402

P = "/api"
DRAW = [3, 13, 20, 30, 35]


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    monkeypatch.setattr(audit_store, "_db_path", lambda: tmp_path / "audit.db")
    monkeypatch.setattr(group_store, "_db_path", lambda: tmp_path / "group.db")
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")
    monkeypatch.setattr(data, "draw_by_issue",
                        lambda key, issue: (DRAW, "2026-09-01") if str(issue) == "115000300" else None)
    monkeypatch.setattr(data, "draw_by_date", lambda key, d: None)
    return get_game("lotto539"), edition_store.get_odds(1, "lotto539")


@pytest.fixture()
def client(env):
    app = FastAPI()
    for r in (ledger.router, importer.router, audit.router):
        app.include_router(r, prefix=P)
    return TestClient(app)


ALICE = {"Authorization": f"Bearer {auth.make_token('alice')}"}
DETAIL = [{"n": 13, "cars": 8, "base": 72.5}, {"n": 27, "cars": 5, "base": 74.5}]


def test_recost_per_ball(env):
    g, odds = env
    it = importer._recost(g, odds, "single", [], 1, 0, ball_detail=DETAIL)
    assert it.cost == pytest.approx((8 * 72.5 + 5 * 74.5) * 38)
    assert it.ball_detail == [{"n": 13, "cars": 8.0, "base": 72.5}, {"n": 27, "cars": 5.0, "base": 74.5}]
    assert it.balls == [13, 27] and it.ball_deltas == {}
    assert "13" in it.play_type and "27" in it.play_type   # 不同車數 → playType 列出逐顆
    assert "13號" in it.cost_expr and "27號" in it.cost_expr


def test_recost_uniform_detail_collapses_to_plain(env):
    g, odds = env
    base = float(odds["cost_per_car"]) / 38
    it = importer._recost(g, odds, "multi", [], 1, 0,
                          ball_detail=[{"n": 1, "cars": 5, "base": None}, {"n": 2, "cars": 5, "base": None}])
    plain = importer._recost(g, odds, "multi", [1, 2], 5, 0)
    assert it.ball_detail == [] and it.units == 5
    assert it.cost == pytest.approx(plain.cost) and it.play_type == plain.play_type
    assert it.base_cost == pytest.approx(base)


def test_recost_detail_validation(env):
    g, odds = env
    with pytest.raises(ValueError):
        importer._recost(g, odds, "single", [], 1, 0, ball_detail=[{"n": 13, "cars": 0, "base": 72.5}])
    with pytest.raises(ValueError):
        importer._recost(g, odds, "single", [], 1, 0,
                         ball_detail=[{"n": 13, "cars": 1, "base": 1}, {"n": 13, "cars": 2, "base": 1}])
    with pytest.raises(ValueError):
        importer._recost(g, odds, "single", [], 1, 0, ball_detail=[{"n": 40, "cars": 1, "base": 1}])


def test_settle_per_ball_payout(env):
    g, odds = env
    it = importer._recost(g, odds, "single", [], 1, 0, ball_detail=DETAIL)
    rec = importer.to_record(it, g, "2026-09-01", "115000300")
    assert rec["ballDetail"] == it.ball_detail
    out = settle.settle(rec, DRAW, g)      # 13 中(8 車)、27 沒中
    assert out["result"] == "中 1 顆"
    assert out["payout"] == round(8 * float(odds["win_payout"]))
    out = settle.settle(rec, [13, 27, 1, 2, 4], g)
    assert out["payout"] == round(13 * float(odds["win_payout"]))


def test_settle_without_detail_unchanged(env):
    g, odds = env
    rec = {"mode": "multi", "cars": 5, "units": 5, "selectedBalls": [13, 27], "cost": 100, "game": g.name}
    out = settle.settle(rec, DRAW, g)
    assert out["payout"] == round(1 * 5 * float(odds["win_payout"]))


def test_manual_hit_rejected_for_per_ball(env):
    g, _ = env
    rec = {"mode": "single", "cars": 8, "units": 8, "selectedBalls": [13, 27], "cost": 1,
           "ballDetail": DETAIL}
    with pytest.raises(ValueError):
        settle.settle(rec, None, g, hit_count=1)


def test_reconcile_total_carry_per_ball(env):
    rec = {"mode": "single", "betsCount": 2, "cars": 8, "ballDetail": DETAIL}
    assert reconcile._total_carry(rec, 39) == (8 + 5) * 38


def test_sig_includes_detail(env):
    a = {"mode": "single", "selectedBalls": [13, 27], "units": 8, "ballDetail": DETAIL}
    b = {**a, "ballDetail": [{"n": 13, "cars": 8, "base": 72.5}, {"n": 27, "cars": 6, "base": 74.5}]}
    assert importer._sig(a) != importer._sig(b)


def _commit(client, items, issue="115000300"):
    res = client.post(f"{P}/ledger/quick-import/commit", headers=ALICE, json={
        "game": "lotto539", "items": items, "date": "2026-09-01", "issue": issue, "edition": 1}).json()
    return [it["id"] for it in res["items"]]


def _rec(client, eid):
    return next(e for e in client.get(f"{P}/ledger", headers=ALICE).json() if e["id"] == eid)["record"]


def test_batch_edit_per_ball_and_resettle(client, env):
    _, odds = env
    [eid] = _commit(client, [{"mode": "single", "selectedBalls": [13, 27], "units": 8}])
    res = client.post(f"{P}/ledger/batch-edit", headers=ALICE,
                      json={"items": [{"id": eid, "ball_detail": DETAIL}]}).json()
    assert res["errors"] == [] and res["saved"] == 1
    rec = _rec(client, eid)
    assert rec["selectedBalls"] == [13, 27]
    assert rec["cost"] == round((8 * 72.5 + 5 * 74.5) * 38)
    assert rec["payout"] == round(8 * float(odds["win_payout"]))
    assert rec["ballDetail"][1] == {"n": 27, "cars": 5.0, "base": 74.5}
    # 作廢還原成編輯前(沒有 ballDetail 的一般紀錄)
    log = client.get(f"{P}/audit", headers=ALICE).json()[0]
    client.post(f"{P}/audit/{log['id']}/void", headers=ALICE)
    assert _rec(client, eid)["ballDetail"] == []


def test_batch_edit_manual_record_to_per_ball_is_error(client):
    res = client.post(f"{P}/ledger/quick-import/commit", headers=ALICE, json={
        "game": "lotto539", "date": "2026-09-01", "issue": "", "edition": 1,
        "items": [{"mode": "single", "selectedBalls": [13, 27], "units": 8, "hit_count": 1}]}).json()
    eid = res["items"][0]["id"]
    res = client.post(f"{P}/ledger/batch-edit", headers=ALICE,
                      json={"items": [{"id": eid, "ball_detail": DETAIL}]}).json()
    assert res["saved"] == 0 and res["errors"][0]["id"] == eid


def test_resettle_manual_on_per_ball_returns_400(client):
    [eid] = _commit(client, [{"mode": "single", "selectedBalls": [13, 27], "units": 8}], issue="115000999")
    client.post(f"{P}/ledger/batch-edit", headers=ALICE, json={"items": [{"id": eid, "ball_detail": DETAIL}]})
    r = client.put(f"{P}/ledger/{eid}", headers=ALICE, json={"issue": "", "hit_count": 1})
    assert r.status_code == 400
