"""同區 3-4 球 —— 忠實移植 spec-zone34.md。

監控「同區(柱)同時開出 3 顆以上」已連續幾期沒發生,連槓達 5 / 7 觸發兩策略。
全頁無機率常數,唯一可調參數是兩個整數門檻 5 與 7(照抄)。
"""
from __future__ import annotations

# 門檻常數(spec-zone34 §③彙整)
THRESHOLD_HIT = 3    # 某柱單期 >= 3 顆視為命中,連槓歸零
THR_A = 5            # 策略 A 觸發連槓
THR_B = 7            # 策略 B 觸發連槓

_COLUMNS = [
    {"label": "第1柱 (01-09)", "lo": 1, "hi": 9},
    {"label": "第2柱 (10-19)", "lo": 10, "hi": 19},
    {"label": "第3柱 (20-29)", "lo": 20, "hi": 29},
    {"label": "第4柱 (30-39)", "lo": 30, "hi": 39},
]


def analyze_zone34(draws_old_to_new: list[list[int]],
                   threshold_hit: int = THRESHOLD_HIT,
                   thr_a: int = THR_A, thr_b: int = THR_B) -> dict:
    """draws_old_to_new:由舊到新的開獎序列(idx 0 = 最舊)。

    回:consecutive_miss、四柱最冷號 coldest[c1..c4]、strategy_a/b 是否達標。
    """
    last_seen = {i: -1 for i in range(1, 40)}
    consecutive_miss = 0
    for idx, draw in enumerate(draws_old_to_new):
        zones = [0, 0, 0, 0]
        for raw in draw:
            n = int(raw)
            if 1 <= n <= 39:
                last_seen[n] = idx
            if n <= 9:
                zones[0] += 1
            elif n <= 19:
                zones[1] += 1
            elif n <= 29:
                zones[2] += 1
            else:
                zones[3] += 1
        consecutive_miss = 0 if max(zones) >= threshold_hit else consecutive_miss + 1

    def coldest(start: int, end: int) -> int:
        # last_seen 最小者;平手取號碼小者(對應原檔嚴格 < 更新)
        return min(range(start, end + 1), key=lambda i: (last_seen[i], i))

    coldest_by_zone = [coldest(c["lo"], c["hi"]) for c in _COLUMNS]
    return {
        "consecutive_miss": consecutive_miss,
        "coldest": coldest_by_zone,
        "strategy_a": consecutive_miss >= thr_a,
        "strategy_b": consecutive_miss >= thr_b,
    }


def _zones(draw: list[int]) -> list[int]:
    z = [0, 0, 0, 0]
    for raw in draw:
        n = int(raw)
        if 1 <= n <= 9:
            z[0] += 1
        elif 10 <= n <= 19:
            z[1] += 1
        elif 20 <= n <= 29:
            z[2] += 1
        elif 30 <= n <= 39:
            z[3] += 1
    return z


# 極端偏態雷達(原站 index.html analyzeRadar)常數照抄
EXT_WINDOW = 1500
EXT_BASE_TRIPLE = 0.357          # 任一柱 >=3 的基準機率
EXT_TRIPLE_STEP = 0.015          # 每連漏 1 期 +1.5%
EXT_TRIPLE_CAP = 0.95
EXT_COL_BASE = [0.0702, 0.0956, 0.0956, 0.0956]   # 第1柱 9 顆,其餘 10 顆
EXT_COL_STEP = 0.005
EXT_COL_CAP = 0.99


def extreme_radar(draws_old_to_new: list[list[int]]) -> dict:
    """極端偏態雷達:最近 1500 期內,大盤/各柱「同柱 >=3 顆」目前連漏幾期,
    依連漏線性加成出「爆發機率」,機率最高的柱為最危險區域。"""
    data = list(reversed(draws_old_to_new))[:EXT_WINDOW]   # 新→舊
    triple_streak, overall_found = 0, False
    col_streaks = [0, 0, 0, 0]
    col_found = [False] * 4
    col_hits = [0, 0, 0, 0]
    for draw in data:
        z = _zones(draw)
        for i in range(4):
            if z[i] >= 3:
                col_hits[i] += 1
        if not overall_found:
            if max(z) >= 3:
                overall_found = True
            else:
                triple_streak += 1
        for i in range(4):
            if not col_found[i]:
                if z[i] >= 3:
                    col_found[i] = True
                else:
                    col_streaks[i] += 1
    triple_prob = min(EXT_BASE_TRIPLE + triple_streak * EXT_TRIPLE_STEP, EXT_TRIPLE_CAP)
    col_probs = [min(EXT_COL_BASE[i] + col_streaks[i] * EXT_COL_STEP, EXT_COL_CAP)
                 for i in range(4)]
    mx = max(col_probs)
    return {
        "totalDraws": len(data),
        "tripleStreak": triple_streak,
        "tripleNextProb": round(triple_prob, 4),
        "columns": [
            {"label": _COLUMNS[i]["label"], "streak": col_streaks[i],
             "hits": col_hits[i], "prob": round(col_probs[i], 4),
             "danger": col_probs[i] == mx}
            for i in range(4)
        ],
    }


QUANT_MIN = 30


def quant_zones(draws_old_to_new: list[list[int]]) -> dict | None:
    """同區戰情室「新系統」(原站 3or4.html runQuantModel):6 因子分區評分 →
    正規化成百分比,最高者為今晚最佳打擊區。歷史 < 30 期回 None。"""
    history = [_zones(d) for d in draws_old_to_new]
    if len(history) < QUANT_MIN:
        return None
    scores = [0.0] * 4
    recent = history[-50:]
    # 1. 均值回歸(原檔固定以 50 期計期望值)
    total = [sum(d[i] for d in recent) for i in range(4)]
    expected = 50 * 5 / 4
    for i in range(4):
        scores[i] += (expected - total[i]) * 1.5
    # 2. SMA5 動能
    for i in range(4):
        scores[i] += sum(d[i] for d in history[-5:]) * 2.0
    # 3. EWMA(alpha 0.2,起始 0)
    ewma = [0.0] * 4
    for d in recent:
        for i in range(4):
            ewma[i] = d[i] * 0.2 + ewma[i] * 0.8
    for i in range(4):
        scores[i] += ewma[i] * 10
    # 4. 布林擠壓(變異數越小加越多;原檔分母固定 50)
    for i in range(4):
        mean = total[i] / 50
        var = sum((d[i] - mean) ** 2 for d in recent) / 50
        scores[i] += (2 - var) * 5
    # 5. 馬可夫轉移:上期最多球的區 → 下一期最多球的區(平手取前者)
    argmax = lambda z: z.index(max(z))
    hot_last = argmax(history[-1])
    trans = [0, 0, 0, 0]
    for a, b in zip(history, history[1:]):
        if argmax(a) == hot_last:
            trans[argmax(b)] += 1
    for i in range(4):
        scores[i] += trans[i] * 0.5
    # 6. 泊松加成:近 50 期該區 >=3 次數
    for i in range(4):
        scores[i] += sum(1 for d in recent if d[i] >= 3) * 2
    lo = min(scores)
    scores = [s - lo + 10 for s in scores]
    tot = sum(scores)
    pct = [round(s / tot * 100, 1) for s in scores]
    best = pct.index(max(pct))
    return {
        "pct": pct,
        "best": best,
        "labels": [f"第 {i + 1} 區 ({c['lo']:02d}-{c['hi']:02d})" for i, c in enumerate(_COLUMNS)],
    }


def radar_response(game: str, draws_old_to_new: list[list[int]]) -> dict:
    """組出 API 端點 2 的 JSON。"""
    r = analyze_zone34(draws_old_to_new)
    coldest = r["coldest"]
    return {
        "extreme": extreme_radar(draws_old_to_new),
        "quant": quant_zones(draws_old_to_new),
        "game": game,
        "consecutiveMiss": r["consecutive_miss"],
        "strategyA": {
            "active": r["strategy_a"], "threshold": THR_A, "coldest": coldest,
            "note": "各區刪1冷號,壓至 756 碰",
        },
        "strategyB": {
            "active": r["strategy_b"], "threshold": THR_B,
            "note": "保本防呆,四區 1200 碰全包",
        },
        "columns": [
            {"label": _COLUMNS[i]["label"], "coldest": coldest[i]}
            for i in range(4)
        ],
    }
