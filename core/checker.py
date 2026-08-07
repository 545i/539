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
    cols = loader.detect_num_cols(df)
    if not cols:
        return None
    row = hit.iloc[-1]          # 同日多筆時取最後一筆(補抓後的較新)
    nums = []
    for c in cols:
        v = row[c]
        if pd.isna(v):
            return None
        nums.append(int(v))
    return sorted(nums)


def count_hits(picked: list[int], drawn: list[int]) -> int:
    """圈選的號碼裡,有幾顆出現在開獎號碼中。"""
    return len(set(picked) & set(drawn))


def check(df: pd.DataFrame, draw_date, picked: list[int]) -> dict:
    """對一筆下注自動對獎。

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
    drawn = draw_of(df, draw_date)
    if drawn is None:
        return {"ok": False, "hits": None, "drawn": [], "matched": [],
                "reason": "還沒有這天的開獎資料(可到「資料」頁更新後再試)。"}
    matched = sorted(set(picked) & set(drawn))
    return {"ok": True, "hits": len(matched), "drawn": drawn,
            "matched": matched, "reason": ""}


def today_or_last(df: pd.DataFrame) -> dt.date | None:
    """資料裡最後一期的日期(用來提示使用者資料更新到哪天)。"""
    if df is None or df.empty or "date" not in df.columns:
        return None
    d = pd.to_datetime(df["date"], errors="coerce").max()
    return None if pd.isna(d) else d.date()
