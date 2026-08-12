"""三星 / 四星:選 8 顆,買下其中所有 3 碼(或 4 碼)組合。

玩法:
    選 8 顆號碼 → 買下這 8 顆的**所有 k 碼組合**,一組叫一「碰」。
        三星 k=3  C(8,3) = 56 碰   每碰 63 元 → 1 支 = 63 × 56 = 3,528
        四星 k=4  C(8,4) = 70 碰   每碰 50 元 → 1 支 = 50 × 70 = 3,500

中獎:
    開獎 5 顆裡,你的 8 顆對中了 k_hit 顆,則中的碰數 = C(k_hit, stars)
        三星:中 3 顆 → 1 碰、中 4 顆 → 4 碰、中 5 顆 → 10 碰
        四星:中 4 顆 → 1 碰、中 5 顆 → 5 碰
    中獎金額 = 支數 × 中的碰數 × 每碰可得,而 **每碰可得 = 每碰成本 × 倍率**。

    倍率是「賠率幾倍」不是「幾元」—— 三星 570 倍即 63 × 570 = 35,910。
    若把 570 當成 570 元,返還率會低到 0.99%,那種盤口不存在(見測試)。

跟 core.pillar 的 1800碰 一樣是三合包牌,但這裡是「自選 8 顆的全組合」,
不是「三柱各取一號」,注數與中獎結構都不同,所以另立一個模組。
"""
from __future__ import annotations

from dataclasses import dataclass
from math import comb

PICK_NUMBERS = 8        # 選幾顆(玩法固定)
STARS = (3, 4)          # 三星 / 四星


@dataclass(frozen=True)
class StarPlan:
    stars: int
    name: str
    default_cost: float     # 每碰成本
    default_odds: float     # 賠率(倍)


PLANS: dict[int, StarPlan] = {
    3: StarPlan(3, "三星", 63.0, 570.0),
    4: StarPlan(4, "四星", 50.0, 7500.0),
}


def plan(stars: int) -> StarPlan:
    return PLANS[int(stars)]


def name(stars: int) -> str:
    return PLANS[int(stars)].name


# ── 注數與成本 ───────────────────────────────────────────
def combos(stars: int, picked: int = PICK_NUMBERS) -> int:
    """一支要買幾碰 = C(選幾顆, 星數)。三星 56 碰、四星 70 碰。"""
    return comb(int(picked), int(stars))


def sheet_cost(cost_per_combo: float, stars: int,
               picked: int = PICK_NUMBERS) -> float:
    """1 支的成本 = 每碰成本 × 碰數。"""
    return float(cost_per_combo) * combos(stars, picked)


def round_cost(cost_per_combo: float, stars: int, sheets: int = 1,
               picked: int = PICK_NUMBERS) -> float:
    """本局成本 = 單支成本 × 支數。"""
    return sheet_cost(cost_per_combo, stars, picked) * int(sheets)


def payout_per_combo(cost_per_combo: float, odds: float) -> float:
    """中一碰可得 = 每碰成本 × 倍率(三星 63 × 570 = 35,910)。"""
    return float(cost_per_combo) * float(odds)


# ── 中獎 ─────────────────────────────────────────────────
def hits_for(matched: int, stars: int) -> int:
    """對中 matched 顆時,中的碰數 = C(matched, 星數)。"""
    m, k = int(matched), int(stars)
    return comb(m, k) if m >= k else 0


def possible_hits(stars: int, pick: int = 5,
                  picked: int = PICK_NUMBERS) -> list[int]:
    """一期可能中的碰數(由大到小),供下拉選單用。"""
    top = min(int(pick), int(picked))
    got = {hits_for(m, stars) for m in range(top + 1)}
    return sorted(got, reverse=True)


def round_payout(hits: int, cost_per_combo: float, odds: float,
                 sheets: int = 1) -> float:
    """本局回收 = 中的碰數 × 每碰可得 × 支數。"""
    return int(hits) * payout_per_combo(cost_per_combo, odds) * int(sheets)


def settle(hits: int, cost_per_combo: float, odds: float, stars: int,
           sheets: int = 1, picked: int = PICK_NUMBERS) -> dict:
    """結算一期:成本、回收、本局損益。"""
    cost = round_cost(cost_per_combo, stars, sheets, picked)
    payout = round_payout(hits, cost_per_combo, odds, sheets)
    return {"hits": int(hits), "cost": cost, "payout": payout,
            "net": payout - cost}


# ── 機率(組合數列舉,不寫死百分比)──────────────────────
def match_probs(picked: int = PICK_NUMBERS, num_max: int = 39,
                pick: int = 5) -> dict[int, float]:
    """自選 picked 顆時,對中 k 顆的機率(超幾何分布)。"""
    total = comb(num_max, pick)
    top = min(picked, pick)
    return {k: comb(picked, k) * comb(num_max - picked, pick - k) / total
            for k in range(top + 1)}


def hit_probs(stars: int, picked: int = PICK_NUMBERS, num_max: int = 39,
              pick: int = 5) -> dict[int, float]:
    """中的碰數 → 機率(把對中顆數依 C(k, stars) 彙總)。"""
    out: dict[int, float] = {}
    for k, p in match_probs(picked, num_max, pick).items():
        h = hits_for(k, stars)
        out[h] = out.get(h, 0.0) + p
    return dict(sorted(out.items()))


def expected_hits(stars: int, picked: int = PICK_NUMBERS, num_max: int = 39,
                  pick: int = 5) -> float:
    """每期期望中幾碰。

    另一條等價路徑:碰數 × 單碰中獎機率
    = C(picked, stars) × C(num_max−stars, pick−stars) / C(num_max, pick)。
    兩者相等(見測試)—— 每一碰中獎的機率都一樣,期望值可以直接相加。
    """
    return sum(h * p for h, p in hit_probs(stars, picked, num_max, pick).items())


def win_prob(stars: int, picked: int = PICK_NUMBERS, num_max: int = 39,
             pick: int = 5) -> float:
    """至少中一碰的機率。"""
    return sum(p for h, p in hit_probs(stars, picked, num_max, pick).items()
               if h > 0)


# ── 期望值 ───────────────────────────────────────────────
def return_rate(cost_per_combo: float, odds: float, stars: int,
                picked: int = PICK_NUMBERS, num_max: int = 39,
                pick: int = 5) -> float:
    """返還率 = 期望回收 ÷ 成本。"""
    cost = round_cost(cost_per_combo, stars, 1, picked)
    if cost <= 0:
        return 0.0
    e = expected_hits(stars, picked, num_max, pick)
    return e * payout_per_combo(cost_per_combo, odds) / cost


def expected_net(cost_per_combo: float, odds: float, stars: int,
                 sheets: int = 1, picked: int = PICK_NUMBERS,
                 num_max: int = 39, pick: int = 5) -> float:
    """每期期望損益(負值 = 長期淨輸)。"""
    cost = round_cost(cost_per_combo, stars, sheets, picked)
    e = expected_hits(stars, picked, num_max, pick)
    return e * payout_per_combo(cost_per_combo, odds) * int(sheets) - cost


def breakeven_odds(stars: int, picked: int = PICK_NUMBERS, num_max: int = 39,
                   pick: int = 5) -> float:
    """損益兩平的倍率 = 碰數 ÷ 期望中碰數 = 單碰的公平賠率。

    與每碰成本無關 —— 成本與回收都線性於每碰價,會約掉。
    三星 = C(39,3)/C(5,3) = 913.9;四星 = C(39,4)/C(5,4) = 16,450.2。
    """
    e = expected_hits(stars, picked, num_max, pick)
    return combos(stars, picked) / e if e else float("inf")


def best_case_net_per_sheet(cost_per_combo: float, odds: float, stars: int,
                            picked: int = PICK_NUMBERS, num_max: int = 39,
                            pick: int = 5) -> float:
    """最好情況(全中)每 1 支的淨利 = 最大碰數 × 每碰可得 − 單支成本。"""
    top = max(possible_hits(stars, pick, picked))
    return (top * payout_per_combo(cost_per_combo, odds)
            - sheet_cost(cost_per_combo, stars, picked))
