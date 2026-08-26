"""對接人帳單解析 + 與我們記帳流水對帳(第一版格式)。

對接人把我們的下注依「碰級」歸成 二 / 三 / 四 三桶,各桶合併多種玩法:
  二 = 1組 + 2組(二合) + 二星(星碰)
  三 = 1800碰(三柱) + 八顆三星(星碰)
  四 = 八顆四星(星碰)          # 9000碰目前只有提醒、未記錄,先擱置

帳單格式(第一版,可能還有別種,之後再擴充 parse_bill):

    8/24
    539獎號
    09、10、19、23、26
    539牌支
    二2090支 150062
    三 2640支 165000
    四 1050支 51765
    牌支共收366827
    三中4碰 228000
    合計  收 138827

對帳:抓「同版 × 同日期 × 同遊戲」的記帳流水(已自動對獎),照三桶加總支/成本/
中碰/得到的錢,和帳單並排比,標出差異。成本一律用該版盤口(共用盤口已移除)。
"""
from __future__ import annotations

import datetime as dt
import re

# 桶 → 星級(二=2 / 三=3 / 四=4);顯示與換算中碰用
BUCKET_STAR = {"二": 2, "三": 3, "四": 4}
STAR_BUCKET = {2: "二", 3: "三", 4: "四"}

# 遊戲名關鍵字 → game key
_GAME_KEYS = [("天天樂", "fantasy5"), ("fantasy", "fantasy5"),
              ("六合彩", "marksix"), ("marksix", "marksix"),
              ("539", "lotto539"), ("今彩", "lotto539")]

# 全形數字 / 標點攤平
_NORM = {ord("０") + i: str(i) for i in range(10)}
_NORM.update({ord("，"): ",", ord("、"): ",", ord("："): ":", ord(" "): " "})

_DATE_RE = re.compile(r"^(\d{1,2})\s*/\s*(\d{1,2})$")
_SLIP_RE = re.compile(r"^([二三四])\s*(\d+)\s*支\s*([\d,]+)")
_TOTAL_RE = re.compile(r"共收\s*([\d,]+)")
_WIN_RE = re.compile(r"^([二三四])\s*中\s*(\d+)\s*碰\s*([\d,]+)")
_NET_RE = re.compile(r"合計.*?收\s*([\d,]+)")

# ── 第二種帳單格式(碰數彙總,無每桶成本):─────────────────
#   今彩
#   全5320 包三1800 三840 四1050      ← 各類碰數(全=車=二桶、包三+三=三桶、四=四桶)
#   收604163                          ← 總額(沒寫每桶成本就對照總金額)
# 也認 539牌支604163 / 共604163 這種「牌支/共 + 數字」的總額寫法。
_SEG_TOKEN_RE = re.compile(r"(全|二|三|四)\s*(\d+)")   # 包三 的「包」不在字元類,自動歸「三」
_SEG_MAP = {"全": 2, "二": 2, "三": 3, "四": 4}
_PAIZHI_RE = re.compile(r"牌支\s*([\d,]+)\s*$")        # 539牌支604163
_GONG_RE = re.compile(r"^共\s*([\d,]+)\s*$")           # 共604163
_SHOU_RE = re.compile(r"^收\s*([\d,]+)\s*$")           # 收604163


def _int(s: str) -> int:
    return int(str(s).replace(",", "").strip() or 0)


def _game_of(line: str) -> str | None:
    for kw, key in _GAME_KEYS:
        if kw in line:
            return key
    return None


def _infer_date(month: int, day: int, today: dt.date | None = None) -> str:
    """只有月/日 → 補年份:預設今年,若比今天還晚超過 7 天就當去年。"""
    today = today or dt.date.today()
    try:
        d = dt.date(today.year, month, day)
    except ValueError:
        return ""
    if (d - today).days > 7:
        d = dt.date(today.year - 1, month, day)
    return d.isoformat()


def parse_bill(text: str, today: dt.date | None = None) -> dict:
    """把一張帳單文字解析成結構;認不出來的欄位留空 / 空清單,不丟例外。

    回 {date, game, draw, slips:{star:{units,cost}}, total_cost, wins:[{star,carry,amount}],
        net, errors:[...]}。
    """
    date, game = "", None
    draw: list[int] = []
    slips: dict[int, dict] = {}
    wins: list[dict] = []
    total_cost, net = 0, 0
    errors: list[str] = []

    for raw in (text or "").splitlines():
        line = raw.translate(_NORM).strip()
        if not line:
            continue

        m = _DATE_RE.match(line)
        if m and not date:
            date = _infer_date(int(m.group(1)), int(m.group(2)), today)
            continue

        g = _game_of(line)
        if g and game is None:
            game = g
            # 同一行就帶了獎號(少見)也順手抓
        # 一行純號碼(逗號 / 空白分隔,至少 3 個)當開獎號
        nums = re.findall(r"\d{1,2}", line)
        if not draw and ("獎號" not in line) and ("支" not in line) \
                and ("碰" not in line) and ("收" not in line) \
                and len(nums) >= 3 and not _DATE_RE.match(line):
            vals = [int(n) for n in nums]
            if all(1 <= v <= 49 for v in vals):
                draw = vals
                continue

        m = _SLIP_RE.match(line)
        if m:
            star = BUCKET_STAR[m.group(1)]
            slips[star] = {"units": _int(m.group(2)), "cost": _int(m.group(3))}
            continue

        m = _WIN_RE.match(line)
        if m:
            wins.append({"star": BUCKET_STAR[m.group(1)],
                         "carry": _int(m.group(2)), "amount": _int(m.group(3))})
            continue

        m = _TOTAL_RE.search(line)
        if m and "牌支" in line or (m and total_cost == 0 and "合計" not in line):
            total_cost = _int(m.group(1))
            continue

        m = _NET_RE.search(line)
        if m:
            net = _int(m.group(1))
            continue

        # ── 第二種格式 ──
        # 碰數彙總行(需有「全」或「包」當招牌,免得誤吃舊格式的「三 2640支…」)
        if ("全" in line or "包" in line) and _SEG_TOKEN_RE.search(line):
            for tok, n in _SEG_TOKEN_RE.findall(line):
                star = _SEG_MAP[tok]
                sl = slips.setdefault(star, {"units": 0, "cost": 0})
                sl["units"] = int(sl.get("units", 0)) + _int(n)
            continue
        # 「539牌支604163」/「共604163」= 總成本(第一個出現的當總額)
        m = _PAIZHI_RE.search(line) or _GONG_RE.match(line)
        if m and total_cost == 0:
            total_cost = _int(m.group(1))
            continue
        # 「收604163」= 這張單的實收(淨額);沒有每桶成本時就靠這個總額對帳
        m = _SHOU_RE.match(line)
        if m:
            net = _int(m.group(1))
            if total_cost == 0:
                total_cost = _int(m.group(1))
            continue

    if not date:
        errors.append("找不到日期(格式應如 8/24)")
    if game is None:
        errors.append("找不到遊戲(539 / 天天樂 / 六合彩)")
    if not slips:
        errors.append("找不到牌支(二/三/四 各 N支 金額)")

    return {"date": date, "game": game, "draw": draw, "slips": slips,
            "total_cost": total_cost, "wins": wins, "net": net, "errors": errors}


# ── 對帳:我們的流水(已對獎) vs 帳單 ─────────────────────────
_CARRY_RE = re.compile(r"中\s*([\d,]+)\s*碰")


def record_bucket(rec: dict) -> int | None:
    """這筆記帳屬於哪個桶(2/3/4 星級);不屬於回 None。"""
    mode = rec.get("mode")
    if mode in ("single", "multi"):
        return 2                     # 二合 1組/2組 → 二桶
    if mode == "pillar1800":
        return 3                     # 三柱1800碰 → 三桶
    if mode == "combo9000":
        return 4                     # 9000碰:每碰 = 一注四星 → 四桶
    if mode == "combo":              # 星碰:看星數
        pt = str(rec.get("playType", ""))
        for s, kw in ((2, "二星"), (3, "三星"), (4, "四星")):
            if kw in pt:
                return s
        st = rec.get("stars")
        if st in (2, 3, 4):
            return int(st)
    return None


def _carry_of(rec: dict) -> int:
    """從結算結果「中 N 碰」取中碰數;二合(中顆)或待開獎回 0。"""
    m = _CARRY_RE.search(str(rec.get("result", "")))
    return _int(m.group(1)) if m else 0


def _cars(rec: dict) -> float:
    """支數 / 車數:優先 cars,退而求其次 units;都沒有當 1。"""
    for k in ("cars", "units"):
        v = rec.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            return float(v)
    return 1.0


def _total_carry(rec: dict, num_max: int = 39) -> int:
    """這筆的「總碰/注數」= 對接人帳單的「支」。

    星碰(combo):betsCount 是「每支幾碰」,× 支數。
    二合(single/multi):每顆會和其餘 (num_max−1) 顆配成二星碰 → 顆 × 車 × (num_max−1)。
    三柱1800碰:betsCount 已是總注數(units × 1800),直接用。
    """
    bc = int(rec.get("betsCount", 0) or 0)
    mode = rec.get("mode")
    if mode == "combo":
        return int(round(bc * _cars(rec)))
    if mode in ("single", "multi"):
        return int(round(bc * _cars(rec) * max(1, num_max - 1)))
    return bc


def _slip(bill: dict, star: int) -> dict:
    slips = bill.get("slips") or {}
    return slips.get(star) or slips.get(str(star)) or {}


def reconcile(bill: dict, records: list[dict]) -> dict:
    """把我們的流水分桶加總,和帳單並排比;回傳每桶 我們/他/差異 + 提示。"""
    try:
        from core import games
        num_max = games.get(bill.get("game") or "").num_max
    except Exception:       # noqa: BLE001
        num_max = 39
    buckets = {s: {"units": 0, "cost": 0, "payout": 0, "carry": 0, "n": 0}
               for s in (2, 3, 4)}
    for rec in records:
        s = record_bucket(rec)
        if s is None:
            continue
        b = buckets[s]
        b["units"] += _total_carry(rec, num_max)   # 總碰/注數(= 對接人的「支」)
        b["cost"] += round(float(rec.get("cost", 0) or 0))
        b["payout"] += round(float(rec.get("payout", 0) or 0))
        b["carry"] += _carry_of(rec)
        b["n"] += 1

    rows = []
    for star in (2, 3, 4):
        ours = buckets[star]
        sl = _slip(bill, star)
        t_units = int(sl.get("units", 0) or 0)
        t_cost = int(sl.get("cost", 0) or 0)
        t_win = sum(w["amount"] for w in bill.get("wins", []) if w["star"] == star)
        t_carry = sum(w["carry"] for w in bill.get("wins", []) if w["star"] == star)
        rows.append({
            "bucket": STAR_BUCKET[star],
            "star": star,
            "n": ours["n"],
            "units": {"ours": ours["units"], "theirs": t_units,
                      "diff": ours["units"] - t_units},
            "cost": {"ours": ours["cost"], "theirs": t_cost,
                     "diff": ours["cost"] - t_cost},
            "carry": {"ours": ours["carry"], "theirs": t_carry,
                      "diff": ours["carry"] - t_carry},
            "payout": {"ours": ours["payout"], "theirs": t_win,
                       "diff": ours["payout"] - t_win},
        })

    total_ours = sum(b["cost"] for b in buckets.values())
    total_theirs = int(bill.get("total_cost", 0) or 0)
    have_records = any(b["n"] for b in buckets.values())
    cost_gap = total_ours - total_theirs
    # 有紀錄、成本落差超過一半(或 > 1 萬)→ 可能貼錯日期的帳單
    maybe_wrong_date = have_records and abs(cost_gap) > max(total_theirs * 0.5, 10000)

    # 該日期中獎金額 + 最終需付(誰付誰):需付 = 總成本 − 總得到
    payout_ours = sum(b["payout"] for b in buckets.values())
    payout_theirs = sum(w["amount"] for w in bill.get("wins", []))
    net_ours = total_ours - payout_ours          # 正 = 我方要付,負 = 對方要付
    net_theirs = int(bill.get("net", total_theirs - payout_theirs) or 0)

    return {
        "rows": rows,
        "total_cost_ours": total_ours,
        "total_cost_theirs": total_theirs,
        "cost_gap": cost_gap,
        "payout_ours": payout_ours,
        "payout_theirs": payout_theirs,
        "net_ours": net_ours,
        "net_theirs": net_theirs,
        "have_records": have_records,
        "maybe_wrong_date": maybe_wrong_date,
    }
