"""連碰 / 立柱(策略2)試算:注數、機率、成本、期望、凱莉、互動回本、進程模擬。

今彩539(39選5)。一注「r 星」= 指定 r 個號碼,當期開出的 5 碼若全包含這 r 碼即中。
單注機率 P_r = C(39-r, 5-r)/C(39,5):二星 ≈1/74.1、三星 ≈1/914、四星 ≈1/16450。

玩法:
  連碰:選 N 碼全互碰,r 星注數 = C(N, r)。命中 m 碼 → 中 C(m, r) 注。
  立柱:分數柱,同柱不碰、跨柱碰,r 星注數 = 各柱大小的基本對稱多項式 e_r;
        各柱命中 (h1..hk) 碼 → 中 e_r(h1..hk) 注。

誠實前提:每注期望報酬率 = P_r × 賠率 − 1,只由賠率決定;連碰/立柱只決定「買哪些注」,
立柱省的是低機率的同柱組合,改變不了每注的負期望(賠率 < 公平賠率時)。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import combinations
from math import comb, prod, ceil

from core import constants, kelly

STARS = (2, 3, 4)


def star_prob(r: int) -> float:
    """指定 r 碼全被開出的機率 = C(39-r, 5-r)/C(39,5)。"""
    return comb(constants.NUM_MAX - r, constants.PICK - r) / constants.TOTAL_COMB


# 各星公平賠率(期望打平所需賠率)
BREAKEVEN_ODDS = {r: 1.0 / star_prob(r) for r in STARS}


# ── 注數 ─────────────────────────────────────────────────
def lianpeng_notes(n: int, r: int) -> int:
    """連碰 r 星注數 = C(n, r)。"""
    return comb(n, r) if n >= r else 0


def lizhu_notes(sizes: list[int], r: int) -> int:
    """立柱 r 星注數 = 各柱大小的基本對稱多項式 e_r(任選 r 個不同柱,各取一碼相乘加總)。"""
    sizes = [s for s in sizes if s > 0]
    if len(sizes) < r:
        return 0
    return sum(prod(c) for c in combinations(sizes, r))


# ── 期望 / 凱莉 ───────────────────────────────────────────
def ev_rate(r: int, odds: float) -> float:
    """r 星每注期望報酬率 = P_r × 賠率 − 1。"""
    return star_prob(r) * odds - 1.0


def kelly_fraction(r: int, odds: float) -> float:
    """r 星單注凱莉建議下注比例(負期望回 0)。"""
    b = odds - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, kelly.kelly_binary(star_prob(r), b))


# ── 投注計畫(注數 / 成本 / 期望)────────────────────────
@dataclass
class Plan:
    play: str                 # 'lianpeng' | 'lizhu'
    stars: tuple              # 下注的星別,如 (2, 3)
    notes: dict               # {r: 注數}
    price: float              # 每注金額
    odds: dict                # {r: 賠率}
    total_notes: int = 0
    cost: float = 0.0         # 總成本 = 總注數 × 每注金額
    exp_return: float = 0.0   # 期望回收金額
    ev_rate: float = 0.0      # 期望報酬率


def _finalize_plan(p: Plan) -> Plan:
    p.total_notes = sum(p.notes.values())
    p.cost = p.total_notes * p.price
    p.exp_return = sum(
        p.notes[r] * star_prob(r) * p.odds.get(r, 0.0) * p.price for r in p.stars
    )
    p.ev_rate = (p.exp_return / p.cost - 1.0) if p.cost else 0.0
    return p


def plan_lianpeng(n: int, stars, price: float, odds: dict) -> Plan:
    """連碰投注計畫。"""
    stars = tuple(sorted(stars))
    notes = {r: lianpeng_notes(n, r) for r in stars}
    return _finalize_plan(Plan(play="lianpeng", stars=stars, notes=notes,
                               price=float(price), odds=dict(odds)))


def plan_lizhu(sizes, stars, price: float, odds: dict) -> Plan:
    """立柱投注計畫。"""
    stars = tuple(sorted(stars))
    notes = {r: lizhu_notes(sizes, r) for r in stars}
    return _finalize_plan(Plan(play="lizhu", stars=stars, notes=notes,
                               price=float(price), odds=dict(odds)))


# ── 單局淨損益 ───────────────────────────────────────────
def lianpeng_win_notes(hits: int, stars) -> dict:
    """連碰命中 hits 碼時,各星中獎注數 = C(hits, r)。"""
    return {r: (comb(hits, r) if hits >= r else 0) for r in stars}


def lizhu_win_notes(col_hits: list[int], stars) -> dict:
    """立柱各柱命中 col_hits 碼時,各星中獎注數 = e_r(col_hits)。"""
    return {r: lizhu_notes(col_hits, r) for r in stars}


def round_net(plan: Plan, win_notes: dict, mult: int = 1) -> float:
    """一局淨損益 = 中獎注回收 − 成本(皆 × 倍數)。

    回收 = Σ_r 中獎注數 × 賠率_r × 每注金額;成本 = 計畫總成本。
    """
    payout = sum(win_notes.get(r, 0) * plan.odds.get(r, 0.0) for r in plan.stars) * plan.price
    return (payout - plan.cost) * mult


# ── 命中碼數分布(連碰用,超幾何)────────────────────────
def hit_distribution(n: int) -> dict[int, float]:
    """連碰選 N 碼,當期命中 m 碼的機率(超幾何),m = 0..min(N,5)。"""
    return {
        m: comb(n, m) * comb(constants.NUM_MAX - n, constants.PICK - m) / constants.TOTAL_COMB
        for m in range(0, min(n, constants.PICK) + 1)
    }


# ── 互動回本:由累積損益算下一局建議倍數 ─────────────────
def per_mult_net_if_hits(plan: Plan, target_hits: int) -> float:
    """連碰:若命中 target_hits 碼,每『1 倍』的淨利(回收 − 成本)。"""
    win = lianpeng_win_notes(target_hits, plan.stars)
    return round_net(plan, win, mult=1)


def next_mult_for_recovery(cumulative_net: float, plan: Plan,
                           target_hits: int, base_mult: int = 1) -> dict:
    """依目前累積損益,算下一局該下幾倍,使『命中 target_hits 碼』即可回本。

    回傳 next_mult / per_mult_net / recovered / can_recover / next_cost。
    """
    per = per_mult_net_if_hits(plan, target_hits)
    recovered = cumulative_net >= 0
    if recovered:
        next_mult = base_mult
    elif per <= 0:
        next_mult = float("inf")  # 命中目標碼數也無法回本(賠率太低)
    else:
        next_mult = max(base_mult, ceil(-cumulative_net / per))
    next_cost = plan.cost * next_mult if next_mult != float("inf") else float("inf")
    return {
        "next_mult": next_mult,
        "per_mult_net": per,
        "recovered": recovered,
        "can_recover": per > 0,
        "next_cost": next_cost,
    }


# ── 進程模擬(連敗加倍數、有獲利就重置)蒙地卡羅 ─────────
@dataclass
class SimResult:
    per_round_ev: float
    p_profit_round: float          # 單局淨利 > 0 機率
    ruin_rate: float
    avg_final_capital: float
    final_capital: float
    curve: list[float] = field(default_factory=list)


def progression_sim(plan: Plan, n: int, progression=(1, 2, 3, 5, 8),
                    capital: float = 500_000.0, rounds: int = 200,
                    trials: int = 500, seed: int = 539) -> SimResult:
    """連碰『連敗加倍數、單局獲利就重置』蒙地卡羅。

    每局下 progression[step] 倍;依超幾何抽命中碼數 m;算淨利;
    淨利 > 0 則 step 歸 0(重置),否則 step+1。回傳破產率等。
    """
    prog = list(progression)
    nlen = len(prog)
    dist = hit_distribution(n)
    cum = []
    acc = 0.0
    for m in sorted(dist):
        acc += dist[m]
        cum.append((m, acc))

    # 單局期望報酬率與獲利機率(與倍數無關)
    per_round_ev = plan.ev_rate
    p_profit = sum(dist[m] for m in dist
                   if round_net(plan, lianpeng_win_notes(m, plan.stars), 1) > 0)

    ruined = 0
    finals = []
    sample = None
    for t in range(trials):
        r = random.Random(seed + t)
        cap = capital
        curve = [cap]
        step = 0
        bust = False
        for _ in range(rounds):
            mult = prog[min(step, nlen - 1)]
            cost = plan.cost * mult
            if cap < cost:
                bust = True
                break
            u = r.random()
            m = cum[-1][0]
            for mm, cp in cum:
                if u <= cp:
                    m = mm
                    break
            net = round_net(plan, lianpeng_win_notes(m, plan.stars), mult)
            cap += net
            step = 0 if net > 0 else step + 1
            curve.append(cap)
        if bust:
            ruined += 1
        finals.append(cap)
        if t == 0:
            sample = (cap, curve)
    final_cap, curve = sample
    return SimResult(
        per_round_ev=per_round_ev,
        p_profit_round=p_profit,
        ruin_rate=ruined / trials,
        avg_final_capital=sum(finals) / len(finals),
        final_capital=final_cap,
        curve=curve,
    )
