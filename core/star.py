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
from math import ceil, comb

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


def supports(game) -> bool:
    """這一款遊戲適不適用三星 / 四星。

    C(8,k) 的碰數結構本身不挑遊戲,但機率與在跑的盤口(63/570、50/7500)
    都是照「39 選 5」報的;六合彩是 49 選 6,中獎機率與兩平倍率全都不同,
    整套要重推,所以跟 1800碰 一樣不在這裡開放。
    """
    return getattr(game, "num_max", 0) == 39 and getattr(game, "pick", 0) == 5


# ── 注數與成本 ───────────────────────────────────────────
def combos(stars: int, picked: int = PICK_NUMBERS) -> int:
    """一支要買幾碰 = C(選幾顆, 星數)。三星 56 碰、四星 70 碰。"""
    return comb(int(picked), int(stars))


def stars_of_combos(n: int, picked: int = PICK_NUMBERS) -> int:
    """由碰數反推星數(56 → 3、70 → 4);對不上任何一種回 0。

    流水把碰數存在「押幾顆」那一欄(跟 1800碰 存注數同一個位置),
    所以事後要顯示星別、列出可能碰數時得反推回來。
    """
    for k in STARS:
        if combos(k, picked) == int(n):
            return k
    return 0


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


def matched_count(picked, drawn) -> int:
    """自選號碼裡有幾顆出現在開獎號碼中。"""
    return len({int(n) for n in picked} & {int(n) for n in drawn})


def hits_of(picked, drawn, stars: int) -> int:
    """由自選號碼與開獎號碼直接算中的碰數。"""
    return hits_for(matched_count(picked, drawn), stars)


def result_text(hits: int | None, stars: int | None = None) -> str:
    """把中的碰數翻成中文結果;None 代表還沒開獎。"""
    if hits is None:
        return "待開獎"
    label = f"{name(stars)}" if stars in PLANS else ""
    if int(hits) <= 0:
        return f"{label}槓龜" if label else "槓龜"
    return f"{label}中 {int(hits)} 碰" if label else f"中 {int(hits)} 碰"


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


def net_per_sheet(hits: int, cost_per_combo: float, odds: float, stars: int,
                  picked: int = PICK_NUMBERS) -> float:
    """中 hits 碰時,每 1 支的淨利 = 碰數 × 每碰可得 − 單支成本。"""
    return (int(hits) * payout_per_combo(cost_per_combo, odds)
            - sheet_cost(cost_per_combo, stars, picked))


def best_case_net_per_sheet(cost_per_combo: float, odds: float, stars: int,
                            picked: int = PICK_NUMBERS, num_max: int = 39,
                            pick: int = 5) -> float:
    """最好情況(全中)每 1 支的淨利 = 最大碰數 × 每碰可得 − 單支成本。"""
    top = max(possible_hits(stars, pick, picked))
    return net_per_sheet(top, cost_per_combo, odds, stars, picked)


def sheets_for_recovery(loss: float, hits: int, cost_per_combo: float, odds: float,
                        stars: int, picked: int = PICK_NUMBERS,
                        base: int = 1) -> dict:
    """要靠「中 hits 碰」把 loss 一次追平,最少得下幾支。

    跟 1800碰 的 multiplier_for_recovery 同一個算式,差別在這裡不預設用
    最好情況 —— 三星全中(10 碰)的機率只有 0.0097%,拿它當回本基準等於
    在畫大餅,所以由呼叫端指定要押哪一種結果,每一種各算一列。
    """
    gain = net_per_sheet(hits, cost_per_combo, odds, stars, picked)
    loss = max(0.0, float(loss))
    if gain <= 0:
        return {"feasible": False, "sheets": None, "cost": None,
                "gain_per_sheet": gain}
    sheets = max(int(base), ceil(loss / gain)) if loss > 0 else int(base)
    return {"feasible": True, "sheets": sheets,
            "cost": round_cost(cost_per_combo, stars, sheets, picked),
            "gain_per_sheet": gain}


# ── 歷史檢驗 ─────────────────────────────────────────────
def history_stats(draws, picked, stars: int, pick: int = 5) -> dict:
    """拿**固定一組**自選號碼,回頭跑一串開獎紀錄(舊 → 新)的結果。

    顆數不符的期直接略過(資料還沒補齊時不該被算成槓龜,同 core.pillar)。
    這張表是用來說明「哪 8 顆都差不多」的 —— 每一組 8 顆的理論返還率完全
    相同,實際差異只是樣本雜訊。

    回傳 rounds/skipped/wins/win_rate/total_hits/hit_counts/
    streak/max_streak/last_draw/last_matched/last_hits。
    """
    valid = [list(d) for d in draws if d and len(d) == pick]
    hits = [hits_of(picked, d, stars) for d in valid]

    max_streak = streak = 0
    for h in hits:                       # 舊 → 新;連續槓龜最長的一段
        streak = streak + 1 if h == 0 else 0
        max_streak = max(max_streak, streak)
    cur = 0
    for h in reversed(hits):             # 新 → 舊;目前連幾期沒中
        if h != 0:
            break
        cur += 1

    hit_counts: dict[int, int] = {}
    for h in hits:
        hit_counts[h] = hit_counts.get(h, 0) + 1
    wins = sum(1 for h in hits if h > 0)
    return {
        "rounds": len(valid),
        "skipped": len(list(draws)) - len(valid),
        "wins": wins,
        "win_rate": wins / len(valid) if valid else 0.0,
        "total_hits": sum(hits),
        "hit_counts": dict(sorted(hit_counts.items())),
        "streak": cur,
        "max_streak": max_streak,
        "last_draw": valid[-1] if valid else [],
        "last_matched": matched_count(picked, valid[-1]) if valid else 0,
        "last_hits": hits[-1] if hits else 0,
    }
