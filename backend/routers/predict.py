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
    "hot": "近 30 期常開的號碼權重高。看起來「正在發燒」,但發燒不會延續到下一期。",
    "cold": "很久沒開的號碼權重高(賭徒謬誤)。號碼沒有記憶,久沒開不代表快開了,"
            "但很多人愛用。",
    "frequency": "依歷史總出現次數加權。長期下來各號次數本來就會接近,差異多半是雜訊。",
    "balanced": "先隨機抽,再過濾到奇偶比與和值落在歷史常見區間 —— 號碼看起來"
                "「像一般開獎結果」,中獎機率跟純隨機一模一樣。",
}

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


@router.get("")
def predict(game: str = Query(...), sets: int = Query(1, ge=1, le=10),
            window: int = Query(30, ge=1), seed: int | None = Query(None)):
    """5 種策略各自的推薦號碼(依該款的 num_max / pick 出號)。

    seed 不給時依「下一期期號」推導 —— 同一期結果可重現;給了就照給的抽。
    """
    g = get_game(game)
    df = load_df(game)
    target_issue, target_date = predictor.next_target(df)
    base = seed if seed is not None else predictor.seed_for_issue(
        target_issue, target_date)

    strategies = []
    for s in picker.STRATEGIES:
        meta = _strategy_meta(s, g)
        # 每個策略錯開 seed,否則權重接近均勻時不同策略會抽出一模一樣的號碼
        offset = picker.STRATEGIES.index(s) * 7919
        try:
            nums = picker.pick(df, strategy=s, sets=sets, seed=base + offset,
                               num_max=g.num_max, pick_n=g.pick)
        except (ValueError, KeyError, IndexError) as e:
            strategies.append({**meta, "sets": [], "top_numbers": [],
                               "error": str(e)})
            continue
        probs = picker.draw_probabilities(df, strategy=s, window=window,
                                          num_max=g.num_max, pick=g.pick)
        top = sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
        strategies.append({
            **meta,
            "sets": nums,
            # 該策略「偏好」的號碼:random / balanced 是均勻的,所以會等值
            "top_numbers": [{"num": n, "weight": p / g.pick} for n, p in top],
            "uniform": s in ("random", "balanced"),
            "error": None,
        })

    return {
        "game": g.key,
        "game_name": g.label,
        "num_max": g.num_max,
        "pick": g.pick,
        "sets": sets,
        "seed": base,
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
        preds = predictor.generate_for(df, g.key, key, target_date=date)
        if not preds:
            continue                    # 最早幾期前面沒資料可算,跳過
        picks = {}
        for s, nums in preds.items():
            matched = sorted(set(nums) & set(drawn))
            picks[s] = {"numbers": nums, "matched": matched, "hits": len(matched)}
            evaluated.append({"strategy": s, "pending": False,
                              "hits": len(matched)})
        rows.append({
            "issue": issue,
            "date": date.isoformat() if date else None,
            "label": predictor.period_label(key, date),
            "drawn": drawn,
            "picks": picks,
        })

    rows.reverse()                      # 新的期排前面
    ranking = [
        {**a, "hit_rate": (a["total_hits"] / (a["periods"] * g.pick))
         if a["periods"] else 0.0}
        for a in predictor.ranking(evaluated)
    ]
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
