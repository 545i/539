"""包牌(車數/資金)試算、歷史牌型分布、加碼回本(Martingale)破產示範。

三個主題都建立在「誠實」前提上:
  - 包牌:純組合數學,算車數與資金;但每注期望報酬率不變(包再多也是負期望)。
  - 牌型:只描述歷史分布,**不預測下一局**(每期獨立隨機)。
  - 加碼回本:用模擬證明在負期望賭局裡「輸了加碼把本拿回來」會加速破產,而非翻本。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from math import comb

from core import constants


# ── 一、包牌車數 / 資金 ───────────────────────────────────
@dataclass
class WheelPlan:
    picked: int          # 圈選的號碼個數 N
    cars: int            # 全包車數 = C(N, 5)
    unit: int            # 下注基底(每幾車一單位)
    units: int           # 需要幾個基底單位(無條件進位)
    cost: float          # 總資金 = 車數 × 票價
    currency: str
    jackpot_prob: float  # 命中頭獎(5 個開出號全在圈選內)的機率
    expected_return: float  # 期望報酬率(與單注相同,包牌不會改變)


def wheel_plan(picked: int, game, unit: int = 3) -> WheelPlan:
    """計算圈選 picked 個號碼「全包」的車數與資金。

    全包 = 買下這 N 個號碼的所有 C(N,5) 種 5 碼組合。
    只有當開出的 5 個號碼全部落在你圈選的 N 個之內,才中頭獎,
    機率 = C(N,5) / C(39,5);資金 = 車數 × 票價。
    unit:以「每 unit 車」為一個下注基底(預設 3 車)。
    """
    if picked < constants.PICK:
        raise ValueError(f"至少要圈選 {constants.PICK} 個號碼")
    if picked > constants.NUM_MAX:
        raise ValueError(f"最多只能圈選 {constants.NUM_MAX} 個號碼")

    cars = comb(picked, constants.PICK)
    cost = cars * game.ticket_price
    units = -(-cars // unit)  # 無條件進位
    jackpot_prob = cars / constants.TOTAL_COMB
    return WheelPlan(
        picked=picked,
        cars=cars,
        unit=unit,
        units=units,
        cost=cost,
        currency=game.currency,
        jackpot_prob=jackpot_prob,
        expected_return=game.expected_return(),
    )


# ── 二、歷史牌型分布(描述,非預測)──────────────────────
def pattern_distribution(df, top: int = 10) -> list[tuple[str, int, float]]:
    """統計歷史每期「牌型」出現次數與比例。

    牌型定義為 (奇數個數, 大數[>=20]個數, 和值區間)。
    回傳 [(牌型描述, 次數, 比例), ...],由高到低,取前 top 名。
    這是描述過去的頻率,**不代表下一期會出現**(每期獨立隨機)。
    """
    from collections import Counter

    from core.loader import draws_as_lists

    counter: Counter = Counter()
    draws = draws_as_lists(df)
    for draw in draws:
        odd = sum(1 for n in draw if n % 2 == 1)
        big = sum(1 for n in draw if n >= 20)
        s = sum(draw)
        sum_band = f"{(s // 20) * 20}-{(s // 20) * 20 + 19}"  # 以 20 為一段
        key = f"奇{odd}偶{constants.PICK - odd} / 大{big}小{constants.PICK - big} / 和{sum_band}"
        counter[key] += 1

    total = len(draws) or 1
    ranked = counter.most_common(top)
    return [(k, c, c / total) for k, c in ranked]


# ── 三、加碼回本(Martingale)破產示範 ────────────────────
@dataclass
class MartingaleResult:
    rounds_survived: int      # 撐了幾局才破產(或跑完)
    ruined: bool              # 是否破產
    peak_bet_cars: int        # 過程中單局最多下到幾車
    final_capital: float
    capital_curve: list[float]  # 每局後的資金
    ruin_rate: float          # 多次模擬的破產比例


def _one_martingale_run(game, base_cars, start_capital, max_rounds, rng):
    """單次「輸了加碼」模擬:每輸一局,下一局車數翻倍以圖回本。"""
    p_any_win = sum(game.prob(k) for k in (3, 4, 5))  # 約略「有回收」機率(中3碼以上)
    # 注:中2碼在539為打平、在Fantasy5為贈彩券,這裡保守以「中3碼以上才算贏」示範。
    capital = start_capital
    cars = base_cars
    peak = base_cars
    curve = [capital]
    for r in range(1, max_rounds + 1):
        cost = cars * game.ticket_price
        if capital < cost:
            return r - 1, True, peak, capital, curve  # 沒錢下注 = 破產
        capital -= cost
        win = rng.random() < p_any_win
        if win:
            # 假設「贏」就拿回一個保守回收(以中3碼獎金 × 車數的一部分估),重置車數
            capital += game.prize.get(3, 0) * cars
            cars = base_cars
        else:
            cars *= 2  # 輸了加碼(Martingale 核心)
            peak = max(peak, cars)
        curve.append(capital)
        if capital <= 0:
            return r, True, peak, capital, curve
    return max_rounds, False, peak, capital, curve


def martingale_demo(game, base_cars: int = 3, rounds: int = 50,
                    start_capital: float = 100000.0, trials: int = 300,
                    seed: int = 539) -> MartingaleResult:
    """模擬「每 base_cars 車為基底、輸了加碼回本」的下場。

    跑 trials 次蒙地卡羅,回傳代表性的一條資金曲線與整體破產率。
    結論一律是:負期望 + 加碼 → 破產率極高,資金加速歸零。
    """
    rng = random.Random(seed)
    ruined = 0
    sample = None
    for t in range(trials):
        rs, is_ruined, peak, final_cap, curve = _one_martingale_run(
            game, base_cars, start_capital, rounds, random.Random(seed + t)
        )
        if is_ruined:
            ruined += 1
        if t == 0:
            sample = (rs, is_ruined, peak, final_cap, curve)
    rs, is_ruined, peak, final_cap, curve = sample
    return MartingaleResult(
        rounds_survived=rs,
        ruined=is_ruined,
        peak_bet_cars=peak,
        final_capital=final_cap,
        capital_curve=curve,
        ruin_rate=ruined / trials,
    )
