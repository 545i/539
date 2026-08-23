"""開獎統計:遺漏、冷熱號、頻率,以及新功能「區間組合提醒」。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend import reminders, watch_store
from backend.data import get_game, load_df
from backend.deps import current_user
from core import notify, stats

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


class IntervalGroup(BaseModel):
    label: str
    nums: list[int] = Field(default_factory=list)


class IntervalPairsIn(BaseModel):
    game: str
    threshold: int = Field(3, ge=1)
    groups: list[IntervalGroup]


@router.post("/interval-pairs")
def interval_pairs(body: IntervalPairsIn):
    """自訂區間的兩兩配對提醒:使用者自己定義區間(含號碼清單),回各配對連續幾期都沒開。"""
    get_game(body.game)  # 驗證遊戲存在
    df = load_df(body.game)
    groups = [{"label": g.label, "nums": g.nums} for g in body.groups]
    return stats.interval_pair_alerts(df, groups, threshold=body.threshold)


class ComboAbsenceIn(BaseModel):
    game: str
    threshold: int = Field(3, ge=1)
    combos: list[IntervalGroup]  # 每組 = {label, nums},沿用同一個結構


@router.post("/combo-absence")
def combo_absence(body: ComboAbsenceIn):
    """特殊組合提醒:一組號碼整組連續幾期都沒開(例:01 10 20 30 全部沒開)。"""
    get_game(body.game)
    df = load_df(body.game)
    combos = [{"label": c.label, "nums": c.nums} for c in body.combos]
    return stats.combo_absence_alerts(df, combos, threshold=body.threshold)


class CooccurCombo(BaseModel):
    label: str
    groups: list[list[int]] = Field(default_factory=list)  # 數個區間,各自的號碼


class ComboTogetherIn(BaseModel):
    game: str
    threshold: int = Field(3, ge=1)
    combos: list[CooccurCombo]


@router.post("/combo-together")
def combo_together(body: ComboTogetherIn):
    """區間組合同時出現:數個區間連續幾期沒有『全部同時開出』(距上次全部一起出現)。"""
    get_game(body.game)
    df = load_df(body.game)
    combos = [{"label": c.label, "groups": c.groups} for c in body.combos]
    return stats.combo_cooccurrence_alerts(df, combos, threshold=body.threshold)


# ── 區間組合斷檔:公共設定 + Telegram 提醒 ──────────────────
class ComboWatchItem(BaseModel):
    label: str = ""
    groups: list[list[int]] = Field(default_factory=list)
    threshold: int = Field(watch_store.DEFAULT_THRESHOLD, ge=1)


class ComboWatchIn(BaseModel):
    game: str
    combos: list[ComboWatchItem] = Field(default_factory=list)


@router.get("/combo-watch")
def get_combo_watch(game: str = Query(...)):
    """這款目前盯的區間組合(全站公共;含各自的斷檔門檻)。"""
    get_game(game)
    return watch_store.get_combos(game)


@router.put("/combo-watch")
def set_combo_watch(body: ComboWatchIn, user: str = Depends(current_user)):
    """整組覆寫這款的區間組合設定(全站共用,改一次全站生效)。"""
    get_game(body.game)
    combos = [c.model_dump() for c in body.combos]
    return watch_store.set_combos(body.game, combos)


@router.post("/combo-watch/test")
def test_combo_watch(game: str = Query(...), user: str = Depends(current_user)):
    """立即檢查並(若有斷檔)推一則 Telegram —— 測試提醒是否會發。"""
    get_game(game)
    alerts = reminders.check_combo_watch(game)
    sent = reminders.notify_combo_watch(game)
    return {"alerts": alerts, "sent": sent, "notify_enabled": notify.enabled()}


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
