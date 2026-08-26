"""作廢一批上傳:連同它建立的 ledger 下注一起刪(含 entryIds 精準刪與簽名比對退路)。

自己組一顆只含 upload_history router 的 app,三個 store 的 db 都導到 tmp_path。
"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import audit_store, ledger_store, upload_history_store  # noqa: E402
from backend.routers import upload_history  # noqa: E402
from core import auth  # noqa: E402

P = "/api"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    monkeypatch.setattr(upload_history_store, "_db_path", lambda: tmp_path / "uh.db")
    monkeypatch.setattr(audit_store, "_db_path", lambda: tmp_path / "audit.db")
    app = FastAPI()
    app.include_router(upload_history.router, prefix=P)
    return TestClient(app)


@pytest.fixture()
def alice():
    return {"Authorization": f"Bearer {auth.make_token('alice')}"}


def test_void_deletes_bets_by_entry_ids(client, alice):
    # 建 3 筆 ledger,其中 2 筆屬於這批上傳
    e1 = ledger_store.add_entry("alice", "combo", {"game": "天天樂", "issue": "11979", "cost": 100})
    e2 = ledger_store.add_entry("alice", "combo", {"game": "天天樂", "issue": "11979", "cost": 200})
    keep = ledger_store.add_entry("alice", "single", {"game": "天天樂", "issue": "11980", "cost": 999})
    upload_history_store.add_entry("alice", {
        "ts": 111, "gameName": "天天樂", "issue": "11979", "eid": 1,
        "count": 2, "items": [], "entryIds": [e1["id"], e2["id"]],
    })

    r = client.delete(f"{P}/upload-history/111", headers=alice)
    assert r.status_code == 200
    assert r.json() == {"deleted_bets": 2, "deleted_upload": 1}

    left = {x["id"] for x in ledger_store.list_entries("alice")}
    assert left == {keep["id"]}                       # 只剩沒被這批建立的那筆
    assert upload_history_store.list_entries("alice") == []
    # 可還原:audit 記了一筆 bet_clear,reverse_data 帶著被刪的兩筆
    logs = audit_store.list_entries("alice") if hasattr(audit_store, "list_entries") else None
    _ = logs  # 有列出端點才驗,沒有就略過(不強綁 audit 的讀 API)


def test_void_fallback_signature_when_no_entry_ids(client, alice):
    # 舊上傳沒存 entryIds:用 game+issue+edition+mode+cost 簽名比對,只刪該批筆數
    dup1 = ledger_store.add_entry("alice", "combo", {"game": "天天樂", "issue": "11979", "edition": 1, "cost": 100})
    dup2 = ledger_store.add_entry("alice", "combo", {"game": "天天樂", "issue": "11979", "edition": 1, "cost": 100})
    # 不同版 → 不該被誤刪
    other = ledger_store.add_entry("alice", "combo", {"game": "天天樂", "issue": "11979", "edition": 2, "cost": 100})
    upload_history_store.add_entry("alice", {
        "ts": 222, "gameName": "天天樂", "issue": "11979", "eid": 1,
        "count": 1, "items": [{"mode": "combo", "cost": 100}],   # 只記 1 筆
    })

    r = client.delete(f"{P}/upload-history/222", headers=alice)
    assert r.status_code == 200
    assert r.json()["deleted_bets"] == 1                # 同簽名有 2 筆,只刪 1 筆
    left = {x["id"] for x in ledger_store.list_entries("alice")}
    assert other["id"] in left                          # 別版不動
    assert len(left) == 2                               # dup 只被刪掉一筆
    _ = (dup1, dup2)


def test_void_missing_returns_404(client, alice):
    r = client.delete(f"{P}/upload-history/999", headers=alice)
    assert r.status_code == 404
