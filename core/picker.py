"""參考選號:5 種策略。所有策略期望中獎率完全相同,差異只是運氣。

策略:
- random    : 01~39 等機率隨機(數學上最誠實的基準)
- hot       : 近期常開的號碼權重高
- cold      : 很久沒開的號碼權重高(賭徒謬誤,但很多人愛用)
- frequency : 依歷史總頻率加權
- balanced  : 隨機後過濾,使奇偶比與和值落在歷史常見區間
"""
from __future__ import annotations

import random

import pandas as pd

from core.constants import NUM_MAX, NUM_MIN, PICK
from core.stats import ALL_NUMS, SIZE_SPLIT, frequency, missing

STRATEGIES = ["random", "hot", "cold", "frequency", "balanced"]


def _weighted_sample(weights: dict[int, float], rng: random.Random) -> list[int]:
    """依權重不放回抽 PICK 個號碼。"""
    nums = list(weights.keys())
    w = [max(weights[n], 1e-9) for n in nums]
    chosen: list[int] = []
    pool = list(zip(nums, w))
    for _ in range(PICK):
        total = sum(x[1] for x in pool)
        r = rng.uniform(0, total)
        acc = 0.0
        for i, (n, wi) in enumerate(pool):
            acc += wi
            if r <= acc:
                chosen.append(n)
                pool.pop(i)
                break
    return sorted(chosen)


def _weights(df: pd.DataFrame, strategy: str, window: int = 30) -> dict[int, float]:
    if strategy == "random":
        return {n: 1.0 for n in ALL_NUMS}
    if strategy == "frequency":
        freq = frequency(df)
        return {n: freq[n] + 1.0 for n in ALL_NUMS}  # +1 平滑,避免 0 權重
    if strategy == "hot":
        freq = frequency(df.tail(window))
        return {n: freq[n] + 0.5 for n in ALL_NUMS}
    if strategy == "cold":
        miss = missing(df)
        return {n: miss[n]["current"] + 1.0 for n in ALL_NUMS}
    raise ValueError(f"未知策略:{strategy}")


def _common_sum_range(df: pd.DataFrame) -> tuple[int, int]:
    """歷史和值的中央區間(約 10%~90% 分位),供 balanced 過濾。"""
    sums = [sum(r) for r in df[[f"n{i}" for i in range(1, PICK + 1)]].values.tolist()]
    if not sums:
        return (60, 140)
    s = sorted(sums)
    lo = s[int(len(s) * 0.10)]
    hi = s[int(len(s) * 0.90)]
    return lo, hi


def pick(df: pd.DataFrame, strategy: str = "random", sets: int = 5,
         seed: int | None = None) -> list[list[int]]:
    """產生 sets 組參考號碼,每組 PICK 個不重複號(已排序)。

    seed 固定時結果可重現。balanced 會重抽直到符合條件(有上限避免無窮迴圈)。
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"未知策略:{strategy};可用 {STRATEGIES}")
    rng = random.Random(seed)

    if strategy == "balanced":
        lo, hi = _common_sum_range(df)
        results = []
        for _ in range(sets):
            for _attempt in range(200):
                cand = sorted(rng.sample(range(NUM_MIN, NUM_MAX + 1), PICK))
                odd = sum(1 for n in cand if n % 2 == 1)
                big = sum(1 for n in cand if n >= SIZE_SPLIT)
                if 2 <= odd <= 3 and 2 <= big <= 3 and lo <= sum(cand) <= hi:
                    results.append(cand)
                    break
            else:
                results.append(sorted(rng.sample(range(NUM_MIN, NUM_MAX + 1), PICK)))
        return results

    weights = _weights(df, strategy)
    return [_weighted_sample(weights, rng) for _ in range(sets)]
