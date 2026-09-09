"""改 ledger 明細期數 → 快速上傳歷史(含該 ledger id 的那批)期號同步更新。

用 entryIds 連結;沒 entryIds 的舊批次不連動(直接改資料庫,不在此測)。
"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import (audit_store, ledger_store, upload_history_store)  # noqa: E402
from backend.routers import ledger  # noqa: E402
from core import auth  # noqa: E402

P = "/api"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    monkeypatch.setattr(upload_history_store, "_db_path", lambda: tmp_path / "uh.db")
    monkeypatch.setattr(audit_store, "_db_path", lambda: tmp_path / "audit.db")
    app = FastAPI()
    app.include_router(ledger.router, prefix=P)
    return TestClient(app)


@pytest.fixture()
def alice():
    return {"Authorization": f"Bearer {auth.make_token('alice')}"}


def test_store_updates_issue_only_for_batch_containing_the_id():
    e = upload_history_store.add_entry("alice", {
        "ts": 1, "gameName": "天天樂", "issue": "11981", "eid": 1,
        "entryIds": [50, 51],
    })
    other = upload_history_store.add_entry("alice", {
        "ts": 2, "gameName": "天天樂", "issue": "11981", "eid": 1,
        "entryIds": [60],
    })
    n = upload_history_store.update_issue_by_entry_id("alice", 50, "11980")
    assert n == 1
    got = {x["ts"]: x["issue"] for x in upload_history_store.list_entries("alice")}
    assert got[1] == "11980"     # 含 id 50 的批次改了
    assert got[2] == "11981"     # 別批不動
    _ = (e, other)


def test_resettle_propagates_issue_to_upload_history(client, alice, monkeypatch):
    # 開獎查詢 stub:11980 視為已開(避免依賴真實 CSV)
    from backend import data
    monkeypatch.setattr(data, "draw_by_issue",
                        lambda key, issue: ([1, 2, 3, 4, 5], "2026-08-25") if str(issue) == "11980" else None)

    bet = ledger_store.add_entry("alice", "combo",
                                 {"game": "天天樂(加州 Fantasy 5)", "issue": "11981",
                                  "cost": 100, "selectedBalls": []})
    upload_history_store.add_entry("alice", {
        "ts": 111, "gameName": "天天樂(加州 Fantasy 5)", "issue": "11981", "eid": 1,
        "entryIds": [bet["id"]],
    })

    r = client.put(f"{P}/ledger/{bet['id']}", json={"issue": "11980"}, headers=alice)
    assert r.status_code == 200
    assert str(r.json()["record"]["issue"]) == "11980"

    uh = upload_history_store.list_entries("alice")
    assert uh[0]["issue"] == "11980"     # 上傳歷史跟著改
