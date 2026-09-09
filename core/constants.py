"""今彩539 規則、獎金與機率常數(已查證:台灣彩券官網 + 第三方對照 + 組合數驗算)。

重要:這些數字直接決定回測報酬率的正確性,請勿隨意更動。
"""
from __future__ import annotations

from math import comb

# ── 玩法規則 ──────────────────────────────────────────────
NUM_MIN = 1
NUM_MAX = 39
PICK = 5            # 每期 / 每注選 5 個號碼
TICKET_PRICE = 50   # 每注 NT$50

# ── 獎金結構(中 k 碼對應的獎金,NTD)──────────────────────
PRIZE = {
    5: 8_000_000,   # 頭獎(固定;全期上限 2,400 萬則均分,單注回測不觸發)
    4: 20_000,      # 貳獎
    3: 300,         # 參獎
    2: 50,          # 肆獎
    1: 0,           # 無獎
    0: 0,           # 無獎
}

# ── 組合數與機率 ─────────────────────────────────────────
TOTAL_COMB = comb(NUM_MAX, PICK)  # C(39,5) = 575,757

# 中 k 碼的中獎組合數:從開出的 5 個中選 k 個、從其餘 34 個中選 5-k 個
WAYS = {k: comb(PICK, k) * comb(NUM_MAX - PICK, PICK - k) for k in range(PICK + 1)}
# {5:1, 4:170, 3:5610, 2:59840, 1:231880, 0:278256}


def prob(k: int) -> float:
    """中 k 碼的理論機率。"""
    return WAYS[k] / TOTAL_COMB


def expected_prize() -> float:
    """每注期望獎金(NTD)≈ 27.92。"""
    return sum(prob(k) * PRIZE[k] for k in PRIZE)


def expected_return() -> float:
    """每注長期期望報酬率 ≈ -0.4416。"""
    return expected_prize() / TICKET_PRICE - 1.0


EXPECTED_RETURN = expected_return()  # ≈ -0.4416

# ── 免責聲明 ─────────────────────────────────────────────
DISCLAIMER = (
    "今彩539 每期開獎為獨立隨機事件,數學上無法預測下一期號碼。\n"
    f"長期期望報酬率約 {EXPECTED_RETURN:.2%}(每注 NT${TICKET_PRICE},長期平均拿回約 "
    f"NT${expected_prize():.0f})。\n"
    "所有選號策略(隨機/熱號/冷號/頻率/均衡)期望中獎率完全相同,差異只是運氣。\n"
    "本工具僅供統計學習與娛樂用途,請理性娛樂、量力而為。"
)
