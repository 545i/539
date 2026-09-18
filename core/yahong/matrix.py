"""決策矩陣 —— 忠實移植 spec-core.md 的 analyzeSpace + 五裁決。

常數逐字照抄自 vercel 原頁:baseP 0.5536/0.2736、expectedPrizePuffs 3.5576/2.0、
bayesProb 權重 0.3/0.2/0.5、Z 加成 0.035、kellyScale 0/0.03/0.10 等。
"""
from __future__ import annotations

from math import sqrt

# ── 牌局設定(spaceConfigs;只依 type 分)──────────────────────
_CONFIGS = {
    "1800": {"type": "1800", "unitBet": 1, "basePuffs": 1800, "rebate": 37, "unitPrize": 570},
    "9000": {"type": "9000", "unitBet": 1, "basePuffs": 9000, "rebate": 50, "unitPrize": 8000},
}


def config_for(mode: str) -> dict:
    """依 mode(1800|9000)取得牌局設定的副本。"""
    return dict(_CONFIGS[mode])


# ── 中獎判定 ─────────────────────────────────────────────────
def check1800(balls) -> dict:
    """1800碰:三柱球數相乘 = 碰數。第1柱 10~18、第2柱 20~29、第3柱其餘。"""
    p1 = p2 = p3 = 0
    for x in balls:
        n = int(x)
        if 10 <= n <= 18:
            p1 += 1
        elif 20 <= n <= 29:
            p2 += 1
        else:                       # 01~09、19、30~39
            p3 += 1
    return {"puffs": p1 * p2 * p3, "p1": p1, "p2": p2, "p3": p3}


def check9000(balls) -> dict:
    """9000碰:四區(1-9/10-19/20-29/30-39)是否全開。"""
    q1 = q2 = q3 = q4 = 0
    for x in balls:
        n = int(x)
        if 1 <= n <= 9:
            q1 += 1
        elif n <= 19:
            q2 += 1
        elif n <= 29:
            q3 += 1
        elif n <= 39:
            q4 += 1
    puffs = q1 * q2 * q3 * q4
    return {"pass": puffs > 0, "puffs": puffs, "q1": q1, "q2": q2, "q3": q3, "q4": q4}


def _is_win(cfg: dict, draw) -> bool:
    if cfg["type"] == "1800":
        return check1800(draw)["puffs"] >= 3
    return check9000(draw)["pass"]


def analyze_space(cfg: dict, data: list[list[int]]) -> dict | None:
    """決策矩陣主算式。data:新→舊、最多 1500 期。totalDraws==0 回 None。"""
    total_draws = len(data)
    if total_draws == 0:
        return None

    base_p = 0.5536 if cfg["type"] == "1800" else 0.2736
    cost_per_round = cfg["unitBet"] * cfg["basePuffs"] * (1 - cfg["rebate"] / 100)
    expected_prize_puffs = 3.5576 if cfg["type"] == "1800" else 2.0
    avg_prize_when_win = expected_prize_puffs * cfg["unitPrize"] * cfg["unitBet"]

    reversed_data = data[::-1]      # 舊→新

    # ── Loop1(舊→新):理論權益曲線 + 回撤 + 遺漏史 ──
    theoretical_equity = peak_theoretical = max_drawdown = 0.0
    missing_history: list[int] = []
    temp_miss = 0
    for draw in reversed_data:
        is_win = _is_win(cfg, draw)
        round_pnl = (avg_prize_when_win - cost_per_round) if is_win else -cost_per_round
        theoretical_equity += round_pnl
        if theoretical_equity > peak_theoretical:
            peak_theoretical = theoretical_equity
        dd = peak_theoretical - theoretical_equity
        if dd > max_drawdown:
            max_drawdown = dd
        if is_win:
            missing_history.append(temp_miss)
            temp_miss = 0
        else:
            temp_miss += 1

    # ── Loop2(新→舊):勝場數、近 N 期勝數、當前連槓 ──
    wins = wins14 = wins30 = wins120 = wins500 = 0
    losing_streak = 0
    counting_streak = True
    for i in range(total_draws):
        is_win = _is_win(cfg, data[i])
        if is_win:
            wins += 1
            if i < 14:
                wins14 += 1
            if i < 30:
                wins30 += 1
            if i < 120:
                wins120 += 1
            if i < 500:
                wins500 += 1
            counting_streak = False
        elif counting_streak:
            losing_streak += 1

    # ── Loop3(舊→新):馬可夫「連槓深度==目前連槓」時的下一期命中/落空 ──
    markov_hit = markov_miss = 0
    m_miss_tracker = 0
    for i in range(len(reversed_data)):
        is_win = _is_win(cfg, reversed_data[i])
        if i > 0 and m_miss_tracker == losing_streak:
            if is_win:
                markov_hit += 1
            else:
                markov_miss += 1
        m_miss_tracker = 0 if is_win else m_miss_tracker + 1

    ma14 = wins14 / min(total_draws, 14) if min(total_draws, 14) > 0 else 0.0
    ma30 = wins30 / min(total_draws, 30) if min(total_draws, 30) > 0 else 0.0
    ma120 = wins120 / min(total_draws, 120) if min(total_draws, 120) > 0 else 0.0
    ma500 = wins500 / min(total_draws, 500) if min(total_draws, 500) > 0 else 0.0
    rsi14 = (wins14 / min(total_draws, 14)) * 100 if min(total_draws, 14) > 0 else 50.0
    accel = ma30 - ma120
    emp_win_rate = wins / total_draws if total_draws > 0 else base_p

    geom_mean = (1 - base_p) / base_p if base_p > 0 else 0.0
    geom_std = sqrt(1 - base_p) / base_p if base_p > 0 else 1.0
    raw_z = (losing_streak - geom_mean) / geom_std if geom_std > 0 else 0.0
    z_score = max(-3.0, min(raw_z, 3.0))

    shorter_count = sum(1 for m in missing_history if m <= losing_streak)
    pr_surv = (shorter_count / len(missing_history)) * 100 if missing_history else 50.0
    p_markov = (markov_hit + base_p * 2) / (markov_hit + markov_miss + 2)
    max_allowed_prob = min(base_p * 1.6, 0.99)

    bayes_prob = ma14 * 0.3 + ma30 * 0.2 + p_markov * 0.5
    if z_score >= 0.8:
        bayes_prob += z_score * 0.035
    bayes_prob = max(0.0, min(bayes_prob, max_allowed_prob))

    ev = bayes_prob * avg_prize_when_win - cost_per_round
    current_drawdown = peak_theoretical - theoretical_equity
    b = (avg_prize_when_win - cost_per_round) / cost_per_round if cost_per_round > 0 else 0.0
    full_kelly = (bayes_prob * (b + 1) - 1) / b if b > 0 else 0.0
    is_turbulent = (max_drawdown > cost_per_round * 5) and (current_drawdown >= max_drawdown * 0.75)
    kelly_scale = 0.00 if is_turbulent else (0.03 if current_drawdown > max_drawdown * 0.5 else 0.10)
    frac_kelly = max(0.0, min(full_kelly * kelly_scale, 1.0))

    return {
        "totalDraws": total_draws, "losingStreak": losing_streak,
        "ma14": ma14, "ma30": ma30, "ma120": ma120, "ma500": ma500,
        "empWinRate": emp_win_rate, "bayesProb": bayes_prob, "zScore": z_score,
        "EV": ev, "costPerRound": cost_per_round, "fracKelly": frac_kelly,
        "currentDrawdown": current_drawdown, "maxDrawdown": max_drawdown,
        "isTurbulent": is_turbulent, "baseP_Threshold": base_p, "rsi14": rsi14,
        "accel": accel, "prSurv": pr_surv, "pMarkov": p_markov,
        "geomMean": geom_mean, "geomStd": geom_std,
        "avgPrizeWhenWin": avg_prize_when_win, "b": b,
    }


# ── 五裁決 ───────────────────────────────────────────────────
def verdict(a: dict | None) -> dict:
    """下注倍數建議。需 totalDraws>=5,否則「⏳ 歷史數據不足」。

    color ∈ red|amber|gold|green|slate,對應五裁決供前端上色。
    """
    if a is None or a["totalDraws"] < 5:
        return {"title": "⏳ 歷史數據不足", "mult": 0,
                "desc": "累計觀測不足 5 期,無法產生裁決。", "color": "slate"}

    pass_z = 0.8 <= a["zScore"] <= 3.0
    pass_dd = not a["isTurbulent"]
    pass_ev = a["EV"] > 0

    if not pass_ev and not pass_z:
        return {"title": "🔴 系統否決 (期望值為負)", "mult": 0,
                "desc": "【風控否決】期望值 EV<0,強制 0 倍空手觀望!", "color": "red"}
    if not pass_dd:
        return {"title": "🟡 亂流防禦 (波動率限制)", "mult": 0,
                "desc": "【回撤警告】資金曲線進入深水區亂流,建議 0 倍觀望。", "color": "amber"}
    if a["zScore"] >= 1.2 and pass_ev:
        return {"title": "🔥 黃金狙擊 (乖離 Z>1.2)", "mult": 2,
                "desc": f"【精準打擊】連槓 {a['losingStreak']} 期,Z 達標,核准 2 倍火力狙擊!",
                "color": "gold"}
    if a["ma30"] >= a["ma120"] and pass_ev:
        return {"title": "🟢 標準多頭佈局", "mult": 1,
                "desc": "【常態區】短均站上長均且 EV>0,核准 1 倍平推。", "color": "green"}
    return {"title": "🔴 聯合否決 (條件未齊)", "mult": 0,
            "desc": "【觀望區】多空不明確,乖離不足補償 EV,0 倍觀望。", "color": "slate"}


def _r(x: float, nd: int = 6) -> float:
    return round(float(x), nd)


def matrix_response(game: str, mode: str, cfg: dict, data: list[list[int]]) -> dict:
    """組出 API 端點 1 的完整 JSON(華爾街八大 + 東方十大 + 裁決)。"""
    a = analyze_space(cfg, data)
    v = verdict(a)
    total = a["totalDraws"] if a else 0
    if a is None:
        z = 0.0
        wallst = [
            {"key": "bayes", "label": "綜合勝率(Bayes)", "value": 0, "fmt": "pct"},
            {"key": "ev", "label": "期望值(EV)", "value": 0, "fmt": "money"},
            {"key": "kelly", "label": "凱利配置(Kelly)", "value": 0, "fmt": "pct"},
            {"key": "z", "label": "偏離度(Z-Score)", "value": 0, "fmt": "num2"},
            {"key": "drawdown", "label": "資金回撤壓力", "value": 0, "extra": 0, "fmt": "money"},
            {"key": "markov", "label": "馬可夫反轉率", "value": 0, "fmt": "pct"},
            {"key": "rsi", "label": "RSI 震盪(14期)", "value": 50, "fmt": "num1"},
            {"key": "accel", "label": "動能加速(Accel)", "value": 0, "fmt": "num2"},
        ]
        base_p = 0.5536 if mode == "1800" else 0.2736
        eastern = [
            {"key": "pbase", "label": "物理基準 P_base", "value": base_p, "fmt": "pct"},
            {"key": "pemp", "label": "大數勝率 P_emp", "value": 0, "fmt": "pct"},
            {"key": "ma30", "label": "短期均線 MA30", "value": 0, "fmt": "pct"},
            {"key": "ma120", "label": "中期均線 MA120", "value": 0, "fmt": "pct"},
            {"key": "ma500", "label": "長期均線 MA500", "value": 0, "fmt": "pct"},
            {"key": "streak", "label": "當前連槓期數", "value": 0, "fmt": "period"},
            {"key": "geomMean", "label": "理論平均遺漏", "value": 0, "fmt": "num1"},
            {"key": "geomStd", "label": "幾何標準差 σ", "value": 0, "fmt": "num2"},
            {"key": "prSurv", "label": "生存極限 PR值", "value": 50, "fmt": "pct100"},
            {"key": "totalDraws", "label": "累計觀測期數", "value": 0, "fmt": "period"},
        ]
        return {"game": game, "mode": mode, "totalDraws": total,
                "verdict": v, "wallst": wallst, "eastern": eastern}

    wallst = [
        {"key": "bayes", "label": "綜合勝率(Bayes)", "value": _r(a["bayesProb"]), "fmt": "pct"},
        {"key": "ev", "label": "期望值(EV)", "value": _r(a["EV"], 2), "fmt": "money"},
        {"key": "kelly", "label": "凱利配置(Kelly)", "value": _r(a["fracKelly"]), "fmt": "pct"},
        {"key": "z", "label": "偏離度(Z-Score)", "value": _r(a["zScore"], 4), "fmt": "num2"},
        {"key": "drawdown", "label": "資金回撤壓力", "value": _r(a["currentDrawdown"], 2),
         "extra": _r(a["maxDrawdown"], 2), "fmt": "money"},
        {"key": "markov", "label": "馬可夫反轉率", "value": _r(a["pMarkov"]), "fmt": "pct"},
        {"key": "rsi", "label": "RSI 震盪(14期)", "value": _r(a["rsi14"], 4), "fmt": "num1"},
        {"key": "accel", "label": "動能加速(Accel)", "value": _r(a["accel"], 4), "fmt": "num2"},
    ]
    eastern = [
        {"key": "pbase", "label": "物理基準 P_base", "value": _r(a["baseP_Threshold"]), "fmt": "pct"},
        {"key": "pemp", "label": "大數勝率 P_emp", "value": _r(a["empWinRate"]), "fmt": "pct"},
        {"key": "ma30", "label": "短期均線 MA30", "value": _r(a["ma30"]), "fmt": "pct"},
        {"key": "ma120", "label": "中期均線 MA120", "value": _r(a["ma120"]), "fmt": "pct"},
        {"key": "ma500", "label": "長期均線 MA500", "value": _r(a["ma500"]), "fmt": "pct"},
        {"key": "streak", "label": "當前連槓期數", "value": a["losingStreak"], "fmt": "period"},
        {"key": "geomMean", "label": "理論平均遺漏", "value": _r(a["geomMean"], 4), "fmt": "num1"},
        {"key": "geomStd", "label": "幾何標準差 σ", "value": _r(a["geomStd"], 4), "fmt": "num2"},
        {"key": "prSurv", "label": "生存極限 PR值", "value": _r(a["prSurv"], 4), "fmt": "pct100"},
        {"key": "totalDraws", "label": "累計觀測期數", "value": a["totalDraws"], "fmt": "period"},
    ]
    return {"game": game, "mode": mode, "totalDraws": total,
            "verdict": v, "wallst": wallst, "eastern": eastern}
