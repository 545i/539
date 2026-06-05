"""凱莉公式投報計算:用凱莉準則評估今彩539 該不該下注、下注多少。

關鍵正確性:今彩539 為負期望值(EV ≈ -44%)的賭局,
理論凱莉比例 f* 會是負數,實務上代表「數學上根本不該下注」,
因此實務最佳投注比例會被夾在 0。本模組誠實呈現這個結論,
不提供任何「提高勝率」的幻覺。

純函式:只依賴 core.constants 與標準函式庫,不碰網路/檔案/系統時鐘。
需要亂數時一律使用傳入 seed 建立的獨立產生器。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from math import log

from core import constants


@dataclass
class KellyResult:
    raw_fraction: float      # 理論凱莉比例 f*(EV<0 會是負數 → 數學上「不該下注」)
    fraction: float          # 實務最佳投注比例 = max(0.0, raw_fraction)
    ev_per_bet: float        # 每注(預設 NT$50)期望淨利(NTD,可負)
    ev_return_rate: float    # 期望報酬率(應 ≈ constants.EXPECTED_RETURN ≈ -0.4416)
    growth_rate: float       # 在 fraction 下每注對數成長率(fraction=0 → 0.0)
    recommendation: str      # 白話誠實結論(必須點出「EV 為負,凱莉建議下注比例為 0」)


def kelly_binary(p: float, b: float) -> float:
    """二元凱莉公式。

    f* = (b*p - (1-p)) / b
    b 為淨賠率(贏可得 b 倍本金),p 為勝率。
    回傳建議投注比例(可為負,負數代表不該下注)。
    """
    return (b * p - (1.0 - p)) / b


def outcomes_539(bet: int = constants.TICKET_PRICE) -> list[tuple[float, float]]:
    """今彩539 的各結果(機率, 淨報酬倍率)清單。

    net_multiple = PRIZE[k]/bet - 1(贏回扣掉本金後相對於本金的倍率)。
    k=2 時 50/50-1=0 剛好打平;k<=1 時獎金為 0,net=-1(本金全失)。
    回傳順序為 k = 0..5。
    """
    return [
        (constants.prob(k), constants.PRIZE[k] / bet - 1.0)
        for k in range(constants.PICK + 1)
    ]


def outcomes_for(game) -> list[tuple[float, float]]:
    """任意遊戲的各結果(機率, 淨報酬倍率)清單。

    net_multiple = 獎金/票價 - 1;依 GameConfig 的票價與獎金結構計算。
    """
    bet = game.ticket_price
    return [
        (game.prob(k), game.prize.get(k, 0) / bet - 1.0)
        for k in range(constants.PICK + 1)
    ]


def _growth(f: float, outcomes: list[tuple[float, float]]) -> float:
    """對數成長率 g(f) = Σ prob_i * log(1 + f * r_i)。

    若任一結果使 1 + f*r_i <= 0(等於賭到破產),回傳負無限大,
    讓搜尋自動避開。
    """
    total = 0.0
    for prob, r in outcomes:
        x = 1.0 + f * r
        if x <= 0.0:
            return float("-inf")
        total += prob * log(x)
    return total


def kelly_multi(outcomes: list[tuple[float, float]],
                lo: float = -0.999, hi: float = 1.0, iters: int = 300) -> float:
    """多結果凱莉:數值解最大化 g(f)=Σ prob_i*log(1 + f*r_i) 的 f。

    用三分搜尋(ternary search)在 [lo, hi] 找最大值位置。
    g(f) 為凹函數,三分搜尋會收斂到唯一極大。
    若最佳落在 f<=0(539 即如此),照實回傳該值(代表不該下注)。
    """
    left, right = lo, hi
    for _ in range(iters):
        m1 = left + (right - left) / 3.0
        m2 = right - (right - left) / 3.0
        if _growth(m1, outcomes) < _growth(m2, outcomes):
            left = m1
        else:
            right = m2
    return (left + right) / 2.0


def _analyze_outcomes(outcomes, bet, label, currency):
    """以 (機率, 淨倍率) 清單與票價計算 KellyResult(通用核心)。"""
    ev_return_rate = sum(prob * r for prob, r in outcomes)
    ev_per_bet = bet * ev_return_rate
    raw_fraction = kelly_multi(outcomes)
    fraction = max(0.0, raw_fraction)
    growth_rate = 0.0 if fraction == 0.0 else _growth(fraction, outcomes)

    recommendation = (
        f"{label} 每注 {currency}{bet:g} 的期望報酬率約 {ev_return_rate:.2%}"
        f"(每注平均淨虧 {currency}{-ev_per_bet:.2f}),屬於負期望值賭局。\n"
        f"理論凱莉比例 f* = {raw_fraction:.4f} 為負數,"
        "代表數學上根本不該把資金投入這個賭局。\n"
        "因此凱莉準則建議的實務下注比例為 0(完全不下注),"
        "任何選號策略都改變不了這個負期望的結果。\n"
        "請理性娛樂、量力而為,切勿借貸或重押。"
    )
    return KellyResult(
        raw_fraction=raw_fraction,
        fraction=fraction,
        ev_per_bet=ev_per_bet,
        ev_return_rate=ev_return_rate,
        growth_rate=growth_rate,
        recommendation=recommendation,
    )


def analyze_539(bet: int = constants.TICKET_PRICE) -> KellyResult:
    """完整分析今彩539 的凱莉投注建議。

    結論:負期望值賭局,理論凱莉比例 < 0,實務建議下注比例為 0。
    """
    return _analyze_outcomes(outcomes_539(bet), bet, "今彩539", "NT$")


def analyze(game) -> KellyResult:
    """完整分析任意遊戲(GameConfig)的凱莉投注建議。"""
    return _analyze_outcomes(
        outcomes_for(game), game.ticket_price, game.name, game.currency
    )


def simulate_bankroll(fraction: float, outcomes: list[tuple[float, float]],
                      rounds: int, start: float = 10000.0,
                      seed: int = 539) -> list[float]:
    """以固定投注比例模擬資金軌跡(蒙地卡羅)。

    每輪以 stake = fraction * 當前資金 下注,
    依各 outcome 機率抽中某結果 r,資金變化 = stake * r。
    回傳長度 rounds+1 的資金序列(含起始值)。
    fraction=0 → 不下注 → 資金恆定為 start。
    只用傳入的 seed 建立獨立亂數產生器,不讀系統時鐘。
    """
    rng = random.Random(seed)
    probs = [prob for prob, _ in outcomes]
    multiples = [r for _, r in outcomes]

    bankroll = start
    series = [bankroll]
    for _ in range(rounds):
        if fraction == 0.0:
            series.append(bankroll)
            continue
        r = rng.choices(multiples, weights=probs, k=1)[0]
        stake = fraction * bankroll
        bankroll += stake * r
        series.append(bankroll)
    return series
