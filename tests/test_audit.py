"""操作歷史與可逆作廢:每個動作留痕,作廢 = 反轉,而且作廢也留痕。

跟 test_ledger.py 一樣自己組 app(只掛 ledger / importer / audit 三個 router),
兩顆資料庫都導到 tmp_path,不會碰到 data/ 底下的真檔。

這裡最在意的一條是「撤銷之後還救得回來」—— 那是整個功能存在的理由。
"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import audit_store, ledger_store  # noqa: E402
from backend.routers import audit, importer, ledger  # noqa: E402
from core import auth  # noqa: E402

P = "/api"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    monkeypatch.setattr(audit_store, "_db_path", lambda: tmp_path / "audit.db")
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


RECORD = {
    "date": "2026-08-19", "issue": "115000201", "game": "今彩539",
    "mode": "single", "playType": "單顆 3 車", "units": 3, "cars": 3,
    "betsCount": 1, "selectedBalls": [12], "drawBalls": [],
    "result": "待開獎", "cost": 8265, "payout": 0, "pnl": 0,
    "cycle_id": None,   # 無進行中週期時後端補 None(週期性紀錄)
}


def _ledger(client, headers, mode=None):
    return client.get(f"{P}/ledger{f'?mode={mode}' if mode else ''}",
                      headers=headers).json()


def _logs(client, headers):
    return client.get(f"{P}/audit", headers=headers).json()


def test_requires_login(client):
    assert client.get(f"{P}/audit").status_code == 401
    assert client.post(f"{P}/audit/1/void").status_code == 401


def test_bet_add_is_logged_and_void_removes_the_entry(client, alice):
    entry = client.post(f"{P}/ledger", json={"mode": "single", "record": RECORD},
                        headers=alice).json()

    logs = _logs(client, alice)
    assert [r["action"] for r in logs] == ["bet_add"]
    assert logs[0]["target_id"] == entry["id"]
    assert logs[0]["voided"] is False and logs[0]["reversible"] is True
    # 摘要要看得出是哪一筆,不能只有 id
    assert "今彩539" in logs[0]["summary"] and "單顆" in logs[0]["summary"]
    # reverse_data 是內部資料,不外流
    assert "reverse_data" not in logs[0] and "username" not in logs[0]

    res = client.post(f"{P}/audit/{logs[0]['id']}/void", headers=alice).json()
    assert res["ok"] and res["reverted"] == 1
    assert _ledger(client, alice) == []

    # 作廢動作本身不另記一筆:原本那筆標記 voided 但留著,歷史只有它
    after = _logs(client, alice)
    assert [r["action"] for r in after] == ["bet_add"]
    assert after[0]["voided"] is True and after[0]["reversible"] is False


def test_void_of_delete_restores_the_record(client, alice):
    """這條是重點:使用者手滑撤銷了一筆,作廢那個撤銷要把整筆原封不動還回來。"""
    entry = client.post(f"{P}/ledger", json={"mode": "single", "record": RECORD},
                        headers=alice).json()
    client.delete(f"{P}/ledger/{entry['id']}", headers=alice)
    assert _ledger(client, alice) == []

    deleted_log = next(r for r in _logs(client, alice) if r["action"] == "bet_delete")
    res = client.post(f"{P}/audit/{deleted_log['id']}/void", headers=alice).json()
    assert res["reverted"] == 1

    rows = _ledger(client, alice)
    assert len(rows) == 1
    # 內容、id、時間都要跟刪掉之前一樣 —— id 沿用,流水順序才不會跑掉
    assert rows[0]["record"] == RECORD
    assert rows[0]["id"] == entry["id"]
    assert rows[0]["created"] == entry["created"]


def test_quick_import_logs_one_operation_and_void_removes_the_batch(client, alice):
    text = "02x50車\n09_15_19_20x20車"
    res = client.post(f"{P}/ledger/quick-import",
                      json={"game": "lotto539", "text": text},
                      headers=alice).json()
    assert res["saved"] == 2
    assert len(_ledger(client, alice)) == 2

    logs = _logs(client, alice)
    # 上傳兩筆 = 歷史一筆(不是兩筆 bet_add)
    assert [r["action"] for r in logs] == ["quick_import"]
    assert "2 筆" in logs[0]["summary"]

    assert client.post(f"{P}/audit/{logs[0]['id']}/void",
                       headers=alice).json()["reverted"] == 2
    assert _ledger(client, alice) == []


def test_dry_run_import_leaves_no_trace(client, alice):
    client.post(f"{P}/ledger/quick-import",
                json={"game": "lotto539", "text": "02x50車", "dry_run": True},
                headers=alice)
    assert _logs(client, alice) == []


def test_clear_is_reversible(client, alice):
    # 兩筆 single 用不同日期(去重:同 遊戲+日期+版+玩法+星數 只能一筆)
    for mode, rec in (("single", {**RECORD, "date": "2026-08-01"}),
                      ("single", {**RECORD, "date": "2026-08-02"}),
                      ("combo", RECORD)):
        client.post(f"{P}/ledger", json={"mode": mode, "record": rec},
                    headers=alice)
    assert client.delete(f"{P}/ledger?mode=single",
                         headers=alice).json()["deleted"] == 2

    clear_log = next(r for r in _logs(client, alice) if r["action"] == "bet_clear")
    assert client.post(f"{P}/audit/{clear_log['id']}/void",
                       headers=alice).json()["reverted"] == 2
    assert len(_ledger(client, alice, "single")) == 2


def test_cannot_void_twice_or_void_a_void(client, alice):
    client.post(f"{P}/ledger", json={"mode": "single", "record": RECORD},
                headers=alice)
    log_id = _logs(client, alice)[0]["id"]

    assert client.post(f"{P}/audit/{log_id}/void", headers=alice).status_code == 200
    # 同一筆不能作廢兩次(作廢動作本身不另記 log)
    assert client.post(f"{P}/audit/{log_id}/void", headers=alice).status_code == 400


def test_accounts_are_isolated(client, alice, bob):
    client.post(f"{P}/ledger", json={"mode": "single", "record": RECORD},
                headers=alice)
    log_id = _logs(client, alice)[0]["id"]

    assert _logs(client, bob) == []
    # 別人的操作 id 猜到了也作廢不了
    assert client.post(f"{P}/audit/{log_id}/void", headers=bob).status_code == 404
    assert len(_ledger(client, alice)) == 1


def test_void_of_add_survives_the_entry_being_gone(client, alice):
    """紀錄早被清空掃掉了,作廢那個 bet_add 不該爆掉 —— 結果本來就已經達成。"""
    client.post(f"{P}/ledger", json={"mode": "single", "record": RECORD},
                headers=alice)
    add_log = _logs(client, alice)[0]
    client.delete(f"{P}/ledger", headers=alice)

    res = client.post(f"{P}/audit/{add_log['id']}/void", headers=alice).json()
    assert res["ok"] and res["reverted"] == 0
