"""用已抓下來的開獎資料,替「選號下注」自動算出中了幾顆。

只有用選號盤下注(picked 有值)的紀錄才對得了獎;填數量的舊玩法沒有號碼,
一律回傳「無法自動判定」,交還給使用者手填 —— 這樣兩種輸入方式可以並存,
不會因為改了對獎邏輯就把舊紀錄弄壞。

開獎資料還沒抓到當天那期時同樣回 None(待開獎),不會擅自判定成 0 顆。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

from core import loader


def draw_of(df: pd.DataFrame, draw_date) -> list[int] | None:
    """查某一天的開獎號碼;查無該期回 None。

    draw_date 可以是 date、datetime 或 "YYYY-MM-DD" 字串。
    """
    if df is None or df.empty:
        return None
    try:
        want = pd.to_datetime(draw_date).normalize()
    except (ValueError, TypeError):
        return None
    if "date" not in df.columns:
        return None
    hit = df[pd.to_datetime(df["date"], errors="coerce").dt.normalize() == want]
    if hit.empty:
        return None
    return _nums_of_row(df, hit.iloc[-1])   # 同日多筆時取最後一筆(補抓後的較新)


def _nums_of_row(df: pd.DataFrame, row) -> list[int] | None:
    """把一列開獎資料取成號碼清單;任一顆缺值就回 None(資料還沒補齊)。"""
    cols = loader.detect_num_cols(df)
    if not cols:
        return None
    nums = []
    for c in cols:
        v = row[c]
        if pd.isna(v):
            return None
        nums.append(int(v))
    return sorted(nums)


def draw_of_issue(df: pd.DataFrame, issue) -> list[int] | None:
    """依**期號**查開獎號碼;資料沒有期號欄、或查無該期時回 None。"""
    if df is None or df.empty or "issue" not in df.columns:
        return None
    want = str(issue).strip()
    if not want:
        return None
    hit = df[df["issue"].astype(str).str.strip() == want]
    if hit.empty:
        return None
    return _nums_of_row(df, hit.iloc[-1])


def draw_for(df: pd.DataFrame, draw_date, issue=None) -> list[int] | None:
    """查一筆下注該用哪一期的開獎號碼。

    **有期號就以期號為準。** 日期不等於一期 —— 同一天可能剛開完上一期、
    你下的是還沒開的下一期,只用日期查會把上一期的號碼套到下一期上,
    然後把錯的結果寫進帳裡。(2026-08-12 那天真的踩過:期 11967、11968
    兩筆都被比對到 8/12 開的 11966,而 11968 根本還沒開獎。)

    期號查得到就用它;**查不到就回 None**,不會退回去用日期猜 ——
    那正是要防的事。只有完全沒記期號的紀錄才用日期查。
    """
    if str(issue or "").strip():
        if "issue" in getattr(df, "columns", []):
            return draw_of_issue(df, issue)
        # 這款的資料本來就沒有期號欄(例如六合彩),只能靠日期
    return draw_of(df, draw_date)


def count_hits(picked: list[int], drawn: list[int]) -> int:
    """圈選的號碼裡,有幾顆出現在開獎號碼中。"""
    return len(set(picked) & set(drawn))


def check(df: pd.DataFrame, draw_date, picked: list[int], issue=None) -> dict:
    """對一筆下注自動對獎。

    issue 有給就以期號為準(見 draw_for)—— 日期會對到錯的一期。

    回傳 {
        "ok":     能不能自動判定
        "hits":   中幾顆(ok=False 時為 None)
        "drawn":  當期開獎號碼(查不到為 [])
        "matched":圈中的號碼
        "reason": ok=False 時的原因字串
    }
    """
    if not picked:
        return {"ok": False, "hits": None, "drawn": [], "matched": [],
                "reason": "這筆是用「填數量」下的,沒有記號碼,只能手動填。"}
    drawn = draw_for(df, draw_date, issue)
    if drawn is None:
        what = f"第 {str(issue).strip()} 期" if str(issue or "").strip() else "這天"
        return {"ok": False, "hits": None, "drawn": [], "matched": [],
                "reason": f"還沒有{what}的開獎資料(可到「資料」頁更新後再試)。"}
    matched = sorted(set(picked) & set(drawn))
    return {"ok": True, "hits": len(matched), "drawn": drawn,
            "matched": matched, "reason": ""}


def today_or_last(df: pd.DataFrame) -> dt.date | None:
    """資料裡最後一期的日期(用來提示使用者資料更新到哪天)。"""
    if df is None or df.empty or "date" not in df.columns:
        return None
    d = pd.to_datetime(df["date"], errors="coerce").max()
    return None if pd.isna(d) else d.date()
