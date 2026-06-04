"""回測引擎:用歷史資料模擬投注,計算命中分布與報酬率。

關鍵正確性:防 look-ahead bias —— 選第 N 期的號碼時,只能用第 N 期「之前」的資料。
任何策略長期報酬率都應收斂到約 -44%。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.constants import PICK, PRIZE, TICKET_PRICE
from core.loader import draws_as_lists
from core.picker import pick


@dataclass
class BacktestResult:
    strategy: str
    periods: int                       # 實際回測期數
    bet_per_period: int                # 每期注數
    hit_dist: dict = field(default_factory=dict)  # 中 k 碼的注數
    total_bet: int = 0
    total_return: int = 0

    @property
    def roi(self) -> float:
        return (self.total_return - self.total_bet) / self.total_bet if self.total_bet else 0.0


def run(df: pd.DataFrame, strategy: str = "random", start_index: int = 100,
        bet: int = 1, seed: int = 539) -> BacktestResult:
    """從第 start_index 期起回測到最後一期。

    start_index:至少要留一段前置資料給冷熱號/頻率策略使用。
    bet:每期投注幾組(注)。
    """
    draws = draws_as_lists(df)
    n = len(draws)
    if start_index < 1:
        start_index = 1
    if start_index >= n:
        raise ValueError(f"start_index={start_index} 須小於總期數 {n}")

    hit_dist = {k: 0 for k in range(PICK + 1)}
    total_bet = 0
    total_return = 0

    for i in range(start_index, n):
        past = df.iloc[:i]                       # 只用第 i 期之前的資料(防 look-ahead)
        actual = set(draws[i])
        # 每期用不同 seed,確保各期選號獨立但整體可重現
        tickets = pick(past, strategy=strategy, sets=bet, seed=seed + i)
        for ticket in tickets:
            k = len(actual & set(ticket))
            hit_dist[k] += 1
            total_bet += TICKET_PRICE
            total_return += PRIZE[k]

    return BacktestResult(
        strategy=strategy,
        periods=n - start_index,
        bet_per_period=bet,
        hit_dist=hit_dist,
        total_bet=total_bet,
        total_return=total_return,
    )


def compare(df: pd.DataFrame, strategies: list[str], start_index: int = 100,
            bet: int = 1, seed: int = 539) -> list[BacktestResult]:
    """多策略同台 PK,證明都收斂到約 -44%。"""
    return [run(df, s, start_index=start_index, bet=bet, seed=seed) for s in strategies]
