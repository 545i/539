"""今彩539 統計分析:頻率、冷熱號、遺漏值、間隔/連號、奇偶大小和值、卡方、共現矩陣。

所有函式皆為「描述歷史」的統計,不具任何預測未來的能力。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pandas as pd

from core.constants import NUM_MAX, NUM_MIN, PICK
from core.loader import draws_as_lists

ALL_NUMS = list(range(NUM_MIN, NUM_MAX + 1))
SIZE_SPLIT = 20  # 1~19 為「小」,20~39 為「大」


# ── A. 頻率統計 ──────────────────────────────────────────
def frequency(df: pd.DataFrame) -> dict[int, int]:
    """每個號碼 1~39 的歷史出現次數。"""
    counter = Counter()
    for draw in draws_as_lists(df):
        counter.update(draw)
    return {n: counter.get(n, 0) for n in ALL_NUMS}


def frequency_ranked(df: pd.DataFrame) -> list[tuple[int, int]]:
    """依出現次數由高到低排序的 (號碼, 次數)。"""
    freq = frequency(df)
    return sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))


# ── B. 冷熱號 ────────────────────────────────────────────
def hot_cold(df: pd.DataFrame, window: int = 30, top: int = 5):
    """近 window 期的熱號(最常出)與冷號(最少出)。

    回傳 (hot, cold),各為 [(號碼, 次數), ...]。
    """
    recent = df.tail(window)
    freq = frequency(recent)
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    hot = ranked[:top]
    cold = sorted(freq.items(), key=lambda kv: (kv[1], kv[0]))[:top]
    return hot, cold


# ── C. 遺漏值 ────────────────────────────────────────────
def missing(df: pd.DataFrame) -> dict[int, dict]:
    """每個號碼的目前遺漏期數與歷史最大遺漏。

    current:距今幾期沒開(本期仍未開則持續累加)。
    max_gap:歷史上最長連續未開期數。
    """
    draws = draws_as_lists(df)
    total = len(draws)
    last_seen = {n: None for n in ALL_NUMS}
    max_gap = {n: 0 for n in ALL_NUMS}
    prev = {n: -1 for n in ALL_NUMS}  # 上次出現的期序

    for i, draw in enumerate(draws):
        for n in draw:
            gap = i - prev[n] - 1 if prev[n] >= 0 else i
            if gap > max_gap[n]:
                max_gap[n] = gap
            prev[n] = i
            last_seen[n] = i

    result = {}
    for n in ALL_NUMS:
        current = total - 1 - last_seen[n] if last_seen[n] is not None else total
        # 結尾未出現的尾段也要納入 max_gap 比較
        result[n] = {"current": current, "max_gap": max(max_gap[n], current)}
    return result


# ── D. 間隔 / 連號 ───────────────────────────────────────
def gaps_consecutive(df: pd.DataFrame):
    """每期 5 號相鄰間隔分布,以及含連號(相鄰差=1)的期數比例。"""
    gap_counter = Counter()
    consecutive_draws = 0
    draws = draws_as_lists(df)
    for draw in draws:
        s = sorted(draw)
        has_consec = False
        for a, b in zip(s, s[1:]):
            gap = b - a
            gap_counter[gap] += 1
            if gap == 1:
                has_consec = True
        if has_consec:
            consecutive_draws += 1
    ratio = consecutive_draws / len(draws) if draws else 0.0
    return dict(sorted(gap_counter.items())), ratio


# ── E. 奇偶 / 大小 / 和值 ────────────────────────────────
def parity_size_sum(df: pd.DataFrame):
    """回傳 (odd_count_dist, big_count_dist, sums)。

    odd_count_dist:每期奇數個數 (0~5) 的次數分布。
    big_count_dist:每期大數(>=20)個數 (0~5) 的次數分布。
    sums:每期 5 號總和的清單(供直方圖)。
    """
    odd_dist = Counter()
    big_dist = Counter()
    sums = []
    for draw in draws_as_lists(df):
        odd = sum(1 for n in draw if n % 2 == 1)
        big = sum(1 for n in draw if n >= SIZE_SPLIT)
        odd_dist[odd] += 1
        big_dist[big] += 1
        sums.append(sum(draw))
    odd_full = {k: odd_dist.get(k, 0) for k in range(PICK + 1)}
    big_full = {k: big_dist.get(k, 0) for k in range(PICK + 1)}
    return odd_full, big_full, sums


# ── E2. 星數統計(十位分組,俗稱「4興」)──────────────────
TENS_BANDS = ["01~09", "10~19", "20~29", "30~39"]


def _tens_index(n: int) -> int:
    """號碼所屬的十位分組索引:1~9→0、10~19→1、20~29→2、30~39→3。"""
    return min(n // 10, len(TENS_BANDS) - 1)


def tens_band_stats(df: pd.DataFrame):
    """星數統計(俗稱「4興」):把 1~39 依十位分成四組,看每期 5 顆的星數。

    星數 = 這 5 顆落在「幾個不同的十位區段」。同一段內重複(如 10、11 都在
    10~19)只算 1 星,所以星數介於 1~4 星。

    回傳 (star_dist, band_totals, pattern_dist):
    - star_dist:{星數(1~4): 出現期數},每期落在幾個不同區段的分布。
    - band_totals:{組別標籤: 該組號碼歷史出現總次數}(共 期數×5 顆)。
    - pattern_dist:[(牌型, 次數, 比例), ...] 依次數由高到低。
      牌型 = 每期 5 號落在四組各幾顆,如 "1-2-1-1"(01~09 一顆、10~19 兩顆…)。
    """
    star_counter = Counter()
    band_totals = Counter()
    pattern_counter = Counter()
    draws = draws_as_lists(df)
    for draw in draws:
        per_draw = [0] * len(TENS_BANDS)
        for n in draw:
            b = _tens_index(n)
            per_draw[b] += 1
            band_totals[b] += 1
        stars = sum(1 for c in per_draw if c > 0)  # 有號碼的不同區段數
        star_counter[stars] += 1
        pattern_counter[tuple(per_draw)] += 1

    total = len(draws)
    star_out = {s: star_counter.get(s, 0) for s in range(1, len(TENS_BANDS) + 1)}
    band_out = {TENS_BANDS[i]: band_totals.get(i, 0) for i in range(len(TENS_BANDS))}
    patterns = sorted(pattern_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    pattern_out = [
        ("-".join(str(x) for x in pat), cnt, cnt / total if total else 0.0)
        for pat, cnt in patterns
    ]
    return star_out, band_out, pattern_out


# ── F. 卡方適合度檢定 ────────────────────────────────────
@dataclass
class ChiSquareResult:
    statistic: float
    p_value: float
    dof: int
    expected_per_num: float
    enough_data: bool
    conclusion: str


def chi_square(df: pd.DataFrame) -> ChiSquareResult:
    """檢驗 39 個號碼出現次數是否符合均勻分布。

    H0:每個號碼出現機率相等。自由度 = 39 - 1 = 38。
    期望次數 E = 期數 * 5 / 39;期數 < 39 時 E < 5,卡方近似不可靠。
    結論一律不暗示可預測:通過只代表「不違反均勻」=更證明無法預測。
    """
    from scipy.stats import chisquare

    periods = len(df)
    freq = frequency(df)
    observed = [freq[n] for n in ALL_NUMS]
    expected_per = periods * PICK / NUM_MAX
    expected = [expected_per] * NUM_MAX

    stat, p = chisquare(f_obs=observed, f_exp=expected)
    dof = NUM_MAX - 1
    enough = expected_per >= 5  # 慣例:每格期望 >= 5

    if not enough:
        conclusion = (
            f"資料僅 {periods} 期,每格期望次數 {expected_per:.1f} < 5,"
            "卡方近似不可靠,結論僅供參考。"
        )
    elif p < 0.05:
        conclusion = (
            f"p={p:.4f} < 0.05:在統計上偏離均勻(可能搖獎不公或樣本偶然)。"
            "注意:這不代表號碼可預測。"
        )
    else:
        conclusion = (
            f"p={p:.4f} ≥ 0.05:不違反均勻分布,號碼表現隨機。"
            "這正說明任何冷熱號策略都無法預測未來。"
        )
    return ChiSquareResult(stat, p, dof, expected_per, enough, conclusion)


# ── G. 共現矩陣 ──────────────────────────────────────────
def cooccurrence(df: pd.DataFrame) -> dict[tuple[int, int], int]:
    """每對號碼一起出現的次數(無序 pair,i<j)。"""
    co = Counter()
    for draw in draws_as_lists(df):
        s = sorted(draw)
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                co[(s[i], s[j])] += 1
    return dict(co)


def top_pairs(df: pd.DataFrame, top: int = 10) -> list[tuple[tuple[int, int], int]]:
    """最常一起出現的號碼配對。"""
    co = cooccurrence(df)
    return sorted(co.items(), key=lambda kv: (-kv[1], kv[0]))[:top]
