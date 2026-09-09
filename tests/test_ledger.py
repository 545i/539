"""記帳流水帳端點:登入綁定、逐筆增刪、跨帳號隔離。

不掛 backend.main 那顆 app,自己組一顆只含 ledger router 的 —— 這樣就算
main.py 的 include_router 清單改了,這裡驗的仍是端點本身的行為。
資料庫路徑導到 tmp_path,不會碰到 data/ledger.db。
"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import ledger_store  # noqa: E402
from backend.routers import ledger  # noqa: E402
from core import auth  # noqa: E402

P = "/api"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    app = FastAPI()
    app.include_router(ledger.router, prefix=P)
    return TestClient(app)


@pytest.fixture()
def alice():
    return {"Authorization": f"Bearer {auth.make_token('alice')}"}


@pytest.fixture()
def bob():
    return {"Authorization": f"Bearer {auth.make_token('bob')}"}


RECORD = {
    "date": "2026-08-19", "issue": "115000201", "game": "今彩539",
    "mode": "single", "units": 3, "cars": 3, "betsCount": 1,
    "selectedBalls": [12], "drawBalls": [5, 11, 12, 17, 18],
    "result": "待開獎", "cost": 8265, "payout": 0, "pnl": 0,
    "cycle_id": None,   # 無進行中週期時後端補 None(週期性紀錄)
}


def test_requires_login(client):
    assert client.get(f"{P}/ledger").status_code == 401
    assert client.post(f"{P}/ledger", json={"mode": "single", "record": {}}).status_code == 401


def test_expired_token_rejected(client):
    stale = {"Authorization": f"Bearer {auth.make_token('alice', days=-1)}"}
    assert client.get(f"{P}/ledger", headers=stale).status_code == 401


def test_add_list_delete_roundtrip(client, alice):
    assert client.get(f"{P}/ledger?mode=single", headers=alice).json() == []

    entry = client.post(
        f"{P}/ledger", json={"mode": "single", "record": RECORD}, headers=alice).json()
    assert entry["id"] > 0 and entry["mode"] == "single" and entry["created"]
    # 紀錄內容原封不動存回來(中文與陣列都不能走樣)
    assert entry["record"] == RECORD

    rows = client.get(f"{P}/ledger?mode=single", headers=alice).json()
    assert [r["id"] for r in rows] == [entry["id"]]

    assert client.delete(f"{P}/ledger/{entry['id']}", headers=alice).json()["deleted"] == 1
    assert client.get(f"{P}/ledger?mode=single", headers=alice).json() == []
    # 刪過就不在了,再刪一次要回 404 而不是假裝成功
    assert client.delete(f"{P}/ledger/{entry['id']}", headers=alice).status_code == 404


def test_list_without_mode_returns_all_modes_in_order(client, alice):
    for mode in ("single", "combo", "pillar1800"):
        client.post(f"{P}/ledger", json={"mode": mode, "record": {"pnl": -1}}, headers=alice)
    rows = client.get(f"{P}/ledger", headers=alice).json()
    assert [r["mode"] for r in rows] == ["single", "combo", "pillar1800"]
    assert len(client.get(f"{P}/ledger?mode=combo", headers=alice).json()) == 1


def test_accounts_are_isolated(client, alice, bob):
    entry = client.post(
        f"{P}/ledger", json={"mode": "multi", "record": RECORD}, headers=alice).json()
    assert client.get(f"{P}/ledger", headers=bob).json() == []
    # 別人的紀錄連 id 都猜到了也刪不掉
    assert client.delete(f"{P}/ledger/{entry['id']}", headers=bob).status_code == 404
    assert len(client.get(f"{P}/ledger", headers=alice).json()) == 1


def test_clear_by_mode_and_all(client, alice):
    # 兩筆 single 用不同日期(去重以 遊戲+日期+版+玩法+星數 為槽,同槽只能一筆)
    for mode, rec in (("single", {"pnl": -1, "date": "2026-08-01"}),
                      ("single", {"pnl": -1, "date": "2026-08-02"}),
                      ("combo", {"pnl": -1})):
        client.post(f"{P}/ledger", json={"mode": mode, "record": rec}, headers=alice)
    assert client.delete(f"{P}/ledger?mode=single", headers=alice).json()["deleted"] == 2
    assert [r["mode"] for r in client.get(f"{P}/ledger", headers=alice).json()] == ["combo"]
    assert client.delete(f"{P}/ledger", headers=alice).json()["deleted"] == 1
    assert client.get(f"{P}/ledger", headers=alice).json() == []


def test_unknown_mode_rejected(client, alice):
    assert client.get(f"{P}/ledger?mode=bogus", headers=alice).status_code == 400
    assert client.post(
        f"{P}/ledger", json={"mode": "bogus", "record": {}}, headers=alice).status_code == 400
    assert client.delete(f"{P}/ledger?mode=bogus", headers=alice).status_code == 400
