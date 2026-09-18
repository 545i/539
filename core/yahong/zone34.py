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


def radar_response(game: str, draws_old_to_new: list[list[int]]) -> dict:
    """組出 API 端點 2 的 JSON。"""
    r = analyze_zone34(draws_old_to_new)
    coldest = r["coldest"]
    return {
        "game": game,
        "consecutiveMiss": r["consecutive_miss"],
        "strategyA": {
            "active": r["strategy_a"], "threshold": THR_A, "coldest": coldest,
            "note": "各區刪1冷號,壓至 756 碰",
        },
        "strategyB": {
            "active": r["strategy_b"], "threshold": THR_B,
            "note": "四區 1200 碰全包",
        },
        "columns": [
            {"label": _COLUMNS[i]["label"], "coldest": coldest[i]}
            for i in range(4)
        ],
    }
