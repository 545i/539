"""二合(二星)買牌試算:中獎機率階梯、成本、期望投報、凱莉、追損、倍頭。

純計算端點,不讀開獎資料、不需登入。所有數字都由 core.erhe 算,這裡只負責
把遊戲規格(num_max / pick / 盤口預設值)填進去,並把 inf 換成 null 讓 JSON 出得去。

「每車成本 / 中獎可得」預設取 GameConfig 的盤口值;呼叫端可以自己帶,
端點不對盤口做任何假設(二合兩組:每車成本 2755、中一顆得 21200,不除以 4)。
"""
from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.data import get_game
from core import erhe
from core.games import GameConfig

router = APIRouter(prefix="/erhe", tags=["erhe"])


def _fin(x: float) -> float | None:
    """把 inf / nan 換成 None —— Starlette 的 JSONResponse 用 allow_nan=False,
    直接回 float("inf") 會炸 ValueError。"""
    return x if math.isfinite(x) else None


def _odds(g: GameConfig, cost_per_car: float | None,
          win_payout: float | None) -> tuple[float, float]:
    """盤口:沒給就用該遊戲的預設值。"""
    return (cost_per_car if cost_per_car is not None else g.default_cost_per_car,
            win_payout if win_payout is not None else g.default_win_payout)


def _check_numbers(g: GameConfig, n_numbers: int) -> None:
    if n_numbers > g.num_max:
        raise HTTPException(status_code=400,
                            detail=f"{g.name} 只有 {g.num_max} 個號碼,押不了 {n_numbers} 顆")


@router.get("/plan")
def plan(game: str = Query(...),
         n_numbers: int = Query(1, ge=1, description="這局押幾顆"),
         cars: float = Query(1.0, gt=0, description="車數(可為 0.5 車)"),
         cost_per_car: float | None = Query(None, gt=0),
         win_payout: float | None = Query(None, gt=0)):
    """單顆 / 多顆二合下注的整局試算。

    成本 = 押幾顆 × 車數 × 每車成本;中 k 顆回收 = k × 車數 × 中獎可得。
    期望報酬率與凱莉都是車級(單顆中不中的二元賭局),與押幾顆、幾車無關。
    """
    g = get_game(game)
    _check_numbers(g, n_numbers)
    cost, payout = _odds(g, cost_per_car, win_payout)

    dist = erhe.hit_distribution(n_numbers, pick=g.pick, num_max=g.num_max)
    total_cost = n_numbers * cars * cost
    payout_per_hit = cars * payout

    return {
        "game": g.key,
        "n_numbers": n_numbers,
        "cars": cars,
        "cost_per_car": cost,
        "win_payout": payout,
        "notes_per_car": g.notes_per_car,      # 1 車的注數 = 1 膽拖其餘號(碰數)
        "dan_prob": g.dan_prob,                # 單顆命中率 = pick / num_max
        "any_hit_prob": 1.0 - dist.get(0, 0.0),  # 押 n 顆至少中 1 顆
        "total_cost": total_cost,
        "payout_per_hit": payout_per_hit,
        "ev_rate": erhe.car_ev_rate(cost, payout, g.dan_prob),
        "kelly_fraction": erhe.car_kelly_fraction(cost, payout, g.dan_prob),
        "per_car_1hit_net": erhe.per_car_one_hit_net(n_numbers, cost, payout),
        "breakeven_hits": _fin(total_cost / payout_per_hit) if payout_per_hit else None,
        "hits": [
            {
                "hits": k,
                "prob": p,
                "payout": k * payout_per_hit,
                "pnl": erhe.round_net(cars, k, n_numbers, cost, payout),
            }
            for k, p in sorted(dist.items())
        ],
    }


@router.get("/recovery")
def recovery(game: str = Query(...),
             cumulative_net: float = Query(..., description="目前累積損益(負數為虧損)"),
             n_numbers: int = Query(1, ge=1),
             cost_per_car: float | None = Query(None, gt=0),
             win_payout: float | None = Query(None, gt=0),
             base_cars: int = Query(3, ge=1)):
    """追損:下一局要下幾車,「中 1 顆」就能把累積虧損追平。

    next_cars 為 null 代表中 1 顆的淨利 <= 0,再多車也追不回來。
    """
    g = get_game(game)
    _check_numbers(g, n_numbers)
    cost, payout = _odds(g, cost_per_car, win_payout)
    res = erhe.next_cars_for_recovery(cumulative_net, n_numbers, cost, payout,
                                      base_cars=base_cars)
    return {**res,
            "next_cars": _fin(res["next_cars"]),
            "next_cost": _fin(res["next_cost"])}


@router.get("/progression")
def progression(game: str = Query(...),
                progression: str = Query("3,5,7,10,13", description="車數序列,逗號分隔"),
                n_numbers: int = Query(1, ge=1),
                cost_per_car: float | None = Query(None, gt=0),
                win_payout: float | None = Query(None, gt=0),
                capital: float = Query(500000.0, gt=0)):
    """連敗加碼的進程成本表:每局押 n_numbers 顆、車數依序列加碼。"""
    g = get_game(game)
    _check_numbers(g, n_numbers)
    cost, payout = _odds(g, cost_per_car, win_payout)
    try:
        prog = [int(x) for x in progression.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="進程序列格式錯誤,請用「3,5,7」這種寫法")
    if not prog:
        raise HTTPException(status_code=400, detail="進程序列不能是空的")

    rows = erhe.progression_table_multi(prog, n_numbers=n_numbers, cost_per_car=cost,
                                        win_payout=payout, capital=capital)
    return {
        "per_round_ev": erhe.per_round_ev_rate(cost, payout, g.dan_prob),
        "rows": [
            {
                "round": r.round,
                "cars": r.cars,
                "round_cost": r.round_cost,
                "cumulative_cost": r.cumulative_cost,
                "payout_per_hit": r.payout_per_hit,
                "break_even_hits": _fin(r.break_even_hits),
                "busted": r.busted,
            }
            for r in rows
        ],
    }


@router.get("/martingale")
def martingale(game: str = Query(...),
               base_cars: int = Query(3, ge=1),
               multiplier: float = Query(2.0, gt=1),
               rounds: int = Query(12, ge=1, le=40),
               cost_per_car: float | None = Query(None, gt=0),
               win_payout: float | None = Query(None, gt=0),
               capital: float | None = Query(None, gt=0)):
    """倍頭進程:連敗時車數乘以 multiplier,列出「要中幾車才回本」與破產局數。"""
    g = get_game(game)
    cost, payout = _odds(g, cost_per_car, win_payout)
    table = erhe.martingale_table(base_cars=base_cars, multiplier=multiplier,
                                  rounds=rounds, cost_per_car=cost,
                                  win_payout=payout, capital=capital)
    return {
        "multiplier": table.multiplier,
        "bust_round": table.bust_round,
        "steps": [
            {
                "round": s.round,
                "cars": s.cars,
                "round_cost": s.round_cost,
                "cumulative_cost": s.cumulative_cost,
                "cars_to_break_even": _fin(s.cars_to_break_even),
            }
            for s in table.steps
        ],
    }


class SimultaneousIn(BaseModel):
    """同一局同時下多款時的回本試算輸入。

    plans:{遊戲代號: [押幾顆, 每車成本, 中獎可得]}
    fixed:{遊戲代號: 車數} —— 使用者已自行決定車數的款
    share:回本責任分母(1 = 任一款中 1 顆就全回本;N = N 款平攤)
    """
    cumulative_net: float
    plans: dict[str, tuple[int, float, float]]
    fixed: dict[str, int] | None = None
    base_cars: int = 3
    share: float = 1.0


@router.post("/simultaneous")
def simultaneous(body: SimultaneousIn):
    """同一局同時下多款時,各款該下幾車;k >= share 時無解(feasible=false)。"""
    res = erhe.simultaneous_recovery(
        body.cumulative_net, {k: tuple(v) for k, v in body.plans.items()},
        base_cars=body.base_cars, fixed=body.fixed, share=body.share)
    return {**res,
            "total_cost": _fin(res["total_cost"]),
            "worst_after": _fin(res["worst_after"]),
            "all_hit_after": _fin(res["all_hit_after"])}
