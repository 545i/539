"""三柱 1800碰:分柱資訊、部分包牌(新功能 B)、追損、歷史檢驗。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.data import get_game, load_df
from core import pillar
from core.games import GameConfig
from core.loader import draws_as_lists

router = APIRouter(prefix="/pillar", tags=["pillar"])


def _require_pillar(game: str) -> GameConfig:
    g = get_game(game)
    if not pillar.supports(g):
        raise HTTPException(status_code=400, detail=f"{g.name} 不適用三柱1800碰")
    return g


@router.get("/info")
def info(game: str = Query(...)):
    g = _require_pillar(game)
    c1, c2, c3 = pillar.pillars(g.num_max)
    ways = pillar.outcome_ways(g.num_max, g.pick)
    total = pillar.total_draws(g.num_max, g.pick)
    round_cost = pillar.round_cost(g.default_bet_cost, 1, g.num_max)

    theory_rows = []
    broken_ways = 0
    for dist, w in sorted(ways.items(), key=lambda kv: -kv[1]):
        h = pillar.hits_from_counts(dist)
        if h == 0:
            broken_ways += w
            continue
        ret = h * g.default_bet_prize
        theory_rows.append({
            "dist": " + ".join(str(x) for x in dist),
            "hits": h,
            "prob": w / total,
            "return_amount": ret,
            "pnl": ret - round_cost,
        })
    theory_rows.append({
        "dist": "斷柱 (任一柱 0 顆)",
        "hits": 0,
        "prob": broken_ways / total,
        "return_amount": 0.0,
        "pnl": -round_cost,
    })

    return {
        "pillars": [c1, c2, c3],
        "sizes": list(pillar.sizes(g.num_max)),
        "total_bets": pillar.total_bets(g.num_max),
        "pass_prob": pillar.pass_prob(g.num_max, g.pick),
        "expected_hits": pillar.expected_hits(g.num_max, g.pick),
        "theory_rows": theory_rows,
    }


class PartialIn(BaseModel):
    game: str
    picks: list[int]


@router.post("/partial")
def partial(body: PartialIn):
    """使用者自選號碼 → 這組選號的部分包牌注數/涵蓋率(新功能 B)。"""
    g = _require_pillar(body.game)
    res = pillar.partial_bets(body.picks, num_max=g.num_max)
    return {
        "pillars": [list(p) for p in res["pillars"]],
        "counts": list(res["counts"]),
        "bets": res["bets"],
        "total": res["total"],
        "coverage": res["coverage"],
        "buyable": res["buyable"],
    }


@router.get("/recovery")
def recovery(game: str = Query(...), loss: float = Query(...),
             cost: float = Query(...), prize: float = Query(...)):
    g = _require_pillar(game)
    return pillar.multiplier_for_recovery(
        loss, cost, prize, num_max=g.num_max, pick=g.pick)


@router.get("/history")
def history(game: str = Query(...), periods: int = Query(200, ge=1)):
    g = _require_pillar(game)
    df = load_df(game)
    draws = draws_as_lists(df)[-periods:]
    hs = pillar.history_stats(draws, num_max=g.num_max, pick=g.pick)
    return {
        "periods": hs["rounds"],
        "actual_pass_rate": hs["pass_rate"],
        "theory_pass_rate": pillar.pass_prob(g.num_max, g.pick),
        "passed": hs["passes"],
        "current_streak": hs["streak"],
        "max_streak": hs["max_streak"],
    }
