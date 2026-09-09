"""產生「開獎 + 區間斷檔」提醒卡片的**資料(JSON)**;版面在設計好的 HTML 模板裡。

刻意把版面與資料切開:
  - 版面 = backend/templates/reminder_card.html(inline CSS + JS,從 window.__CARD__
    這包 JSON 渲染 DOM)。改版面只動這個檔。
  - 資料 = 這裡的 build_card_data(g, df) → dict。改內容只換 JSON。
  - 渲染(注入 JSON → Chromium 截圖)= core.render;發圖 = core.notify.send_photo。

三者都 best-effort,壞了退回純文字(見 backend.reminders.push_game_update)。資料來源
與文字版提醒(backend.reminders)同一批 core.stats / core.combo9000 計算,確保一致。
"""
from __future__ import annotations

from core import combo9000, stats

# 各款固定開獎時刻(顯示用;與 core.drawtime 說明一致)。
_DRAW_TIME = {"lotto539": "20:30", "marksix": "21:30", "fantasy5": "18:30"}


def _latest(df) -> dict:
    """最新一期:期號、日期、開出號碼。"""
    if df is None or len(df) == 0:
        return {"issue": "", "date": "", "nums": []}
    row = df.iloc[-1]
    nums = [int(row[c]) for c in df.columns if str(c).startswith("n")]
    return {"issue": str(row.get("issue", "")),
            "date": str(row.get("date", ""))[:10], "nums": nums}


def _pairs(df, num_max: int) -> list[dict]:
    """1800碰:任兩十位段連續幾期沒一起開(streak>=1 才列;>=3 示警)。"""
    return [{"a": p["labels"][0], "b": p["labels"][1],
             "streak": p["streak"], "alert": p["alert"]}
            for p in stats.tens_pair_alerts(df, threshold=3, num_max=num_max)
            if p["streak"] >= 1]


def _singles(df, num_max: int) -> list[dict]:
    """1800碰:單一十位段自己連續幾期沒開(streak>=1 才列;斷 1 期就示警)。"""
    groups = []
    for lbl in stats.tens_bands(num_max):
        lo, hi = lbl.split("~")
        groups.append({"label": lbl, "nums": list(range(int(lo), int(hi) + 1))})
    return [{"label": x["label"], "streak": x["streak"], "alert": x["streak"] >= 1}
            for x in stats.combo_absence_alerts(df, groups, threshold=1)
            if x["streak"] >= 1]


def _nine(df, g) -> dict | None:
    """9000碰 全段同開:四段連續幾期沒一起開(距上次全段同開)。不支援回 None。"""
    if not combo9000.supports(g):
        return None
    res = stats.combo_cooccurrence_alerts(
        df, [{"label": "全段同開", "groups": combo9000.segments(g.num_max)}],
        threshold=3)
    r = res[0] if res else {"streak": 0, "max_gap": 0, "alert": False}
    return {"streak": r["streak"], "max_gap": r["max_gap"], "alert": r["alert"]}


def _odd_even(df) -> dict | None:
    """單雙比:目前『單多 / 雙多』連續幾期(翻面歸 0)。無資料 / 平手回 None。"""
    draws = stats.draws_as_lists(df)
    if not draws:
        return None

    def side(draw):
        odd = sum(1 for n in draw if n % 2 == 1)
        even = len(draw) - odd
        return "單多" if odd > even else ("雙多" if even > odd else None)

    cur = side(draws[-1])
    if cur is None:
        return None
    streak = 0
    for draw in reversed(draws):
        if side(draw) == cur:
            streak += 1
        else:
            break
    return {"side": cur, "streak": streak}


def _thirds_missing(df, num_max: int) -> list[dict]:
    """前中後三段,各段目前有遺漏(current>=1)的號碼,依遺漏由大到小。"""
    b1 = round(num_max / 3)
    b2 = round(num_max * 2 / 3)
    bands = [("前段", range(1, b1 + 1)),
             ("中段", range(b1 + 1, b2 + 1)),
             ("後段", range(b2 + 1, num_max + 1))]
    miss = stats.missing(df, num_max)
    out = []
    for name, rng in bands:
        items = [(n, miss.get(n, {}).get("current", 0)) for n in rng]
        items = sorted([(n, c) for n, c in items if c >= 1], key=lambda t: -t[1])
        out.append({"name": name, "items": [{"n": n, "miss": c} for n, c in items]})
    return out


def _hotcold(df, num_max: int, window: int = 30, top: int = 8) -> dict:
    """冷熱號排名(各取 top 名):
      hot  近 window 期最常開 —— [{n, c}](c=開出次數)
      cold 目前最久沒開(遺漏拖牌)—— [{n, miss}](miss=已幾期沒開)
    冷號改用「目前遺漏」而非低頻,語意才是「養牌/拖牌」(參考用戶提供的樣式)。
    """
    hot, _ = stats.hot_cold(df, window=window, top=top, num_max=num_max)
    miss = stats.missing(df, num_max)
    cold = sorted(miss.items(), key=lambda kv: (-kv[1]["current"], kv[0]))[:top]
    return {"window": window,
            "hot": [{"n": n, "c": c} for n, c in hot],
            "cold": [{"n": n, "miss": v["current"]} for n, v in cold]}


def build_card_data(g, df) -> dict:
    """一張提醒卡片的完整資料包(JSON-safe);餵給 reminder_card.html 的 window.__CARD__。

    schema:
      game   str          遊戲顯示名
      issue  str          最新期號
      date   str          最新開獎日期(YYYY-MM-DD)
      time   str          該款固定開獎時刻(顯示用,可空)
      nums   list[int]    最新開出號碼
      singles list[{label,streak,alert}]  1800碰 單一十位段斷檔(streak>=1,斷1期就 alert)
      pairs  list[{a,b,streak,alert}]   1800碰 十位段配對斷檔(streak>=1)
      nine   {streak,max_gap,alert}|null  9000碰 全段同開(不支援的款為 null)
      thirds list[{name, items:[{n,miss}]}]  前中後段目前遺漏
      odd_even {side,streak}|null       單雙比(平手 / 無資料為 null)
      hotcold {window, hot:[{n,c}], cold:[{n,c}]}  近 window 期冷熱號排名
    """
    latest = _latest(df)
    return {
        "game": g.name,
        "issue": latest["issue"],
        "date": latest["date"],
        "time": _DRAW_TIME.get(getattr(g, "key", ""), ""),
        "nums": latest["nums"],
        "singles": _singles(df, g.num_max),
        "pairs": _pairs(df, g.num_max),
        "nine": _nine(df, g),
        "thirds": _thirds_missing(df, g.num_max),
        "odd_even": _odd_even(df),
        "hotcold": _hotcold(df, g.num_max),
    }
