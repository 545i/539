"""週期帳下注明細編輯器:POST /ledger/batch-edit(逐筆改號碼 / 車支數 / 成本)。

- 成本一律走 importer._recost(後端權威),dry_run 回舊 / 新 record 對照與差額,不寫入。
- 儲存後依原本的對獎狀態重新結算:已開獎 → 依開獎號;手填 → 依原手填中獎數;待開獎 → 該期已開就對。
- 只能改自己的紀錄;日期 / 期號 / 版不動;1800碰 自訂分柱原樣保留。
- 一次儲存 = 操作歷史一筆 bet_edit,作廢 = 整批還原成編輯前。
"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import (audit_store, data, edition_store, group_store,  # noqa: E402
                     ledger_store)
from backend.data import get_game  # noqa: E402
from backend.routers import audit, importer, ledger  # noqa: E402
from core import auth  # noqa: E402

P = "/api"
DRAW = [3, 12, 20, 30, 35]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    monkeypatch.setattr(audit_store, "_db_path", lambda: tmp_path / "audit.db")
    monkeypatch.setattr(group_store, "_db_path", lambda: tmp_path / "group.db")
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")
    # 開獎資料:只有 115000300 期開了 DRAW,其他一律未開
    monkeypatch.setattr(data, "draw_by_issue",
                        lambda key, issue: (DRAW, "2026-09-01") if str(issue) == "115000300" else None)
    monkeypatch.setattr(data, "draw_by_date", lambda key, d: None)
    app = FastAPI()
    for r in (ledger.router, importer.router, audit.router):
        app.include_router(r, prefix=P)
    return TestClient(app)


@pytest.fixture()
def alice():
    return {"Authorization": f"Bearer {auth.make_token('alice')}"}


@pytest.fixture()
def bob():
    return {"Authorization": f"Bearer {auth.make_token('bob')}"}


@pytest.fixture()
def odds(client):
    return edition_store.get_odds(1, "lotto539")


def _commit(client, headers, items, issue="115000300"):
    res = client.post(f"{P}/ledger/quick-import/commit", headers=headers, json={
        "game": "lotto539", "items": items, "date": "2026-09-01",
        "issue": issue, "edition": 1,
    }).json()
    return [it["id"] for it in res["items"]]


def _entry(client, headers, eid):
    return next(e for e in client.get(f"{P}/ledger", headers=headers).json() if e["id"] == eid)


def _edit(client, headers, items, dry_run=False):
    return client.post(f"{P}/ledger/batch-edit", headers=headers,
                       json={"items": items, "dry_run": dry_run})


def test_requires_login(client):
    assert client.post(f"{P}/ledger/batch-edit", json={"items": []}).status_code == 401


def test_dry_run_returns_old_new_and_diff_without_writing(client, alice, odds):
    [eid] = _commit(client, alice, [{"mode": "single", "selectedBalls": [5], "units": 10}])
    before = _entry(client, alice, eid)["record"]

    res = _edit(client, alice, [{"id": eid, "selectedBalls": [5, 12], "units": 10}], dry_run=True)
    assert res.status_code == 200
    body = res.json()
    assert body["dry_run"] is True and body["saved"] == 0 and body["errors"] == []
    [it] = body["items"]
    cpc = float(odds["cost_per_car"])
    assert it["old"]["cost"] == round(1 * 10 * cpc)
    assert it["new"]["cost"] == round(2 * 10 * cpc)
    assert it["cost_diff"] == it["new"]["cost"] - it["old"]["cost"]
    # dry_run 也重新對獎(12 有開)→ 試算就看得到新損益
    assert it["new"]["result"] == "中 1 顆"
    # 沒寫入
    assert _entry(client, alice, eid)["record"] == before
    assert [r["action"] for r in client.get(f"{P}/audit", headers=alice).json()] == ["quick_import"]


def test_save_recosts_with_ball_deltas_and_resettles(client, alice, odds):
    [eid] = _commit(client, alice, [{"mode": "single", "selectedBalls": [5], "units": 10}])
    res = _edit(client, alice, [{"id": eid, "selectedBalls": [5, 12], "units": 20,
                                 "ball_deltas": {"12": 2}}]).json()
    assert res["saved"] == 1 and res["errors"] == []
    rec = _entry(client, alice, eid)["record"]
    g = get_game("lotto539")
    expect = importer._recost(g, odds, "single", [5, 12], 20, 0, ball_deltas={"12": 2})
    assert rec["cost"] == round(expect.cost)
    assert rec["ballDeltas"] == {"12": 2.0}
    assert rec["selectedBalls"] == [5, 12] and rec["units"] == 20 and rec["cars"] == 20
    # 該期已開 → 依開獎號重算損益(12 中)
    assert rec["result"] == "中 1 顆"
    assert rec["payout"] == round(1 * 20 * float(odds["win_payout"]))
    assert rec["pnl"] == rec["payout"] - rec["cost"]
    # 日期 / 期號 / 版不動
    assert (rec["date"], rec["issue"], rec["edition"]) == ("2026-09-01", "115000300", 1)


def test_base_cost_override(client, alice, odds):
    [eid] = _commit(client, alice, [{"mode": "pillar1800", "units": 1}])
    res = _edit(client, alice, [{"id": eid, "units": 2, "base_cost": 3}]).json()
    assert res["errors"] == []
    rec = _entry(client, alice, eid)["record"]
    assert rec["cost"] == 1800 * 3 * 2
    assert rec["baseCost"] == 3 and rec["units"] == 2


def test_pending_record_stays_pending_when_issue_not_drawn(client, alice):
    [eid] = _commit(client, alice, [{"mode": "single", "selectedBalls": [5], "units": 10}],
                    issue="115000999")
    _edit(client, alice, [{"id": eid, "selectedBalls": [12], "units": 10}])
    rec = _entry(client, alice, eid)["record"]
    assert rec["result"] == "待開獎" and rec["payout"] == 0


def test_manual_hit_count_is_kept(client, alice, odds):
    """手填中獎(忘記期數)的紀錄:編輯後依原手填中獎數重算派彩,不退回待開獎。"""
    res = client.post(f"{P}/ledger/quick-import/commit", headers=alice, json={
        "game": "lotto539", "date": "2026-09-01", "issue": "", "edition": 1,
        "items": [{"mode": "single", "selectedBalls": [5, 6], "units": 10, "hit_count": 1}],
    }).json()
    eid = res["items"][0]["id"]
    _edit(client, alice, [{"id": eid, "selectedBalls": [5, 6], "units": 20}])
    rec = _entry(client, alice, eid)["record"]
    assert "手填" in rec["result"]
    assert rec["payout"] == round(1 * 20 * float(odds["win_payout"]))


def test_custom_pillars_preserved(client, alice, odds):
    p1 = [20, 21, 22, 23, 25, 26, 27, 28, 29]
    p2 = list(range(30, 40))
    p3 = list(range(1, 20)) + [24]
    [eid] = _commit(client, alice, [{"mode": "pillar1800", "units": 1, "pillars": [p1, p2, p3]}])
    _edit(client, alice, [{"id": eid, "units": 3}])
    rec = _entry(client, alice, eid)["record"]
    assert rec["pillars"] == [p1, p2, p3]
    assert rec["cost"] == round(9 * 10 * 20 * float(odds["bet_cost"]) * 3)
    # DRAW = 3,12 / 20 / 30,35 → 第一柱 1(20)、第二柱 2(30,35)、其他 2(3,12)
    assert rec["pillarDist"] == "1 × 2 × 2"


def test_mixed_modes_in_one_batch(client, alice, odds):
    ids = _commit(client, alice, [
        {"mode": "single", "selectedBalls": [5], "units": 10},
        {"mode": "multi", "selectedBalls": [1, 2, 3], "units": 5},
        {"mode": "combo", "selectedBalls": [1, 2, 3, 4, 5, 6, 7, 8], "units": 2, "stars": 3},
        {"mode": "combo9000", "units": 1},
    ])
    res = _edit(client, alice, [
        {"id": ids[0], "selectedBalls": [5], "units": 12},
        {"id": ids[1], "selectedBalls": [1, 2, 3, 12], "units": 5, "ball_deltas": {"12": 1}},
        {"id": ids[2], "selectedBalls": [1, 2, 3, 4, 5, 6, 7, 12], "units": 3},
        {"id": ids[3], "units": 2},
    ]).json()
    assert res["errors"] == [] and res["saved"] == 4
    recs = {i: _entry(client, alice, i)["record"] for i in ids}
    assert recs[ids[0]]["units"] == 12
    assert recs[ids[1]]["ballDeltas"] == {"12": 1.0}
    assert recs[ids[2]]["stars"] == 3 and recs[ids[2]]["units"] == 3
    assert recs[ids[2]]["selectedBalls"] == [1, 2, 3, 4, 5, 6, 7, 12]
    assert recs[ids[3]]["units"] == 2
    for i, it in zip(ids, res["items"]):
        assert it["id"] == i and it["new"]["cost"] == recs[i]["cost"]


def test_error_in_one_item_saves_nothing(client, alice):
    ids = _commit(client, alice, [
        {"mode": "single", "selectedBalls": [5], "units": 10},
        {"mode": "multi", "selectedBalls": [1, 2], "units": 5},
    ])
    before = [_entry(client, alice, i)["record"] for i in ids]
    res = _edit(client, alice, [
        {"id": ids[0], "selectedBalls": [5], "units": 20},
        {"id": ids[1], "selectedBalls": [1, 99], "units": 5},
    ]).json()
    assert res["saved"] == 0
    assert [e["id"] for e in res["errors"]] == [ids[1]]
    assert [_entry(client, alice, i)["record"] for i in ids] == before


def test_cannot_edit_other_users_record(client, alice, bob):
    [eid] = _commit(client, alice, [{"mode": "single", "selectedBalls": [5], "units": 10}])
    before = _entry(client, alice, eid)["record"]
    res = _edit(client, bob, [{"id": eid, "selectedBalls": [7], "units": 1}])
    assert res.status_code == 404
    assert _entry(client, alice, eid)["record"] == before


def test_audit_void_restores_original_records(client, alice):
    ids = _commit(client, alice, [
        {"mode": "single", "selectedBalls": [5], "units": 10},
        {"mode": "pillar1800", "units": 1},
    ])
    before = [_entry(client, alice, i)["record"] for i in ids]
    _edit(client, alice, [{"id": ids[0], "selectedBalls": [5, 6], "units": 30},
                          {"id": ids[1], "units": 4}])
    logs = client.get(f"{P}/audit", headers=alice).json()
    assert logs[0]["action"] == "bet_edit" and logs[0]["reversible"] is True
    assert "2 筆" in logs[0]["summary"]

    res = client.post(f"{P}/audit/{logs[0]['id']}/void", headers=alice).json()
    assert res["reverted"] == 2
    assert [_entry(client, alice, i)["record"] for i in ids] == before
