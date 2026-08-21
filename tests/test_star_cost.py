"""連碰星數盤口的後台設定:存得住、要登入才給改、而且**真的影響計算**。

最後一項是這組測試的重點 —— 存進資料庫但試算還用舊價,是這個功能最可能
壞掉的方式,所以改完成本一定要回頭驗 combo/calc 與快速上傳算出來的錢。

資料庫路徑導到 tmp_path,不會碰到 data/star_cost.db;每個 case 跑完清掉
core.combo 的覆寫層,免得汙染同一個行程裡的其他測試。
"""
from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import star_cost_store  # noqa: E402
from backend.routers import combo as combo_router  # noqa: E402
from backend.routers import star_cost  # noqa: E402
from core import auth, combo  # noqa: E402

P = "/api"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(star_cost_store, "_db_path", lambda: tmp_path / "star_cost.db")
    combo.clear_market_overrides()
    yield
    combo.clear_market_overrides()


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(star_cost.router, prefix=P)
    app.include_router(combo_router.router, prefix=P)
    return TestClient(app)


@pytest.fixture()
def alice():
    return {"Authorization": f"Bearer {auth.make_token('alice')}"}


# ── 讀 ───────────────────────────────────────────────────
def test_get_returns_core_defaults_when_nothing_saved(client):
    body = client.get(f"{P}/star-cost").json()
    assert body["stars"] == [2, 3, 4]
    assert body["costs"]["3"]["cost"] == combo.MARKET_COST[3]
    assert body["costs"]["3"]["prize"] == combo.MARKET_PRIZE[3]
    assert body["costs"]["3"]["custom"] is False


def test_get_does_not_require_login(client):
    assert client.get(f"{P}/star-cost").status_code == 200


# ── 寫 ───────────────────────────────────────────────────
def test_put_requires_login(client):
    r = client.put(f"{P}/star-cost", json={"costs": {"3": {"cost": 70, "prize": 60000}}})
    assert r.status_code == 401


def test_put_persists_and_marks_custom(client, alice):
    r = client.put(f"{P}/star-cost", headers=alice,
                   json={"costs": {"3": {"cost": 70, "prize": 60000}}})
    assert r.status_code == 200
    assert r.json()["costs"]["3"] == {
        "cost": 70.0, "prize": 60000.0, "custom": True,
        "updated": r.json()["costs"]["3"]["updated"], "updated_by": "alice"}

    # 只改了三星,其餘維持出廠預設
    again = client.get(f"{P}/star-cost").json()
    assert again["costs"]["3"]["cost"] == 70.0
    assert again["costs"]["4"]["custom"] is False
    assert again["defaults"]["3"]["cost"] == combo.MARKET_COST[3]


@pytest.mark.parametrize("bad", [
    {"3": {"cost": 0, "prize": 60000}},       # 成本 0 → 返還率無限大
    {"3": {"cost": 70, "prize": -1}},         # 派彩負數
])
def test_put_rejects_nonpositive(client, alice, bad):
    assert client.put(f"{P}/star-cost", headers=alice,
                      json={"costs": bad}).status_code == 422


def test_put_rejects_unknown_stars(client, alice):
    r = client.put(f"{P}/star-cost", headers=alice,
                   json={"costs": {"7": {"cost": 70, "prize": 60000}}})
    assert r.status_code == 400
    assert "7" in r.json()["detail"]


def test_reset_restores_defaults(client, alice):
    client.put(f"{P}/star-cost", headers=alice,
               json={"costs": {"3": {"cost": 70, "prize": 60000}}})
    body = client.delete(f"{P}/star-cost", headers=alice).json()
    assert body["costs"]["3"]["cost"] == combo.MARKET_COST[3]
    assert body["costs"]["3"]["custom"] is False
    assert combo.market_cost(3) == combo.MARKET_COST[3]


# ── 有沒有真的吃到 ────────────────────────────────────────
def test_core_reads_override(client, alice):
    client.put(f"{P}/star-cost", headers=alice,
               json={"costs": {"3": {"cost": 70, "prize": 60000}}})
    assert combo.market_cost(3) == 70.0
    assert combo.market_prize(3) == 60000.0
    # 出廠預設本身不能被改掉 —— 「還原預設」要靠它
    assert combo.MARKET_COST[3] == 63.0


def test_calc_uses_new_cost(client, alice):
    def cost_of():
        r = client.post(f"{P}/combo/calc",
                        json={"play": "star", "stars": 3, "picked": 8})
        return r.json()["per_bet"], r.json()["total_cost"], r.json()["prize_per_hit"]

    per_bet, total, prize = cost_of()
    assert (per_bet, total, prize) == (63.0, 63.0 * 56, 57_000.0)

    client.put(f"{P}/star-cost", headers=alice,
               json={"costs": {"3": {"cost": 70, "prize": 60000}}})
    assert cost_of() == (70.0, 70.0 * 56, 60_000.0)


def test_plays_reports_effective_prices(client, alice):
    client.put(f"{P}/star-cost", headers=alice,
               json={"costs": {"4": {"cost": 55, "prize": 800000}}})
    body = client.get(f"{P}/combo/plays").json()
    assert body["market_cost"]["4"] == 55.0
    assert body["market_prize"]["4"] == 800000.0


def test_importer_star_cost_follows_setting(client, alice, tmp_path, monkeypatch):
    """快速上傳的星碰成本 = 支數 × 碰數 × 每碰成本,也要吃後台的價。"""
    from backend.routers import importer
    from backend.data import get_game

    g = get_game("lotto539")
    picks = [2, 9, 15, 19, 20, 25, 28, 33]
    before = importer._star_item(g, 3, picks, 12, "八顆三星1200").cost
    assert before == 12 * 56 * 63.0

    client.put(f"{P}/star-cost", headers=alice,
               json={"costs": {"3": {"cost": 70, "prize": 60000}}})
    after = importer._star_item(g, 3, picks, 12, "八顆三星1200").cost
    assert after == 12 * 56 * 70.0
