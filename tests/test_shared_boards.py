"""佔比帳單(backend/routers/shared.py):被連動帳號只看得到該版、自己有佔比那些日子的紀錄。"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import edition_store, ledger_store  # noqa: E402
from backend.deps import current_user  # noqa: E402
from backend.routers import shared  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(edition_store, "_db_path", lambda: tmp_path / "edition.db")
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    app = FastAPI()
    app.include_router(shared.router, prefix="/api")
    who = {"u": "amin"}
    app.dependency_overrides[current_user] = lambda: who["u"]
    c = TestClient(app)
    c.who = who
    return c


def _bet(owner, date, edition=1, pnl=100):
    ledger_store.add_entry(owner, "single", {"date": date, "edition": edition, "cost": 10, "payout": 10 + pnl})


def test_partner_sees_only_linked_board_after_since(client):
    e2 = edition_store.add_edition("第二版")["eid"]
    edition_store.set_shares("boss", 1, [{"name": "阿閔", "pct": 40, "account": "amin"}], "2026-09-30")
    for d in ("2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"):
        _bet("boss", d)
    _bet("boss", "2026-10-01", edition=e2)      # 別的版:看不到
    _bet("other", "2026-10-01")                  # 別的版主:看不到
    _bet("boss", "")                             # 沒日期:看不到

    rows = client.get("/api/shared/boards").json()
    assert len(rows) == 1
    b = rows[0]
    assert (b["owner"], b["eid"], b["edition_name"]) == ("boss", 1, "第一版")
    assert sorted(e["record"]["date"] for e in b["entries"]) == ["2026-09-30", "2026-10-01"]
    assert [v["since"] for v in b["versions"]] == ["", "2026-09-30"]


def test_partner_removed_later_loses_later_days(client):
    edition_store.set_shares("boss", 1, [{"name": "阿閔", "pct": 40, "account": "amin"}], "2026-09-30")
    edition_store.set_shares("boss", 1, [], "2026-10-02")     # 10/2 起不分了
    for d in ("2026-09-30", "2026-10-02"):
        _bet("boss", d)
    b = client.get("/api/shared/boards").json()[0]
    assert [e["record"]["date"] for e in b["entries"]] == ["2026-09-30"]


def test_unlinked_sees_nothing(client):
    edition_store.set_shares("boss", 1, [{"name": "阿閔", "pct": 40, "account": "amin"}])
    client.who["u"] = "stranger"
    assert client.get("/api/shared/boards").json() == []
