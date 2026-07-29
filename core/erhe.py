"""二合(二星)買牌試算:中獎機率、成本、期望投報、凱莉、倍頭(Martingale)。

二合玩法(以今彩539 的 39 選 5 開獎為基礎):
  選 2 個號碼,當期開出的 5 個號碼若同時包含這 2 個,即中獎。

模組常數(PAIR_PROB / DAN_PROB)是今彩539 的值;六合彩(49 選 6)等其他玩法,
呼叫端傳入 dan_prob / pick / num_max 即可(GameConfig 有對應欄位)。

誠實前提:
  - 二合單組中獎機率固定為 C(37,3)/C(39,5) ≈ 1/74.1,且每號真實開機率相同。
  - 期望報酬率 = 中獎機率 × 賠率 − 1,只由「賠率」決定,與選哪些號碼無關。
  - 賠率 < 74.1 為負期望(凱莉建議 0、倍投必破產);> 74.1 才正期望。
"""
from __future__ import annotations

import random
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
def car_ev_rate(cost_per_car: float, win_payout: float,
                dan_prob: float = DAN_PROB) -> float:
    """拖牌車的期望報酬率。

    車「中」(膽號被開出,機率 dan_prob = pick/num_max)時收到 win_payout,否則 0。
    期望報酬率 = dan_prob × win_payout / cost_per_car − 1。
    """
    return dan_prob * win_payout / cost_per_car - 1.0


def car_kelly_fraction(cost_per_car: float, win_payout: float,
                       dan_prob: float = DAN_PROB) -> float:
    """拖牌車的凱莉建議下注比例(車級二元賭局)。

    勝率 p = dan_prob(539 為 5/39、六合彩為 6/49);
    淨賠率 b = (win_payout − cost)/cost。負期望時為 0。
    """
    b = (win_payout - cost_per_car) / cost_per_car
    if b <= 0:
        return 0.0
    return max(0.0, kelly.kelly_binary(dan_prob, b))


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


# ── 互動回本計算(輸入結果 → 下一局車數)─────────────────
from math import ceil  # noqa: E402


def round_net(cars: float, hits: int, n_numbers: int,
              cost_per_car: float, win_payout: float) -> float:
    """一局的淨損益 = 中 hits 顆的回收 − 該局成本。

    成本 = n_numbers × cars × cost_per_car;回收 = hits × cars × win_payout。
    """
    cost = n_numbers * cars * cost_per_car
    payout = hits * cars * win_payout
    return payout - cost


def per_car_one_hit_net(n_numbers: int, cost_per_car: float, win_payout: float) -> float:
    """每車押 n_numbers 顆、恰中 1 顆時,每 1 車的淨利。

    = 中獎金額 − n_numbers × 每車成本。>0 才可能用「中1顆」回本。
    """
    return win_payout - n_numbers * cost_per_car


def next_cars_for_recovery(cumulative_net: float, n_numbers: int,
                           cost_per_car: float, win_payout: float,
                           base_cars: int = 3) -> dict:
    """根據目前累積損益,算下一局該下幾車,使『中 1 顆』即回本。

    回傳 dict:
      next_cars        下一局建議車數(已回本/獲利時回到 base_cars)
      per_car_1hit     中 1 顆每車淨利
      recovered        目前是否已回本(累積 >= 0)
      can_recover_1hit 是否可能靠中 1 顆回本(per_car_1hit > 0)
      next_cost        下一局成本 = n_numbers × next_cars × 每車成本
    """
    per1 = per_car_one_hit_net(n_numbers, cost_per_car, win_payout)
    recovered = cumulative_net >= 0
    if recovered:
        next_cars = base_cars
    elif per1 <= 0:
        next_cars = float("inf")  # 中 1 顆永遠不夠回本
    else:
        next_cars = max(base_cars, ceil(-cumulative_net / per1))
    next_cost = (n_numbers * next_cars * cost_per_car
                 if next_cars != float("inf") else float("inf"))
    return {
        "next_cars": next_cars,
        "per_car_1hit": per1,
        "recovered": recovered,
        "can_recover_1hit": per1 > 0,
        "next_cost": next_cost,
    }


# ── 多顆數進程(每局押 N 顆、車數依進程加碼)──────────────
def hit_distribution(n_numbers: int, pick: int = constants.PICK,
                     num_max: int = constants.NUM_MAX) -> dict[int, float]:
    """每局押 n_numbers 顆,中 k 顆的機率(超幾何分布)。

    P(中k顆) = C(n,k)·C(num_max−n, pick−k) / C(num_max, pick),k = 0..min(n, pick)。
    """
    total = comb(num_max, pick)
    out = {}
    for k in range(0, min(n_numbers, pick) + 1):
        out[k] = comb(n_numbers, k) * comb(num_max - n_numbers, pick - k) / total
    return out


def per_round_ev_rate(cost_per_car: float, win_payout: float,
                      dan_prob: float = DAN_PROB) -> float:
    """每局(任一車級)期望報酬率;與顆數、車數無關,恆為單號 EV。"""
    return dan_prob * win_payout / cost_per_car - 1.0


@dataclass
class ProgRow:
    round: int
    cars: int
    round_cost: float
    cumulative_cost: float
    payout_per_hit: float       # 該局每中 1 號的回收 = 車數 × 中獎金額
    break_even_hits: float      # 到此局累積投入,需中幾號才打平
    busted: bool                # 累積成本是否已超過資金


def progression_table_multi(progression=(3, 5, 7, 10, 13), n_numbers: int = 5,
                            cost_per_car: float = 2755.0, win_payout: float = 21200.0,
                            capital: float = 500000.0) -> list[ProgRow]:
    """連敗情境的進程成本表(每局押 n_numbers 顆,車數依 progression 加碼)。"""
    rows: list[ProgRow] = []
    cum = 0.0
    for i, c in enumerate(progression, 1):
        cost = n_numbers * c * cost_per_car
        cum += cost
        pay_hit = c * win_payout
        rows.append(ProgRow(
            round=i, cars=c, round_cost=cost, cumulative_cost=cum,
            payout_per_hit=pay_hit, break_even_hits=cum / pay_hit if pay_hit else float("inf"),
            busted=cum > capital,
        ))
    return rows


@dataclass
class ProgMultiResult:
    progression: list[float]
    n_numbers: int
    per_round_ev: float
    p_lose_round: float          # 每局全沒中(輸、需加碼)機率
    p_win_round: float           # 每局中 ≥1 號(重置)機率
    ruin_rate: float
    final_capital: float
    curve: list[float]
    avg_final_capital: float


def progression_sim_multi(progression=(3, 5, 7, 10, 13), n_numbers: int = 5,
                          cost_per_car: float = 2755.0, win_payout: float = 21200.0,
                          capital: float = 500000.0, rounds: int = 200,
                          trials: int = 500, seed: int = 539,
                          pick: int = constants.PICK,
                          num_max: int = constants.NUM_MAX) -> ProgMultiResult:
    """蒙地卡羅模擬「每局押 N 顆、輸了加碼、中獎重置」策略。

    每局押 n_numbers 顆,車級取自 progression(連敗格 index,超出停最後一格);
    成本 = n_numbers × 車 × cost_per_car;依超幾何抽出中 k 顆;
    回收 = k × 車 × win_payout;中 ≥1 號則重置回進程起點,否則加碼。
    """
    prog = list(progression)
    nlen = len(prog)
    dist = hit_distribution(n_numbers, pick, num_max)
    cum_dist = []
    acc = 0.0
    for k in sorted(dist):
        acc += dist[k]
        cum_dist.append((k, acc))
    p_lose = dist.get(0, 0.0)

    ruined = 0
    finals = []
    sample = None
    for t in range(trials):
        r = random.Random(seed + t)
        cap = capital
        curve = [cap]
        step = 0
        bust = False
        for _ in range(rounds):
            c = prog[min(step, nlen - 1)]
            cost = n_numbers * c * cost_per_car
            if cap < cost:
                bust = True
                break
            cap -= cost
            # 抽中 k 顆
            u = r.random()
            k = cum_dist[-1][0]
            for kk, cp in cum_dist:
                if u <= cp:
                    k = kk
                    break
            cap += k * c * win_payout
            step = 0 if k >= 1 else step + 1
            curve.append(cap)
        if bust:
            ruined += 1
        finals.append(cap)
        if t == 0:
            sample = (cap, curve)
    final_cap, curve = sample
    return ProgMultiResult(
        progression=prog,
        n_numbers=n_numbers,
        per_round_ev=per_round_ev_rate(cost_per_car, win_payout, pick / num_max),
        p_lose_round=p_lose,
        p_win_round=1.0 - p_lose,
        ruin_rate=ruined / trials,
        final_capital=final_cap,
        curve=curve,
        avg_final_capital=sum(finals) / len(finals),
    )


# ── 進程策略(自訂車數序列 + 中獎重置)──────────────────
@dataclass
class ProgressionResult:
    progression: list[float]      # 連敗時的車數序列,例如 [3, 5, 7.5, 10]
    win_prob: float               # 每局中獎機率(整車「中」)
    per_round_ev: float           # 每局期望報酬率(與車數無關)
    p_win_in_progression: float   # 在整個進程內(連 len 局)至少中一次的機率
    expected_rounds_to_win: float # 期望幾局才中(= 1/p)
    expected_cars_to_win: float   # 期望累積下注幾車才中(含進程加碼)
    final_capital: float          # 模擬代表路徑的最終資金
    ruin_rate: float              # 多次模擬的破產比例
    curve: list[float]            # 代表路徑的資金曲線


def progression_sim(progression=(3, 5, 7.5, 10), win_prob: float = DAN_PROB,
                    cost_per_car: float = 2755.0, win_payout: float = 21200.0,
                    rounds: int = 200, start_capital: float = 100000.0,
                    trials: int = 300, seed: int = 539) -> ProgressionResult:
    """模擬「固定車數進程 + 中獎重置」策略。

    每局押 progression[step] 車(step 為目前連敗格,超出則停在最後一格);
    成本 = 車數 × cost_per_car;以 win_prob 判定是否中;
    中了領 車數 × win_payout 並把 step 歸 0(回到進程起點),否則 step+1。

    win_prob 預設為拖牌單車膽中機率 5/39。每局期望報酬率 = win_prob×回收/成本 − 1,
    與車數無關;進程只改變下注大小與破產風險,改變不了期望值。
    """
    prog = list(progression)
    n = len(prog)
    per_round_ev = win_prob * win_payout / cost_per_car - 1.0
    p_win_in = 1.0 - (1.0 - win_prob) ** n
    expected_rounds = 1.0 / win_prob if win_prob > 0 else float("inf")

    # 期望累積車數才中(幾何分布,進程超出後停在最後一格)
    exp_cars = 0.0
    cum_cars = 0.0
    prob_reach = 1.0
    # E[cars to win] = Σ_{k>=1} P(連敗 k-1 後第 k 局中) × (前 k 局累積車數)
    for k in range(1, 2000):
        cars_k = prog[min(k - 1, n - 1)]
        cum_cars += cars_k
        p_first_win_here = ((1.0 - win_prob) ** (k - 1)) * win_prob
        exp_cars += p_first_win_here * cum_cars
        prob_reach *= (1.0 - win_prob)
        if prob_reach < 1e-9:
            break

    rng = random.Random(seed)
    ruined = 0
    sample_curve = None
    for t in range(trials):
        r = random.Random(seed + t)
        capital = start_capital
        curve = [capital]
        step = 0
        is_ruined = False
        for _ in range(rounds):
            cars = prog[min(step, n - 1)]
            cost = cars * cost_per_car
            if capital < cost:
                is_ruined = True
                break
            capital -= cost
            if r.random() < win_prob:
                capital += cars * win_payout
                step = 0
            else:
                step += 1
            curve.append(capital)
        if is_ruined:
            ruined += 1
        if t == 0:
            sample_curve = (capital, curve)
    final_cap, curve = sample_curve
    return ProgressionResult(
        progression=prog,
        win_prob=win_prob,
        per_round_ev=per_round_ev,
        p_win_in_progression=p_win_in,
        expected_rounds_to_win=expected_rounds,
        expected_cars_to_win=exp_cars,
        final_capital=final_cap,
        ruin_rate=ruined / trials,
        curve=curve,
    )
