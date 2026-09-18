"""雅宏策略後端測試:各端點函式結構、matrix 五裁決、zone34 門檻、single 名次制、
常數正確、marksix 被擋。用真實資料(backend.data.load_df)+ 小筆造假資料驗證。
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.data import load_df
from core.loader import draws_as_lists
from core.yahong import analysis, matrix, plan, single, zone34
from backend.routers import yahong as yahong_router


def _new_old(game: str) -> list[list[int]]:
    return list(reversed(draws_as_lists(load_df(game))))


# ── 決策矩陣 / analyze_space ────────────────────────────────
def test_matrix_response_structure():
    data = _new_old("lotto539")
    resp = matrix.matrix_response("lotto539", "1800", matrix.config_for("1800"), data)
    assert resp["game"] == "lotto539" and resp["mode"] == "1800"
    assert resp["totalDraws"] == len(data)
    assert len(resp["wallst"]) == 8 and len(resp["eastern"]) == 10
    assert {w["key"] for w in resp["wallst"]} == {
        "bayes", "ev", "kelly", "z", "drawdown", "markov", "rsi", "accel"}
    assert {e["key"] for e in resp["eastern"]} == {
        "pbase", "pemp", "ma30", "ma120", "ma500", "streak",
        "geomMean", "geomStd", "prSurv", "totalDraws"}
    assert resp["verdict"]["color"] in {"red", "amber", "gold", "green", "slate"}


def test_matrix_constants():
    """baseP / expectedPrizePuffs / costPerRound 常數逐字對照。"""
    # 1800:baseP 0.5536、cost=1*1800*(1-0.37)=1134、avgPrize=3.5576*570=2027.832
    cfg = matrix.config_for("1800")
    assert cfg["basePuffs"] == 1800 and cfg["rebate"] == 37 and cfg["unitPrize"] == 570
    a = matrix.analyze_space(cfg, [[10, 20, 1, 2, 3]] * 10)
    assert a["baseP_Threshold"] == 0.5536
    assert a["costPerRound"] == pytest.approx(1134.0)
    assert a["avgPrizeWhenWin"] == pytest.approx(3.5576 * 570)
    # 9000:baseP 0.2736、cost=1*9000*0.5=4500、avgPrize=2.0*8000
    cfg9 = matrix.config_for("9000")
    a9 = matrix.analyze_space(cfg9, [[1, 10, 20, 30, 5]] * 10)
    assert a9["baseP_Threshold"] == 0.2736
    assert a9["costPerRound"] == pytest.approx(4500.0)
    assert a9["avgPrizeWhenWin"] == pytest.approx(2.0 * 8000)


def test_verdict_insufficient():
    v = matrix.verdict(matrix.analyze_space(matrix.config_for("1800"), [[10, 20, 1, 2, 3]] * 3))
    assert v["title"] == "⏳ 歷史數據不足" and v["mult"] == 0
    assert matrix.verdict(None)["mult"] == 0


def test_verdict_system_reject_negative_ev():
    """全部落空(1800 puffs 恆為 0)→ EV<0 且 Z 不達 → 系統否決,mult 0。"""
    # 只開第3柱(01-09),p1=p2=0 → puffs=0 → 從不命中
    data = [[1, 2, 3, 4, 5]] * 50
    a = matrix.analyze_space(matrix.config_for("1800"), data)
    v = matrix.verdict(a)
    assert a["EV"] <= 0
    assert v["mult"] == 0
    assert v["color"] in {"red", "amber", "slate"}


def test_verdict_branches_reachable():
    """五裁決分支:掃過真實資料的兩個 mode,至少能產生合法裁決。"""
    for game in ("lotto539", "fantasy5"):
        data = _new_old(game)
        for mode in ("1800", "9000"):
            v = matrix.verdict(matrix.analyze_space(matrix.config_for(mode), data))
            assert v["mult"] in (0, 1, 2)
            assert isinstance(v["desc"], str) and v["title"]


# ── 同區 3-4 球 / zone34 ────────────────────────────────────
def test_zone34_threshold_and_coldest():
    # 造 6 期都「無任一柱 >=3 顆」→ consecutive_miss=6 → A(>=5)亮、B(<7)不亮
    draws = [[1, 11, 21, 31, 2], [3, 12, 22, 32, 4], [5, 13, 23, 33, 6],
             [7, 14, 24, 34, 8], [9, 15, 25, 35, 10], [16, 26, 36, 17, 27]]
    r = zone34.analyze_zone34(draws)
    assert r["consecutive_miss"] == 6
    assert r["strategy_a"] is True and r["strategy_b"] is False
    assert len(r["coldest"]) == 4


def test_zone34_hit_resets_streak():
    # 最後一期第1柱開 3 顆(1,2,3)→ 命中 → consecutive_miss 歸零
    draws = [[10, 20, 30, 11, 21], [1, 2, 3, 15, 25]]
    r = zone34.analyze_zone34(draws)
    assert r["consecutive_miss"] == 0
    assert r["strategy_a"] is False and r["strategy_b"] is False


def test_zone34_thresholds_are_5_and_7():
    assert zone34.THR_A == 5 and zone34.THR_B == 7 and zone34.THRESHOLD_HIT == 3


def test_radar_response_structure():
    draws_old_new = draws_as_lists(load_df("lotto539"))
    resp = zone34.radar_response("lotto539", draws_old_new)
    assert resp["strategyA"]["threshold"] == 5 and resp["strategyB"]["threshold"] == 7
    assert len(resp["strategyA"]["coldest"]) == 4
    assert len(resp["columns"]) == 4


# ── 單碼必贏 / single ───────────────────────────────────────
def test_single_insufficient_data():
    resp = single.single_response("lotto539", [[1, 2, 3, 4, 5]] * 50, None)
    assert resp["error"] == "資料不足 100 期" and resp["totalDraws"] == 50


def test_single_ranking_grades():
    data = _new_old("lotto539")
    assert len(data) >= 100
    resp = single.single_response("lotto539", data, 7)
    assert len(resp["ranking"]) == 39
    # 分數降序、名次 1..39、S/A/B/C 依名次切
    scores = [r["score"] for r in resp["ranking"]]
    assert scores == sorted(scores, reverse=True)
    assert resp["ranking"][0]["grade"] == "S" and resp["ranking"][0]["rank"] == 1
    assert resp["ranking"][2]["grade"] == "S"
    assert resp["ranking"][3]["grade"] == "A"
    assert resp["ranking"][9]["grade"] == "B"
    assert resp["ranking"][25]["grade"] == "C"
    # target 明細:18 宗師 + 5 摘要 + sparkline
    tgt = resp["target"]
    assert tgt["num"] == 7 and len(tgt["giants"]) == 18
    assert set(tgt["summary"]) == {"probAll", "survivalPR", "accel", "maxMiss", "prob30"}
    assert tgt["sparkline"] and tgt["grade"] in {"S", "A", "B", "C"}


def test_single_constants():
    assert single.MIN_DRAWS == 100 and single.B_ODDS == 3.3
    assert single.HIT_PROFIT == 330 and single.MISS_COST == 100


# ── 綜合分析 / analysis ─────────────────────────────────────
def test_analysis_response_structure():
    for game in ("lotto539", "fantasy5"):
        data = _new_old(game)
        resp = analysis.analysis_response(game, data, "2026-09-17")
        assert resp["totalDraws"] == len(data)
        assert set(resp["pillars"]) == {"p1800", "p9000"}
        assert resp["pillars"]["p1800"]["badge"] in {"alert", "ready", "ok"}
        assert len(resp["hot"]) == 8 and len(resp["cold"]) == 8
        assert len(resp["probScore"]) == 39
        assert len(resp["recommend"]) == 4
        assert [m["mode"] for m in resp["recommend"]] == [1, 2, 3, 4]


def test_analysis_recommend_reproducible():
    data = _new_old("lotto539")
    r1 = analysis.analysis_response("lotto539", data, None, seed=123)
    r2 = analysis.analysis_response("lotto539", data, None, seed=123)
    assert r1["recommend"] == r2["recommend"]
    # 預設 seed 也應可重現
    a = analysis.analysis_response("lotto539", data, None)
    b = analysis.analysis_response("lotto539", data, None)
    assert a["recommend"] == b["recommend"]


def test_analysis_prob_score_constants():
    assert analysis.BASE_P_1800 == 0.5536
    assert analysis.BASE_P_9000_539 == 0.2736 and analysis.BASE_P_9000_FANTASY == 0.2735
    # 539:2 因子 rebound 門檻 5~12/=0/>20/其餘
    assert analysis._rebound_539(6) == 95
    assert analysis._rebound_539(0) == 75
    assert analysis._rebound_539(25) == 35
    assert analysis._rebound_539(3) == 50
    # 天天樂:3 因子 rebound 門檻 gap∈[2,5]/{0,1}/else
    assert analysis._rebound_fantasy(3) == 95
    assert analysis._rebound_fantasy(1) == 80
    assert analysis._rebound_fantasy(0) == 80
    assert analysis._rebound_fantasy(10) == 40


def test_analysis_prob_score_factor_fields_per_game():
    """539 帶 freq/rebound;天天樂帶 freq/recent/rebound。"""
    s539 = analysis.analysis_response("lotto539", _new_old("lotto539"), None)["probScore"][0]
    assert "freq" in s539 and "rebound" in s539 and "recent" not in s539
    sfan = analysis.analysis_response("fantasy5", _new_old("fantasy5"), None)["probScore"][0]
    assert "freq" in sfan and "recent" in sfan and "rebound" in sfan


def test_analysis_pillar_algo_differs_by_game():
    """539 柱碰用幾何(無 avgCycle);天天樂用線性 boost(帶 avgCycle)。"""
    p539 = analysis.analysis_response("lotto539", _new_old("lotto539"), None)["pillars"]["p1800"]
    pfan = analysis.analysis_response("fantasy5", _new_old("fantasy5"), None)["pillars"]["p1800"]
    assert "avgCycle" not in p539
    assert "avgCycle" in pfan
    for p in (p539, pfan):
        assert set(p) >= {"miss", "nextProb", "badge", "badgeText"}
        assert p["badge"] in {"alert", "ready", "ok"}


# ── 資金規劃 / plan ─────────────────────────────────────────
def test_plan_single_structure():
    resp = plan.plan_response("single", 1.0, 18440, None, 2755, 21200, "single")
    assert resp["kind"] == "single" and len(resp["rows"]) == 15
    row = resp["rows"][0]
    assert set(row) >= {"day", "target", "units", "dailyCost", "accCost",
                        "winPrize", "netProfit"}


def test_plan_four_has_double_win():
    resp = plan.plan_response("four", 1.0, 18440, None, 2755, 21200, "four")
    assert resp["kind"] == "four" and len(resp["rows"]) == 6
    assert "doubleWin" in resp["rows"][0]


def test_plan_tier_step():
    resp = plan.plan_response("tier", 1.0, 18440, 15, 2755, 21200, "single")
    assert resp["kind"] == "tier" and len(resp["rows"]) == 15
    # single 每 3 期一階:第1~3 期 tier=1、第4 期起 tier=2
    tiers = [r["tier"] for r in resp["rows"]]
    assert tiers[0] == 1 and tiers[2] == 1 and tiers[3] == 2


def test_plan_units_ceil_to_005():
    resp = plan.plan_response("single", 0.01, 18440, 15, 2755, 21200, "single")
    for row in resp["rows"]:
        # 車數為 0.05 的倍數(允許浮點誤差)
        assert abs(round(row["units"] / 0.05) * 0.05 - row["units"]) < 1e-6


# ── marksix 被擋 + 遊戲驗證 ─────────────────────────────────
def test_marksix_blocked():
    with pytest.raises(HTTPException) as ei:
        yahong_router._guard("marksix")
    assert ei.value.status_code == 400
    assert "539" in ei.value.detail


def test_unknown_game_404():
    with pytest.raises(HTTPException) as ei:
        yahong_router._guard("nonexistent_game")
    assert ei.value.status_code == 404


def test_supported_games_pass_guard():
    yahong_router._guard("lotto539")   # 不應拋
    yahong_router._guard("fantasy5")
