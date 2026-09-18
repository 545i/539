"""綜合分析(唯讀)—— lotto539 依 spec-539.md、fantasy5 依 spec-fantasy.md。

⚠️ 兩款演算法**不同**,不可強制共用(API.md 舊敘述有誤,已由團隊修正):
- probScore:539 為 2 因子(freq0.65+rebound0.35,視窗 50);天天樂為 3 因子
  (freq0.35+recent0.35+rebound0.30,視窗 15,rebound 門檻不同)。
- 柱碰看板 nextProb:539 用幾何 1-(1-baseP)^(miss+1);天天樂用線性 boost
  min(p_base*(1+0.15*gap/avgCycle),0.99)。
JSON 形狀維持 API.md(欄位同、值依 game 不同);probScore 項目帶出該款實際用到的因子。
不含「AI vs 我 對戰紀錄」。
"""
from __future__ import annotations

import math
import random

# 柱碰基礎機率:539 與天天樂的 9000 常數不同(0.2736 vs 0.2735,照各自 spec)
BASE_P_1800 = 0.5536
BASE_P_9000_539 = 0.2736
BASE_P_9000_FANTASY = 0.2735

NEVER_539 = None       # 539 未出現 → missingStreak = 總期數(見 _num_stats)
NEVER_FANTASY = 999    # 天天樂未出現 → lastSeenAgo = 999


# ── 柱位定義(1800 三柱 / 9000 四柱;§B 各至少 1 顆才算命中)──
def _cols_1800(draw) -> tuple[bool, bool, bool]:
    c1 = c2 = c3 = False
    for x in draw:
        n = int(x)
        if 10 <= n <= 18:
            c1 = True
        elif 20 <= n <= 29:
            c2 = True
        else:
            c3 = True
    return c1, c2, c3


def _cols_9000(draw) -> tuple[bool, bool, bool, bool]:
    c1 = c2 = c3 = c4 = False
    for x in draw:
        n = int(x)
        if 1 <= n <= 9:
            c1 = True
        elif n <= 19:
            c2 = True
        elif n <= 29:
            c3 = True
        elif n <= 39:
            c4 = True
    return c1, c2, c3, c4


def _is_hit_1800(draw) -> bool:
    return all(_cols_1800(draw))


def _is_hit_9000(draw) -> bool:
    return all(_cols_9000(draw))


# ── 柱碰看板 ─────────────────────────────────────────────────
def _miss(data: list[list[int]], is_hit) -> int:
    """從最新(data[0])往回,連續未命中期數(碰到第一個命中就停)。"""
    m = 0
    for draw in data:
        if is_hit(draw):
            break
        m += 1
    return m


def _pillar_539(data, is_hit, base_p: float, kind: str) -> dict:
    """spec-539 §B:幾何反彈機率 + 徽章(1800:>95/>80、9000:>85/>70)。"""
    miss = _miss(data, is_hit)
    next_prob = (1 - (1 - base_p) ** (miss + 1)) * 100
    if kind == "1800":
        if next_prob > 95:
            badge, text = "alert", "🚨 極限警戒必出"
        elif next_prob > 80:
            badge, text = "ready", "⚡ 蓄勢開出中"
        else:
            badge, text = "ok", "✅ 安全常規區間"
    else:
        if next_prob > 85:
            badge, text = "alert", "🚨 嚴重偏離必開"
        elif next_prob > 70:
            badge, text = "ready", "⚡ 進入高期望期"
        else:
            badge, text = "ok", "✅ 安全常規區間"
    return {"miss": miss, "nextProb": round(next_prob, 2), "badge": badge, "badgeText": text}


def _pillar_fantasy(data, is_hit, base_p: float) -> dict:
    """spec-fantasy §立柱:線性 boost + 週期燈號(gap>avgCycle 紅 / ==⌊avgCycle⌋ 黃 / else 綠)。"""
    n = len(data)
    gap = _miss(data, is_hit)
    hits = sum(1 for draw in data if is_hit(draw))
    avg_cycle = (n / hits) if hits > 0 else (1 / base_p if base_p > 0 else 0.0)
    boost = (gap / avg_cycle) * 0.15 if avg_cycle > 0 else 0.0
    final_prob = min(base_p * (1 + boost), 0.99) * 100
    if avg_cycle > 0 and gap > avg_cycle:
        badge, text = "alert", "🚨 漏期達標,強烈建議進場"
    elif avg_cycle > 0 and gap == math.floor(avg_cycle) and gap > 0:
        badge, text = "ready", "⚠️ 接近週期,可準備佈局"
    else:
        badge, text = "ok", "✅ 剛開出不久,建議繼續觀望"
    return {"miss": gap, "nextProb": round(final_prob, 2), "badge": badge, "badgeText": text,
            "avgCycle": round(avg_cycle, 2), "histProb": round(hits / n * 100, 2) if n else 0.0}


# ── 逐號統計 ─────────────────────────────────────────────────
def _num_stats(data: list[list[int]], game: str) -> dict[int, dict]:
    """每號:遺漏(lastSeenAgo)、近 50/15 期次數、總次數。data 新→舊。

    未出現的遺漏值:539 = 總期數;天天樂 = 999(照各自 spec)。
    """
    n = len(data)
    max50 = min(50, n)
    max15 = min(15, n)
    never = n if game == "lotto539" else NEVER_FANTASY
    stats: dict[int, dict] = {}
    for num in range(1, 40):
        streak = never
        for d, draw in enumerate(data):
            if num in draw:
                streak = d
                break
        stats[num] = {
            "num": num, "missingStreak": streak,
            "recent50Count": sum(1 for draw in data[:max50] if num in draw),
            "recent15Count": sum(1 for draw in data[:max15] if num in draw),
            "totalCount": sum(1 for draw in data if num in draw),
        }
    return stats


def _rebound_539(miss: int) -> int:
    """spec-539:遺漏 5~12→95 / =0→75 / >20→35 / 其餘 50。"""
    if 5 <= miss <= 12:
        return 95
    if miss == 0:
        return 75
    if miss > 20:
        return 35
    return 50


def _rebound_fantasy(last_seen_ago: int) -> int:
    """spec-fantasy:gap∈[2,5]→95 / gap∈{0,1}→80 / else 40。"""
    if 2 <= last_seen_ago <= 5:
        return 95
    if last_seen_ago in (0, 1):
        return 80
    return 40


def _prob_scores(stats: dict[int, dict], n: int, game: str) -> list[dict]:
    """probScore(降序)。539:freq0.65+rebound0.35;天天樂:freq0.35+recent0.35+rebound0.30。"""
    out = []
    if game == "lotto539":
        max50 = min(50, n) or 1
        for num in range(1, 40):
            s = stats[num]
            freq = (s["recent50Count"] / max50) * 100
            rebound = _rebound_539(s["missingStreak"])
            score = freq * 0.65 + rebound * 0.35
            out.append({"num": num, "score": round(score, 4), "freq": round(freq, 4),
                        "rebound": rebound, "miss": s["missingStreak"],
                        "recent50": s["recent50Count"]})
    else:
        total = n or 1
        max15 = min(15, n) or 1
        for num in range(1, 40):
            s = stats[num]
            freq = (s["totalCount"] / total) * 100
            recent = (s["recent15Count"] / max15) * 100
            rebound = _rebound_fantasy(s["missingStreak"])
            score = freq * 0.35 + recent * 0.35 + rebound * 0.30
            out.append({"num": num, "score": round(score, 4), "freq": round(freq, 4),
                        "recent": round(recent, 4), "rebound": rebound,
                        "miss": s["missingStreak"], "recent15": s["recent15Count"]})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def _hot_cold(stats: dict[int, dict], latest: list[int], game: str) -> tuple[list, list]:
    """熱門/冷門 TOP8。539 依 recent50Count 排;天天樂依 totalCount 排(照各自 spec)。"""
    vals = list(stats.values())
    if game == "lotto539":
        hot_sorted = sorted(vals, key=lambda s: (-s["recent50Count"], s["missingStreak"]))
        hot = [{"num": s["num"], "count": s["recent50Count"], "today": s["num"] in latest}
               for s in hot_sorted[:8]]
    else:
        hot_sorted = sorted(vals, key=lambda s: (-s["totalCount"], s["missingStreak"]))
        hot = [{"num": s["num"], "count": s["totalCount"], "today": s["num"] in latest}
               for s in hot_sorted[:8]]
    cold_key = ((lambda s: (-s["missingStreak"], s["recent50Count"])) if game == "lotto539"
                else (lambda s: (-s["missingStreak"], s["totalCount"])))
    cold_sorted = sorted(vals, key=cold_key)
    cold = [{"num": s["num"], "miss": s["missingStreak"]} for s in cold_sorted[:8]]
    return hot, cold


# ── 四模式推薦矩陣(§F;固定 seed 加權隨機,可重現)──────────────
def _pick(rng: random.Random, source: list[int], count: int) -> list[int]:
    src = list(source)
    rng.shuffle(src)
    out: list[int] = []
    for x in src:
        if x not in out:
            out.append(x)
        if len(out) >= count:
            break
    return sorted(out)


def _recommend(ranked_nums: list[int], seed: int) -> list[dict]:
    rng = random.Random(seed)
    all39 = list(range(1, 40))
    pool = ranked_nums if len(ranked_nums) >= 15 else all39

    def merge(*parts: list[int]) -> list[int]:
        combined: list[int] = []
        for p in parts:
            combined.extend(p)
        return sorted(set(combined))

    m1_3 = _pick(rng, all39, 3)
    m1_4 = _pick(rng, all39, 4)
    m2_3 = _pick(rng, pool[0:16], 3)
    m2_4 = _pick(rng, pool[0:16], 4)
    top, mid = pool[0:5], pool[5:12]
    m3_3 = merge(_pick(rng, top, 2), _pick(rng, mid, 1))
    m3_4 = merge(_pick(rng, top, 2), _pick(rng, mid, 2))
    pool1, pool2 = pool[1:7], pool[6:15]
    m4_3 = merge(_pick(rng, pool1, 2), _pick(rng, pool2, 1))
    m4_4 = merge(_pick(rng, pool1, 2), _pick(rng, pool2, 2))
    return [
        {"mode": 1, "name": "搖球機物理模式", "star3": m1_3, "star4": m1_4, "color": "gold"},
        {"mode": 2, "name": "歷史紀錄出牌模式", "star3": m2_3, "star4": m2_4, "color": "rose"},
        {"mode": 3, "name": "尋找AI必開牌", "star3": m3_3, "star4": m3_4, "color": "cyan"},
        {"mode": 4, "name": "AI必開加強矩陣", "star3": m4_3, "star4": m4_4, "color": "purple"},
    ]


def _default_seed(data: list[list[int]]) -> int:
    if not data:
        return 0
    latest = data[0]
    return len(data) * 100003 + sum(num * (i + 1) for i, num in enumerate(latest))


def analysis_response(game: str, data: list[list[int]],
                      latest_date: str | None, seed: int | None = None) -> dict:
    """組出 API 端點 4 的 JSON。data 新→舊(data[0]=最新)。演算法依 game 分流。"""
    total = len(data)
    stats = _num_stats(data, game)
    latest = data[0] if data else []

    if game == "lotto539":
        pillars = {
            "p1800": _pillar_539(data, _is_hit_1800, BASE_P_1800, "1800"),
            "p9000": _pillar_539(data, _is_hit_9000, BASE_P_9000_539, "9000"),
        }
    else:
        pillars = {
            "p1800": _pillar_fantasy(data, _is_hit_1800, BASE_P_1800),
            "p9000": _pillar_fantasy(data, _is_hit_9000, BASE_P_9000_FANTASY),
        }

    hot, cold = _hot_cold(stats, latest, game)
    prob_score = _prob_scores(stats, total, game)
    ranked_nums = [p["num"] for p in prob_score]
    use_seed = seed if seed is not None else _default_seed(data)

    return {
        "game": game, "totalDraws": total, "latestDate": latest_date,
        "pillars": pillars, "hot": hot, "cold": cold, "probScore": prob_score,
        "recommend": _recommend(ranked_nums, use_seed), "seed": use_seed,
    }
