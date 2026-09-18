"""雅宏策略 5 端點:決策矩陣 / 同區3-4球 / 單碼必贏 / 綜合分析 / 資金規劃。

僅支援 lotto539 / fantasy5(39選5,符合「碰」模型);marksix 回 400。
純計算端點,不需登入。演算法見 core.yahong.* 與 docs/yahong/。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.data import get_game, load_df
from core.loader import draws_as_lists
from core.yahong import analysis, matrix, plan, single, zone34

router = APIRouter(prefix="/yahong", tags=["yahong"])

SUPPORTED = {"lotto539", "fantasy5"}
MAX_DRAWS = 1500


def _guard(game: str) -> None:
    """驗證遊戲存在(未知回 404)且在支援範圍(marksix 回 400)。"""
    get_game(game)                       # 未知/停用 → 404
    if game not in SUPPORTED:
        raise HTTPException(status_code=400, detail="雅宏策略僅支援 539 / 天天樂")


def _draws_new_old(game: str) -> list[list[int]]:
    """新→舊序列(data[0]=最新),最多 1500 期。"""
    return list(reversed(draws_as_lists(load_df(game))))[:MAX_DRAWS]


@router.get("/matrix")
def matrix_ep(game: str = Query(...), mode: str = Query("1800")):
    _guard(game)
    if mode not in ("1800", "9000"):
        raise HTTPException(status_code=400, detail="mode 僅支援 1800 / 9000")
    data = _draws_new_old(game)
    return matrix.matrix_response(game, mode, matrix.config_for(mode), data)


@router.get("/radar")
def radar_ep(game: str = Query(...)):
    _guard(game)
    draws_old_new = draws_as_lists(load_df(game))     # 舊→新
    return zone34.radar_response(game, draws_old_new)


@router.get("/single")
def single_ep(game: str = Query(...), target: int | None = Query(None, ge=1, le=39)):
    _guard(game)
    data = _draws_new_old(game)
    return single.single_response(game, data, target)


@router.get("/analysis")
def analysis_ep(game: str = Query(...), seed: int | None = Query(None)):
    _guard(game)
    df = load_df(game)
    data = list(reversed(draws_as_lists(df)))[:MAX_DRAWS]
    latest_date = df["date"].iloc[-1].strftime("%Y-%m-%d") if not df.empty else None
    return analysis.analysis_response(game, data, latest_date, seed)


@router.get("/plan")
def plan_ep(kind: str = Query("single"), units: float = Query(1.0, ge=0),
            target: float = Query(plan.DEFAULT_TARGET), days: int | None = Query(None, ge=1, le=60),
            cost: float = Query(plan.DEFAULT_COST, gt=0),
            prize: float = Query(plan.DEFAULT_PRIZE, gt=0),
            tierMode: str = Query("single")):
    if kind not in ("single", "four", "tier"):
        raise HTTPException(status_code=400, detail="kind 僅支援 single / four / tier")
    if tierMode not in ("single", "four"):
        raise HTTPException(status_code=400, detail="tierMode 僅支援 single / four")
    return plan.plan_response(kind, units, target, days, cost, prize, tierMode)
