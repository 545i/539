"""流水帳的「開獎核對」:拿某一期的真實開獎號,把一筆記帳重新對獎、算損益。

前端的核對列表可以事後改一筆的期數;改完就用這裡把該期開獎號抓進來、判定中
了幾顆 / 幾碰,再依各下法的派彩規則重算 payout 與 pnl。**money 規則只寫在這一
個地方**(後端權威),登入(存 DB)與未登入(前端暫存)兩條路都呼叫這裡,不
各算各的。

各下法的對獎與派彩:
- single / multi  二合買牌的兩個「組」(1組 / 2組),派彩公式統一:命中幾顆 ×
                  車數 × 每車中獎可得(成本 2755 / 車 → 中一顆得 21200 / 車,不除以 4)。
                  (single 是舊「單顆」的 mode key,如今就是 1組;不再特例。)
- pillar1800  三柱全包,命中注數只可能是 4 / 3 / 0(見 core.pillar),
              回收 = 支數 × 命中注數 × 每注可得。
- combo   星碰用 core.combo.star_hits_of(中的碰數),其餘連碰家族用 hits_of。
          回收 = 中的碰/注數 × 中一碰可得(盤口後台可改) × 支數。
          注:連碰家族的「膽」沒存進紀錄,這裡一律當 dans=0(全碰)——
          對星碰與連碰(全碰)精確,對立柱 / 拖膽是近似。

**手填中獎顆數**(hit_count 不為 None):使用者忘記期數但記得中幾顆時,不看 draw,
直接用該下法「每中一單位」的派彩乘上手填數量。drawBalls 維持原值(不清空)。

draw 傳 None 且沒手填(該期還沒開 / 查不到)時,退回「待開獎」:清空開獎號、
payout / pnl 歸零,不亂算。cost 一律沿用原紀錄(投入的錢不因對獎而變)。
"""
from __future__ import annotations

import re

from backend import edition_store
from core import combo, pillar
from core.games import GameConfig


def _edition(record: dict) -> int:
    """紀錄屬於哪個版;沒標就當第一版(eid=1)。"""
    v = record.get("edition")
    try:
        return int(v) if v else 1
    except (ValueError, TypeError):
        return 1


def _odds(record: dict, g: GameConfig) -> dict:
    """這筆紀錄該用的盤口(依它的版 × 遊戲);讀不到就回該版預設。"""
    return edition_store.get_odds(_edition(record), g.key)


def _f(record: dict, key: str, default: float = 0.0) -> float:
    v = record.get(key)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def _cars(record: dict) -> float:
    """車數 / 支數:優先 cars,退而求其次 units。"""
    c = _f(record, "cars", 0.0)
    return c if c > 0 else _f(record, "units", 0.0)


# 前端 playType 的星數是中文(STAR_NAMES:二星/三星/四星),不是阿拉伯數字
_STAR_WORD = {"二": 2, "三": 3, "四": 4, "五": 5, "六": 6}


def _stars_of(play_type: str) -> int:
    """從 playType 取星數;支援中文星名。取不到當 3 星。

    playType 形如「星碰 三星 (12 支)」「連碰(全碰) 三星 (5 支)」——
    **不能直接抓第一個數字**,那會抓到「12 支」的支數。認「X星」的 X:
    先中文(二/三/四/五/六),再退而求其次認阿拉伯數字接「星」。
    """
    m = re.search(r"([二三四五六])星", play_type or "")
    if m:
        return _STAR_WORD[m.group(1)]
    m = re.search(r"(\d+)\s*星", play_type or "")
    return int(m.group(1)) if m else 3


def _manual(record: dict, hit_count: int, g: GameConfig) -> dict:
    """手填中獎數量:不看開獎號,直接用該下法「每中一單位」的派彩換算。

    drawBalls 不動(使用者不記得期數,本來就沒有開獎號可填)。
    """
    out = dict(record)
    cost = _f(record, "cost", 0.0)
    mode = record.get("mode")
    cars = _cars(record)
    k = max(0, int(hit_count))
    odds = _odds(record, g)

    if mode == "combo":
        stars = _stars_of(str(record.get("playType", "") or ""))
        prize = float(odds.get(f"combo_prize{stars}", g.default_bet_prize) or 0.0)
        payout = k * prize * cars
        result = f"中 {k} 碰(手填)" if k > 0 else "槓龜(手填)"
    elif mode == "pillar1800":
        payout = k * cars * odds["bet_prize"]
        result = f"中 {k} 碰(手填)" if k > 0 else "槓龜(手填)"
    else:  # single / multi 二合組:每中一顆 = 車數 × 每車中獎(不除以 4)
        payout = k * cars * odds["win_payout"]
        result = f"中 {k} 顆(手填)" if k > 0 else "槓龜(手填)"

    out["payout"] = round(float(payout))
    out["pnl"] = round(float(payout) - cost)
    out["result"] = result
    return out


def settle(record: dict, draw: list[int] | None, g: GameConfig,
           hit_count: int | None = None) -> dict:
    """回傳「對過獎」的紀錄(淺拷貝),更新 drawBalls / result / payout / pnl。

    只動對獎會變的欄位,其餘(selectedBalls / cost / 期數 …)原樣保留。
    hit_count 有值時走手填(不看 draw,見 _manual)。
    """
    if hit_count is not None:
        return _manual(record, hit_count, g)

    out = dict(record)
    cost = _f(record, "cost", 0.0)

    # 該期還沒開 / 查不到 → 待開獎,不硬算
    if not draw:
        out["drawBalls"] = []
        out["result"] = "待開獎"
        out["payout"] = 0.0
        out["pnl"] = 0.0
        return out

    draw = [int(x) for x in draw]
    out["drawBalls"] = draw
    selected = [int(x) for x in record.get("selectedBalls", []) or []]
    mode = record.get("mode")
    cars = _cars(record)
    odds = _odds(record, g)   # 依這筆的版 × 遊戲取盤口

    if mode in ("single", "multi"):
        # 二合兩組(1組/2組)派彩統一:命中幾顆 × 車數 × 每車中獎(不除以 4)
        matched = len(set(selected) & set(draw))
        payout = matched * cars * odds["win_payout"]
        result = f"中 {matched} 顆" if matched > 0 else "槓龜"

    elif mode == "pillar1800":
        groups = record.get("pillars") or []
        if groups:
            # 自訂柱(部分包牌):過關注數 = 各柱命中數相乘(∩ 開獎),與全包同一套公式
            hits = [len({int(x) for x in gp} & set(draw)) for gp in groups]
            ph = 1
            for h in hits:
                ph *= h
            payout = cars * ph * odds["bet_prize"]
            result = f"中 {ph:,} 碰" if ph > 0 else "槓龜(斷柱)"
            out["pillarDist"] = " × ".join(str(h) for h in hits)
        else:
            counts = pillar.pillar_counts(draw, g.num_max)
            ph = pillar.hits_from_counts(counts)          # 4 / 3 / 0
            payout = cars * ph * odds["bet_prize"]
            result = pillar.result_text(ph) if ph else "槓龜(斷柱)"
            out["pillarDist"] = " + ".join(str(c) for c in counts)

    elif mode == "combo":
        play_type = str(record.get("playType", "") or "")
        stars = _stars_of(play_type)
        prize = float(odds.get(f"combo_prize{stars}", g.default_bet_prize) or 0.0)
        if play_type.startswith("星碰"):
            wh = combo.star_hits_of(stars, draw, selected)
            result = f"中 {wh} 碰" if wh > 0 else "槓龜"
        else:
            # 膽沒存進紀錄,連碰家族一律當 dans=0(全碰精確,立柱/拖膽近似)
            wh = combo.hits_of(stars, draw, selected, ())
            result = f"中 {wh:,} 注" if wh > 0 else "槓龜"
        payout = wh * prize * cars

    else:
        # 未知下法:只填開獎號,不動金額
        return out

    out["payout"] = round(float(payout))
    out["pnl"] = round(float(payout) - cost)
    out["result"] = result
    return out
