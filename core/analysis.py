"""五策略預測的統計檢定:對「選定範圍」的歷史開獎做敘述統計與隨機性檢定。

全部**確定性**(同一份資料 + 同一範圍 → 同一結果);變異數模擬用**固定種子**,
確保使用者「切回同一區間答案一致」。

用途是檢視開獎是否符合「均勻且獨立」的公平隨機特性 —— **不是預測下一期**。
彩券每期獨立、無記憶,任何檢定都無法預測下一期號碼;這裡只把「這批歷史看起來
有多接近理論上的公平隨機」量化出來。

範圍(range)可依:
  - periods:最近 n 期
  - days:最近 n 天(以資料最後一筆日期為基準)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from core.loader import detect_num_cols
from core.stats import all_nums

# 變異數模擬:固定種子 + 固定次數 → 同範圍每次跑結果一致(使用者要求切回一致)
_SIM_SEED = 20260826
_SIM_RUNS = 2000


def _num_cols(df: pd.DataFrame, pick: int) -> list[str]:
    return detect_num_cols(df) or [f"n{i}" for i in range(1, pick + 1)]


def _matrix(df: pd.DataFrame, pick: int) -> np.ndarray:
    """開獎號矩陣 shape (期數, pick),整數。"""
    cols = _num_cols(df, pick)
    if len(df) == 0:
        return np.empty((0, len(cols)), dtype=int)
    return df[cols].to_numpy(dtype=int)


def slice_range(df: pd.DataFrame, mode: str = "periods", n: int = 30) -> pd.DataFrame:
    """依 mode 取子範圍:periods=最近 n 期;days=最近 n 天(含最後一天往回 n 天)。"""
    if mode == "days":
        dates = pd.to_datetime(df["date"], errors="coerce")
        last = dates.max()
        if pd.isna(last):
            return df.tail(0)
        cutoff = last - pd.Timedelta(days=int(n))
        return df[dates >= cutoff]
    return df.tail(int(n))


def counts(df: pd.DataFrame, num_max: int, pick: int) -> dict[int, int]:
    """各號(1..num_max)在範圍內的出現次數。"""
    mat = _matrix(df, pick)
    c = {n: 0 for n in all_nums(num_max)}
    for v in mat.reshape(-1):
        iv = int(v)
        if 1 <= iv <= num_max:
            c[iv] += 1
    return c


def _split(num_max: int) -> int:
    """大小分界:< split 為小、>= split 為大(539 → 20)。"""
    return (num_max // 2) + 1


# ── 1. 敘述性統計 ─────────────────────────────────────────
def descriptive(df: pd.DataFrame, num_max: int, pick: int) -> dict:
    mat = _matrix(df, pick)
    p = len(mat)
    cnt = counts(df, num_max, pick)
    if p == 0:
        return {"periods": 0, "expected_per_num": 0.0, "sum": None,
                "odd_avg": 0.0, "big_avg": 0.0,
                "hot": [], "cold": []}
    sums = mat.sum(axis=1)
    split = _split(num_max)
    odd = (mat % 2 == 1).sum(axis=1)
    big = (mat >= split).sum(axis=1)
    return {
        "periods": int(p),
        "expected_per_num": round(pick * p / num_max, 2) if num_max else 0.0,
        "sum": {
            "mean": round(float(sums.mean()), 1),
            "median": float(np.median(sums)),
            "std": round(float(sums.std(ddof=0)), 1),
            "min": int(sums.min()),
            "max": int(sums.max()),
        },
        "odd_avg": round(float(odd.mean()), 2),
        "big_avg": round(float(big.mean()), 2),
        "hot": [{"num": n, "count": cnt[n]}
                for n, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:6]],
        "cold": [{"num": n, "count": cnt[n]}
                 for n, _ in sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]))[:6]],
    }


# ── 2. 均勻度檢定(χ² 適合度 vs 均勻)──────────────────────
def uniformity(df: pd.DataFrame, num_max: int, pick: int) -> dict:
    cnt = counts(df, num_max, pick)
    obs = np.array([cnt[n] for n in all_nums(num_max)], dtype=float)
    total = float(obs.sum())
    dof = num_max - 1
    if total == 0:
        return {"chi2": 0.0, "dof": dof, "p": 1.0, "uniform": True,
                "verdict": "沒有資料"}
    exp = total / num_max
    chi2 = float(((obs - exp) ** 2 / exp).sum())
    p = float(stats.chi2.sf(chi2, dof))
    return {
        "chi2": round(chi2, 2), "dof": dof, "p": round(p, 4),
        "uniform": p > 0.05,
        "verdict": ("看不出偏差,符合均勻(各號機率相當)" if p > 0.05
                    else "偏離均勻:某些號明顯過熱/過冷(僅為這批樣本的波動,不代表下期)"),
    }


# ── 3. 貢獻性分析(各號對均勻度 χ² 的貢獻)──────────────────
def contribution(df: pd.DataFrame, num_max: int, pick: int, top: int = 10) -> dict:
    cnt = counts(df, num_max, pick)
    total = float(sum(cnt.values()))
    exp = total / num_max if num_max else 0.0
    chi2_total = (sum((cnt[n] - exp) ** 2 / exp for n in all_nums(num_max))
                  if exp else 0.0)
    rows = []
    for n in all_nums(num_max):
        o = cnt[n]
        c = (o - exp) ** 2 / exp if exp else 0.0
        rows.append({
            "num": n, "observed": o, "expected": round(exp, 2),
            "contrib": round(c, 3),
            "pct": round(c / chi2_total * 100, 1) if chi2_total else 0.0,
            "dir": "熱" if o > exp else ("冷" if o < exp else "平"),
        })
    rows.sort(key=lambda r: -r["contrib"])
    return {"expected": round(exp, 2), "chi2_total": round(chi2_total, 2),
            "rows": rows[:top]}


# ── 4. 獨立性檢定(前後期「和值分組」χ² 獨立性)────────────
def independence(df: pd.DataFrame, num_max: int, pick: int) -> dict:
    mat = _matrix(df, pick)
    if len(mat) < 10:
        return {"chi2": 0.0, "dof": 0, "p": 1.0, "independent": True,
                "verdict": "資料太少(需至少 10 期)"}
    sums = mat.sum(axis=1).astype(float)
    q1, q2 = np.quantile(sums, [1 / 3, 2 / 3])

    def binof(s: float) -> int:
        return 0 if s <= q1 else (1 if s <= q2 else 2)

    table = np.zeros((3, 3))
    for a, b in zip(sums[:-1], sums[1:]):
        table[binof(a), binof(b)] += 1
    # 移除全 0 的行/列,否則 chi2_contingency 期望值為 0 會報錯
    table = table[table.sum(axis=1) > 0][:, table.sum(axis=0) > 0]
    if table.shape[0] < 2 or table.shape[1] < 2:
        return {"chi2": 0.0, "dof": 0, "p": 1.0, "independent": True,
                "verdict": "和值幾乎沒有變化,無法檢定"}
    chi2, p, dof, _ = stats.chi2_contingency(table)
    p = float(p)
    return {
        "chi2": round(float(chi2), 2), "dof": int(dof), "p": round(p, 4),
        "independent": bool(p > 0.05),
        "verdict": ("前後期看不出關聯,符合獨立(開獎沒有記憶)" if p > 0.05
                    else "前後期出現統計關聯(這批樣本的巧合,理論上開獎彼此獨立)"),
    }


# ── 5. 皮爾森相關係數(相鄰兩期特徵的線性關聯,理論應≈0)──
def pearson_serial(df: pd.DataFrame, num_max: int, pick: int) -> dict:
    mat = _matrix(df, pick)
    if len(mat) < 3:
        return {"features": []}
    split = _split(num_max)
    feats = {
        "和值": mat.sum(axis=1).astype(float),
        "奇數個數": (mat % 2 == 1).sum(axis=1).astype(float),
        "大數個數": (mat >= split).sum(axis=1).astype(float),
    }
    out = []
    for name, arr in feats.items():
        a, b = arr[:-1], arr[1:]
        if a.std() == 0 or b.std() == 0:
            r, p = 0.0, 1.0
        else:
            r, p = stats.pearsonr(a, b)
        out.append({
            "feature": name, "r": round(float(r), 3), "p": round(float(p), 4),
            "note": ("無明顯線性關聯(符合獨立)" if abs(r) < 0.2
                     else "有些線性關聯(樣本波動,非可預測訊號)"),
        })
    return {"features": out}


# ── 6. 變異數模擬(蒙地卡羅:觀測 vs 公平隨機)────────────
def variance_sim(df: pd.DataFrame, num_max: int, pick: int,
                 runs: int = _SIM_RUNS) -> dict:
    """模擬 runs 次『公平開獎』同樣期數,比對『各號出現次數的變異數』落在模擬分佈
    的百分位。固定種子 → 同範圍每次一致。

    百分位落在 2.5~97.5 之間 = 觀測到的號碼分佈鬆緊度與公平隨機無異;
    過高 = 比隨機更不均(有號特別集中),過低 = 比隨機更平。
    """
    mat = _matrix(df, pick)
    p = len(mat)
    cnt = counts(df, num_max, pick)
    obs_var = float(np.var([cnt[n] for n in all_nums(num_max)], ddof=0))
    if p == 0:
        return {"observed_var": 0.0, "sim_mean": 0.0, "sim_lo": 0.0,
                "sim_hi": 0.0, "percentile": 50.0, "verdict": "沒有資料"}
    rng = np.random.default_rng(_SIM_SEED)
    sim_vars = np.empty(runs)
    for i in range(runs):
        c = np.zeros(num_max)
        for _ in range(p):
            draw = rng.choice(num_max, size=pick, replace=False)
            c[draw] += 1
        sim_vars[i] = c.var()
    pct = float((sim_vars < obs_var).mean() * 100)
    return {
        "observed_var": round(obs_var, 2),
        "sim_mean": round(float(sim_vars.mean()), 2),
        "sim_lo": round(float(np.percentile(sim_vars, 2.5)), 2),
        "sim_hi": round(float(np.percentile(sim_vars, 97.5)), 2),
        "percentile": round(pct, 1),
        "verdict": ("號碼分佈的鬆緊度與公平隨機無異" if 2.5 <= pct <= 97.5
                    else ("比隨機更集中(某些號偏多)" if pct > 97.5
                          else "比隨機更平均")),
    }


def analyze(df: pd.DataFrame, num_max: int, pick: int,
            mode: str = "periods", n: int = 30) -> dict:
    """一次算完六項檢定,回給 API。"""
    sub = slice_range(df, mode, n)
    return {
        "mode": mode, "n": int(n), "periods": int(len(sub)),
        "descriptive": descriptive(sub, num_max, pick),
        "uniformity": uniformity(sub, num_max, pick),
        "contribution": contribution(sub, num_max, pick),
        "independence": independence(sub, num_max, pick),
        "pearson": pearson_serial(sub, num_max, pick),
        "variance_sim": variance_sim(sub, num_max, pick),
    }
