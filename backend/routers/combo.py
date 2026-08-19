"""連碰 / 星碰 / 立柱 / 拖膽:注數、成本、損益兩平與機率試算。

純計算端點 —— 不讀開獎資料、不需登入。數學一律走 core.combo,這裡只負責把
UI 的玩法參數翻成它的引數(哪幾顆是膽、拖幾顆),再把結果攤平成 JSON。

星碰與其餘三種是**不同的算法**(見 core.combo 的說明):星碰一碰是「一組星
+ 一顆搭配號」,注數走 star_bets / star_* 系列;連碰、立柱、拖膽同屬一條
C(拖幾顆, 星數 − 膽幾顆) 的公式,差別只在膽幾顆。這裡照玩法分岔,不混用。
"""
from __future__ import annotations

from math import isfinite

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.data import get_game
from core import combo

router = APIRouter(prefix="/combo", tags=["combo"])

# bet_list 會把整張注單攤成 list 再排序 —— 顆數一大就是幾十萬筆(39 顆五星
# 全展開是 575,757 注),而前端只要前幾注當預覽,為了它吃掉幾十 MB 不划算。
# 超過這個上限就不展開(回 truncated=true),注數本身照樣算給你。
MAX_EXPAND = 200_000


def _num(x: float | None) -> float | None:
    """inf / nan 換成 None —— JSON 沒有無限大,原樣送出前端 parse 會炸。"""
    if x is None:
        return None
    x = float(x)
    return x if isfinite(x) else None


def _play(key: str) -> combo.Play:
    p = combo.PLAY_BY_KEY.get(key)
    if p is None:
        raise HTTPException(status_code=400, detail=f"未知玩法:{key}")
    return p


@router.get("/plays")
def plays():
    """玩法清單與盤口預設值(星數、每碰成本、中一碰可得)。"""
    return {
        "plays": [{"key": p.key, "name": p.name, "dans": p.dans, "desc": p.desc}
                  for p in combo.PLAYS],
        "stars": list(combo.STARS),
        "star_names": {str(k): v for k, v in combo.STAR_NAMES.items()},
        "star_pick": combo.STAR_PICK,
        "market_cost": {str(k): v for k, v in combo.MARKET_COST.items()},
        "market_prize": {str(k): v for k, v in combo.MARKET_PRIZE.items()},
    }


class CalcIn(BaseModel):
    game: str = "lotto539"
    play: str = "combo"                # star / combo / pillar / dan
    stars: int = Field(3, ge=1)
    picked: int = Field(..., ge=0)     # 選幾顆(膽 + 拖)
    dans: int = Field(0, ge=0)         # 只有「拖膽」吃這個值,其餘由玩法決定
    per_bet: float | None = None       # 每碰成本;留空用 core 的市場價
    prize: float | None = None         # 中一碰可得;留空用 core 的市場派彩
    sheets: int = Field(1, ge=1)       # 買幾支(1 支 = 買滿這張的全部碰數)


@router.post("/calc")
def calc(body: CalcIn):
    """一張牌的注數 / 成本 / 打平點 / 返還率 / 中獎機率分佈。"""
    g = get_game(body.game)
    p = _play(body.play)
    stars, picked = int(body.stars), int(body.picked)
    if picked > g.num_max:
        raise HTTPException(
            status_code=400,
            detail=f"選了 {picked} 顆,超過 {g.name} 的 {g.num_max} 個號碼")

    # 玩法固定幾顆膽就用它的;拖膽(dans=None)才吃使用者給的
    dans = int(body.dans) if p.dans is None else p.dans
    drag = picked - dans
    if drag < 0:
        raise HTTPException(status_code=400,
                            detail=f"膽 {dans} 顆比選的 {picked} 顆還多")

    # 沒指定就用 core 的市場盤口;星數超出 2~4 時退回遊戲本身的三合預設
    per_bet = float(body.per_bet if body.per_bet is not None
                    else combo.MARKET_COST.get(stars, g.default_bet_cost))
    prize = float(body.prize if body.prize is not None
                  else combo.MARKET_PRIZE.get(stars, g.default_bet_prize))
    odds = prize / per_bet if per_bet else 0.0

    if p.key == "star":
        n = combo.star_bets(stars, picked)
        probs = combo.star_hit_probs(stars, picked, g.num_max, g.pick)
        win = combo.star_win_prob(stars, picked, g.num_max, g.pick)
        e_hits = combo.star_expected_hits(stars, picked, g.num_max, g.pick, n)
        rate = combo.star_return_rate(stars, picked, odds, g.num_max, g.pick, n)
        fair = combo.star_fair_odds(stars, picked, g.num_max, g.pick, n)
        cost = n * per_bet
        # 星碰沒有膽 / 拖之分,打平碰數 = 成本 ÷ 中一碰可得 = 碰數 ÷ 倍率
        breakeven = n / odds if odds else float("inf")
        net = e_hits * prize - cost
    else:
        n = combo.bets(stars, drag, dans)
        probs = combo.hit_probs(stars, drag, dans, g.num_max, g.pick)
        win = combo.win_prob(stars, drag, dans, g.num_max, g.pick)
        e_hits = combo.expected_hits(stars, drag, dans, g.num_max, g.pick)
        rate = combo.return_rate(stars, odds, g.num_max, g.pick)
        fair = combo.fair_odds(stars, g.num_max, g.pick)
        cost = combo.total_cost(stars, drag, per_bet, dans)
        breakeven = combo.breakeven_bets(stars, drag, odds, dans)
        net = combo.expected_net(stars, drag, per_bet, odds, dans,
                                 g.num_max, g.pick)

    return {
        "game": g.key,
        "play": {"key": p.key, "name": p.name, "dans": p.dans, "desc": p.desc},
        "stars": stars,
        "star_name": combo.star_name(stars),
        "picked": picked,
        "dans": dans,
        "drag": drag,
        "bets": n,
        "per_bet": per_bet,
        "prize_per_hit": prize,
        "odds": _num(odds),
        "sheets": int(body.sheets),
        "total_cost": cost,                       # 單支
        "round_cost": cost * int(body.sheets),    # 本局(× 支數)
        "breakeven_bets": _num(breakeven),
        "fair_odds": _num(fair),
        "win_prob": win,
        "expected_hits": e_hits,
        "expected_net": net,
        "return_rate": rate,
        "possible_hits": sorted(probs, reverse=True),
        "hit_probs": [{"hits": h, "prob": pr}
                      for h, pr in sorted(probs.items(), reverse=True)],
    }


class ExpandIn(BaseModel):
    game: str = "lotto539"
    stars: int = Field(3, ge=1)
    nums: list[int] = Field(default_factory=list)      # 選的號碼(含膽)
    dan_nums: list[int] = Field(default_factory=list)  # 其中哪幾顆是膽
    limit: int = Field(10, ge=0, le=200)               # 只要前幾注當預覽


@router.post("/bets")
def expand(body: ExpandIn):
    """實際注單展開(連碰家族)。膽由 dan_nums 決定,不必再傳玩法。

    星碰不走這裡 —— 它的一碰是「一組星 + 一顆搭配號」,不是組合展開。
    """
    g = get_game(body.game)
    nums = sorted({int(x) for x in body.nums})
    dan = sorted({int(x) for x in body.dan_nums})
    bad = [x for x in nums + dan if not 1 <= x <= g.num_max]
    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"號碼超出範圍(1~{g.num_max}):{sorted(set(bad))}")

    drag = [x for x in nums if x not in set(dan)]
    total = combo.bets(body.stars, len(drag), len(dan))
    rows = (combo.bet_list(body.stars, drag, dan)[:body.limit]
            if total <= MAX_EXPAND else [])
    return {
        "bets": total,
        "stars": int(body.stars),
        "dans": len(dan),
        "drag": len(drag),
        "limit": body.limit,
        "truncated": total > MAX_EXPAND,
        "list": [list(t) for t in rows],
    }


@router.get("/table")
def table(dans: int = Query(0, ge=0)):
    """「拖幾顆 → 各星數各幾碰」對照表;碰數 0 的格子回 null。"""
    rows = combo.bets_table(dans)
    return {
        "dans": dans,
        "stars": list(combo.STARS),
        "rows": [{"drag": r["drag"],
                  "bets": {str(k): r[k] for k in combo.STARS}} for r in rows],
    }
