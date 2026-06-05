"""二合(二星)買牌試算:中獎機率、成本、期望投報、凱莉、倍頭(Martingale)。

二合玩法(以今彩539 的 39 選 5 開獎為基礎):
  選 2 個號碼,當期開出的 5 個號碼若同時包含這 2 個,即中獎。

誠實前提:
  - 二合單組中獎機率固定為 C(37,3)/C(39,5) ≈ 1/74.1,且每號真實開機率相同。
  - 期望報酬率 = 中獎機率 × 賠率 − 1,只由「賠率」決定,與選哪些號碼無關。
  - 賠率 < 74.1 為負期望(凱莉建議 0、倍投必破產);> 74.1 才正期望。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import comb

from core import constants, kelly

# 二合單組(任一 2 碼)中獎機率:其餘 3 個開獎號從剩下 37 個中選
PAIR_WAYS = comb(constants.NUM_MAX - 2, constants.PICK - 2)   # C(37,3) = 7770
PAIR_PROB = PAIR_WAYS / constants.TOTAL_COMB                  # ≈ 0.013495
BREAKEVEN_ODDS = 1.0 / PAIR_PROB                              # ≈ 74.10(公平賠率)


# 拖牌車「中」的機率 = 膽號被開出(在當期 5 個開獎號內)= 5/39
DAN_PROB = constants.PICK / constants.NUM_MAX  # ≈ 0.12821


def ev_rate(odds: float) -> float:
    """二合每注期望報酬率 = 中獎機率 × 賠率 − 1。"""
    return PAIR_PROB * odds - 1.0


# ── 車級模型(以「每車成本 + 中獎可得」直接計算)──────────
def car_ev_rate(cost_per_car: float, win_payout: float) -> float:
    """拖牌車的期望報酬率。

    車「中」(膽號被開出,機率 5/39)時收到 win_payout,否則 0。
    期望報酬率 = 5/39 × win_payout / cost_per_car − 1。
    """
    return DAN_PROB * win_payout / cost_per_car - 1.0


def car_kelly_fraction(cost_per_car: float, win_payout: float) -> float:
    """拖牌車的凱莉建議下注比例(車級二元賭局)。

    勝率 p = 5/39;淨賠率 b = (win_payout − cost)/cost。負期望時為 0。
    """
    b = (win_payout - cost_per_car) / cost_per_car
    if b <= 0:
        return 0.0
    return max(0.0, kelly.kelly_binary(DAN_PROB, b))


def kelly_fraction(odds: float) -> float:
    """二合的凱莉建議下注比例(占總資金)。

    視為二元賭局:勝率 p = PAIR_PROB,淨賠率 b = 賠率 − 1。
    f* = (b·p − (1−p)) / b;負期望時夾到 0。
    """
    b = odds - 1.0
    if b <= 0:
        return 0.0
    return max(0.0, kelly.kelly_binary(PAIR_PROB, b))


# ── 拖牌包車成本 ─────────────────────────────────────────
@dataclass
class TuoPlan:
    notes_per_car: int    # 每車注數(拖 1 膽配其餘號碼數)
    bet_per_note: float   # 每注金額
    cost_per_car: float   # 每車成本 = 注數 × 注金
    cars: int             # 車數
    total_notes: int      # 總注數
    total_cost: float     # 總成本
    odds: float
    ev_rate: float        # 期望報酬率
    exp_win_notes: float  # 期望中獎注數
    exp_return: float     # 期望回收金額


def tuo_plan(cars: int = 3, notes_per_car: int = 38, bet_per_note: float = 72.5,
             odds: float = BREAKEVEN_ODDS) -> TuoPlan:
    """拖牌包車試算。

    1 車 = 拖 1 個膽號配其餘 notes_per_car 個號碼(預設 38,即 1車=38注)。
    cars:買幾車(預設從 3 車起)。
    """
    total_notes = cars * notes_per_car
    cost_per_car = notes_per_car * bet_per_note
    total_cost = total_notes * bet_per_note
    exp_win_notes = total_notes * PAIR_PROB
    exp_return = exp_win_notes * odds * bet_per_note
    return TuoPlan(
        notes_per_car=notes_per_car,
        bet_per_note=bet_per_note,
        cost_per_car=cost_per_car,
        cars=cars,
        total_notes=total_notes,
        total_cost=total_cost,
        odds=odds,
        ev_rate=ev_rate(odds),
        exp_win_notes=exp_win_notes,
        exp_return=exp_return,
    )


# ── 倍頭(Martingale)進程表 ─────────────────────────────
@dataclass
class MartingaleStep:
    round: int
    cars: int
    round_cost: float
    cumulative_cost: float
    cars_to_break_even: float  # 此局起,要中幾車的獎才能把累積投入打平


@dataclass
class MartingaleTable:
    steps: list[MartingaleStep] = field(default_factory=list)
    multiplier: float = 2.0
    bust_round: int | None = None  # 第幾局累積成本超過資金(破產)


def martingale_table(base_cars: int = 3, multiplier: float = 2.0, rounds: int = 12,
                     cost_per_car: float = 2755.0, win_payout: float = 21200.0,
                     capital: float | None = None) -> MartingaleTable:
    """倍頭進程:連敗時每局車數乘以 multiplier(倍頭),列出車數與累積成本。

    cars_to_break_even:到此局為止的累積投入,需要中幾車的獎(每車中得 win_payout)才能打平,
    用來凸顯連敗後「要中幾車才回本」快速膨脹到不切實際。
    capital:給定資金時,標記第幾局累積成本超過資金(破產)。
    """
    steps: list[MartingaleStep] = []
    cumulative = 0.0
    cars = base_cars
    bust = None
    for r in range(1, rounds + 1):
        round_cost = cars * cost_per_car
        cumulative += round_cost
        need_cars = cumulative / win_payout if win_payout else float("inf")
        steps.append(MartingaleStep(r, cars, round_cost, cumulative, need_cars))
        if capital is not None and bust is None and cumulative > capital:
            bust = r
        cars = int(round(cars * multiplier))
    return MartingaleTable(steps=steps, multiplier=multiplier, bust_round=bust)
