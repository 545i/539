"""策略預測追蹤:開獎前存下各策略的預測,開獎後比對中了幾顆。

跟 core/backtest.py 的差別 ——
  backtest  回頭看:拿歷史資料重跑,結果當下就算得出來(給的是長期期望值)
  這裡      往前記:先把預測寫進資料庫,等真的開出來才比對(給的是真實戰績)

兩件事都需要:回測告訴你期望值,預測追蹤告訴你實際發生了什麼。

**所有策略的期望中獎率完全相同**(見 core/picker 的說明),
這裡的排行只是把運氣視覺化,不代表哪個策略比較會中。

命中數不存進資料庫,顯示時才用當期開獎號即時算 —— 歷史資料被修正過
(天天樂就發生過日期基準修正),存下來的命中數會跟事實對不上。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from core import checker, games, picker, storage


def _as_date(value) -> dt.date | None:
    """把 date / datetime / 字串統一成 date;轉不動回 None。"""
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    ts = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def seed_for(target_date) -> int:
    """依目標期推導 seed:同一期永遠重現,不同期不會撞號。

    現行 page_picker 寫死 seed=539,同一份資料每期都產生一模一樣的號碼,
    拿來做逐期追蹤沒有意義。
    """
    d = _as_date(target_date)
    return 539 if d is None else d.toordinal()


def history_before(df: pd.DataFrame, target_date) -> pd.DataFrame:
    """只留目標期「之前」的開獎資料。

    防 look-ahead:熱號/冷號/頻率策略若看得到當期答案,預測就沒有意義了。
    比照 core/backtest.py 的 past = df.iloc[:i] 做法。
    """
    d = _as_date(target_date)
    if df is None or df.empty or d is None or "date" not in df.columns:
        return df if df is not None else pd.DataFrame()
    return df[pd.to_datetime(df["date"], errors="coerce").dt.date < d]


def issue_of(df: pd.DataFrame, target_date) -> str | None:
    """查該期的期號;沒有 issue 欄或該期沒填就回 None(顯示時退回用日期)。

    只有天天樂固定有期號,539 得靠 scraper 補、六合彩來源根本沒有。
    """
    d = _as_date(target_date)
    if df is None or df.empty or d is None or "issue" not in df.columns:
        return None
    hit = df[pd.to_datetime(df["date"], errors="coerce").dt.date == d]
    if hit.empty:
        return None
    raw = str(hit.iloc[-1]["issue"] or "").strip()
    return raw or None


def period_label(target_date, issue: str | None = None) -> str:
    """期別的顯示字樣:有期號優先顯示期號,沒有就用日期。"""
    d = _as_date(target_date)
    ds = d.isoformat() if d else str(target_date)
    if not issue:
        return ds
    tail = issue[-3:].lstrip("0") or issue      # 115000192 → 192
    return f"第 {tail} 期({ds[5:]})"


def generate_for(df: pd.DataFrame, game_key: str, target_date,
                 strategies: list[str] | None = None) -> dict[str, list[int]]:
    """替某一期產生各策略的預測號碼(只算,不寫入)。

    用目標期之前的資料當輸入,seed 依目標期推導。
    前置資料太少時(冷熱號沒東西可算)回空 dict。
    """
    strategies = strategies or picker.STRATEGIES
    past = history_before(df, target_date)
    if past is None or past.empty:
        return {}
    # 依該款的玩法規格出號 —— 六合彩是 49 選 6,用預設的 39 選 5 會出錯號
    g = games.get(game_key)
    base = seed_for(target_date)
    out: dict[str, list[int]] = {}
    for s in strategies:
        # 每個策略再錯開 seed。同 seed 下權重接近均勻時,不同策略會抽出
        # 一模一樣的號碼(random 與 frequency 實測就撞在一起),那樣拿來
        # 比較誰準完全沒有意義。偏移取自策略在 STRATEGIES 裡的固定位置,
        # 所以仍然可重現。
        offset = picker.STRATEGIES.index(s) if s in picker.STRATEGIES else 0
        try:
            got = picker.pick(past, strategy=s, sets=1, seed=base + offset * 7919,
                              num_max=g.num_max, pick_n=g.pick)
        except (ValueError, KeyError, IndexError):
            continue                    # 某策略算不出來就跳過,不拖垮其他策略
        if got:
            out[s] = got[0]
    return out


def save_for(df: pd.DataFrame, game_key: str, target_date,
             strategies: list[str] | None = None) -> tuple[int, dict[str, list[int]]]:
    """產生並存檔;回傳 (實際新增筆數, 這次算出來的預測)。

    同期同策略已存過的不會被覆蓋,所以重複按不會改掉先前的預測。
    """
    rows = generate_for(df, game_key, target_date, strategies)
    if not rows:
        return 0, {}
    added = storage.add_predictions(
        game_key, _as_date(target_date).isoformat(),
        rows, issue=issue_of(df, target_date),
    )
    return added, rows


def evaluate(df: pd.DataFrame, game_key: str,
             target_date: str | None = None) -> list[dict]:
    """把預測跟當期開獎號比對,回傳逐筆結果(新的期在前)。

    每筆多出來的欄位:
      drawn    當期開獎號(還沒開就是 [])
      matched  命中的號碼
      hits     中幾顆(還沒開獎為 None)
      pending  是否還沒開獎
      label    期別顯示字樣(期號優先)
    """
    out = []
    drawn_cache: dict[str, list[int] | None] = {}
    for row in storage.load_predictions(game_key, target_date):
        td = row["target_date"]
        if td not in drawn_cache:
            drawn_cache[td] = checker.draw_of(df, td)
        drawn = drawn_cache[td]
        nums = row["numbers"]
        pending = drawn is None
        matched = [] if pending else sorted(set(nums) & set(drawn))
        out.append({
            **row,
            "drawn": drawn or [],
            "matched": matched,
            "hits": None if pending else len(matched),
            "pending": pending,
            "label": period_label(td, row.get("issue")),
        })
    return out


def ranking(evaluated: list[dict]) -> list[dict]:
    """各策略的累計戰績,依平均命中由高到低。

    只算已經開獎的期 —— 待開獎的還不知道結果,計進去會把平均拉低。
    """
    agg: dict[str, dict] = {}
    for r in evaluated:
        if r["pending"]:
            continue
        a = agg.setdefault(r["strategy"], {"strategy": r["strategy"], "periods": 0,
                                           "total_hits": 0, "best": 0})
        a["periods"] += 1
        a["total_hits"] += r["hits"]
        a["best"] = max(a["best"], r["hits"])
    rows = []
    for a in agg.values():
        rows.append({**a, "label": picker.label(a["strategy"]),
                     "avg": a["total_hits"] / a["periods"] if a["periods"] else 0.0})
    rows.sort(key=lambda x: (-x["avg"], -x["best"], x["strategy"]))
    return rows


def next_target(df: pd.DataFrame) -> dt.date:
    """建議的目標期:資料最後一期的下一天(沒資料就用今天)。"""
    last = checker.today_or_last(df)
    return (last + dt.timedelta(days=1)) if last else dt.date.today()


def marked(nums: list[int], matched: set[int] | None = None) -> str:
    """號碼字串,中的用【】框起來(跟下注紀錄表的呈現一致)。"""
    hit = matched or set()
    return " ".join(f"【{n:02d}】" if n in hit else f"{n:02d}" for n in nums)
