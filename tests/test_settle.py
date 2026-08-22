"""開獎核對的結算邏輯(backend.settle):各下法對獎、派彩、待開獎退回。

純函式測試,不碰 DB、不讀 CSV —— 直接餵一組開獎號進去驗結果。
金額用 GameConfig 動態算,盤口改了也不會誤判。
"""
from __future__ import annotations

from backend import settle
from core.games import LOTTO539 as G


def _rec(**kw) -> dict:
    base = {"game": G.name, "selectedBalls": [], "cost": 1000,
            "cars": 1, "units": 1}
    base.update(kw)
    return base


def test_single_win_and_lose():
    # 1組(舊 single)與 2組派彩公式統一:中幾顆 × 車數 × 每車中獎(不除以 4)
    draw = [5, 11, 12, 17, 18]
    win = settle.settle(_rec(mode="single", selectedBalls=[12], cars=3), draw, G)
    assert win["payout"] == round(1 * 3 * G.default_win_payout)
    assert win["pnl"] == round(1 * 3 * G.default_win_payout - 1000)
    assert win["result"] == "中 1 顆"
    assert win["drawBalls"] == draw

    lose = settle.settle(_rec(mode="single", selectedBalls=[9], cars=3), draw, G)
    assert lose["payout"] == 0
    assert lose["pnl"] == -1000
    assert lose["result"] == "槓龜"


def test_manual_hit_count_ignores_draw():
    # 忘記期數但記得中幾顆:不看 draw,直接依組公式結算,drawBalls 不動
    r = settle.settle(_rec(mode="single", selectedBalls=[12], cars=3, cost=1000),
                      None, G, hit_count=2)
    assert r["payout"] == round(2 * 3 * G.default_win_payout)
    assert r["result"] == "中 2 顆(手填)"
    assert r["pnl"] == r["payout"] - 1000

    zero = settle.settle(_rec(mode="multi", cars=1), None, G, hit_count=0)
    assert zero["payout"] == 0 and zero["result"] == "槓龜(手填)"


def test_multi_counts_hits():
    draw = [5, 11, 12, 17, 18]
    r = settle.settle(
        _rec(mode="multi", selectedBalls=[5, 12, 17, 30], cars=2), draw, G)
    # 中 3 顆(5/12/17),每顆 = 車數 × 每車中獎可得(不除以 4)
    assert r["payout"] == round(3 * 2 * G.default_win_payout)
    assert r["result"] == "中 3 顆"


def test_multi_all_miss():
    r = settle.settle(
        _rec(mode="multi", selectedBalls=[1, 2, 3]), [5, 11, 12, 17, 18], G)
    assert r["payout"] == 0
    assert r["result"] == "槓龜"


def test_pillar_four_and_broken():
    # 12,15→第一柱 22,25→第二柱 5→第三柱 → counts (2,2,1) → 中 4 碰
    four = settle.settle(
        _rec(mode="pillar1800", cars=1), [12, 15, 22, 25, 5], G)
    assert four["payout"] == round(1 * 4 * G.default_bet_prize)
    assert four["result"] == "中 4 碰"
    assert four["pillarDist"] == "2 + 2 + 1"

    # 全部落第三柱 → 斷柱
    broke = settle.settle(
        _rec(mode="pillar1800", cars=1), [1, 2, 3, 4, 5], G)
    assert broke["payout"] == 0
    assert broke["result"] == "槓龜(斷柱)"


def test_combo_star_hits():
    # 星碰三星選 8 顆,重到 3 顆以上 → 中 (8-3)=5 碰
    # playType 用真實格式「星碰 三星 (支)」—— 星數是中文,不能被支數 12 蓋掉
    draw = [1, 2, 3, 20, 39]
    r = settle.settle(
        _rec(mode="combo", playType="星碰 三星 (12 支)",
             selectedBalls=[1, 2, 3, 4, 5, 6, 7, 8], cars=12), draw, G)
    from core import combo
    prize = combo.market_prize(3, G.default_bet_prize)
    assert r["result"] == "中 5 碰"
    assert r["payout"] == round(5 * prize * 12)


def test_combo_stars_parsed_from_chinese_not_sheets():
    # 迴歸:別把「(12 支)」的 12 當成星數 —— 三星選 8 顆重 3 顆該中,不是槓龜
    r = settle.settle(
        _rec(mode="combo", playType="星碰 三星 (12 支)",
             selectedBalls=[3, 6, 12, 15, 22, 25, 32, 35], cars=12),
        [3, 6, 12, 1, 2], G)
    assert r["result"] == "中 5 碰"
    assert r["payout"] > 0 and r["pnl"] > 0

    assert settle._stars_of("星碰 三星 (12 支)") == 3
    assert settle._stars_of("連碰(全碰) 四星 (5 支)") == 4
    assert settle._stars_of("星碰 二星 (1 支)") == 2


def test_draw_missing_stays_pending():
    r = settle.settle(_rec(mode="single", selectedBalls=[12], cars=3), None, G)
    assert r["result"] == "待開獎"
    assert r["payout"] == 0 and r["pnl"] == 0
    assert r["drawBalls"] == []


# ── 端點:改期數對獎 + 未登入預覽 + 作廢還原 ──────────────────
import pytest  # noqa: E402

pytest.importorskip("httpx", reason="TestClient 需要 httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import audit_store, ledger_store  # noqa: E402
from backend.routers import audit as audit_router  # noqa: E402
from backend.routers import ledger as ledger_router  # noqa: E402
from core import auth  # noqa: E402

P = "/api"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger_store, "_db_path", lambda: tmp_path / "ledger.db")
    monkeypatch.setattr(audit_store, "_db_path", lambda: tmp_path / "audit.db")
    # 不讀 CSV:期號 115000201 給一組固定開獎號
    monkeypatch.setattr(
        ledger_router.data, "draw_by_issue",
        lambda key, issue: ([5, 11, 12, 17, 18], "2026-08-18")
        if issue == "115000201" else None)
    app = FastAPI()
    app.include_router(ledger_router.router, prefix=P)
    app.include_router(audit_router.router, prefix=P)
    return TestClient(app)


@pytest.fixture()
def alice():
    return {"Authorization": f"Bearer {auth.make_token('alice')}"}


def test_resettle_updates_and_is_reversible(client, alice):
    rec = {"date": "2026-08-01", "issue": "000", "game": "今彩539",
           "mode": "single", "units": 3, "cars": 3, "betsCount": 1,
           "selectedBalls": [12], "drawBalls": [], "result": "待開獎",
           "cost": 8265, "payout": 0, "pnl": 0}
    eid = client.post(f"{P}/ledger", json={"mode": "single", "record": rec},
                      headers=alice).json()["id"]

    # 改期數對獎:應抓到開獎號、判定中獎、算損益、期數/日期更新
    r = client.put(f"{P}/ledger/{eid}", json={"issue": "115000201"},
                   headers=alice)
    assert r.status_code == 200
    body = r.json()["record"]
    assert body["issue"] == "115000201"
    assert body["date"] == "2026-08-18"
    assert body["drawBalls"] == [5, 11, 12, 17, 18]
    assert body["payout"] == round(1 * 3 * G.default_win_payout)
    assert "中" in body["result"]

    # 作廢那次對獎 → payload 回到改之前(待開獎、payout 0)
    log_id = client.get(f"{P}/audit", headers=alice).json()[0]["id"]
    assert client.post(f"{P}/audit/{log_id}/void", headers=alice).status_code == 200
    back = client.get(f"{P}/ledger?mode=single", headers=alice).json()[0]["record"]
    assert back["result"] == "待開獎"
    assert back["payout"] == 0 and back["issue"] == "000"


def test_resettle_unknown_issue_pending(client, alice):
    rec = {"game": "今彩539", "mode": "single", "cars": 3,
           "selectedBalls": [12], "cost": 8265}
    eid = client.post(f"{P}/ledger", json={"mode": "single", "record": rec},
                      headers=alice).json()["id"]
    body = client.put(f"{P}/ledger/{eid}", json={"issue": "999"},
                      headers=alice).json()["record"]
    assert body["result"] == "待開獎" and body["drawBalls"] == []


def test_settle_preview_no_auth_no_write(client):
    rec = {"game": "今彩539", "mode": "single", "cars": 3,
           "selectedBalls": [12], "cost": 8265}
    r = client.post(f"{P}/ledger/settle-preview",
                    json={"record": rec, "issue": "115000201"})
    assert r.status_code == 200
    body = r.json()
    assert body["drawBalls"] == [5, 11, 12, 17, 18]
    assert body["payout"] == round(1 * 3 * G.default_win_payout)


def test_settle_preview_manual_hit_count(client):
    # 手填中獎顆數:不查期數,直接依組公式算
    rec = {"game": "今彩539", "mode": "single", "cars": 3, "cost": 8265}
    r = client.post(f"{P}/ledger/settle-preview",
                    json={"record": rec, "issue": "", "hit_count": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["payout"] == round(2 * 3 * G.default_win_payout)
    assert "手填" in body["result"]


def test_resettle_requires_login(client):
    assert client.put(f"{P}/ledger/1", json={"issue": "115000201"}).status_code == 401
