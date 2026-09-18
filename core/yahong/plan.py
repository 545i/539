"""資金規劃計算機 —— 移植 spec-539.md §A(單碼倍投 / 4碼倍投 / 階梯均注)。

車數一律 ceil 到 0.05;cost 2755 / prize 21200 預設可覆寫。純計算,不碰開獎資料。

TODO(天天樂專屬,暫未實作,不阻擋驗收):spec-fantasy §4 另有立柱倍投
(calculateMatrixPlan,常數 1134/570/4545/8000)與 4 碼階梯規則(2 期一階、
+1200/×2.2、負利修正 +500)。目前 single/four/tier 三種對 539/天天樂共用
(cost 2755 / prize 21200),天天樂立柱倍投待後續補上。
"""
from __future__ import annotations

import math

DEFAULT_COST = 2755.0
DEFAULT_PRIZE = 21200.0
DEFAULT_TARGET = 18440.0
STEP = 0.05


# 天天樂預設(spec-fantasy §4)
FANTASY_FIRST_UNITS = 0.10
FANTASY_TARGET_DAILY = 1844.0
PILLAR_FIRST_BET = 1
PILLAR_TARGET_PROFIT = 500.0


def _ceil_step(x: float) -> float:
    """向上取整到 0.05 的倍數(先修浮點誤差)—— 539 用。"""
    return math.ceil(round(x / STEP, 9)) * STEP


def _ceil2(x: float) -> float:
    """向上取整到 0.01(ceil(x*100)/100)—— 天天樂用。"""
    return math.ceil(round(x * 100, 6)) / 100


def _rm(x: float) -> int:
    """四捨五入(half-up,對齊 JS Math.round)。"""
    return math.floor(x + 0.5)


def single_plan(units: float, target: float, days: int,
                cost: float, prize: float) -> list[dict]:
    """A-1 單碼目標倍投。"""
    rows = []
    acc = 0.0
    for i in range(1, days + 1):
        current_target = target * i
        req = (current_target + acc) / (prize - cost)
        if i == 1 and units >= req:
            req = units
        else:
            req = _ceil_step(req)
        if req < 0.01:
            req = STEP
        daily_cost = req * cost
        acc += daily_cost
        win_prize = req * prize
        net = win_prize - acc
        rows.append({"day": i, "target": round(current_target), "units": round(req, 2),
                     "dailyCost": round(daily_cost), "accCost": round(acc),
                     "winPrize": round(win_prize), "netProfit": round(net)})
    return rows


def four_plan(units: float, target: float, days: int,
              cost: float, prize: float) -> list[dict]:
    """A-2 4碼目標倍投(同押 4 碼:分母扣 4*cost、成本 ×4)。"""
    rows = []
    acc = 0.0
    for i in range(1, days + 1):
        current_target = target * i
        req = (current_target + acc) / (prize - 4 * cost)
        if i == 1 and units >= req:
            req = units
        else:
            req = _ceil_step(req)
        if req < 0.01:
            req = STEP
        daily_cost = req * cost * 4
        acc += daily_cost
        win_prize = req * prize
        net = win_prize - acc
        double_win = win_prize * 2 - acc
        rows.append({"day": i, "target": round(current_target), "units": round(req, 2),
                     "dailyCost": round(daily_cost), "accCost": round(acc),
                     "winPrize": round(win_prize), "netProfit": round(net),
                     "doubleWin": round(double_win)})
    return rows


def _tier_next_units(prev_cost: float, prev_u: float, tier_mode: str) -> float:
    """A-3 跨階重算車數:用已累計成本回推 + 5% 緩衝,至少比上一階多 0.05。"""
    cost_unit = DEFAULT_COST if tier_mode == "single" else DEFAULT_COST * 4
    u = prev_cost / (DEFAULT_PRIZE - cost_unit) * 1.05
    u = _ceil_step(u)
    if u <= prev_u:
        u = prev_u + STEP
    return round(u, 2)


def tier_plan(units: float, days: int, tier_mode: str) -> list[dict]:
    """A-3 階梯均注(prize 固定 21200;single 每 3 期一階、four 每 2 期一階)。"""
    cost_unit = DEFAULT_COST if tier_mode == "single" else DEFAULT_COST * 4
    step = 3 if tier_mode == "single" else 2
    rows = []
    acc = 0.0
    cur_u = units
    tier = 1
    for i in range(1, days + 1):
        if i > 1 and (i - 1) % step == 0:
            tier += 1
            cur_u = _tier_next_units(acc, cur_u, tier_mode)
        daily_cost = cur_u * cost_unit
        acc += daily_cost
        win_prize = cur_u * DEFAULT_PRIZE
        net = win_prize - acc
        rows.append({"day": i, "tier": tier, "units": round(cur_u, 2),
                     "dailyCost": round(daily_cost), "accCost": round(acc),
                     "winPrize": round(win_prize), "netProfit": round(net)})
    return rows


# ── 天天樂版(spec-fantasy §4;車數 ceil 到 0.01、金額 Math.round)──────────
def single_plan_fantasy(first_units: float, target_daily: float, days: int,
                        cost: float, prize: float) -> list[dict]:
    """§4.1 天天樂單碼目標倍投。day1 恆用 first_units;車數 ceil 到 0.01。"""
    net_win = prize - cost
    rows = []
    acc = 0.0
    for day in range(1, days + 1):
        target_cum = target_daily * day
        units = first_units if day == 1 else _ceil2((acc + target_cum) / net_win)
        current_cost = _rm(units * cost)
        acc += current_cost
        win_prize = _rm(units * prize)
        net = win_prize - acc
        rows.append({"day": day, "target": _rm(target_cum), "units": round(units, 2),
                     "dailyCost": current_cost, "accCost": _rm(acc),
                     "winPrize": win_prize, "netProfit": net})
    return rows


def four_plan_fantasy(first_units: float, target_daily: float, days: int,
                      cost: float, prize: float) -> list[dict]:
    """§4.2 天天樂 4碼目標倍投(分母 prize-4*cost、成本 ×4、含 doubleWin)。"""
    net_win = prize - 4 * cost
    rows = []
    acc = 0.0
    for day in range(1, days + 1):
        target_cum = target_daily * day
        units = first_units if day == 1 else _ceil2((acc + target_cum) / net_win)
        round_cost = _rm(units * 4 * cost)
        acc += round_cost
        prize_one = _rm(units * prize)
        net_one = prize_one - acc
        prize_two = _rm(units * prize * 2)
        net_two = prize_two - acc
        rows.append({"day": day, "target": _rm(target_cum), "units": round(units, 2),
                     "dailyCost": round_cost, "accCost": _rm(acc),
                     "winPrize": prize_one, "netProfit": net_one, "doubleWin": net_two,
                     "doubleWinPrize": prize_two})
    return rows


def tier_plan_fantasy(start_units: float, days: int, tier_mode: str) -> list[dict]:
    """§4.3 天天樂階梯:單碼 3 期一階(+1000);4碼 2 期一階(+1200/×2.2/負利修正+500)。"""
    prize = DEFAULT_PRIZE
    single = tier_mode == "single"
    cost_unit = DEFAULT_COST if single else 4 * DEFAULT_COST   # 2755 / 11020
    step = 3 if single else 2
    denom = prize - (3 * DEFAULT_COST if single else cost_unit)  # 12935 / 10180
    total_tiers = math.ceil(days / step) if days > 0 else 0
    rows = []
    acc = 0.0
    cars = prev_cars = start_units
    day = 0
    for t in range(total_tiers):
        if t != 0:                            # 跨階重算車數
            const = 1000 if single else 1200
            cars = _ceil2((acc + const) / denom)
            if cars <= prev_cars:
                cars = round(prev_cars + STEP, 2) if single else _ceil2(prev_cars * 2.2)
        for _ in range(step):
            day += 1
            if day > days:
                break
            prev_cum = acc
            cur_cost = _rm(cars * cost_unit)
            acc = prev_cum + cur_cost
            win_prize = _rm(cars * prize)
            profit = win_prize - acc
            if not single and profit < 0:     # 4碼:修正保證正淨利
                cars = _ceil2((prev_cum + 500) / denom)
                cur_cost = _rm(cars * cost_unit)
                acc = prev_cum + cur_cost
                win_prize = _rm(cars * prize)
                profit = win_prize - acc
            rows.append({"day": day, "tier": t + 1, "units": round(cars, 2),
                         "dailyCost": cur_cost, "accCost": _rm(acc),
                         "winPrize": win_prize, "netProfit": profit})
        prev_cars = cars
    return rows


def pillar_plan(mode: str, first_bet: int, target_profit: float, days: int) -> list[dict]:
    """§4.4 天天樂立柱倍投,**改讀我方即時盤口、無退水**(移除寫死 1134/570/4545/8000)。

    每輪(每 bet 倍全包)成本 = 碰數 × 每碰成本 × bet;
    1800:三星,中3碰=3×中一碰可得×bet、中4碰暴利=4×…;9000:四星,過關中2碰=2×…。
    每碰成本讀 combo.market_cost(3|4);中一碰可得:1800=combo.market_prize(3)、
    9000=combo9000.PRIZE_PER_BET(800000)。bet 為整數倍:day1=first_bet,
    其後 max(1, ceil((累計+目標)/單位淨賺))。
    """
    from core import combo, combo9000
    if mode == "1800":
        puffs = 1800
        unit_cost = float(combo.market_cost(3) or 63.0)
        unit_prize = float(combo.market_prize(3) or 57_000.0)
        base_prize_unit = 3 * unit_prize
    else:
        puffs = 9000
        unit_cost = float(combo.market_cost(4) or 50.0)
        unit_prize = float(combo9000.PRIZE_PER_BET)
        base_prize_unit = 2 * unit_prize
    cost_unit = puffs * unit_cost
    net_win = base_prize_unit - cost_unit
    rows = []
    cum = 0.0
    for day in range(1, days + 1):
        if day == 1:
            bet = first_bet
        elif net_win > 0:
            bet = max(1, math.ceil((cum + target_profit) / net_win))
        else:
            bet = first_bet          # 淨賺非正時無法追號,退回起步注(理論上不會發生)
        current_cost = bet * cost_unit
        cum += current_cost
        base_prize = bet * base_prize_unit
        base_profit = base_prize - cum
        row = {"day": day, "bet": bet, "dailyCost": _rm(current_cost), "accCost": _rm(cum),
               "basePrize": _rm(base_prize), "baseProfit": _rm(base_profit)}
        if mode == "1800":                   # 4 碰暴利
            bonus_prize = bet * 4 * unit_prize
            row["bonusPrize"] = _rm(bonus_prize)
            row["bonusProfit"] = _rm(bonus_prize - cum)
        rows.append(row)
    return rows


def plan_response(game: str, kind: str, units: float | None, target: float | None,
                  days: int | None, cost: float, prize: float, tier_mode: str) -> dict:
    """組出 API 端點 5 的 JSON,依 game 分流(539 維持 spec-539 §A;天天樂照 spec-fantasy §4)。"""
    # 立柱倍投:天天樂專屬,常數固定,與 game 無關(539 UI 不提供)
    if kind in ("pillar1800", "pillar9000"):
        first_bet = int(units) if units is not None else PILLAR_FIRST_BET
        target_profit = target if target is not None else PILLAR_TARGET_PROFIT
        d = days if days is not None else 6
        rows = pillar_plan("1800" if kind == "pillar1800" else "9000",
                           first_bet, target_profit, d)
        return {"kind": kind, "game": game, "rows": rows}

    if game == "fantasy5":
        u = units if units is not None else FANTASY_FIRST_UNITS
        tg = target if target is not None else FANTASY_TARGET_DAILY
        if kind == "four":
            rows = four_plan_fantasy(u, tg, days if days is not None else 6, cost, prize)
        elif kind == "tier":
            rows = tier_plan_fantasy(u, days if days is not None else 15, tier_mode)
        else:
            kind = "single"
            rows = single_plan_fantasy(u, tg, days if days is not None else 15, cost, prize)
        return {"kind": kind, "game": game, "rows": rows}

    # lotto539(維持不動:target 為每期目標增量,預設 18440;車數 ceil 0.05)
    u = units if units is not None else 1.0
    tg = target if target is not None else DEFAULT_TARGET
    if kind == "four":
        rows = four_plan(u, tg, days if days is not None else 6, cost, prize)
    elif kind == "tier":
        rows = tier_plan(u, days if days is not None else 15, tier_mode)
    else:
        kind = "single"
        rows = single_plan(u, tg, days if days is not None else 15, cost, prize)
    return {"kind": kind, "game": game, "rows": rows}
