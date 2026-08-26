"""9000碰:把 39 顆號碼依「十位頭」切成四段,包下四段笛卡兒積的全部組合。

四段(每段一個十位頭):

    0頭  01~09      9 顆
    1頭  10~19     10 顆
    2頭  20~29     10 顆
    3頭  30~39     10 顆

四段互斥且窮盡(9 + 10 + 10 + 10 = 39)。每一碰 = 四段各取一顆組成的 4 星
組合;買滿四段的全組合就是 9 × 10 × 10 × 10 = **9000 碰**,名稱由此而來。

一期開 5 顆,落在四段的顆數 (n0, n1, n2, n3) 之和固定為 5。**中獎判定跟
pillar(乘積)不同**:這裡是「每一段都至少開出 1 顆」才過關,而且過關就
**固定中 2 碰**(不看乘積)。因為 n0+n1+n2+n3 = 5、每段要 ≥ 1,整數分割
只有 {2,1,1,1} 一種,所以過關時必有一段開 2 顆、其餘各 1 顆 —— 對應到
包牌裡剛好有 2 碰的四顆全被開出(那 2 顆同段號各配另外三段的中號)。
任一段掛 0(缺頭)→ 中 0 碰。

    命中碰數 = 2  (四段都有開,即 {2,1,1,1} 分布)
             = 0  (任一段沒開)

成本用「四星每碰單價」(沿用星碰四星的盤口 combo_cost4),派彩用「四星中
一碰可得」(combo_prize4,預設 750,000)—— 一碰就是一注四星,兩者同源。
"""
from __future__ import annotations

# 四段的固定骨架(十位頭切法);第 0 段沒有 00,所以只有 9 顆。
SEGMENT_NAMES = ("0頭", "1頭", "2頭", "3頭")

# 段數
SEGMENTS = 4

# 過關(四段都有開)時固定中的碰數 —— {2,1,1,1} 分布必有 2 碰全中。
PASS_HITS = 2


# ── 分段 ─────────────────────────────────────────────────
def segments(num_max: int = 39) -> tuple[list[int], list[int], list[int], list[int]]:
    """把 1~num_max 依十位頭切成四段;0頭沒有 00,所以 01~09 只有 9 顆。"""
    s0 = [n for n in range(1, 10) if n <= num_max]
    s1 = [n for n in range(10, 20) if n <= num_max]
    s2 = [n for n in range(20, 30) if n <= num_max]
    s3 = [n for n in range(30, 40) if n <= num_max]
    return s0, s1, s2, s3


def sizes(num_max: int = 39) -> tuple[int, int, int, int]:
    """四段各幾顆號碼;39 → (9, 10, 10, 10)。"""
    s0, s1, s2, s3 = segments(num_max)
    return len(s0), len(s1), len(s2), len(s3)


def seg_of(n: int) -> int:
    """某號碼屬於第幾段(0/1/2/3),即它的十位頭。"""
    return int(n) // 10


def seg_counts(nums) -> tuple[int, int, int, int]:
    """一組號碼落在四段各幾顆,也就是 (n0, n1, n2, n3)。"""
    c = [0, 0, 0, 0]
    for n in nums:
        idx = seg_of(int(n))
        if 0 <= idx <= 3:
            c[idx] += 1
    return c[0], c[1], c[2], c[3]


def broken_segments(counts) -> list[int]:
    """這一期哪幾段掛蛋(0-based 十位頭);空清單代表四段都有開,整期過關。"""
    return [i for i, v in enumerate(counts) if v == 0]


def passed(counts) -> bool:
    """四段是否都至少開出 1 顆(過關)。"""
    return all(v > 0 for v in counts)


def supports(game) -> bool:
    """這一款遊戲適不適用 9000碰。

    四段 9/10/10/10 與 9000 碰的結構綁定「39 選 5」—— 今彩539 與天天樂符合;
    六合彩是 49 選 6,段數與命中結構都不同,不在這裡開放(同 core.pillar)。
    """
    return getattr(game, "num_max", 0) == 39 and getattr(game, "pick", 0) == 5


# ── 碰數與命中 ───────────────────────────────────────────
def total_bets(num_max: int = 39) -> int:
    """買滿四段全組合的碰數 = k0 × k1 × k2 × k3(39 → 9000)。"""
    k0, k1, k2, k3 = sizes(num_max)
    return k0 * k1 * k2 * k3


def hits_from_counts(counts) -> int:
    """命中碰數:四段都有開 → 固定 2 碰;任一段掛 0 → 0 碰。"""
    return PASS_HITS if passed(counts) else 0


def hits_of(draw) -> int:
    """直接由開獎號碼算命中碰數。"""
    return hits_from_counts(seg_counts(draw))


def result_text(hits: int | None) -> str:
    """把命中碰數翻成中文結果;None 代表還沒開獎。"""
    if hits is None:
        return "待開獎"
    if hits <= 0:
        return "槓龜(缺頭)"
    return f"中 {hits} 碰"


# ── 損益 ─────────────────────────────────────────────────
def round_cost(cost_per_bet: float, multiplier: int = 1, num_max: int = 39) -> float:
    """一期的下注成本 = 總碰數 × 每碰成本 × 支數(1 支 = 買滿全組合)。"""
    return total_bets(num_max) * float(cost_per_bet) * int(multiplier)


def round_payout(hits: int, prize_per_bet: float, multiplier: int = 1) -> float:
    """一期的回收 = 命中碰數 × 每碰派彩 × 支數。"""
    return int(hits) * float(prize_per_bet) * int(multiplier)


def settle(hits: int, cost_per_bet: float, prize_per_bet: float,
           multiplier: int = 1, num_max: int = 39) -> dict:
    """結算一期:成本、回收、本局損益。"""
    cost = round_cost(cost_per_bet, multiplier, num_max)
    payout = round_payout(hits, prize_per_bet, multiplier)
    return {"hits": int(hits), "cost": cost, "payout": payout, "net": payout - cost}
