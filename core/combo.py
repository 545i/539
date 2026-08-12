"""連碰 / 立柱 / 拖膽:民間組合下注的注數、成本與損益平衡。

三種下法看起來是三條公式,其實是同一條 —— 差別只在「一注裡有幾顆是你
指定死的(**膽**)」:

    連碰(全碰、天碰)  選 N 顆,任意 K 顆湊一注      注數 = C(N, K)
    立柱               1 顆膽 + 拖 M 顆              注數 = C(M, K−1)
    拖膽               D 顆膽 + 拖 M 顆              注數 = C(M, K−D)

膽是每一注都要用到的號碼,所以一注裡只剩 K−D 個位置要從拖的號碼裡挑:

    注數 = C(拖幾顆, 星數 − 膽幾顆)

連碰就是 D=0(全部從拖裡挑)、立柱就是 D=1。本模組只留這一條式子,
不為三種下法各寫一份 —— 那樣改了一邊忘了另一邊就會對不起來。
(「天二 / 天三」是二星 / 三星連碰的別名,算式完全相同,不另立一種。)

一注要中,**那一注的 K 顆得全部開出**。所以膽只要有一顆沒開整張就歸零,
膽全中時中的注數 = C(拖中幾顆, K−D)。

倍率是「賠率幾倍」不是「幾元」—— 二星 1賠53 指的是每注成本 × 53
(下 50 中 2,650),跟 core.star 的三星 570 是同一個意思。

core.star(三星 / 四星 記帳)是本模組在 N=8、D=0 的特例,它另外還管
對獎與流水;這裡只做試算,不碰資料庫。
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import ceil, comb

STARS = (2, 3, 4)
STAR_NAMES = {2: "二星", 3: "三星", 4: "四星"}

# 民間常見的參考賠率(倍)。各組頭不同,UI 上可以改;這只是進頁面的初值。
MARKET_ODDS: dict[int, float] = {2: 53.0, 3: 580.0, 4: 7500.0}

# 每注下多少錢的預設值(民間常見 2 元起跳)
DEFAULT_PER_BET = 2.0

# 對照表預設列出的顆數範圍
TABLE_SIZES = tuple(range(4, 16))


@dataclass(frozen=True)
class Play:
    """一種下法。dans 是固定的膽數;None 代表由使用者自己決定。"""
    key: str
    name: str
    dans: int | None
    desc: str


PLAYS: tuple[Play, ...] = (
    Play("combo", "連碰(全碰)", 0,
         "選幾顆就任意湊,每一注的號碼全部從你圈的裡面挑"),
    Play("pillar", "立柱", 1,
         "1 顆膽固定進每一注,其餘位置從拖的號碼挑"),
    Play("dan", "拖膽", None,
         "自己決定幾顆膽;膽全部進每一注,剩下的位置從拖的號碼挑"),
)
PLAY_BY_KEY = {p.key: p for p in PLAYS}


def play(key: str) -> Play:
    return PLAY_BY_KEY[key]


def star_name(stars: int) -> str:
    return STAR_NAMES.get(int(stars), f"{int(stars)} 星")


# ── 注數 ─────────────────────────────────────────────────
def bets(stars: int, drag: int, dans: int = 0) -> int:
    """注數 = C(拖幾顆, 星數 − 膽幾顆)。

    膽比星數多、或拖的顆數不夠挑時回 0 —— 那種組合湊不出任何一注。
    膽剛好等於星數是另一回事:那就是 1 注(你買的就是那幾顆膽),
    C(n,0)=1 在這裡是對的,不要一起擋掉。
    """
    need = int(stars) - int(dans)
    if need < 0 or int(dans) < 0 or int(drag) < need:
        return 0
    return comb(int(drag), need)


def bet_list(stars: int, drag_nums, dan_nums=()) -> list[tuple[int, ...]]:
    """實際的每一注:膽 + 從拖的號碼裡挑 K−D 顆,每注由小到大。

    給的是真的要拿去下的注單,不只是注數 —— 所以順序固定(注與注之間也排序),
    同一組輸入每次跑出來都一樣。
    """
    dan = sorted({int(n) for n in dan_nums})
    drag = sorted({int(n) for n in drag_nums} - set(dan))
    need = int(stars) - len(dan)
    if need < 0 or len(drag) < need:
        return []
    return sorted(tuple(sorted(dan + list(c))) for c in combinations(drag, need))


# ── 成本與獎金 ───────────────────────────────────────────
def total_cost(stars: int, drag: int, per_bet: float, dans: int = 0) -> float:
    """總成本 = 注數 × 每注多少錢。"""
    return bets(stars, drag, dans) * float(per_bet)


def prize_per_bet(per_bet: float, odds: float) -> float:
    """中一注可得 = 每注成本 × 倍率(二星 50 × 53 = 2,650)。"""
    return float(per_bet) * float(odds)


def breakeven_bets(stars: int, drag: int, odds: float, dans: int = 0) -> float:
    """要中幾注才打平 = 總成本 ÷ 中一注可得 = **注數 ÷ 倍率**。

    每注多少錢會約掉 —— 成本與獎金都線性於它,所以打平點跟下多大無關,
    只看你買了幾注、賠率多少。
    """
    n = bets(stars, drag, dans)
    return n / float(odds) if odds else float("inf")


# ── 中獎 ─────────────────────────────────────────────────
def hits(stars: int, matched_drag: int, dans: int = 0,
         matched_dans: int | None = None) -> int:
    """中的注數。膽沒全中就是 0;膽全中時 = C(拖中幾顆, 星數 − 膽幾顆)。

    matched_dans 留空代表「膽全中」(連碰沒有膽,預設就成立)。
    """
    d = int(dans)
    got = d if matched_dans is None else int(matched_dans)
    if got < d:
        return 0
    need = int(stars) - d
    if need < 0 or int(matched_drag) < need:
        return 0
    return comb(int(matched_drag), need)


def hits_of(stars: int, drawn, drag_nums, dan_nums=()) -> int:
    """直接由開獎號碼算中的注數。"""
    drawn = {int(n) for n in drawn}
    dan = {int(n) for n in dan_nums}
    drag = {int(n) for n in drag_nums} - dan
    return hits(stars, len(drag & drawn), len(dan), len(dan & drawn))


def possible_hits(stars: int, drag: int, dans: int = 0, num_max: int = 39,
                  pick: int = 5) -> list[int]:
    """這一張可能中的注數(由大到小),供下拉選單用。

    值域由列舉算出,不是 0..注數 全開 —— 例如三星拖 8 顆只可能中
    10 / 4 / 1 / 0 注,中 2 注這種事不存在,下拉裡就不該出現。
    """
    return sorted(hit_probs(stars, drag, dans, num_max, pick), reverse=True)


def result_text(hits_: int | None) -> str:
    """把中的注數翻成中文結果;None 代表還沒開獎。"""
    if hits_ is None:
        return "待開獎"
    return "槓龜" if int(hits_) <= 0 else f"中 {int(hits_):,} 注"


# ── 一張多支(等比放大)────────────────────────────────────
def round_cost(stars: int, drag: int, per_bet: float, dans: int = 0,
               sheets: int = 1) -> float:
    """本局成本 = 單支成本 × 支數(1 支 = 買滿這張的全部注數)。"""
    return total_cost(stars, drag, per_bet, dans) * int(sheets)


def round_payout(hits_: int, per_bet: float, odds: float, sheets: int = 1) -> float:
    """本局回收 = 中的注數 × 中一注可得 × 支數。"""
    return int(hits_) * prize_per_bet(per_bet, odds) * int(sheets)


def net_per_sheet(hits_: int, stars: int, drag: int, per_bet: float, odds: float,
                  dans: int = 0) -> float:
    """中 hits_ 注時,每 1 支的淨利 = 注數 × 每注可得 − 單支成本。"""
    return (round_payout(hits_, per_bet, odds)
            - total_cost(stars, drag, per_bet, dans))


def sheets_for_recovery(loss: float, hits_: int, stars: int, drag: int,
                        per_bet: float, odds: float, dans: int = 0,
                        base: int = 1) -> dict:
    """要靠「中 hits_ 注」把 loss 一次追平,最少得下幾支。

    刻意由呼叫端指定要押哪一種結果,而不是預設用最好情況 —— 全中的機率
    通常是萬分之一等級,拿它當回本基準等於在畫大餅。
    """
    gain = net_per_sheet(hits_, stars, drag, per_bet, odds, dans)
    loss = max(0.0, float(loss))
    if gain <= 0:
        return {"feasible": False, "sheets": None, "cost": None,
                "gain_per_sheet": gain}
    sheets = max(int(base), ceil(loss / gain)) if loss > 0 else int(base)
    return {"feasible": True, "sheets": sheets,
            "cost": round_cost(stars, drag, per_bet, dans, sheets),
            "gain_per_sheet": gain}


# ── 歷史檢驗 ─────────────────────────────────────────────
def history_stats(draws, stars: int, drag_nums, dan_nums=(),
                  pick: int = 5) -> dict:
    """拿**固定一張牌**(同一組拖與膽)回頭跑一串開獎紀錄(舊 → 新)。

    顆數不符的期直接略過 —— 資料還沒補齊時不該被算成槓龜。
    這張表是用來說明「換一組號碼不會比較好」的:每一張的理論返還率完全
    相同,實際差異只是樣本雜訊。

    回傳 rounds/skipped/wins/win_rate/total_hits/hit_counts/
    streak/max_streak/last_draw/last_hits。
    """
    valid = [list(d) for d in draws if d and len(d) == int(pick)]
    got = [hits_of(stars, d, drag_nums, dan_nums) for d in valid]

    max_streak = streak = 0
    for h in got:                        # 舊 → 新;連續槓龜最長的一段
        streak = streak + 1 if h == 0 else 0
        max_streak = max(max_streak, streak)
    cur = 0
    for h in reversed(got):              # 新 → 舊;目前連幾期沒中
        if h != 0:
            break
        cur += 1

    counts: dict[int, int] = {}
    for h in got:
        counts[h] = counts.get(h, 0) + 1
    wins = sum(1 for h in got if h > 0)
    return {
        "rounds": len(valid),
        "skipped": len(list(draws)) - len(valid),
        "wins": wins,
        "win_rate": wins / len(valid) if valid else 0.0,
        "total_hits": sum(got),
        "hit_counts": dict(sorted(counts.items())),
        "streak": cur,
        "max_streak": max_streak,
        "last_draw": valid[-1] if valid else [],
        "last_hits": got[-1] if got else 0,
    }


# ── 機率(組合數列舉,不寫死百分比)──────────────────────
def hit_probs(stars: int, drag: int, dans: int = 0, num_max: int = 39,
              pick: int = 5) -> dict[int, float]:
    """中的注數 → 機率。

    號碼分成三群:膽 D 顆、拖 M 顆、其餘 num_max−D−M 顆,開獎 pick 顆的
    分佈是超幾何 —— 膽中 a 顆、拖中 b 顆的組合數 =
    C(D,a)·C(M,b)·C(其餘, pick−a−b),再依 hits 彙總。
    """
    d, m = int(dans), int(drag)
    rest = int(num_max) - d - m
    if rest < 0:
        raise ValueError(f"膽 {d} + 拖 {m} 顆超過號碼總數 {num_max}")
    total = comb(int(num_max), int(pick))
    out: dict[int, float] = {}
    for a in range(min(d, pick) + 1):
        for b in range(min(m, pick - a) + 1):
            c = int(pick) - a - b
            if c < 0 or c > rest:
                continue
            ways = comb(d, a) * comb(m, b) * comb(rest, c)
            h = hits(stars, b, d, a)
            out[h] = out.get(h, 0.0) + ways / total
    return dict(sorted(out.items()))


def win_prob(stars: int, drag: int, dans: int = 0, num_max: int = 39,
             pick: int = 5) -> float:
    """至少中一注的機率。"""
    return sum(p for h, p in hit_probs(stars, drag, dans, num_max, pick).items()
               if h > 0)


def single_bet_prob(stars: int, num_max: int = 39, pick: int = 5) -> float:
    """**一注**中獎的機率 = C(pick, K) / C(num_max, K)。

    一注要中就是它的 K 顆全在開出的 pick 顆裡,跟你買了幾注、有沒有膽無關。
    """
    return comb(int(pick), int(stars)) / comb(int(num_max), int(stars))


def expected_hits(stars: int, drag: int, dans: int = 0, num_max: int = 39,
                  pick: int = 5) -> float:
    """每期期望中幾注 = 注數 × 單注中獎機率。

    每一注中獎的機率都一樣,期望值可以直接相加 —— 所以不必管注與注之間
    重疊多少。這條路徑與列舉 hit_probs 的結果相等(見測試)。
    """
    return bets(stars, drag, dans) * single_bet_prob(stars, num_max, pick)


# ── 期望值 ───────────────────────────────────────────────
def fair_odds(stars: int, num_max: int = 39, pick: int = 5) -> float:
    """單注的公平賠率 = 1 ÷ 單注中獎機率 = C(num_max,K) / C(pick,K)。

    39 選 5 下:二星 74.1、三星 913.9、四星 16,450.2。
    """
    p = single_bet_prob(stars, num_max, pick)
    return 1.0 / p if p else float("inf")


def return_rate(stars: int, odds: float, num_max: int = 39,
                pick: int = 5) -> float:
    """返還率 = **倍率 ÷ 公平賠率**。

    這是整個模組最該記住的一件事:返還率跟你選幾顆、幾個膽、每注下多少
    **完全無關**。買越多注只是把成本與期望回收一起等比放大,比例不動。
    39 選 5 的市場參考價:二星 53/74.1 = 71.5%、三星 580/913.9 = 63.5%、
    四星 7500/16,450.2 = 45.6% —— 三者都 < 1,沒有哪一種比較划算。
    """
    fair = fair_odds(stars, num_max, pick)
    return float(odds) / fair if fair else 0.0


def expected_net(stars: int, drag: int, per_bet: float, odds: float,
                 dans: int = 0, num_max: int = 39, pick: int = 5) -> float:
    """每期期望損益(負值 = 長期淨輸)。"""
    cost = total_cost(stars, drag, per_bet, dans)
    e = expected_hits(stars, drag, dans, num_max, pick)
    return e * prize_per_bet(per_bet, odds) - cost


def breakeven_odds(stars: int, num_max: int = 39, pick: int = 5) -> float:
    """損益兩平的倍率 —— 就是公平賠率本身。"""
    return fair_odds(stars, num_max, pick)


# ── 對照表 ───────────────────────────────────────────────
def bets_table(dans: int = 0, sizes=TABLE_SIZES, stars=STARS) -> list[dict]:
    """「拖幾顆 → 各星數各幾注」的對照表;注數 0 的格子留 None 由呼叫端處理。"""
    return [{"drag": int(n),
             **{int(k): (bets(k, n, dans) or None) for k in stars}}
            for n in sizes]
