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

    # 下一期(還沒開):不論期號格式都帶「下一次開獎時刻」——
    #   date  下一次開獎的**台灣日期**(YYYY-MM-DD)
    #   at    下一次開獎的完整時刻(ISO,含 +08:00),給前端跑倒數用
    #   issue 只有在最新期號是純數字時才附(= 最新期 +1);六合彩期號 2026/093
    #         非純數字,故只有 date/at、沒有 issue。
    # 主來源是 drawtime.next_draw(依各款時刻表算,不依賴期號);理論上三款都算得出,
    # 只有時刻表未登記(不該發生)才會是 None,此時退回 sc888 index 頁的下一期時刻備援。
    # sc888 只在 drawtime 缺時才呼叫,不會拖慢 history 主流程。
    nxt = None
    moment = drawtime.next_draw(game)
    if moment is None:
        from core import scraper_sc888
        moment = scraper_sc888.fetch_next_time(game)
    if moment is not None:
        nxt = {
            "date": moment.date().strftime("%Y-%m-%d"),
            "at": moment.isoformat(),
        }
        if latest and re.fullmatch(r"\d+", str(latest.get("issue", ""))):
            nxt["issue"] = str(int(latest["issue"]) + 1)

    return {"game": game, "count": total, "draws": draws,
            "latest": latest, "next": nxt}
