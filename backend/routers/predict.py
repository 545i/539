"""五策略參考選號 / 預測分析。

core.picker 的 5 種策略(random / hot / cold / frequency / balanced)**期望中獎率
完全相同** —— 這裡把它們並排出號,只是把「不同的挑號習慣」視覺化,不是預測。

出號的 seed 由 core.predictor 依「下一期期號」推導,所以同一期重整頁面拿到的
號碼一樣(換期才會換號);要另外抽一組就帶 seed 參數。

/review 是回顧:對最近幾期,只餵「該期之前」的資料重新出號再跟當期開獎比對
(防 look-ahead,做法沿用 core.predictor.generate_for),所以命中數是誠實的。
純計算,不寫入資料庫、不需登入。
"""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Query

from backend.data import get_game, load_df
from core import analysis, picker, predictor
from core.games import GameConfig
from core.loader import detect_num_cols

router = APIRouter(prefix="/predict", tags=["predict"])

# 每個策略在畫面上的一句話說明(picker.STRATEGY_LABELS 是短標籤,這裡是白話)
STRATEGY_DESCS = {
    "random": "01~{num_max} 等機率隨機抽 {pick} 顆。數學上最誠實的基準 —— "
              "每期開獎互相獨立,這就是真實的中獎機率。",
    "hot": "選定範圍內出現次數最多的 {pick} 顆(與統計檢定的『熱號』一致)。"
           "看起來「正在發燒」,但發燒不會延續到下一期。",
    "cold": "選定範圍內出現次數最少的 {pick} 顆(賭徒謬誤,與統計檢定的『冷號』一致)。"
            "號碼沒有記憶,少開不代表快開了,但很多人愛用。",
    "frequency": "全部歷史出現次數最多的 {pick} 顆。長期下來各號次數本來就會接近,"
                 "差異多半是雜訊。",
    "balanced": "先隨機抽,再過濾到奇偶比與和值落在(範圍內)常見區間 —— 號碼看起來"
                "「像一般開獎結果」,中獎機率跟純隨機一模一樣。",
}

# 依「排名」出號的策略(確定性,直接對應統計檢定);其餘走隨機抽樣
RANKING_STRATEGIES = {"hot", "cold", "frequency"}

NOTICE = ("五種策略的期望中獎率完全相同,差別只有運氣。任何冷熱號 / 頻率加權都"
          "無法預測下一期,號碼僅供參考,請理性娛樂。")


def _strategy_meta(key: str, g: GameConfig) -> dict:
    return {
        "key": key,
        "label": picker.label(key),
        "desc": STRATEGY_DESCS.get(key, "").format(num_max=g.num_max, pick=g.pick),
    }


def _row_nums(row, cols: list[str]) -> list[int]:
    return sorted(int(row[c]) for c in cols)


# 只有「均衡」策略是在壓單雙(奇偶);其餘四個是選號策略,不做單雙中獎判定。
OE_STRATEGY = "balanced"


def _oe_lean(odd: int, total: int) -> str:
    """一組號碼的單雙偏向:單(奇)數多→單多、雙(偶)數多→雙多、一樣→平。"""
    even = total - odd
    if odd > even:
        return "單多"
    if even > odd:
        return "雙多"
    return "平"


def _top_by_count(cnt: dict[int, int], pick: int, most: bool = True) -> list[int]:
    """依出現次數取前 pick 名:most=True 取最多(熱),False 取最少(冷)。
    平手以號碼小者優先。回排序後的號碼清單(確定性)。"""
    ranked = sorted(cnt.items(),
                    key=lambda kv: (-kv[1] if most else kv[1], kv[0]))
    return sorted(n for n, _ in ranked[:pick])


@router.get("")
def predict(game: str = Query(...), sets: int = Query(1, ge=1, le=10),
            mode: str = Query("periods", pattern="^(periods|days)$"),
            n: int = Query(50, ge=1, le=100000),
            seed: int | None = Query(None)):
    """5 種策略各自的推薦號碼,依「選定範圍(最近 n 期 / n 天)」計算。

    - hot / cold / frequency:**確定性排名**(直接對應統計檢定的熱/冷/總頻率),
      同範圍永遠同一組。
    - random / balanced:隨機抽樣,seed 不給時依「下一期期號」推導 → 同一期可重現。

    sets 只對隨機抽樣的策略有意義(排名策略永遠是排名前 pick 那一組)。
    """
    g = get_game(game)
    df = load_df(game)
    target_issue, target_date = predictor.next_target(df)
    base = seed if seed is not None else predictor.seed_for_issue(
        target_issue, target_date)

    sub = analysis.slice_range(df, mode, n)
    cnt_range = analysis.counts(sub, g.num_max, g.pick)   # 熱/冷:選定範圍
    cnt_all = analysis.counts(df, g.num_max, g.pick)      # 頻率:全部歷史
    ranking = {
        "hot": _top_by_count(cnt_range, g.pick, most=True),
        "cold": _top_by_count(cnt_range, g.pick, most=False),
        "frequency": _top_by_count(cnt_all, g.pick, most=True),
    }

    strategies = []
    for s in picker.STRATEGIES:
        meta = _strategy_meta(s, g)
        if s in RANKING_STRATEGIES:
            # 確定性排名:一組(對應統計檢定,不做隨機、不吃 sets)
            strategies.append({**meta, "sets": [ranking[s]], "top_numbers": [],
                               "uniform": False, "ranked": True, "error": None})
            continue
        # random / balanced:隨機抽樣(balanced 的和值/奇偶區間取自選定範圍)
        offset = picker.STRATEGIES.index(s) * 7919
        src = sub if s == "balanced" else df
        try:
            nums = picker.pick(src, strategy=s, sets=sets, seed=base + offset,
                               num_max=g.num_max, pick_n=g.pick)
        except (ValueError, KeyError, IndexError) as e:
            strategies.append({**meta, "sets": [], "top_numbers": [],
                               "uniform": True, "ranked": False, "error": str(e)})
            continue
        strategies.append({**meta, "sets": nums, "top_numbers": [],
                           "uniform": True, "ranked": False, "error": None})

    return {
        "game": g.key,
        "game_name": g.label,
        "num_max": g.num_max,
        "pick": g.pick,
        "sets": sets,
        "seed": base,
        "mode": mode,
        "n": int(n),
        "range_periods": int(len(sub)),
        "periods": int(len(df)),
        "target": {
            "issue": target_issue,
            "date": target_date.isoformat() if target_date else None,
            "label": predictor.period_label(target_issue, target_date),
        },
        "strategies": strategies,
        "notice": NOTICE,
    }


ANALYSIS_NOTICE = (
    "以下是對『選定範圍』歷史開獎的隨機性檢定(均勻度 / 獨立性 / 相關 / 變異數模擬),"
    "用來看這批號碼有多接近『公平隨機』。彩券每期獨立、無記憶,這些數字**不能預測"
    "下一期**;結果同一範圍固定不變。")


@router.get("/analysis")
def analysis_route(game: str = Query(...),
                   mode: str = Query("periods", pattern="^(periods|days)$"),
                   n: int = Query(30, ge=1, le=100000)):
    """對選定範圍(最近 n 期 / 最近 n 天)做六項統計檢定。

    確定性:同一 game + mode + n → 同一結果(變異數模擬用固定種子)。
    """
    g = get_game(game)
    df = load_df(game)
    res = analysis.analyze(df, g.num_max, g.pick, mode=mode, n=n)
    return {
        "game": g.key, "game_name": g.label,
        "num_max": g.num_max, "pick": g.pick,
        "total_periods": int(len(df)),
        **res,
        "notice": ANALYSIS_NOTICE,
    }


@router.get("/review")
def review(game: str = Query(...), periods: int = Query(20, ge=1, le=100)):
    """最近 N 期的回顧:各策略在「當期開獎前」會出什麼號、實際中幾顆。

    每期都只用該期之前的資料重新出號(防 look-ahead),所以命中數是誠實的。
    """
    g = get_game(game)
    df = load_df(game)
    cols = detect_num_cols(df) or [f"n{i}" for i in range(1, g.pick + 1)]
    tail = df.tail(periods)

    rows = []
    evaluated = []
    oe_tally: dict[str, dict] = {}      # 各策略單雙命中統計 {strategy:{wins,periods}}
    for _, r in tail.iterrows():
        ts = pd.to_datetime(r["date"], errors="coerce")
        date = None if pd.isna(ts) else ts.date()
        issue = None
        if "issue" in tail.columns:
            issue = str(r["issue"] or "").strip() or None
            if issue in ("nan", "None"):
                issue = None
        key = issue or (date.isoformat() if date else "")
        drawn = _row_nums(r, cols)
        draw_odd = sum(1 for n in drawn if n % 2 == 1)
        draw_lean = _oe_lean(draw_odd, len(drawn))
        preds = predictor.generate_for(df, g.key, key, target_date=date)
        if not preds:
            continue                    # 最早幾期前面沒資料可算,跳過
        picks = {}
        for s, nums in preds.items():
            matched = sorted(set(nums) & set(drawn))
            odd = sum(1 for n in nums if n % 2 == 1)
            lean = _oe_lean(odd, len(nums))
            # 只有「均衡」壓單雙才判中獎;其餘策略 oe_win = None(不適用)
            is_oe = s == OE_STRATEGY
            oe_win = (lean == draw_lean) if is_oe else None
            picks[s] = {"numbers": nums, "matched": matched, "hits": len(matched),
                        "odd": odd, "lean": lean, "oe_win": oe_win}
            evaluated.append({"strategy": s, "pending": False,
                              "hits": len(matched)})
            if is_oe:
                ot = oe_tally.setdefault(s, {"wins": 0, "periods": 0})
                ot["wins"] += 1 if oe_win else 0
                ot["periods"] += 1
        bal = picks.get(OE_STRATEGY)
        rows.append({
            "issue": issue,
            "date": date.isoformat() if date else None,
            "label": predictor.period_label(key, date),
            "drawn": drawn,
            "draw_odd": draw_odd,
            "draw_lean": draw_lean,
            # 這期單雙結果 = 均衡有沒有中(只有均衡壓單雙);None = 均衡沒出號
            "oe_win": (bal["oe_win"] if bal else None),
            "picks": picks,
        })

    rows.reverse()                      # 新的期排前面
    ranking = []
    for a in predictor.ranking(evaluated):
        ot = oe_tally.get(a["strategy"], {"wins": 0, "periods": 0})
        ranking.append({
            **a,
            "hit_rate": (a["total_hits"] / (a["periods"] * g.pick))
            if a["periods"] else 0.0,
            "oe_wins": ot["wins"],
            "oe_rate": (ot["wins"] / ot["periods"]) if ot["periods"] else 0.0,
        })
    return {
        "game": g.key,
        "pick": g.pick,
        "num_max": g.num_max,
        # 隨機出 pick 顆、開 pick 顆的期望命中 = pick² / num_max
        "expected_avg": g.pick * g.pick / g.num_max,
        "periods": len(rows),
        "strategies": [_strategy_meta(s, g) for s in picker.STRATEGIES],
        "rows": rows,
        "ranking": ranking,
        "notice": NOTICE,
    }
