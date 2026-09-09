"""週期性紀錄(cycle):store 的 create/close/current/list,以及開週期後下注會自動
帶 cycle_id、週期 summary 彙總正確。"""
from __future__ import annotations

import pytest

from backend import cycle_store

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import audit_store, autosettle, ledger_store  # noqa: E402
from backend.routers import cycles as cycles_router  # noqa: E402
from backend.routers import ledger as ledger_router  # noqa: E402
from core import auth  # noqa: E402

P = "/api"


# ── store 層 ─────────────────────────────────────────────
@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle_store, "_db_path", lambda: tmp_path / "cycle.db")
    return cycle_store


def test_create_current_list(store):
    assert store.current_cycle("alice") is None       # 一開始沒有進行中週期
    c1 = store.create_cycle("alice", "8月W4")
    assert c1["name"] == "8月W4" and c1["status"] == "open"
    assert store.current_cycle("alice")["id"] == c1["id"]
    assert [c["id"] for c in store.list_cycles("alice")] == [c1["id"]]


def test_only_one_open_per_user(store):
    """開新週期前,先把舊 open 自動結算 —— 同帳號同時只留一個 open。"""
    c1 = store.create_cycle("alice", "第一週")
    c2 = store.create_cycle("alice", "第二週")
    assert store.current_cycle("alice")["id"] == c2["id"]
    # c1 被自動結算
    got1 = next(c for c in store.list_cycles("alice") if c["id"] == c1["id"])
    assert got1["status"] == "closed" and got1["closed_at"]


def test_close_cycle(store):
    c1 = store.create_cycle("alice", "本週")
    closed = store.close_cycle("alice", c1["id"])
    assert closed["status"] == "closed" and closed["closed_at"]
    assert store.current_cycle("alice") is None       # 結算後沒有進行中週期
    # 不是自己的週期回 None
    assert store.close_cycle("bob", c1["id"]) is None


def test_per_user_isolation(store):
    a = store.create_cycle("alice", "A")
    b = store.create_cycle("bob", "B")
    assert store.current_cycle("alice")["id"] == a["id"]
    assert store.current_cycle("bob")["id"] == b["id"]
    assert [c["id"] for c in store.list_cycles("alice")] == [a["id"]]


# ── router 層(含下注自動帶 cycle_id + summary)──────────────
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(cycle_store, "_db_path", lambda: tmp_path / "cycle.db")
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    monkeypatch.setattr(audit_store, "_db_path", lambda: tmp_path / "audit.db")
    monkeypatch.setattr(autosettle, "settle_record_if_drawn", lambda rec, g: rec)
    app = FastAPI()
    app.include_router(cycles_router.router, prefix=P)
    app.include_router(ledger_router.router, prefix=P)
    return TestClient(app)


@pytest.fixture()
def alice():
    return {"Authorization": f"Bearer {auth.make_token('alice')}"}


def _rec(**kw):
    base = {"game": "今彩539", "date": "2026-08-27", "edition": 1, "mode": "multi",
            "selectedBalls": [1, 2, 3], "cost": 1000, "payout": 0, "result": "待開獎"}
    base.update(kw)
    return base


def _bet(client, alice, rec):
    return client.post(f"{P}/ledger",
                       json={"mode": rec["mode"], "record": rec}, headers=alice).json()


def test_cycle_crud_api(client, alice):
    assert client.get(f"{P}/cycles/current", headers=alice).json() is None
    c = client.post(f"{P}/cycles", json={"name": "8月W4"}, headers=alice).json()
    assert c["name"] == "8月W4" and c["status"] == "open"
    assert client.get(f"{P}/cycles/current", headers=alice).json()["id"] == c["id"]
    lst = client.get(f"{P}/cycles", headers=alice).json()
    assert len(lst) == 1 and lst[0]["id"] == c["id"]
    closed = client.post(f"{P}/cycles/{c['id']}/close", headers=alice).json()
    assert closed["status"] == "closed"
    assert client.get(f"{P}/cycles/current", headers=alice).json() is None


def test_bet_auto_tags_current_cycle(client, alice):
    # 各筆用不同日期避開去重(去重槽含日期)
    # 沒有進行中週期 → cycle_id 留空(行為照舊)
    e0 = _bet(client, alice, _rec(date="2026-08-25"))
    assert e0["record"].get("cycle_id") is None
    # 開週期後,新下注自動帶目前週期的 cycle_id
    c = client.post(f"{P}/cycles", json={"name": "本週"}, headers=alice).json()
    e1 = _bet(client, alice, _rec(date="2026-08-26"))
    assert e1["record"]["cycle_id"] == c["id"]
    # 結算後,新下注不再歸入(cycle_id 又留空)
    client.post(f"{P}/cycles/{c['id']}/close", headers=alice)
    e2 = _bet(client, alice, _rec(date="2026-08-27"))
    assert e2["record"].get("cycle_id") is None


def test_cycle_summary(client, alice):
    c = client.post(f"{P}/cycles", json={"name": "彙總週"}, headers=alice).json()
    _bet(client, alice, _rec(date="2026-08-26", cost=1000, payout=0))
    _bet(client, alice, _rec(date="2026-08-27", cost=500, payout=2000))
    s = client.get(f"{P}/cycles/{c['id']}/summary", headers=alice).json()
    assert s["cycle_id"] == c["id"]
    assert s["cost"] == 1500 and s["payout"] == 2000
    assert s["pnl"] == 500 and s["n"] == 2
    # 不存在的週期回 404
    assert client.get(f"{P}/cycles/999999/summary", headers=alice).status_code == 404
