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
from core.stats import ALL_NUMS, SIZE_SPLIT, all_nums, frequency, missing

STRATEGIES = ["random", "hot", "cold", "frequency", "balanced"]

# 策略中文標籤(供選單與報表顯示;內部仍以英文 key 運作)
STRATEGY_LABELS = {
    "random": "隨機(最誠實的基準)",
    "hot": "熱號權重",
    "cold": "冷號權重(賭徒謬誤)",
    "frequency": "歷史頻率權重",
    "balanced": "均衡(奇偶/和值落常見區間)",
}


def label(strategy: str) -> str:
    """取得策略的中文標籤;未知策略回傳原字串。"""
    return STRATEGY_LABELS.get(strategy, strategy)


def draw_probabilities(df, strategy: str = "random", window: int = 30,
                       num_max: int = NUM_MAX, pick: int = PICK) -> dict[int, float]:
    """各號碼「被開出(落在當期開獎號內)」的『預估』機率,依策略加權。

    回傳 {號碼: 機率},全部加總為 pick(即每期開 pick 個號的期望)。
    - random / balanced:均勻,每號 pick/num_max(這也是『真實』機率)。
    - hot / cold / frequency:依歷史加權的啟發式估計。

    重要:每期開獎獨立隨機,真實開機率永遠是均勻的 pick/num_max;
    非 random 的『預估開機率』只是把歷史傾向視覺化,**沒有預測下一期的能力**。
    """
    nums = all_nums(num_max)
    if strategy in ("random", "balanced"):
        weights = {n: 1.0 for n in nums}
    else:
        weights = _weights(df, strategy, window, num_max)
    total = sum(weights.values()) or 1.0
    return {n: pick * weights[n] / total for n in nums}


def _weighted_sample(weights: dict[int, float], rng: random.Random,
                     pick_n: int = PICK) -> list[int]:
    """依權重不放回抽 pick_n 個號碼。"""
    nums = list(weights.keys())
    w = [max(weights[n], 1e-9) for n in nums]
    chosen: list[int] = []
    pool = list(zip(nums, w))
    for _ in range(pick_n):
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


def _weights(df: pd.DataFrame, strategy: str, window: int = 30,
             num_max: int = NUM_MAX) -> dict[int, float]:
    nums = all_nums(num_max)
    if strategy == "random":
        return {n: 1.0 for n in nums}
    if strategy == "frequency":
        freq = frequency(df, num_max)
        return {n: freq[n] + 1.0 for n in nums}  # +1 平滑,避免 0 權重
    if strategy == "hot":
        freq = frequency(df.tail(window), num_max)
        return {n: freq[n] + 0.5 for n in nums}
    if strategy == "cold":
        miss = missing(df, num_max)
        return {n: miss[n]["current"] + 1.0 for n in nums}
    raise ValueError(f"未知策略:{strategy}")


def _common_sum_range(df: pd.DataFrame, pick_n: int = PICK) -> tuple[int, int]:
    """歷史和值的中央區間(約 10%~90% 分位),供 balanced 過濾。

    號碼欄依實際資料推斷(六合彩有 n1~n6),不寫死 5 欄。
    """
    from core.loader import detect_num_cols

    cols = detect_num_cols(df) or [f"n{i}" for i in range(1, pick_n + 1)]
    sums = [sum(r) for r in df[cols].values.tolist()]
    if not sums:
        return (60, 140)
    s = sorted(sums)
    lo = s[int(len(s) * 0.10)]
    hi = s[int(len(s) * 0.90)]
    return lo, hi


def pick(df: pd.DataFrame, strategy: str = "random", sets: int = 5,
         seed: int | None = None, num_max: int = NUM_MAX,
         pick_n: int = PICK) -> list[list[int]]:
    """產生 sets 組參考號碼,每組 pick_n 個不重複號(已排序)。

    seed 固定時結果可重現。balanced 會重抽直到符合條件(有上限避免無窮迴圈)。

    num_max / pick_n 預設是今彩539 的 39 選 5;六合彩要傳 49 選 6,
    否則會抽出 5 個 1~39 的號碼(規格不符),cold 策略更會直接 KeyError。
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"未知策略:{strategy};可用 {STRATEGIES}")
    rng = random.Random(seed)

    if strategy == "balanced":
        lo, hi = _common_sum_range(df, pick_n)
        # 奇數/大數各佔約 4~6 成(對 39 選 5 就是原本的 2~3 個)
        lo_n, hi_n = round(pick_n * 0.4), round(pick_n * 0.6)
        split = round(num_max / 2) if num_max != NUM_MAX else SIZE_SPLIT
        results = []
        for _ in range(sets):
            for _attempt in range(200):
                cand = sorted(rng.sample(range(NUM_MIN, num_max + 1), pick_n))
                odd = sum(1 for n in cand if n % 2 == 1)
                big = sum(1 for n in cand if n >= split)
                if (lo_n <= odd <= hi_n and lo_n <= big <= hi_n
                        and lo <= sum(cand) <= hi):
                    results.append(cand)
                    break
            else:
                results.append(sorted(rng.sample(range(NUM_MIN, num_max + 1), pick_n)))
        return results

    weights = _weights(df, strategy, num_max=num_max)
    return [_weighted_sample(weights, rng, pick_n) for _ in range(sets)]
