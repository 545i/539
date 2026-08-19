"""FastAPI 端點煙霧測試(用 TestClient,不開真的 socket)。

這個環境會對「監聽 socket 的常駐行程」送信號收掉,所以用行程內 TestClient
驗證 API,才能穩定地跑在 CI/pytest 裡。
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("APP_PREFIX", "/539")
P = "/539/api"

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    assert client.get(f"{P}/health").json() == {"ok": True}


def test_games_lists_three():
    r = client.get(f"{P}/games")
    assert r.status_code == 200
    data = r.json()
    keys = {g["key"] for g in data}
    assert keys == {"lotto539", "fantasy5", "marksix"}
    g539 = next(g for g in data if g["key"] == "lotto539")
    assert g539["num_max"] == 39 and g539["pick"] == 5
    assert g539["supports_pillar"] is True


def test_history_latest_has_pillar_summary():
    r = client.get(f"{P}/history?game=lotto539&limit=1")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    assert len(body["latest"]["nums"]) == 5
    assert "pillar_dist" in body["latest"]


def test_stats_missing_and_hotcold():
    assert len(client.get(f"{P}/stats/missing?game=lotto539").json()) == 39
    hc = client.get(f"{P}/stats/hotcold?game=lotto539&window=830&top=6").json()
    assert len(hc["hot"]) == 6 and len(hc["cold"]) == 6


def test_stats_tens_pairs_shape():
    data = client.get(f"{P}/stats/tens-pairs?game=lotto539").json()
    assert len(data) == 6  # C(4,2)
    for row in data:
        assert set(row.keys()) >= {"bands", "labels", "range", "streak", "alert"}


def test_pillar_info_539():
    d = client.get(f"{P}/pillar/info?game=lotto539").json()
    assert d["sizes"] == [9, 10, 20]
    assert d["total_bets"] == 1800
    assert abs(d["pass_prob"] - 0.5536189746716063) < 1e-9


def test_pillar_partial_roundtrip():
    r = client.post(f"{P}/pillar/partial",
                    json={"game": "lotto539", "picks": [10, 11, 20, 21, 1, 2]})
    assert r.status_code == 200
    assert r.json()["bets"] == 8 and r.json()["counts"] == [2, 2, 2]


def test_pillar_rejects_marksix():
    assert client.get(f"{P}/pillar/info?game=marksix").status_code == 400


def test_auth_me_requires_token():
    assert client.get(f"{P}/auth/me").status_code == 401


def test_auth_login_wrong_credentials():
    r = client.post(f"{P}/auth/login",
                    json={"username": "nobody_xyz", "password": "bad"})
    assert r.status_code == 401
