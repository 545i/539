"""開獎統計分析:頻率、冷熱號、遺漏值、間隔/連號、奇偶大小和值、卡方、共現矩陣。

所有函式皆為「描述歷史」的統計,不具任何預測未來的能力。

num_max 預設為今彩539 / 天天樂的 39;六合彩(49 選 6)由呼叫端傳 num_max=49。
每期開幾顆(pick)一律從資料的號碼欄位自動推斷,不必傳。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pandas as pd

from core.constants import NUM_MAX, NUM_MIN, PICK
from core.loader import draws_as_lists

ALL_NUMS = list(range(NUM_MIN, NUM_MAX + 1))
SIZE_SPLIT = 20  # 今彩539:1~19 為「小」,20~39 為「大」


def all_nums(num_max: int = NUM_MAX) -> list[int]:
    """該玩法的完整號碼清單。"""
    return list(range(NUM_MIN, num_max + 1))


def size_split(num_max: int = NUM_MAX) -> int:
    """「大 / 小」的分界號碼(>= 此值為大)。39→20、49→25。"""
    return num_max // 2 + 1


def _pick_of(df: pd.DataFrame, draws: list[list[int]]) -> int:
    """從資料推斷每期開幾顆;無資料時回落到今彩539 的 5。"""
    return len(draws[0]) if draws else PICK


# ── A. 頻率統計 ──────────────────────────────────────────
def frequency(df: pd.DataFrame, num_max: int = NUM_MAX) -> dict[int, int]:
    """每個號碼 1~num_max 的歷史出現次數。"""
    counter = Counter()
    for draw in draws_as_lists(df):
        counter.update(draw)
    return {n: counter.get(n, 0) for n in all_nums(num_max)}


def frequency_ranked(df: pd.DataFrame, num_max: int = NUM_MAX) -> list[tuple[int, int]]:
    """依出現次數由高到低排序的 (號碼, 次數)。"""
    freq = frequency(df, num_max)
    return sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))


# ── B. 冷熱號 ────────────────────────────────────────────
def hot_cold(df: pd.DataFrame, window: int = 30, top: int = 5,
             num_max: int = NUM_MAX):
    """近 window 期的熱號(最常出)與冷號(最少出)。

    回傳 (hot, cold),各為 [(號碼, 次數), ...]。
    """
    recent = df.tail(window)
    freq = frequency(recent, num_max)
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    hot = ranked[:top]
    cold = sorted(freq.items(), key=lambda kv: (kv[1], kv[0]))[:top]
    return hot, cold


# ── C. 遺漏值 ────────────────────────────────────────────
def missing(df: pd.DataFrame, num_max: int = NUM_MAX) -> dict[int, dict]:
    """每個號碼的目前遺漏期數與歷史最大遺漏。

    current:距今幾期沒開(本期仍未開則持續累加)。
    max_gap:歷史上最長連續未開期數。
    """
    draws = draws_as_lists(df)
    total = len(draws)
    nums = all_nums(num_max)
    last_seen = {n: None for n in nums}
    max_gap = {n: 0 for n in nums}
    prev = {n: -1 for n in nums}  # 上次出現的期序

    for i, draw in enumerate(draws):
        for n in draw:
            gap = i - prev[n] - 1 if prev[n] >= 0 else i
            if gap > max_gap[n]:
                max_gap[n] = gap
            prev[n] = i
            last_seen[n] = i

    result = {}
    for n in nums:
        current = total - 1 - last_seen[n] if last_seen[n] is not None else total
        # 結尾未出現的尾段也要納入 max_gap 比較
        result[n] = {"current": current, "max_gap": max(max_gap[n], current)}
    return result


# ── D. 間隔 / 連號 ───────────────────────────────────────
def gaps_consecutive(df: pd.DataFrame):
    """每期開獎號相鄰間隔分布,以及含連號(相鄰差=1)的期數比例。"""
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
def parity_size_sum(df: pd.DataFrame, num_max: int = NUM_MAX):
    """回傳 (odd_count_dist, big_count_dist, sums)。

    odd_count_dist:每期奇數個數 (0~pick) 的次數分布。
    big_count_dist:每期大數(>= size_split)個數 (0~pick) 的次數分布。
    sums:每期開獎號總和的清單(供直方圖)。
    """
    split = size_split(num_max)
    odd_dist = Counter()
    big_dist = Counter()
    sums = []
    draws = draws_as_lists(df)
    for draw in draws:
        odd = sum(1 for n in draw if n % 2 == 1)
        big = sum(1 for n in draw if n >= split)
        odd_dist[odd] += 1
        big_dist[big] += 1
        sums.append(sum(draw))
    pick = _pick_of(df, draws)
    odd_full = {k: odd_dist.get(k, 0) for k in range(pick + 1)}
    big_full = {k: big_dist.get(k, 0) for k in range(pick + 1)}
    return odd_full, big_full, sums


# ── E2. 星數統計(十位分組,今彩539 俗稱「4興」)────────────
TENS_BANDS = ["01~09", "10~19", "20~29", "30~39"]


def tens_bands(num_max: int = NUM_MAX) -> list[str]:
    """依十位切出的區段標籤:39→4 段(01~09…30~39),49→5 段(…40~49)。"""
    n_bands = num_max // 10 + 1
    bands = ["01~09"]
    for i in range(1, n_bands):
        hi = min(i * 10 + 9, num_max)
        bands.append(f"{i * 10}~{hi}")
    return bands


def _tens_index(n: int, n_bands: int = len(TENS_BANDS)) -> int:
    """號碼所屬的十位分組索引:1~9→0、10~19→1、20~29→2、…(超出末段則歸末段)。"""
    return min(n // 10, n_bands - 1)


def tens_band_stats(df: pd.DataFrame, num_max: int = NUM_MAX):
    """星數統計:把 1~num_max 依十位分組,看每期開出的號碼落在幾個不同區段。

    星數 = 該期號碼落在「幾個不同的十位區段」。同一段內重複(如 10、11 都在
    10~19)只算 1 星。今彩539 分 4 段(俗稱「4興」),六合彩分 5 段。

    回傳 (star_dist, band_totals, pattern_dist):
    - star_dist:{星數: 出現期數},每期落在幾個不同區段的分布。
    - band_totals:{組別標籤: 該組號碼歷史出現總次數}。
    - pattern_dist:[(牌型, 次數, 比例), ...] 依次數由高到低。
      牌型 = 每期號碼落在各組各幾顆,如 "1-2-1-1"(01~09 一顆、10~19 兩顆…)。
    """
    bands = tens_bands(num_max)
    star_counter = Counter()
    band_totals = Counter()
    pattern_counter = Counter()
    draws = draws_as_lists(df)
    for draw in draws:
        per_draw = [0] * len(bands)
        for n in draw:
            b = _tens_index(n, len(bands))
            per_draw[b] += 1
            band_totals[b] += 1
        stars = sum(1 for c in per_draw if c > 0)  # 有號碼的不同區段數
        star_counter[stars] += 1
        pattern_counter[tuple(per_draw)] += 1

    total = len(draws)
    star_out = {s: star_counter.get(s, 0) for s in range(1, len(bands) + 1)}
    band_out = {bands[i]: band_totals.get(i, 0) for i in range(len(bands))}
    patterns = sorted(pattern_counter.items(), key=lambda kv: (-kv[1], kv[0]))
    pattern_out = [
        ("-".join(str(x) for x in pat), cnt, cnt / total if total else 0.0)
        for pat, cnt in patterns
    ]
    return star_out, band_out, pattern_out


# ── E3. 區間組合斷檔提醒(任意兩十位區段連續幾期都沒開)────────
def tens_pair_alerts(df: pd.DataFrame, threshold: int = 3,
                     num_max: int = NUM_MAX) -> list[dict]:
    """任意兩個十位區段的配對,連續幾期都沒開出任何號碼。

    區段沿用 tens_bands / _tens_index:01~09、10~19、20~29、30~39
    (顯示標籤用民間慣用的開頭 01 / 11 / 21 / 31)。

    對每組配對 (A, B),從最新一期往回數,streak = 連續幾期裡「A、B 兩區段
    都沒開出任何號碼」;只要某期 A 或 B 有號,streak 即中斷歸零。
    streak >= threshold(預設 3)時 alert=True,之後每新增一期 +1。

    回傳依 streak 由大到小排序的清單,每組:
      {"bands": (i, j), "labels": (str, str), "range": (str, str),
       "streak": int, "alert": bool}
    """
    bands = tens_bands(num_max)
    n_bands = len(bands)
    draws = draws_as_lists(df)

    # 每一期出現了哪些十位區段(band index 的集合)
    present = [{_tens_index(n, n_bands) for n in draw} for draw in draws]

    def _label(i: int) -> str:
        return f"{i * 10 + 1:02d}"  # band0→"01"、band1→"11"、band2→"21"…

    out = []
    for i in range(n_bands):
        for j in range(i + 1, n_bands):
            streak = 0
            for seen in reversed(present):
                if i in seen or j in seen:
                    break
                streak += 1
            out.append({
                "bands": (i, j),
                "labels": (_label(i), _label(j)),
                "range": (bands[i], bands[j]),
                "streak": streak,
                "alert": streak >= threshold,
            })
    out.sort(key=lambda d: -d["streak"])
    return out


# ── F. 卡方適合度檢定 ────────────────────────────────────
@dataclass
class ChiSquareResult:
    statistic: float
    p_value: float
    dof: int
    expected_per_num: float
    enough_data: bool
    conclusion: str


def chi_square(df: pd.DataFrame, num_max: int = NUM_MAX) -> ChiSquareResult:
    """檢驗 num_max 個號碼出現次數是否符合均勻分布。

    H0:每個號碼出現機率相等。自由度 = num_max − 1。
    期望次數 E = 期數 × pick / num_max;E < 5 時卡方近似不可靠。
    結論一律不暗示可預測:通過只代表「不違反均勻」=更證明無法預測。
    """
    from scipy.stats import chisquare

    periods = len(df)
    nums = all_nums(num_max)
    freq = frequency(df, num_max)
    observed = [freq[n] for n in nums]
    pick = _pick_of(df, draws_as_lists(df))
    expected_per = periods * pick / num_max
    expected = [expected_per] * num_max

    stat, p = chisquare(f_obs=observed, f_exp=expected)
    dof = num_max - 1
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
