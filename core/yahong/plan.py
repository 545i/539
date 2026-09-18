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


def _ceil_step(x: float) -> float:
    """向上取整到 0.05 的倍數(先修浮點誤差)。"""
    return math.ceil(round(x / STEP, 9)) * STEP


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


def plan_response(kind: str, units: float, target: float, days: int | None,
                  cost: float, prize: float, tier_mode: str) -> dict:
    """組出 API 端點 5 的 JSON。days 依 kind 給預設:single 15 / four 6 / tier 15。"""
    if days is None:
        days = 6 if kind == "four" else 15
    if kind == "four":
        rows = four_plan(units, target, days, cost, prize)
    elif kind == "tier":
        rows = tier_plan(units, days, tier_mode)
    else:
        kind = "single"
        rows = single_plan(units, target, days, cost, prize)
    return {"kind": kind, "rows": rows}
