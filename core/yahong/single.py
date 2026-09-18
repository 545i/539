"""單碼必贏 —— 忠實移植 spec-single.md(18 宗師 + finalScore + 名次分級)。

命中 +330 / 未中 -100 / b=3.3;需 >= 100 期。常數、門檻、權重逐字照抄,
包含原檔的怪癖(DD 顯示 6000 vs 計分 4000/8000、m12 不對稱 2.0/-1.5、
m16 門檻 50、m18 tenkan/kijun 預設 40 混尺度 bug)。
"""
from __future__ import annotations

from math import sqrt

from core import combo

MIN_DRAWS = 100

_FIB = {1, 2, 3, 5, 8, 13, 21, 34}


def _econ() -> tuple[float, float, float, float, float]:
    """單碼頁損益模型:單一號碼 = 包該號的**二星全車**(讀即時盤口、無退水)。

    38 注全車(該號 + 其餘 38 號各一注);命中(該號開出)= 與另 4 顆各成 1 碰 → 中 4 注。
    回 (COST 每期成本, GROSS 命中派彩, NET 命中淨賺, b 賠率, SCALE 金額門檻縮放)。
    """
    c2 = float(combo.market_cost(2) or 80.0)
    p2 = float(combo.market_prize(2) or 80.0 * 53)
    cost = 38 * c2                       # 全車二星 38 注
    gross = 4 * p2                       # 命中 → 4 碰中
    net = gross - cost
    b = net / cost if cost > 0 else 0.0
    scale = cost / 100                   # finalScore 金額門檻等比縮放基準
    return cost, gross, net, b, scale

_GIANT_LABELS = {
    "m1": "數學家(均值)", "m2": "資金家(凱利)", "m3": "贏家(馬可夫)",
    "m4": "銀行家(偏離)", "m5": "精算家(壓力)", "m6": "莊家(期望值)",
    "m7": "操盤手(RSI)", "m8": "分析師(夏普)", "m9": "蒙地卡羅動能",
    "m10": "傅立葉共振", "m11": "貝氏條件機率", "m12": "混沌極限理論",
    "m13": "卜瓦松反轉", "m14": "費波那契數列", "m15": "高斯回歸偏態",
    "m16": "馬可夫歷史狀態", "m17": "深度神經擬合", "m18": "一目均衡突破",
}


def _compute(data: list[list[int]], target: int) -> dict:
    """對單一號碼 target 掃過歷史(data 為新→舊,data[0]=最新),算 18 宗師 + finalScore。"""
    n = len(data)
    reversed_ = data[::-1]      # 舊→新
    cost, gross, net, b, scale = _econ()

    # ── 前置回測(舊→新)──
    missing_history: list[int] = []
    temp_miss = 0
    eq_curve = [0]
    peak = 0
    max_dd = 0
    hot_state_encounters = hot_state_hits = 0
    window5: list[bool] = []
    for item in reversed_:
        is_hit = target in item
        if len(window5) == 5:
            recent_hits = sum(1 for x in window5 if x)
            if recent_hits >= 2:
                hot_state_encounters += 1
                if is_hit:
                    hot_state_hits += 1
        window5.append(is_hit)
        if len(window5) > 5:
            window5.pop(0)
        if is_hit:
            missing_history.append(temp_miss)
            temp_miss = 0
            new_eq = eq_curve[-1] + net
            eq_curve.append(new_eq)
            if new_eq > peak:
                peak = new_eq
        else:
            temp_miss += 1
            new_eq = eq_curve[-1] - cost
            eq_curve.append(new_eq)
        dd = peak - eq_curve[-1]
        if dd > max_dd:
            max_dd = dd
    current_miss = temp_miss

    # ── 命中次數(data,新→舊,取近端)──
    hits = hits5 = hits10 = hits30 = 0
    for idx, item in enumerate(data):
        is_hit = target in item
        if is_hit:
            hits += 1
            if idx < 5:
                hits5 += 1
            if idx < 10:
                hits10 += 1
            if idx < 30:
                hits30 += 1

    prob_all = hits / n if n else 0.0
    prob10 = hits10 / 10
    prob30 = hits30 / 30
    accel = (prob10 - prob30) * 100
    hot_state_prob = (hot_state_hits / hot_state_encounters) if hot_state_encounters > 0 else prob_all
    if missing_history:
        avg_miss = sum(missing_history) / len(missing_history)
    else:
        avg_miss = (1 / prob_all - 1) if prob_all > 0 else float(current_miss)
    max_miss = max(list(missing_history) + [0] if not missing_history else missing_history)
    max_miss = max(max_miss, current_miss, 1)
    variance = (sum((v - avg_miss) ** 2 for v in missing_history) / (len(missing_history) or 1))
    std_dev = sqrt(variance if variance else 1)

    # ── 西方 8 大 ──
    m1 = (hits + 1) / (n + 2)
    m2 = prob30 - ((1 - prob30) / b) if b > 0 else 0.0

    m_hit = m_miss = trk = 0
    for idx, item in enumerate(reversed_):
        is_hit = target in item
        if idx > 0 and trk == current_miss:
            if is_hit:
                m_hit += 1
            else:
                m_miss += 1
        trk = 0 if is_hit else trk + 1
    m3 = (m_hit + prob_all * 5) / (m_hit + m_miss + 5)

    m4 = (current_miss - avg_miss) / std_dev if std_dev > 0 else 0.0
    m5 = max_dd

    m6 = (prob30 * net) - ((1 - prob30) * cost)

    gains = losses = 0.0
    for item in data[:14]:
        if target in item:
            gains += net
        else:
            losses += cost
    if losses == 0:
        m7 = 100.0
    else:
        rs = (gains / 14) / (losses / 14)
        m7 = 100 - (100 / (1 + rs))

    rets = [net if (target in item) else -cost for item in data[:30]]
    avg_ret = sum(rets) / (len(rets) or 1)
    var_ret = sum((v - avg_ret) ** 2 for v in rets) / (len(rets) or 1)
    std_ret = sqrt(var_ret) or 1
    m8 = avg_ret / std_ret

    # ── 東方 10 大 ──
    m9 = 85 if prob10 > prob_all else 45
    m10 = 40
    if len(missing_history) >= 2:
        if current_miss == missing_history[-1]:
            m10 = 95
        elif current_miss == missing_history[-2]:
            m10 = 80
    total_over_miss = sum(1 for x in missing_history if x >= current_miss)
    m11 = (1 / (total_over_miss + 1)) * 100 if total_over_miss > 0 else 99
    m12 = 90 if (m4 > 2.0 or m4 < -1.5) else 40
    m13 = 95 if current_miss >= (max_miss * 0.8) else 30
    m14 = 85 if current_miss in _FIB else 35
    m15 = 75 if (prob10 - prob30) > 0 else 45
    if hits5 >= 2:
        if hot_state_prob > prob_all * 1.2:
            m16 = 95
        elif hot_state_prob < prob_all * 0.8:
            m16 = 15
        else:
            m16 = 60
    elif hits10 == 0 and current_miss > 3:
        m16 = 85
    else:
        m16 = 55
    m17 = (m1 * 0.3 + m3 * 0.4 + prob30 * 0.3) * 100
    tenkan = kijun = 40
    if len(missing_history) >= 9:
        last9 = missing_history[-9:]
        tenkan = (max(last9) + min(last9)) / 2
    if len(missing_history) >= 26:
        last26 = missing_history[-26:]
        kijun = (max(last26) + min(last26)) / 2
    if current_miss > kijun:
        m18 = 90
    elif current_miss < tenkan:
        m18 = 30
    else:
        m18 = 60

    shorter_count = sum(1 for m in missing_history if m <= current_miss)
    survival_pr = (shorter_count / len(missing_history)) * 100 if missing_history else 50.0

    # ── finalScore ──
    kelly_clamped = max(0.0, min(m2 * 10, 1.0)) * 10
    z_pts = 6 if m4 > 1.5 else (4 if m4 > 0.5 else (2 if m4 > -0.5 else 0))
    # 金額門檻等比縮放(SCALE=COST/100),否則換成全車成本後級距失效
    dd_pts = 5 if m5 <= 4000 * scale else (3 if m5 <= 8000 * scale else 0)
    ev_pts = 5 if m6 > 20 * scale else (3 if m6 > 0 else 0)
    rsi_pts = 5 if m7 >= 60 else (3 if m7 >= 40 else 0)
    sharpe_pts = 5 if m8 > 0.5 else (3 if m8 > 0 else 0)
    final_score = (
        (m1 * 100 * 0.08) + kelly_clamped + (m3 * 100 * 0.10)
        + z_pts + dd_pts + ev_pts + rsi_pts + sharpe_pts
        + (m9 * 0.04) + (m10 * 0.06) + (m11 * 0.04) + (m12 * 0.04)
        + (m13 * 0.06) + (m14 * 0.04) + (m15 * 0.04) + (m16 * 0.04)
        + (m17 * 0.05) + (m18 * 0.04)
    )
    # 過熱熔斷(在 finalScore 之後)
    if hits5 >= 3:
        final_score = min(final_score, 35)
    elif hits5 == 2 and current_miss == 0:
        final_score = final_score - 15

    return {
        "target": target, "finalScore": final_score, "scale": scale,
        "probAll": prob_all, "prob30": prob30, "accel": accel,
        "maxMiss": int(max_miss), "survivalPR": survival_pr, "currentMiss": current_miss,
        "missingHistory": missing_history,
        "giants": {
            "m1": m1, "m2": m2, "m3": m3, "m4": m4, "m5": m5, "m6": m6,
            "m7": m7, "m8": m8, "m9": m9, "m10": m10, "m11": m11, "m12": m12,
            "m13": m13, "m14": m14, "m15": m15, "m16": m16, "m17": m17, "m18": m18,
        },
    }


def _giants_display(c: dict) -> list[dict]:
    """18 宗師顯示格式(display 字串 + green 燈號)。"""
    g = c["giants"]
    prob_all = c["probAll"]
    scale = c["scale"]
    out = [
        {"key": "m1", "display": f"{g['m1'] * 100:.1f}%", "green": g["m1"] > prob_all},
        {"key": "m2", "display": f"f* {(g['m2'] * 100 if g['m2'] > 0 else 0):.1f}%", "green": g["m2"] > 0},
        {"key": "m3", "display": f"{g['m3'] * 100:.1f}%", "green": g["m3"] > prob_all},
        {"key": "m4", "display": f"Z = {g['m4']:.2f}", "green": g["m4"] > 0},
        {"key": "m5", "display": f"DD ${round(g['m5'])}", "green": g["m5"] <= 6000 * scale},
        {"key": "m6", "display": f"EV {g['m6']:+.0f}", "green": g["m6"] > 0},
        {"key": "m7", "display": f"{g['m7']:.1f}", "green": 40 <= g["m7"] <= 75},
        {"key": "m8", "display": f"{g['m8']:.2f}", "green": g["m8"] > 0},
        {"key": "m9", "display": f"{g['m9']:.0f} 分", "green": g["m9"] >= 60},
        {"key": "m10", "display": f"{g['m10']:.0f} 分", "green": g["m10"] >= 60},
        {"key": "m11", "display": f"{g['m11']:.0f} 分", "green": g["m11"] >= 60},
        {"key": "m12", "display": f"{g['m12']:.0f} 分", "green": g["m12"] >= 60},
        {"key": "m13", "display": f"{g['m13']:.0f} 分", "green": g["m13"] >= 60},
        {"key": "m14", "display": f"{g['m14']:.0f} 分", "green": g["m14"] >= 60},
        {"key": "m15", "display": f"{g['m15']:.0f} 分", "green": g["m15"] >= 60},
        {"key": "m16", "display": f"{g['m16']:.0f} 分", "green": g["m16"] >= 50},
        {"key": "m17", "display": f"{g['m17']:.0f} 分", "green": g["m17"] >= 60},
        {"key": "m18", "display": f"{g['m18']:.0f} 分", "green": g["m18"] >= 60},
    ]
    for item in out:
        item["label"] = _GIANT_LABELS[item["key"]]
    return out


def _grade(rank: int) -> str:
    """名次(0-based)→ 級別。前3 S / 4-9 A / 10-25 B / 26+ C。"""
    if rank < 3:
        return "S"
    if rank < 9:
        return "A"
    if rank < 25:
        return "B"
    return "C"


def rank_all(data: list[list[int]]) -> list[dict]:
    """對 1~39 全算 finalScore,由高到低排序,回 [{num,score,grade,rank}]。"""
    scored = [(num, _compute(data, num)["finalScore"]) for num in range(1, 40)]
    scored.sort(key=lambda t: t[1], reverse=True)
    return [
        {"num": num, "score": round(score, 4), "grade": _grade(rank), "rank": rank + 1}
        for rank, (num, score) in enumerate(scored)
    ]


def _sparkline(c: dict) -> list[int]:
    """最近遺漏段(新→舊)+ 末尾當前遺漏。"""
    recent = list(reversed(c["missingHistory"][-10:]))
    return recent + [c["currentMiss"]]


def single_response(game: str, data: list[list[int]], target: int | None,
                    recent8: list[dict] | None = None) -> dict:
    """組出 API 端點 3 的 JSON。資料 <100 期回 error。

    recent8:最新 8 期 [{date, nums:[..]}](新→舊),由 router 從 df 取日期組好傳入。
    """
    total = len(data)
    if total < MIN_DRAWS:
        return {"error": "資料不足 100 期", "totalDraws": total}

    ranking = rank_all(data)
    result = {"game": game, "totalDraws": total, "ranking": ranking,
              "target": None, "recent8": recent8 or []}

    if target is not None:
        row = next((r for r in ranking if r["num"] == target), None)
        c = _compute(data, target)
        result["target"] = {
            "num": target,
            "score": round(c["finalScore"], 4),
            "grade": row["grade"] if row else _grade(38),
            "rank": row["rank"] if row else 39,
            "summary": {
                "probAll": round(c["probAll"], 4),
                "survivalPR": round(c["survivalPR"], 4),
                "accel": round(c["accel"], 4),
                "maxMiss": c["maxMiss"],
                "prob30": round(c["prob30"], 4),
            },
            "giants": _giants_display(c),
            "sparkline": _sparkline(c),
        }
    return result
