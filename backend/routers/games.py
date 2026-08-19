"""遊戲清單:把 core.games 的三款序列化給前端做遊戲切換。"""
from __future__ import annotations

from fastapi import APIRouter

from backend.data import all_games
from core import pillar
from core.games import GameConfig

router = APIRouter(prefix="/games", tags=["games"])


def serialize(g: GameConfig) -> dict:
    return {
        "key": g.key,
        "name": g.name,
        "short_name": g.short_name,
        "num_max": g.num_max,
        "pick": g.pick,
        "ticket_price": g.ticket_price,
        "currency": g.currency,
        "prize": {str(k): v for k, v in g.prize.items()},
        "total_comb": g.total_comb,
        "supports_pillar": pillar.supports(g),
        "default_bet_cost": g.default_bet_cost,
        "default_bet_prize": g.default_bet_prize,
        "default_cost_per_car": g.default_cost_per_car,
        "default_win_payout": g.default_win_payout,
    }


@router.get("")
def list_games():
    return [serialize(g) for g in all_games()]
