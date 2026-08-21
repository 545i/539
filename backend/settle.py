"""流水帳的「開獎核對」:拿某一期的真實開獎號,把一筆記帳重新對獎、算損益。

前端的核對列表可以事後改一筆的期數;改完就用這裡把該期開獎號抓進來、判定中
了幾顆 / 幾碰,再依各下法的派彩規則重算 payout 與 pnl。**money 規則只寫在這一
個地方**(後端權威),登入(存 DB)與未登入(前端暫存)兩條路都呼叫這裡,不
各算各的。

各下法的對獎與派彩:
- single  押 1 顆,命中(該顆有開)回收 = 車數 × 每車中獎可得,否則 0。
- multi   押多顆,命中幾顆 × 車數 × (每車中獎可得 ÷ 4);盤口沿用多顆下注頁。
- pillar1800  三柱全包,命中注數只可能是 4 / 3 / 0(見 core.pillar),
              回收 = 支數 × 命中注數 × 每注可得。
- combo   星碰用 core.combo.star_hits_of(中的碰數),其餘連碰家族用 hits_of。
          回收 = 中的碰/注數 × 中一碰可得(盤口後台可改) × 支數。
          注:連碰家族的「膽」沒存進紀錄,這裡一律當 dans=0(全碰)——
          對星碰與連碰(全碰)精確,對立柱 / 拖膽是近似。

draw 傳 None(該期還沒開 / 查不到)時,退回「待開獎」:清空開獎號、payout /
pnl 歸零,不亂算。cost 一律沿用原紀錄(投入的錢不因對獎而變)。
"""
from __future__ import annotations

import re

from core import combo, pillar
from core.games import GameConfig


def _f(record: dict, key: str, default: float = 0.0) -> float:
    v = record.get(key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def _cars(record: dict) -> float:
    """車數 / 支數:優先 cars,退而求其次 units。"""
    c = _f(record, "cars", 0.0)
    return c if c > 0 else _f(record, "units", 0.0)


def _stars_of(play_type: str) -> int:
    """從 playType(如「連碰(全碰) 3 (5 支)」)取星數;取不到當 3 星。"""
    m = re.search(r"\d+", play_type or "")
    return int(m.group()) if m else 3


def settle(record: dict, draw: list[int] | None, g: GameConfig) -> dict:
    """回傳「對過獎」的紀錄(淺拷貝),更新 drawBalls / result / payout / pnl。

    只動對獎會變的欄位,其餘(selectedBalls / cost / 期數 …)原樣保留。
    """
    out = dict(record)
    cost = _f(record, "cost", 0.0)

    # 該期還沒開 / 查不到 → 待開獎,不硬算
    if not draw:
        out["drawBalls"] = []
        out["result"] = "待開獎"
        out["payout"] = 0.0
        out["pnl"] = 0.0
        return out

    draw = [int(x) for x in draw]
    out["drawBalls"] = draw
    selected = [int(x) for x in record.get("selectedBalls", []) or []]
    mode = record.get("mode")
    cars = _cars(record)

    if mode == "single":
        hit = 1 if set(selected) & set(draw) else 0
        payout = hit * cars * g.default_win_payout
        result = "中了 1 顆 (中獎)" if hit else "槓龜 (沒中)"

    elif mode == "multi":
        matched = len(set(selected) & set(draw))
        payout = matched * cars * (g.default_win_payout / 4)
        result = f"中 {matched} 顆" if matched > 0 else "槓龜"

    elif mode == "pillar1800":
        counts = pillar.pillar_counts(draw, g.num_max)
        ph = pillar.hits_from_counts(counts)          # 4 / 3 / 0
        payout = cars * ph * g.default_bet_prize
        result = pillar.result_text(ph) if ph else "槓龜(斷柱)"
        out["pillarDist"] = " + ".join(str(c) for c in counts)

    elif mode == "combo":
        play_type = str(record.get("playType", "") or "")
        stars = _stars_of(play_type)
        prize = float(combo.market_prize(stars, g.default_bet_prize) or 0.0)
        if play_type.startswith("星碰"):
            wh = combo.star_hits_of(stars, draw, selected)
            result = f"中 {wh} 碰" if wh > 0 else "槓龜"
        else:
            # 膽沒存進紀錄,連碰家族一律當 dans=0(全碰精確,立柱/拖膽近似)
            wh = combo.hits_of(stars, draw, selected, ())
            result = f"中 {wh:,} 注" if wh > 0 else "槓龜"
        payout = wh * prize * cars

    else:
        # 未知下法:只填開獎號,不動金額
        return out

    out["payout"] = round(float(payout))
    out["pnl"] = round(float(payout) - cost)
    out["result"] = result
    return out
