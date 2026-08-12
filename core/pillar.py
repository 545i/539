"""三柱 1800碰:買下三柱笛卡兒積的全部組合。

39 個號碼切成三柱(民間盤的分法,見專案根目錄 539-SPEC.md §3):

    第一柱  10~18                              9 顆
    第二柱  20~29                             10 顆
    第三柱  01~09、19、30~39(其餘全部)      20 顆

三柱互斥且窮盡(9 + 10 + 20 = 39)。**19 歸第三柱**,第一柱嚴格只到 18 ——
這是刻意的不對稱,不是筆誤。

每注取三柱各一號,恰好是一注「39樂合彩三合」;買滿三柱的全組合就是
9 × 10 × 20 = **1800 注**,名稱由此而來。一期開 5 顆,只要三柱各中至少一顆
就有注中獎,命中注數:

    hits = n1 × n2 × n3        n_i = 開獎號碼落在第 i 柱的顆數

因為 n1+n2+n3 = 5 且每項要 ≥ 1,整數分割只有 {1,2,2} 與 {1,1,3} 兩種,
所以 hits 的值域只有 **4(中四碰)、3(中三碰)、0(任一柱沒開 = 斷柱)**。

本模組的機率一律以組合數列舉算出,不寫死任何百分比 —— 39選5 下應得
過關率 55.3619%、E[hits] = 1.96958,可與 539-SPEC §4.5 對照驗算。
"""
from __future__ import annotations

from math import ceil, comb

# 三柱的固定骨架(第三柱是「其餘全部」,依 num_max 動態展開)
_C1 = list(range(10, 19))       # 10~18
_C2 = list(range(20, 30))       # 20~29

PILLAR_NAMES = ("第一柱", "第二柱", "第三柱")

# 一注 = 三柱各取一號
COMBO_SIZE = 3

# 官方 39樂合彩三合定價:每注 25 元,全中一注派彩 11,250 元(返還率 49.24%)。
OFFICIAL_COST_PER_BET = 25.0
OFFICIAL_PRIZE_PER_BET = 11_250.0


# ── 分柱 ─────────────────────────────────────────────────
def pillars(num_max: int = 39) -> tuple[list[int], list[int], list[int]]:
    """把 1~num_max 切成三柱;第三柱吃下所有不屬於前兩柱的號碼。"""
    c1 = [n for n in _C1 if n <= num_max]
    c2 = [n for n in _C2 if n <= num_max]
    taken = set(c1) | set(c2)
    c3 = [n for n in range(1, num_max + 1) if n not in taken]
    return c1, c2, c3


def sizes(num_max: int = 39) -> tuple[int, int, int]:
    """三柱各幾顆號碼;39 → (9, 10, 20)。"""
    c1, c2, c3 = pillars(num_max)
    return len(c1), len(c2), len(c3)


def pillar_of(n: int, num_max: int = 39) -> int:
    """某號碼屬於第幾柱(1/2/3)。第三柱是「其餘全部」,所以永遠有歸屬。"""
    if n in _C1:
        return 1
    if n in _C2:
        return 2
    return 3


def pillar_counts(nums, num_max: int = 39) -> tuple[int, int, int]:
    """一組號碼落在三柱各幾顆,也就是算式裡的 (n1, n2, n3)。"""
    c = [0, 0, 0]
    for n in nums:
        c[pillar_of(int(n), num_max) - 1] += 1
    return c[0], c[1], c[2]


def broken_pillars(counts) -> list[int]:
    """這一期是哪幾柱掛蛋(1-based);空清單代表三柱都有開,整期過關。"""
    return [i + 1 for i, v in enumerate(counts) if v == 0]


def supports(game) -> bool:
    """這一款遊戲適不適用 1800碰。

    三柱 9/10/20 與 1800 注的結構綁定「39 選 5」—— 今彩539 與天天樂符合;
    六合彩是 49 選 6,第三柱會變 30 顆(2700 注)、hits 值域也完全不同,
    整套機率要重推,所以不在這裡開放。
    """
    return getattr(game, "num_max", 0) == 39 and getattr(game, "pick", 0) == 5


# ── 注數與命中 ───────────────────────────────────────────
def total_bets(num_max: int = 39) -> int:
    """買滿三柱全組合的注數 = k1 × k2 × k3(39 → 1800)。"""
    k1, k2, k3 = sizes(num_max)
    return k1 * k2 * k3


def hits_from_counts(counts) -> int:
    """命中注數 = n1 × n2 × n3。

    一注要中,三柱各自選的那一號都得被開出;第 i 柱有 n_i 顆被開出,
    三柱各取一顆的組合數就是乘積。任一柱為 0(斷柱)整期歸零。
    """
    n1, n2, n3 = counts
    return n1 * n2 * n3


def hits_of(draw, num_max: int = 39) -> int:
    """直接由開獎號碼算命中注數。"""
    return hits_from_counts(pillar_counts(draw, num_max))


def result_text(hits: int | None) -> str:
    """把命中注數翻成中文結果;None 代表還沒開獎。"""
    if hits is None:
        return "待開獎"
    if hits <= 0:
        return "槓龜(斷柱)"
    return f"中 {hits} 碰"


# ── 機率(全部由組合數列舉,不寫死百分比)────────────────
def total_draws(num_max: int = 39, pick: int = 5) -> int:
    """所有可能的開獎組合數 C(num_max, pick)。"""
    return comb(num_max, pick)


def outcome_ways(num_max: int = 39, pick: int = 5) -> dict[tuple[int, int, int], int]:
    """各種柱分佈 (n1,n2,n3) 各有幾種開獎組合。

    ways(n1,n2,n3) = C(k1,n1) · C(k2,n2) · C(k3,n3),總和 = C(num_max, pick)。
    """
    k1, k2, k3 = sizes(num_max)
    out: dict[tuple[int, int, int], int] = {}
    for n1 in range(min(k1, pick) + 1):
        for n2 in range(min(k2, pick - n1) + 1):
            n3 = pick - n1 - n2
            if n3 < 0 or n3 > k3:
                continue
            out[(n1, n2, n3)] = comb(k1, n1) * comb(k2, n2) * comb(k3, n3)
    return out


def hit_ways(num_max: int = 39, pick: int = 5) -> dict[int, int]:
    """命中注數 → 組合數(把柱分佈依 hits 彙總)。"""
    out: dict[int, int] = {}
    for dist, ways in outcome_ways(num_max, pick).items():
        h = hits_from_counts(dist)
        out[h] = out.get(h, 0) + ways
    return dict(sorted(out.items()))


def hit_probs(num_max: int = 39, pick: int = 5) -> dict[int, float]:
    """命中注數 → 機率;39選5 應為 {0: .4464, 3: .2449, 4: .3087}。"""
    tot = total_draws(num_max, pick)
    return {h: w / tot for h, w in hit_ways(num_max, pick).items()}


def pass_prob(num_max: int = 39, pick: int = 5) -> float:
    """過關(三柱都有開,至少中一注)的機率;39選5 = 55.3619%。"""
    return sum(p for h, p in hit_probs(num_max, pick).items() if h > 0)


def expected_hits(num_max: int = 39, pick: int = 5) -> float:
    """每期期望命中注數;39選5 = 1.96958。

    另一條等價路徑:總注數 × 單注三合中獎機率
    = 1800 × C(5,3)/C(39,3) = 1800 × 10/9139。兩者相等(見測試)。
    """
    return sum(h * p for h, p in hit_probs(num_max, pick).items())


def max_hits(num_max: int = 39, pick: int = 5) -> int:
    """一期最多可能中幾注(39選5 = 4,即中四碰)。"""
    return max(hit_ways(num_max, pick))


# ── 損益 ─────────────────────────────────────────────────
def round_cost(cost_per_bet: float, multiplier: int = 1, num_max: int = 39) -> float:
    """一期的下注成本 = 總注數 × 每注成本 × 支數(1 支 = 買滿全組合)。"""
    return total_bets(num_max) * float(cost_per_bet) * int(multiplier)


def round_payout(hits: int, prize_per_bet: float, multiplier: int = 1) -> float:
    """一期的回收 = 命中注數 × 每注派彩 × 支數。"""
    return int(hits) * float(prize_per_bet) * int(multiplier)


def settle(hits: int, cost_per_bet: float, prize_per_bet: float,
           multiplier: int = 1, num_max: int = 39) -> dict:
    """結算一期:成本、回收、本局損益。"""
    cost = round_cost(cost_per_bet, multiplier, num_max)
    payout = round_payout(hits, prize_per_bet, multiplier)
    return {"hits": int(hits), "cost": cost, "payout": payout, "net": payout - cost}


def breakeven_prize(cost_per_bet: float, num_max: int = 39, pick: int = 5) -> float:
    """損益兩平的單注派彩 = 每注成本 × C(num_max,3) / C(pick,3)。

    39選5 時等於 913.9 × 每注成本 —— 也就是**單注三合的公平賠率**。
    包牌的成本與回收都線性於注數,所以兩平點與買幾注無關。
    """
    return round_cost(cost_per_bet, 1, num_max) / expected_hits(num_max, pick)


def return_rate(cost_per_bet: float, prize_per_bet: float,
                num_max: int = 39, pick: int = 5) -> float:
    """返還率 = 期望回收 ÷ 成本;官方三合為 49.24%,> 1 代表正期望(不可能)。"""
    cost = round_cost(cost_per_bet, 1, num_max)
    if cost <= 0:
        return 0.0
    return expected_hits(num_max, pick) * float(prize_per_bet) / cost


def expected_net(cost_per_bet: float, prize_per_bet: float, multiplier: int = 1,
                 num_max: int = 39, pick: int = 5) -> float:
    """每期期望損益(負值 = 長期淨輸)。"""
    cost = round_cost(cost_per_bet, multiplier, num_max)
    return expected_hits(num_max, pick) * float(prize_per_bet) * int(multiplier) - cost


def best_case_net_per_multiple(cost_per_bet: float, prize_per_bet: float,
                               num_max: int = 39, pick: int = 5) -> float:
    """最好情況(中四碰)每 1 支的淨利 = 4 × 每注派彩 − 總成本。

    這是 1800碰 單期回收的上限。官方盤口下它恰好是 0
    (4 × 11,250 = 45,000 = 1800 × 25)—— 代表就算中四碰也只是打平,
    永遠沒有能力追回過去的虧損。
    """
    return (max_hits(num_max, pick) * float(prize_per_bet)
            - round_cost(cost_per_bet, 1, num_max))


def multiplier_for_recovery(loss: float, cost_per_bet: float, prize_per_bet: float,
                            num_max: int = 39, pick: int = 5,
                            base: int = 1) -> dict:
    """要把 loss 一次追平,最少得下幾支(以中四碰為回收上限)。

    追平條件:支數 × 中四碰淨利 ≥ 目前虧損。中四碰淨利 ≤ 0 時無解 ——
    這不是算不出來,是這個盤口本身就沒有回本的可能。
    """
    gain = best_case_net_per_multiple(cost_per_bet, prize_per_bet, num_max, pick)
    loss = max(0.0, float(loss))
    if gain <= 0:
        return {"feasible": False, "multiplier": None, "cost": None,
                "gain_per_multiple": gain}
    mult = max(int(base), ceil(loss / gain)) if loss > 0 else int(base)
    return {"feasible": True, "multiplier": mult,
            "cost": round_cost(cost_per_bet, mult, num_max),
            "gain_per_multiple": gain}


# ── 逐柱的連續未開(斷柱提醒)──────────────────────────
PILLAR_ALERT_DRAWS = 4      # 某一柱連續幾期沒開就提醒


def range_label(nums) -> str:
    """把一柱的號碼壓成區間字樣:第三柱 → 「01~09、19、30~39」。

    整柱 20 個號碼全列出來太長,壓成區間才看得懂它涵蓋哪裡。
    """
    parts: list[str] = []
    start = prev = None
    for n in sorted(int(x) for x in nums):
        if start is None:
            start = prev = n
            continue
        if n == prev + 1:
            prev = n
            continue
        parts.append(f"{start:02d}" if start == prev else f"{start:02d}~{prev:02d}")
        start = prev = n
    if start is not None:
        parts.append(f"{start:02d}" if start == prev else f"{start:02d}~{prev:02d}")
    return "、".join(parts)


def pillar_missing(draws, num_max: int = 39, pick: int = 5) -> dict[int, dict]:
    """每一柱目前連續幾期沒開(斷柱)與歷史最長。

    一期只要那一柱**有任何一個號碼**開出就算開了,整柱掛蛋才累計。
    顆數不齊的期直接略過 —— 資料還沒補齊時不該被算成沒開(同 history_stats)。

    回傳 {柱別(1/2/3): {current, max_gap, name, label, size}}。
    """
    valid = [list(d) for d in draws if d and len(d) == pick]
    per_draw = [{pillar_of(int(n), num_max) for n in d} for d in valid]

    out = {}
    for i, nums in enumerate(pillars(num_max), start=1):
        current = 0
        for hits in reversed(per_draw):
            if i in hits:
                break
            current += 1
        run = max_gap = 0
        for hits in per_draw:
            run = 0 if i in hits else run + 1
            max_gap = max(max_gap, run)
        out[i] = {"current": current, "max_gap": max_gap,
                  "name": PILLAR_NAMES[i - 1], "label": range_label(nums),
                  "size": len(nums)}
    return out


def pillar_alerts(draws, num_max: int = 39, pick: int = 5,
                  threshold: int = PILLAR_ALERT_DRAWS) -> list[dict]:
    """連續 threshold 期(含)以上整柱沒開的柱別,久的排前面。"""
    got = [{"pillar": i, **v}
           for i, v in pillar_missing(draws, num_max, pick).items()
           if v["current"] >= threshold]
    return sorted(got, key=lambda d: (-d["current"], d["pillar"]))


# ── 歷史檢驗 ─────────────────────────────────────────────
def history_stats(draws, num_max: int = 39, pick: int = 5) -> dict:
    """一串開獎號碼(**舊 → 新**)拿 1800碰 回頭檢驗的結果。

    顆數不符的期直接略過(資料還沒補齊時不該被算成槓龜)。斷柱以
    「最新的**有效**期」為準 —— 539-SPEC §8.9 指出原站把「跳過無效期」寫在
    「是否為最近一期」的判斷之前,導致最近一期資料不完整時永遠記不到斷柱;
    這裡先濾掉無效期再取最後一筆,不會有那個洞。

    回傳 rounds/passes/pass_rate/hit_counts/streak/max_streak/
    last_counts/last_broken/dist_counts。
    """
    valid = [list(d) for d in draws if d and len(d) == pick]
    hits = [hits_of(d, num_max) for d in valid]

    max_streak = streak = 0
    for h in hits:                       # 舊 → 新;連續槓龜的最長一段
        streak = streak + 1 if h == 0 else 0
        max_streak = max(max_streak, streak)
    cur = 0
    for h in reversed(hits):             # 新 → 舊;目前連幾期沒過關
        if h != 0:
            break
        cur += 1

    hit_counts: dict[int, int] = {}
    dist_counts: dict[tuple[int, int, int], int] = {}
    for d, h in zip(valid, hits):
        hit_counts[h] = hit_counts.get(h, 0) + 1
        key = pillar_counts(d, num_max)
        dist_counts[key] = dist_counts.get(key, 0) + 1

    passes = sum(1 for h in hits if h > 0)
    last_counts = pillar_counts(valid[-1], num_max) if valid else (0, 0, 0)
    return {
        "rounds": len(valid),
        "skipped": len(list(draws)) - len(valid),
        "passes": passes,
        "pass_rate": passes / len(valid) if valid else 0.0,
        "hit_counts": dict(sorted(hit_counts.items())),
        "dist_counts": dist_counts,
        "streak": cur,
        "max_streak": max_streak,
        "last_draw": valid[-1] if valid else [],
        "last_counts": last_counts,
        "last_broken": broken_pillars(last_counts) if valid else [],
    }
