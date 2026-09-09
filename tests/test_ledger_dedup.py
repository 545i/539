"""記帳去重:同 遊戲+日期+版+玩法+星數 只能一筆;重複回衝突,overwrite 才覆蓋。"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import audit_store, autosettle, ledger_store  # noqa: E402
from backend.routers import ledger  # noqa: E402
from core import auth  # noqa: E402

P = "/api"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    monkeypatch.setattr(audit_store, "_db_path", lambda: tmp_path / "audit.db")
    # 不碰開獎 CSV:對獎直接原樣回(測去重邏輯,不測結算)
    monkeypatch.setattr(autosettle, "settle_record_if_drawn", lambda rec, g: rec)
    app = FastAPI()
    app.include_router(ledger.router, prefix=P)
    return TestClient(app)


@pytest.fixture()
def alice():
    return {"Authorization": f"Bearer {auth.make_token('alice')}"}


def _rec(**kw):
    base = {"game": "今彩539", "date": "2026-08-27", "edition": 1, "mode": "multi",
            "selectedBalls": [1, 2, 3], "cost": 1000, "result": "待開獎"}
    base.update(kw)
    return base


def _post(client, alice, rec, overwrite=False):
    return client.post(f"{P}/ledger",
                       json={"mode": rec["mode"], "record": rec, "overwrite": overwrite},
                       headers=alice).json()


def _count(client, alice, mode):
    return len(client.get(f"{P}/ledger?mode={mode}", headers=alice).json())


def test_add_then_conflict_then_overwrite(client, alice):
    assert _post(client, alice, _rec())["status"] == "ok"
    # 同槽再送(號碼不同也算同槽)→ 衝突,不寫入
    res = _post(client, alice, _rec(selectedBalls=[4, 5, 6]))
    assert res["status"] == "conflict" and len(res["conflicts"]) == 1
    assert _count(client, alice, "multi") == 1
    # overwrite → 刪舊寫新,仍只有一筆、且是新的號碼
    res2 = _post(client, alice, _rec(selectedBalls=[4, 5, 6]), overwrite=True)
    assert res2["status"] == "ok"
    lst = client.get(f"{P}/ledger?mode=multi", headers=alice).json()
    assert len(lst) == 1
    assert lst[0]["record"]["selectedBalls"] == [4, 5, 6]


def test_different_game_not_conflict(client, alice):
    _post(client, alice, _rec(game="今彩539"))
    res = _post(client, alice, _rec(game="天天樂(加州 Fantasy 5)"))
    assert res["status"] == "ok"          # 不同遊戲不算同槽(key 含 game)
    assert _count(client, alice, "multi") == 2


def test_combo_stars_are_distinct_slots(client, alice):
    assert _post(client, alice, _rec(mode="combo", stars=3))["status"] == "ok"
    assert _post(client, alice, _rec(mode="combo", stars=4))["status"] == "ok"
    assert _count(client, alice, "combo") == 2       # 三星、四星各一筆
    # 再送三星 → 衝突(同槽)
    assert _post(client, alice, _rec(mode="combo", stars=3))["status"] == "conflict"


def test_overwrite_leaves_audit_for_restore(client, alice):
    _post(client, alice, _rec())
    _post(client, alice, _rec(cost=2000), overwrite=True)
    logs = audit_store.list_logs("alice")
    assert any(l.get("action") == "bet_clear" and "覆蓋" in str(l.get("summary")) for l in logs)
