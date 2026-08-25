"""開獎歷史:回傳每期號碼(舊→新),最新一期附三柱分佈與碰數摘要。"""
from __future__ import annotations

import re

import pandas as pd
from fastapi import APIRouter, Query

from backend.data import get_game, load_df
from core import drawtime, pillar
from core.loader import detect_num_cols

router = APIRouter(prefix="/history", tags=["history"])


def _row_to_draw(row: pd.Series, num_cols: list[str]) -> dict:
    nums = [int(row[c]) for c in num_cols]
    draw = {"date": row["date"].strftime("%Y-%m-%d"), "nums": nums}
    if "issue" in row and pd.notna(row.get("issue")):
        draw["issue"] = str(row["issue"])
    return draw


@router.get("")
def history(game: str = Query(...), limit: int = Query(0, ge=0)):
    g = get_game(game)
    df = load_df(game)
    num_cols = detect_num_cols(df)
    total = len(df)

    rows = df if limit <= 0 else df.tail(limit)
    draws = [_row_to_draw(r, num_cols) for _, r in rows.iterrows()]

    latest = None
    if total:
        latest = dict(draws[-1])
        if pillar.supports(g):
            counts = pillar.pillar_counts(latest["nums"], g.num_max)
            latest["pillar_dist"] = " + ".join(str(c) for c in counts)
            latest["hits_summary"] = pillar.result_text(
                pillar.hits_from_counts(counts))

    # 下一期(還沒開):期號 = 最新期 +1,日期 = 下一次開獎的**台灣日期**。
    # 之前前端誤把下一期的日期沿用「已開最新一期」的日期(例如 206 顯示成 205
    # 的 08-24),這裡用 drawtime 算出真正的下一期開獎日,前端直接拿去用。
    # 期號非純數字(如六合彩 2026/092)或時刻表未登記則回 None,前端自行退回舊行為。
    nxt = None
    if latest and re.fullmatch(r"\d+", str(latest.get("issue", ""))):
        moment = drawtime.next_draw(game)
        if moment is not None:
            nxt = {
                "issue": str(int(latest["issue"]) + 1),
                "date": moment.date().strftime("%Y-%m-%d"),
            }

    return {"game": game, "count": total, "draws": draws,
            "latest": latest, "next": nxt}
