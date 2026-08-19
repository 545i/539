"""開獎統計:遺漏、冷熱號、頻率,以及新功能「區間組合提醒」。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from backend.data import get_game, load_df
from core import stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/missing")
def missing(game: str = Query(...)):
    g = get_game(game)
    df = load_df(game)
    data = stats.missing(df, num_max=g.num_max)
    return [
        {"num": n, "current": v["current"], "max_gap": v["max_gap"]}
        for n, v in sorted(data.items())
    ]


@router.get("/hotcold")
def hotcold(game: str = Query(...), window: int = 30, top: int = 5):
    g = get_game(game)
    df = load_df(game)
    hot, cold = stats.hot_cold(df, window=window, top=top, num_max=g.num_max)
    return {
        "hot": [{"num": n, "count": c} for n, c in hot],
        "cold": [{"num": n, "count": c} for n, c in cold],
    }


@router.get("/frequency")
def frequency(game: str = Query(...)):
    g = get_game(game)
    df = load_df(game)
    return [
        {"num": n, "count": c}
        for n, c in stats.frequency_ranked(df, num_max=g.num_max)
    ]


@router.get("/tens-pairs")
def tens_pairs(game: str = Query(...), threshold: int = Query(3, ge=1)):
    """區間組合提醒:任意兩個十位區段連續幾期都沒開(新功能 A)。"""
    g = get_game(game)
    df = load_df(game)
    return stats.tens_pair_alerts(df, threshold=threshold, num_max=g.num_max)


@router.get("/tens-bands")
def tens_bands(game: str = Query(...)):
    """星數統計:各十位區段出現總次數、每期落幾個區段、牌型分布。"""
    g = get_game(game)
    df = load_df(game)
    star, band_totals, patterns = stats.tens_band_stats(df, num_max=g.num_max)
    return {
        "bands": stats.tens_bands(g.num_max),
        "band_totals": band_totals,
        "star_dist": star,
        "patterns": [
            {"pattern": p, "count": c, "ratio": r} for p, c, r in patterns
        ],
    }


@router.get("/parity")
def parity(game: str = Query(...)):
    """奇偶 / 大小 / 和值分布。"""
    g = get_game(game)
    df = load_df(game)
    odd, big, sums = stats.parity_size_sum(df, num_max=g.num_max)
    return {
        "odd_dist": odd,
        "big_dist": big,
        "size_split": stats.size_split(g.num_max),
        "sum_min": min(sums) if sums else 0,
        "sum_max": max(sums) if sums else 0,
        "sum_avg": (sum(sums) / len(sums)) if sums else 0,
    }
