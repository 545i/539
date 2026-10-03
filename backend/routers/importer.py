"""快速上傳下注紀錄:貼一段文字 → 解析成多筆記帳流水。

使用者手上的下注單是純文字(從通訊軟體複製過來的),一筆一筆重敲進四個下注
分頁太慢。這裡把那段文字直接翻成 ledger 的紀錄。

**認得的四種寫法**(每一行判一次,順序有意義):

    02x50車                       單顆(single):1 顆號碼、50 車
    09_15_19_20x20車              多顆(multi):4 顆號碼、20 車
    02_09_15_19_20_25_28_33       選號(先記著,不成一筆)
    八顆三星1200                   星碰(combo):用上面那組選號,三星、12 支
    八顆四星1200                   星碰(combo):同一組選號,四星、12 支
    10_18 / 20_29 / 其他400        1800碰(pillar1800):三行一整組 = 一筆、4 支
    20_29(去除24) / 30_39 / 其他100 1800碰 自訂分柱:前兩行是柱(起訖範圍,可去除號碼),
                                   其他 = 剩下全部(含被去除的);前兩行合計最多 19 顆

規則兩條就講完:**支數 = 金額 ÷ 100**(1200 → 12 支、400 → 4 支);
**車數 = 「車」前面那個數字**(直接用,不再換算)。中文顆數(「八顆」)不解析
—— 顆數以選號那行實際有幾個號碼為準,兩者不一致時以號碼為準。

成本一律走 core:星碰 combo.star_bets × combo.market_cost(後台可改的盤口)、1800碰
pillar.total_bets × GameConfig.default_bet_cost、二合 押幾顆 × 車數 × 每車成本
(與 backend/routers/erhe.py 的 plan 同一條式子)。這裡不寫死任何金額。

**這一版不做結算**:每筆的 result 一律「待開獎」、payout / pnl 都是 0,
開獎之後另外做對獎。解析不出來的行收進 errors 回給前端,不會讓整包失敗。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import (audit_store, autosettle, cycle_store, edition_store,
                     group_store, ledger_store, settle)
from backend.data import get_game
from backend.deps import current_user
from core import combo as combo_mod
from core import combo9000 as combo9000_mod
from core import games as games_mod
from core import pillar as pillar_mod
from core.games import GameConfig

router = APIRouter(prefix="/ledger", tags=["ledger"])

# 一「支」= 100 元的寫法(1200 → 12 支)。組頭的單子就是這樣報的。
UNITS_PER_AMOUNT = 100.0

# 多顆下注的盤口換算,與前端 MultiBetTab 一致:
# 每顆每車成本 = 每車成本 ÷ 20(今彩539 → 2755 / 20 = 137.75)。
# 單顆下注不除(押 1 顆、每車就是 default_cost_per_car)。

# 全形數字 / 全形 X / 各種乘號都先攤平成半形,免得每條 regex 各寫一次
_NORMALIZE = {ord("０") + i: str(i) for i in range(10)}
_NORMALIZE.update({
    ord("Ｘ"): "x", ord("ｘ"): "x", ord("X"): "x", ord("×"): "x", ord("*"): "x",
    ord("＿"): "_", ord("车"): "車", ord("顆"): "顆",
})

# 行內分隔:換行之外,逗號 / 頓號 / 分號也當換行(貼過來常被壓成一行)
_SPLIT_RE = re.compile(r"[\n\r,,;;、]+")

# 02x50車 / 09_15_19_20x20車 / 21_24x20(車可省略)—— x 前面是號碼(可含底線),
# 後面是車數;結尾的「車」字寫不寫都認。號碼間 / 與 x 之間多打的底線與空白
# (03_21_28_x50、03__21x50)一律容忍,交給 _nums 清乾淨。
_CAR_RE = re.compile(r"^([0-9]{1,2}(?:[_\s]+[0-9]{1,2})*)[_\s]*x\s*([0-9]+)\s*車?$")
# 一行純號碼(有底線)= 選號,或 1800碰 的柱別行(10_18、20_29);首尾 / 連續底線容忍
_PICK_RE = re.compile(r"^[_\s]*[0-9]{1,2}(?:[_\s]+[0-9]{1,2})+[_\s]*$")
# 八顆三星1200 / 三星1200 / 8顆3星1200 —— 第一個 group 是宣告顆數(可省略)
_STAR_RE = re.compile(
    r"^(?:([一二三四五六七八九十0-9]+)\s*顆)?\s*([二三四234])\s*星\s*([0-9]+)$")
# 1800碰 柱別行:起訖範圍 20_29,可帶去除號碼 20_29(去除24) / 20_29(去除24_25)。
# 多個去除號碼用底線或空白分隔(頓號、逗號會被 _SPLIT_RE 當換行切掉)。
_PILLAR_RANGE_RE = re.compile(
    r"^([0-9]{1,2})\s*_\s*([0-9]{1,2})\s*"
    r"(?:[(（]\s*(?:去除|排除|除去|去掉|扣除)\s*([0-9][0-9_\s]*)\s*[)）])?$")
# 1800碰 前兩柱合計上限:39 選 5 的三柱結構是 9 + 10 + 20,前兩柱超過 19 顆
# 「其他」就不足 20 顆,不再是 1800 注的結構 → 要求使用者去除號碼。
PILLAR_FRONT_MAX = 19
# 其他400 —— 1800碰 那一組的收尾行,金額在這裡
_OTHER_RE = re.compile(r"^其[他它餘余]\s*([0-9]+)$")
# 9000碰x10 —— 9000碰(四段全包)下注,不需選號。x 後面的數字換算支數:
#   整數 → 同全站慣例「÷ 100」(9000碰x10 → 0.1 支、x100 → 1 支、x50 → 0.5 支);
#   小數 → 直接當支數(9000碰x0.5 → 0.5 支)—— 否則 0.5÷100=0.005 支會誤判。
# 全形數字 / ×／＊／Ｘ 已由 _norm 攤平成 x。
_COMBO9000_RE = re.compile(r"^9000\s*碰\s*x\s*([0-9]+(?:\.[0-9]+)?)$")
# 純分隔線(___ / --- / === 之類):使用者用來隔開不同下注區塊,當空行略過、不報錯
_SEP_RE = re.compile(r"^[_\-–—=~\s]+$")

_STAR_NUM = {"二": 2, "三": 3, "四": 4, "2": 2, "3": 3, "4": 4}

# 中文數字(顆數用,最多到十幾顆就夠;超過的就當阿拉伯數字)
_CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_int(s: str) -> int:
    """把「八」「十」「十二」或「8」解析成整數;認不出來回 0。"""
    s = (s or "").strip()
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if "十" in s:  # 十X / X十 / X十Y
        left, _, right = s.partition("十")
        tens = _CN_DIGIT.get(left, 1) if left else 1
        ones = _CN_DIGIT.get(right, 0) if right else 0
        return tens * 10 + ones
    return _CN_DIGIT.get(s, 0)


def _norm(line: str) -> str:
    return line.translate(_NORMALIZE).strip()


def _nums(text: str) -> list[int]:
    """`09_15_19_20` → [9, 15, 19, 20](保留輸入順序,去重)。

    以「非數字」切段,空段 / 雜散底線 / 多餘空白一律忽略 —— 這樣
    `03_21_28_`、`03__21`、`03_ 21` 這類手滑輸入都不會讓整行崩掉。
    """
    out: list[int] = []
    for part in re.split(r"[^0-9]+", text):
        if not part:
            continue
        n = int(part)
        if n not in out:
            out.append(n)
    return out


def _units(amount: int) -> float:
    """金額 → 支數;整數支就回 int,讓 JSON 出去是 12 而不是 12.0。"""
    u = amount / UNITS_PER_AMOUNT
    return int(u) if u == int(u) else u


def _money(x: float) -> str:
    return f"${round(x):,}"


def _g(x: float) -> str:
    """去掉多餘小數(20.0 → 20、137.75 → 137.75)。"""
    return f"{x:g}"


@dataclass
class _Item:
    """解析出來的一筆(還沒變成 ledger 紀錄)。"""
    mode: str
    play_type: str
    balls: list[int]
    units: float          # 支數(星碰 / 1800碰)或 車數(1組 / 2組)
    bets_count: int       # 注 / 碰數
    cost: float
    line: str             # 產生這一筆的原文(1800碰 是三行併起來)
    stars: int = 0        # 星碰的星數(其他下法 0);提交時重算成本要用
    incomplete: bool = False  # 星碰向上補足仍湊不到宣告顆數 → 提醒使用者手動補
    cost_expr: str = ""   # 成本怎麼算出來的(給前端顯示計算式)
    base_cost: float = 0.0  # 這筆用的「每單位基礎成本」(二合每注/1800每注/連碰每碰/
                            # 9000每碰);逐筆可覆蓋,前端顯示+可改,改了就重算成本
    ball_deltas: dict = field(default_factory=dict)  # 二合個別號碼加價 {"15": 2.0}(只存非 0)
    pillars: list = field(default_factory=list)  # 1800碰自訂分柱 [[柱1],[柱2],[其他]];標準分柱為 []
    ball_detail: list = field(default_factory=list)  # 二合逐顆 [{n, cars, base}](各顆車數/每注不一時才有)


@dataclass
class _State:
    """逐行解析的中間狀態。"""
    items: list[_Item] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    picks: list[int] = field(default_factory=list)      # 最近一行選號
    pick_line: str = ""
    pending: list[str] = field(default_factory=list)    # 還沒被用掉的純號碼行
    pending_no: list[int] = field(default_factory=list)  # pending 各行的行號(1800碰提醒定位用)
    # 上方出現過的所有號碼行(1組/2組下注號 + 純選號),依先後 —— 星碰向上補足用
    number_lines: list[list[int]] = field(default_factory=list)
    erhe_n: int = 0       # 已出現幾個二合下注行(決定歸到第幾組)

    def fail(self, line_no: int, line: str, message: str) -> None:
        self.errors.append({"line_no": line_no, "line": line, "message": message})


def _fill_upward(picks: list[int], number_lines: list[list[int]],
                 declared: int) -> tuple[list[int], bool]:
    """星碰宣告 declared 顆但選號不足時,從上方所有號碼行往上去重補足。

    以最近的選號為底,再從 number_lines 由新到舊收集沒出現過的號碼,直到湊滿
    declared 顆。回 (補足後的號碼[:declared], 是否仍不足)。
    """
    gathered: list[int] = list(dict.fromkeys(picks))  # 去重保序
    for line_nums in reversed(number_lines):
        if len(gathered) >= declared:
            break
        for n in line_nums:
            if n not in gathered:
                gathered.append(n)
                if len(gathered) >= declared:
                    break
    incomplete = len(gathered) < declared
    return gathered[:declared], incomplete


# ── 各種下法的成本(全部走 core + 該版盤口,不寫死金額)────────────
def _erhe_cost(odds: dict, n_balls: int, cars: float) -> float:
    """二合:成本 = 押幾顆 × 車數 × 每車成本(每車成本取該版盤口)。"""
    return n_balls * cars * float(odds["cost_per_car"])


def _star_item(odds: dict, stars: int, picks: list[int], units: float,
               line: str, incomplete: bool = False) -> _Item:
    """星碰:碰數 = star_bets(星, 選幾顆),成本 = 支數 × 碰數 × 每碰成本(該版盤口)。

    picks 是(已向上補足的)最終號碼;incomplete 代表補足後仍不到宣告顆數,
    交給前端提醒使用者手動補後再上傳。
    """
    bets = combo_mod.star_bets(stars, len(picks))
    if bets <= 0 and not incomplete:
        raise ValueError(f"選 {len(picks)} 顆湊不出{combo_mod.star_name(stars)}碰")
    per_bet = float(odds[f"combo_cost{stars}"])
    cost = units * bets * per_bet
    return _Item(
        mode="combo",
        play_type=f"星碰 {combo_mod.star_name(stars)}({bets} 碰/支)",
        balls=picks,
        units=units,
        # 碰數欄比照連碰分頁:記「一支幾碰」,支數另外一欄,兩者不相乘
        bets_count=bets,
        cost=cost,
        line=line,
        stars=stars,
        incomplete=incomplete,
        cost_expr=f"{_g(units)} 支 × {bets} 碰 × {_money(per_bet)}/碰 = {_money(cost)}",
        base_cost=per_bet,
    )


def _normalize_pillars(g: GameConfig, pillars) -> list[list[int]]:
    """驗證 1800碰 自訂分柱並正規化;與標準分柱相同時回 [](結算走固定分柱)。

    pillars = [柱1, 柱2, 其他]:三柱互斥、窮盡 1~num_max、各柱非空,
    前兩柱合計不得超過 PILLAR_FRONT_MAX 顆。違反就丟 ValueError。
    """
    if not pillars:
        return []
    if len(pillars) != 3:
        raise ValueError("1800碰 自訂分柱要剛好三柱(兩行柱 + 其他)")
    groups = [sorted({int(n) for n in p}) for p in pillars]
    if any(not p for p in groups):
        raise ValueError("1800碰 每一柱至少要有 1 顆號碼")
    seen: set[int] = set()
    for p in groups:
        bad = [n for n in p if not 1 <= n <= g.num_max]
        if bad:
            raise ValueError(f"{g.name} 只有 1~{g.num_max} 號,不認得 {bad}")
        dup = seen & set(p)
        if dup:
            raise ValueError(f"1800碰 各柱號碼重疊:{sorted(dup)}")
        seen |= set(p)
    if seen != set(range(1, g.num_max + 1)):
        raise ValueError("1800碰 三柱合起來要涵蓋全部號碼")
    front = len(groups[0]) + len(groups[1])
    if front > PILLAR_FRONT_MAX:
        raise ValueError(f"1800碰 前兩柱合計 {front} 顆,最多 {PILLAR_FRONT_MAX} 顆,請去除號碼")
    std = [sorted(p) for p in pillar_mod.pillars(g.num_max)]
    return [] if groups == std else groups


def _pillar_item(odds: dict, g: GameConfig, units: float, line: str,
                 pillars=None) -> _Item:
    """1800碰:注數 = 三柱顆數相乘 × 支數,每注成本取該版盤口的 bet_cost。

    pillars 為自訂分柱(見 _normalize_pillars);空的就是標準三柱(9 × 10 × 20)。
    自訂分柱存進紀錄,對獎時 backend.settle 依各柱 ∩ 開獎相乘。
    """
    if not pillar_mod.supports(g):
        raise ValueError(f"{g.name}不適用 1800碰(三柱結構綁定 39 選 5)")
    groups = _normalize_pillars(g, pillars)
    bet_cost = float(odds["bet_cost"])
    if groups:
        sizes = [len(p) for p in groups]
        total = sizes[0] * sizes[1] * sizes[2]
        shape = f"{' × '.join(str(n) for n in sizes)} = "
        tag = "・自訂柱"
    else:
        total, shape, tag = pillar_mod.total_bets(g.num_max), "", ""
    cost = total * bet_cost * units
    return _Item(
        mode="pillar1800",
        play_type=f"1800碰({total:,} 注{tag})",
        balls=[],
        units=units,
        bets_count=int(round(units * total)),
        cost=cost,
        line=line,
        cost_expr=f"{shape}{total:,} 注 × {_money(bet_cost)}/注 × {_g(units)} 支 = {_money(cost)}",
        base_cost=bet_cost,
        pillars=groups,
    )


def _range_pillar(g: GameConfig, line: str) -> list[int] | None:
    """`20_29(去除24)` → [20,21,22,23,25,…,29];不是起訖格式回 None。

    起訖反寫(29_20)、超出號碼範圍、去除的號碼不在範圍內都丟 ValueError。
    """
    m = _PILLAR_RANGE_RE.match(line)
    if not m:
        return None
    lo, hi = int(m.group(1)), int(m.group(2))
    if lo > hi:
        raise ValueError(f"柱別 {line}:起號要小於迄號")
    if lo < 1 or hi > g.num_max:
        raise ValueError(f"柱別 {line}:{g.name} 只有 1~{g.num_max} 號")
    nums = list(range(lo, hi + 1))
    excl = _nums(m.group(3) or "")
    outside = [n for n in excl if n not in nums]
    if outside:
        raise ValueError(f"柱別 {line}:去除的號碼 {outside} 不在 {lo:02d}~{hi:02d} 範圍內")
    return [n for n in nums if n not in excl]


def _combo9000_item(odds: dict, g: GameConfig, units: float, line: str) -> _Item:
    """9000碰:碰數 = total_bets × 支數,每碰成本用 9000碰專屬單價(combo9000_cost;
    沒自訂時 edition_store 已讓它沿用四星 combo_cost4)。"""
    if not combo9000_mod.supports(g):
        raise ValueError(f"{g.name}不適用 9000碰(四段結構綁定 39 選 5)")
    total = combo9000_mod.total_bets(g.num_max)
    bet_cost = float(odds.get("combo9000_cost") or odds["combo_cost4"])
    cost = combo9000_mod.round_cost(bet_cost, 1, g.num_max) * units
    return _Item(
        mode="combo9000",
        play_type=f"9000碰({total:,} 碰)",
        balls=[],
        units=units,
        bets_count=int(round(units * total)),
        cost=cost,
        line=line,
        cost_expr=f"{total:,} 碰 × {_money(bet_cost)}/碰 × {_g(units)} 支 = {_money(cost)}",
        base_cost=bet_cost,
    )


# ── 解析 ─────────────────────────────────────────────────
def parse(text: str, g: GameConfig, odds: dict) -> tuple[list[_Item], list[dict]]:
    """把整段文字翻成待寫入的紀錄;認不出來的行收進 errors,不中斷。

    odds 是「這次上傳的版 × 遊戲」的盤口(見 backend.edition_store.get_odds)。
    """
    st = _State()
    for line_no, raw in enumerate(_SPLIT_RE.split(text or ""), start=1):
        line = _norm(raw)
        if not line:
            continue
        # 純分隔線(___ / --- 之類)= 使用者隔開區塊用,當空行略過不報錯
        if _SEP_RE.match(line):
            continue

        m = _COMBO9000_RE.match(line)
        if m:
            rej = _reject_game_mode(g, "combo9000")
            if rej:                       # 六合彩不支援 9000碰 → 🔴 拒絕這筆
                st.fail(line_no, line, rej)
                continue
            # 慣例:整數走「金額 ÷ 100 = 支數」(9000碰x100→1支、x50→0.5支、x10→0.1支)。
            # 但寫成小數(9000碰x0.5)時,使用者是「直接指定支數」,不再 ÷100 ——
            # 否則 0.5 會被算成 0.005 支(使用者回報的誤判)。
            raw = m.group(1)
            units = float(raw) if "." in raw else float(raw) / UNITS_PER_AMOUNT
            if units <= 0:
                st.fail(line_no, line, "支數要大於 0")
                continue
            try:
                st.items.append(_combo9000_item(odds, g, units, line))
            except ValueError as e:
                st.fail(line_no, line, str(e))
            continue

        m = _CAR_RE.match(line)
        if m:
            balls, cars = _nums(m.group(1)), int(m.group(2))
            if cars <= 0:
                st.fail(line_no, line, "車數要大於 0")
                continue
            bad = [n for n in balls if not 1 <= n <= g.num_max]
            if bad:
                st.fail(line_no, line,
                        f"{g.name} 只有 1~{g.num_max} 號,不認得 {bad}")
                continue
            # 二合下注行依「出現順序」歸組:第 1 個下注行 → 1組、第 2 個 → 2組。
            st.number_lines.append(balls)
            st.erhe_n += 1
            gid = st.erhe_n
            grp = group_store.get_group(gid)
            if grp is None:
                st.fail(line_no, line, f"超過組數,只有 {len(group_store.GID_TO_MODE)} 組")
                continue
            if not grp["enabled"]:
                st.fail(line_no, line, f"{grp['name']}已停用,無法記入")
                continue
            cpc = float(odds["cost_per_car"])
            erhe_cost = _erhe_cost(odds, len(balls), cars)
            st.items.append(_Item(
                mode=grp["mode"],
                play_type=f"{grp['name']} {cars} 車({len(balls)} 顆)",
                balls=balls,
                units=cars,
                bets_count=len(balls),
                cost=erhe_cost,
                line=line,
                cost_expr=f"{len(balls)} 顆 × {cars} 車 × {_money(cpc)}/車 = {_money(erhe_cost)}",
                base_cost=cpc / max(1, g.num_max - 1),
            ))
            continue

        m = _OTHER_RE.match(line)
        if m:
            # 1800碰 一整組(10_18 / 20_29 / 其他400)算一筆;柱別行只是標示,
            # 不是選號,所以這裡把 pending 清掉不讓它被後面的星碰行撿去用。
            labels, label_nos = st.pending[-2:], st.pending_no[-2:]   # 只取緊鄰的兩行柱別
            whole = " / ".join(labels + [line])
            st.pending, st.pending_no, st.picks, st.pick_line = [], [], [], ""
            rej = _reject_game_mode(g, "pillar1800")
            if rej:                       # 六合彩不支援三柱 → 🔴 拒絕這筆
                st.fail(line_no, whole, rej)
                continue
            try:
                # 兩行柱別都是起訖格式(20_29 / 20_29(去除24))→ 依它分柱,其他 = 剩下全部;
                # 不是起訖格式(舊單子只當標示)→ 標準三柱。
                ranges = [_range_pillar(g, lb) for lb in labels] if len(labels) == 2 else []
                pillars = None
                if len(ranges) == 2 and all(r is not None for r in ranges):
                    front = len(ranges[0]) + len(ranges[1])
                    if front > PILLAR_FRONT_MAX and not set(ranges[0]) & set(ranges[1]):
                        # 🔴 前兩柱超過上限 → 帶結構化資料讓前端彈窗選要去除的號碼
                        st.errors.append({
                            "line_no": line_no, "line": whole,
                            "code": "pillar_exclude_required",
                            "pillar_count": front,
                            "pillar_max": PILLAR_FRONT_MAX,
                            "pillar_lines": [{"line_no": no, "line": lb, "numbers": r}
                                             for no, lb, r in zip(label_nos, labels, ranges)],
                            "message": (f"1800碰 前兩柱合計 {front} 顆,最多 {PILLAR_FRONT_MAX} 顆,"
                                        f"請指定去除號碼,例如 {labels[0]}(去除{ranges[0][0]:02d})"),
                        })
                        continue
                    used = set(ranges[0]) | set(ranges[1])
                    other = [n for n in range(1, g.num_max + 1) if n not in used]
                    pillars = [ranges[0], ranges[1], other]
                st.items.append(_pillar_item(odds, g, _units(int(m.group(1))), whole,
                                             pillars=pillars))
            except ValueError as e:
                st.fail(line_no, whole, str(e))
            continue

        m = _STAR_RE.match(line)
        if m:
            rej = _reject_game_mode(g, "combo")
            if rej:                       # 六合彩不支援星碰 → 🔴 拒絕這筆
                st.fail(line_no, line, rej)
                continue
            if not st.picks:
                st.fail(line_no, line, "這行星碰前面找不到選號(要先有一行 02_09_… 的號碼)")
                continue
            stars = _STAR_NUM[m.group(2)]
            # 宣告顆數(八顆 → 8);沒寫就用最近選號那行的顆數
            declared = _cn_int(m.group(1)) if m.group(1) else len(st.picks)
            if declared <= 0:
                declared = len(st.picks)
            # 選號不足宣告顆數時,從上方所有號碼行往上去重補足
            balls, incomplete = _fill_upward(list(st.picks), st.number_lines, declared)
            whole = f"{st.pick_line} / {line}"
            try:
                st.items.append(
                    _star_item(odds, stars, balls, _units(int(m.group(3))), whole,
                               incomplete=incomplete))
            except ValueError as e:
                st.fail(line_no, whole, str(e))
            continue

        if _PICK_RE.match(line):
            picks = _nums(line)
            bad = [n for n in picks if not 1 <= n <= g.num_max]
            if bad:
                st.fail(line_no, line, f"{g.name} 只有 1~{g.num_max} 號,不認得 {bad}")
                continue
            st.picks, st.pick_line = picks, line
            st.pending.append(line)
            st.pending_no.append(line_no)
            st.number_lines.append(picks)
            continue

        # 1800碰 帶去除號碼的柱別行 20_29(去除24):只當柱別,不是選號,
        # 等「其他N」收尾行再一起成一筆(見上方 _OTHER_RE)。
        m = _PILLAR_RANGE_RE.match(line)
        if m and m.group(3):
            st.pending.append(line)
            st.pending_no.append(line_no)
            continue

        st.fail(line_no, line, "看不懂這一行")

    return st.items, st.errors


def _resolve_cycle_id(user: str, cycle_id: int | None) -> int | None:
    """決定這批上傳歸到哪個週期:body 有帶就用,沒帶就補目前進行中(open)週期;
    都沒有就 None(不歸任何週期,行為照舊)。"""
    if cycle_id is not None:
        return int(cycle_id)
    cur = cycle_store.current_cycle(user)
    return cur["id"] if cur else None


def to_record(item: _Item, g: GameConfig, bet_date: str, issue: str,
              edition: int = 1, cycle_id: int | None = None) -> dict:
    """_Item → 前端的 BetRecord(id / index / cumPnl 由前端依順序補)。

    多帶 stars / incomplete / edition:提交時後端靠 stars 重算連碰成本,incomplete
    讓前端標出「補足仍不夠」的列,edition 標記這筆屬於哪個版(對獎 / 損益要分版)。
    cycle_id 標記這筆歸到哪個週期(沒有進行中週期就留 None,行為照舊)。
    """
    return {
        "date": bet_date,
        "issue": issue,
        "game": g.name,
        "mode": item.mode,
        "edition": int(edition),
        "cycle_id": int(cycle_id) if cycle_id is not None else None,
        "playType": item.play_type,
        "units": item.units,
        "cars": item.units,
        "betsCount": item.bets_count,
        "selectedBalls": item.balls,
        "stars": item.stars,
        "incomplete": item.incomplete,
        "drawBalls": [],
        "result": "待開獎",       # 這一版不結算,開獎後另外對獎
        "cost": round(item.cost),
        "costExpr": item.cost_expr,   # 成本計算式(給前端顯示「怎麼算的」)
        "baseCost": round(item.base_cost, 4),   # 每單位基礎成本(逐筆可改)
        "ballDeltas": item.ball_deltas,         # 二合個別號碼加價 {"15": 2.0};沒有就 {}
        "pillars": item.pillars,                # 1800碰自訂分柱(對獎依各柱 ∩ 開獎相乘);標準分柱 []
        "ballDetail": item.ball_detail,         # 二合逐顆車數/每注 [{n, cars, base}];一般紀錄 []
        "payout": 0,
        "pnl": 0,
    }


def _base_field(mode: str, stars: int) -> str:
    """某 mode 的「每單位基礎成本」對應到 odds 的哪個欄位。"""
    if mode in ("single", "multi"):
        return "cost_per_car"          # 特別:實際用的是每車;基礎=每車 ÷ (num_max-1)
    if mode == "pillar1800":
        return "bet_cost"
    if mode == "combo9000":
        return "combo9000_cost"
    if mode == "combo":
        return f"combo_cost{int(stars)}"
    return ""


def _apply_base(g: GameConfig, odds: dict, mode: str, stars: int,
                base: float | None) -> dict:
    """把「逐筆基礎成本」覆蓋進 odds(回新 dict,不動原本)。base 為 None/<=0 就原樣。

    二合的 base 是「每注」基礎,換算成每車 = base × (num_max-1) 再塞 cost_per_car;
    其餘玩法的 base 就是每注/每碰,直接塞對應欄位。
    """
    if base is None or base <= 0:
        return odds
    o = dict(odds)
    if mode in ("single", "multi"):
        o["cost_per_car"] = float(base) * max(1, g.num_max - 1)
    else:
        f = _base_field(mode, stars)
        if f:
            o[f] = float(base)
    return o


def _recost(g: GameConfig, odds: dict, mode: str, balls: list[int], units: float,
            stars: int, base: float | None = None,
            ball_deltas: dict[str, float] | None = None,
            pillars: list[list[int]] | None = None,
            ball_detail: list[dict] | None = None) -> _Item:
    """依(可能被前端編輯過的)mode / 號碼 / 支或車 / 星數 + 該版盤口重算一筆成本。

    money 一律後端算 —— 前端只送使用者改完的號碼、支/車、以及**逐筆基礎成本 base**
    (可覆蓋該版盤口的每注/每碰基礎);沒給 base 就吃版盤口。金額不讓前端直接決定。

    ball_deltas:1組(single)專用,個別號碼的「每注基礎」加價(號→+N)。有給時該筆
    成本改為逐顆計:車數 × Σ(每顆每車),每顆每車 =(每注基礎 + 該號加價)×(num_max−1)。
    """
    rej = _reject_game_mode(g, mode)
    if rej:                               # 六合彩×星碰/三柱/9000碰 → 🔴 拒絕這筆
        raise ValueError(rej)
    if ball_detail and mode in ("single", "multi"):
        return _per_ball_item(g, odds, mode, ball_detail)
    balls = [int(b) for b in balls]
    bad = [n for n in balls if not 1 <= n <= g.num_max]
    if bad:
        raise ValueError(f"{g.name} 只有 1~{g.num_max} 號,不認得 {bad}")
    if units <= 0:
        raise ValueError("支數 / 車數要大於 0")

    odds = _apply_base(g, odds, mode, stars, base)   # 逐筆基礎成本覆蓋(有給才動)

    if mode == "combo":
        return _star_item(odds, int(stars), balls, units, "", incomplete=False)
    if mode == "pillar1800":
        return _pillar_item(odds, g, units, "", pillars=pillars)
    if mode == "combo9000":
        return _combo9000_item(odds, g, units, "")
    if mode in group_store.MODE_TO_GID:
        if not balls:
            raise ValueError("這一組至少要選 1 顆號碼")
        grp = group_store.get_group(group_store.MODE_TO_GID[mode])
        name = grp["name"] if grp else mode
        cpc = float(odds["cost_per_car"])
        notes = max(1, g.num_max - 1)
        default_base = cpc / notes
        deltas = ball_deltas or {}
        # 二合(1組/2組)個別號碼加價(每注基礎 +N)→ 逐顆算每車成本。含 15 的注數
        # = 車數 × (num_max−1),每注 +N,與對接人帳單「N號漲N元 X支」一致。
        use_pn = mode in ("single", "multi") and any(float(deltas.get(str(n), 0) or 0) for n in balls)
        if use_pn:
            per_car = [(default_base + float(deltas.get(str(n), 0) or 0)) * notes for n in balls]
            erhe_cost = units * sum(per_car)
            adj = [f"{n}號+{float(deltas[str(n)]):g}"
                   for n in balls if float(deltas.get(str(n), 0) or 0)]
            expr = (f"{len(balls)} 顆 × {_g(units)} 車,每車合計 {_money(sum(per_car))}"
                    f"({'、'.join(adj)}) = {_money(erhe_cost)}")
        else:
            erhe_cost = _erhe_cost(odds, len(balls), units)
            expr = f"{len(balls)} 顆 × {_g(units)} 車 × {_money(cpc)}/車 = {_money(erhe_cost)}"
        return _Item(
            mode=mode,
            play_type=f"{name} {int(units)} 車({len(balls)} 顆)",
            balls=balls,
            units=units,
            bets_count=len(balls),
            cost=erhe_cost,
            line="",
            cost_expr=expr,
            base_cost=default_base,
            # 存進紀錄,週期帳明細才看得到哪顆號碼加了多少
            ball_deltas=({str(n): float(deltas[str(n)]) for n in balls
                          if float(deltas.get(str(n), 0) or 0)} if use_pn else {}),
        )
    raise ValueError(f"未知的下注模式:{mode}")


def _per_ball_item(g: GameConfig, odds: dict, mode: str, detail: list[dict]) -> _Item:
    """二合逐顆:每顆號碼各自的車數與每注成本(絕對值;base 為 None/<=0 = 版盤口每注)。

    成本 = Σ 車數 × 每注 × (num_max−1)。各顆車數與每注都相同 → 收斂成一般紀錄
    (走原本 _recost 路徑、不存 ballDetail),舊紀錄與快速上傳格式不受影響。
    """
    notes = max(1, g.num_max - 1)
    default_base = float(odds["cost_per_car"]) / notes
    rows: list[dict] = []
    for d in detail:
        n, cars = int(d.get("n") or 0), float(d.get("cars") or 0)
        base = float(d.get("base") or 0) or default_base
        if not 1 <= n <= g.num_max:
            raise ValueError(f"{g.name} 只有 1~{g.num_max} 號,不認得 {n}")
        if any(r["n"] == n for r in rows):
            raise ValueError(f"號碼 {n:02d} 重複")
        if cars <= 0:
            raise ValueError(f"{n:02d} 號的車數要大於 0")
        rows.append({"n": n, "cars": cars, "base": base})
    if not rows:
        raise ValueError("這一組至少要選 1 顆號碼")
    balls = [r["n"] for r in rows]
    if len({r["cars"] for r in rows}) == 1 and len({r["base"] for r in rows}) == 1:
        return _recost(g, odds, mode, balls, rows[0]["cars"], 0, base=rows[0]["base"])
    grp = group_store.get_group(group_store.MODE_TO_GID[mode])
    name = grp["name"] if grp else mode
    cost = sum(r["cars"] * r["base"] * notes for r in rows)
    parts = [f"{r['n']:02d}號 {_g(r['cars'])} 車 × {_money(r['base'] * notes)}/車" for r in rows]
    each = " ".join(f"{r['n']:02d}×{_g(r['cars'])}車" for r in rows)
    return _Item(
        mode=mode,
        play_type=f"{name} {each}({len(rows)} 顆)",
        balls=balls,
        units=max(r["cars"] for r in rows),   # 代表值(上限提醒用);對獎 / 成本一律看 ballDetail
        bets_count=len(rows),
        cost=cost,
        line="",
        cost_expr=f"{' + '.join(parts)} = {_money(cost)}",
        base_cost=default_base,
        ball_detail=[{**r, "base": round(r["base"], 4)} for r in rows],
    )


# ── 防呆邊界檢查 ────────────────────────────────────────────
# 兩種嚴重度:errors(🔴 拒絕、那一筆不寫)與 warnings(🟡 提示但仍可上傳)。
# 下面這幾條依 0923 真實數據歸納:六合彩×特殊下法一律拒絕(結構綁 39 選 5);
# 期號格式 / 大車支 / 舊日期 / 重複只提醒,不阻斷。
#
# 各下法「車/支數」的上限(依 0923 實際用量取 2 倍餘裕);超過只提醒不擋。
_UNIT_LIMIT = {"single": 150, "multi": 150, "combo": 30,
               "pillar1800": 16, "combo9000": 10}
# 六合彩(49 選 6)不支援的下法 → 顯示名(星碰 / 三柱 / 9000碰 綁定 39 選 5)。
_MARKSIX_REJECT = {"combo": "星碰", "pillar1800": "三柱", "combo9000": "9000碰"}


def _reject_game_mode(g: GameConfig, mode: str) -> str | None:
    """遊戲×下法不合 → 回傳拒絕訊息(🔴 error);相容就回 None。

    六合彩(49 選 6)不支援星碰 / 三柱 / 9000碰:這些下法的段數 / 命中結構綁定
    「39 選 5」(見 core.pillar / core.combo9000 的 supports),換到 49 選 6 整套
    機率要重推,所以在解析 / 重算階段直接擋掉。
    """
    if getattr(g, "key", "") == "marksix" and mode in _MARKSIX_REJECT:
        return f"六合彩不支援{_MARKSIX_REJECT[mode]}"
    return None


def _issue_format_warning(g: GameConfig, issue: str) -> dict | None:
    """期號格式 × 遊戲不符 → 🟡 警告(踩過真實 bug:天天樂存成 539 期號)。

    天天樂(fantasy5)純數字(11981);今彩539(lotto539)9 碼(115000207);
    六合彩(marksix)YYYY/NNN(2026/093)。明顯不像就提醒確認沒選錯遊戲/期號。
    """
    issue = (issue or "").strip()
    if not issue:
        return None
    key = getattr(g, "key", "")
    ok = True
    if key == "fantasy5":
        ok = issue.isdigit() and len(issue) <= 6
    elif key == "lotto539":
        ok = issue.isdigit() and 8 <= len(issue) <= 10
    elif key == "marksix":
        ok = bool(re.match(r"^\d{4}/\d{2,3}$", issue))
    if ok:
        return None
    return {"message": f"期號「{issue}」格式看起來不像{g.name},確認沒選錯遊戲/期號"}


def _units_warning(record: dict) -> dict | None:
    """車/支數異常大 → 🟡 警告(是不是多打一位)。依 0923 上限取 2 倍餘裕。"""
    mode = record.get("mode")
    units = record.get("units") or 0
    limit = _UNIT_LIMIT.get(mode)
    if limit and isinstance(units, (int, float)) and not isinstance(units, bool) \
            and units > limit:
        return {"message": f"車/支數 {units:g} 偏大,是不是多打一位?"}
    return None


def _latest_draw_date(g: GameConfig) -> _date | None:
    """該款遊戲 CSV 裡的最新開獎日;讀不到(無檔 / 空 / 格式錯)一律回 None。"""
    from backend.data import load_df
    try:
        df = load_df(g.key)
        if df is None or df.empty or "date" not in df.columns:
            return None
        return df["date"].max().date()
    except Exception:
        return None


def _date_warning(g: GameConfig, bet_date: str) -> dict | None:
    """上傳日期比最新開獎早超過 14 天 → 🟡 警告(確認沒補錯期)。"""
    latest = _latest_draw_date(g)
    if latest is None:
        return None
    try:
        d = _date.fromisoformat((bet_date or "").strip())
    except ValueError:
        return None
    if (latest - d).days > 14:
        return {"message": f"日期 {bet_date} 比最新開獎日 {latest.isoformat()} "
                           f"早很多,確認沒補錯期"}
    return None


def _sig(record: dict) -> tuple:
    """重複判定簽章:版(edition)+ 期(issue)+ 下法(mode)+ 號碼 + 車支數(units)。"""
    balls = tuple(int(b) for b in (record.get("selectedBalls") or []))
    return (
        int(record.get("edition") or 0),
        str(record.get("issue") or ""),
        str(record.get("mode") or ""),
        balls,
        float(record.get("units") or 0),
        tuple(tuple(int(n) for n in p) for p in (record.get("pillars") or [])),
        tuple((int(d.get("n") or 0), float(d.get("cars") or 0), float(d.get("base") or 0))
              for d in (record.get("ballDetail") or [])),
    )


def _collect_warnings(g: GameConfig, bet_date: str, issue: str,
                      indexed_records: list[tuple[int, dict]],
                      existing: list[dict]) -> list[dict]:
    """組出這批的所有 🟡 警告(不阻斷上傳):期號格式 / 大車支 / 舊日期 / 重複。

    indexed_records 是 [(line_no, record), …];line_no 對齊使用者看到的第幾筆。
    existing 是「寫入前」的 ledger 快照 —— 重複判定要拿現有紀錄比,才不會跟自己
    這批對到。形狀比照 errors:{line_no?, message}(批次層級的沒有 line_no)。
    """
    warnings: list[dict] = []
    w = _issue_format_warning(g, issue)
    if w:
        warnings.append(w)
    w = _date_warning(g, bet_date)
    if w:
        warnings.append(w)
    exist_sigs = {_sig(e.get("record", {}) or {}) for e in existing}
    for line_no, rec in indexed_records:
        w = _units_warning(rec)
        if w:
            warnings.append({"line_no": line_no, **w})
        if _sig(rec) in exist_sigs:
            warnings.append({"line_no": line_no,
                             "message": "這批和已存在的紀錄重複,確認不是重複上傳"})
    return warnings


class QuickImportIn(BaseModel):
    game: str
    text: str = ""
    dry_run: bool = Field(default=False, description="只解析不寫入(前端預覽用)")
    date: str | None = Field(default=None, description="下注日期;不給就用今天")
    issue: str = Field(default="", description="期別;不知道就留空")
    edition: int = Field(default=1, description="上傳到哪個版(eid);預設第一版")
    cycle_id: int | None = Field(default=None,
                                 description="歸到哪個週期;不給就自動補目前進行中週期")


@router.post("/quick-import")
def quick_import(body: QuickImportIn, user: str = Depends(current_user)):
    """貼一段下注文字 → 解析(dry_run)或解析並寫進自己的記帳流水。

    回傳 items(每筆的玩法 / 球 / 支或車 / 碰數 / 成本,寫入後含資料庫 id)
    與 errors(認不出來的行)。errors 不影響其他筆 —— 認得幾筆就記幾筆。
    """
    g = get_game(body.game)
    bet_date = body.date or _date.today().isoformat()
    odds = edition_store.get_odds(body.edition, g.key)   # 依上傳的版取盤口
    cid = _resolve_cycle_id(user, body.cycle_id)         # 沒帶就補目前進行中週期
    items, errors = parse(body.text, g, odds)

    # 🟡 警告(期號格式 / 大車支 / 舊日期 / 重複):dry_run 也算,讓預覽就看到。
    # 重複比對用「寫入前」的 ledger 快照,才不會跟自己這批對到。
    existing = ledger_store.list_entries(user)
    base_records = [(i, to_record(it, g, bet_date, body.issue, edition=body.edition,
                                  cycle_id=cid))
                    for i, it in enumerate(items, start=1)]
    warnings = _collect_warnings(g, bet_date, body.issue, base_records, existing)

    out = []
    saved: list[dict] = []
    for it in items:
        record = to_record(it, g, bet_date, body.issue, edition=body.edition,
                           cycle_id=cid)
        entry_id = None
        if not body.dry_run:
            record = autosettle.settle_record_if_drawn(record, g)  # 上傳時該期已開就對獎
            entry = ledger_store.add_entry(user, it.mode, record)
            entry_id = entry["id"]
            saved.append(entry)
        out.append({"id": entry_id, "line": it.line, "mode": it.mode,
                    "record": record})

    # 一次上傳 = 操作歷史裡的一筆(不是 N 筆)—— 作廢時整批一起回收,
    # 使用者的心智模型是「我剛剛上傳了那張單」,不是「我新增了 7 筆」。
    if saved:
        audit_store.log(
            user, "quick_import",
            summary=f"{g.name} {bet_date} 上傳 {len(saved)} 筆下注"
                    + (f"(第 {body.issue} 期)" if body.issue else ""),
            reverse_data={"entries": saved},
        )

    return {
        "game": g.key,
        "game_name": g.name,
        "dry_run": body.dry_run,
        "parsed": len(out),
        "saved": 0 if body.dry_run else len(out),
        "items": out,
        "errors": errors,
        "warnings": warnings,
    }


class CommitItemIn(BaseModel):
    mode: str
    selectedBalls: list[int] = Field(default_factory=list)
    units: float = 0
    stars: int = 0
    hit_count: int | None = None   # 忘記期數但記得中幾顆:直接依該版盤口手填結算
    base_cost: float | None = Field(   # 逐筆基礎成本覆蓋(每注/每碰);None=吃版盤口
        default=None, description="這筆的每單位基礎成本(二合每注/連碰每碰…),覆蓋版盤口")
    ball_deltas: dict[str, float] = Field(   # 1組專用:個別號碼的「每注基礎」加價(號→+N)
        default_factory=dict,
        description="1組(single)每個號碼的每注基礎加價,鍵為號碼字串。其餘下法忽略")
    pillars: list[list[int]] = Field(   # 1800碰自訂分柱 [[柱1],[柱2],[其他]];空 = 標準三柱
        default_factory=list, description="1800碰自訂分柱;其餘下法忽略")


class QuickImportCommitIn(BaseModel):
    game: str
    items: list[CommitItemIn] = Field(default_factory=list)
    date: str | None = None
    issue: str = ""
    edition: int = 1
    cycle_id: int | None = Field(default=None,
                                 description="歸到哪個週期;不給就自動補目前進行中週期")
    dry_run: bool = Field(default=False, description="只重算成本不寫入(預覽試算用)")


@router.post("/quick-import/commit")
def quick_import_commit(body: QuickImportCommitIn, user: str = Depends(current_user)):
    """把(使用者在預覽裡編輯過的)items 寫進記帳流水,成本後端重算。

    與 /quick-import 不同:這裡收的是結構化、可能被手動改過的解析結果,不是原始
    文字。每筆依 mode / 號碼 / 支或車 / 星數重算成本(見 _recost),money 不讓
    前端決定。哪筆算不出來收進 errors,其他筆照記。
    """
    g = get_game(body.game)
    bet_date = body.date or _date.today().isoformat()
    odds = edition_store.get_odds(body.edition, g.key)
    cid = _resolve_cycle_id(user, body.cycle_id)   # 沒帶就補目前進行中週期

    # 重複判定要拿「寫入前」的 ledger 快照比(dry_run 也算,讓預覽就看到重複警告)。
    existing = ledger_store.list_entries(user)
    warn_records: list[tuple[int, dict]] = []

    out, saved, errors = [], [], []
    for i, it in enumerate(body.items, start=1):
        try:
            item = _recost(g, odds, it.mode, it.selectedBalls, it.units, it.stars,
                           base=it.base_cost, ball_deltas=it.ball_deltas,
                           pillars=it.pillars)
        except ValueError as e:
            errors.append({"line_no": i, "line": "", "message": str(e)})
            continue
        record = to_record(item, g, bet_date, body.issue, edition=body.edition,
                           cycle_id=cid)
        warn_records.append((i, record))
        # 有填中獎顆數就直接手填結算(不必期數);settle 依 record 的版取盤口算派彩
        if it.hit_count is not None:
            record = settle.settle(record, None, g, hit_count=it.hit_count)
        if body.dry_run:                # 只試算成本、不寫入(預覽用)
            out.append({"id": None, "mode": item.mode, "record": record})
            continue
        if it.hit_count is None:        # 沒手填 → 上傳時該期已開就自動對獎
            record = autosettle.settle_record_if_drawn(record, g)
        entry = ledger_store.add_entry(user, item.mode, record)
        saved.append(entry)
        out.append({"id": entry["id"], "mode": item.mode, "record": record})

    warnings = _collect_warnings(g, bet_date, body.issue, warn_records, existing)

    if saved:
        audit_store.log(
            user, "quick_import",
            summary=f"{g.name} {bet_date} 上傳 {len(saved)} 筆下注"
                    + (f"(第 {body.issue} 期)" if body.issue else ""),
            reverse_data={"entries": saved},
        )

    return {
        "game": g.key,
        "game_name": g.name,
        "saved": len(saved),
        "items": out,
        "errors": errors,
        "warnings": warnings,
    }


# ── 週期帳下注明細編輯器:逐筆改號碼 / 車支數 / 成本 ─────────────────
# 只開放這幾欄;日期 / 期號 / 版 / 下法不動。成本照樣走 _recost(後端權威),
# 1800碰 的自訂分柱原樣沿用紀錄裡的 pillars(編輯器不改柱)。
_EDIT_KEYS = ("playType", "units", "cars", "betsCount", "selectedBalls", "stars",
              "incomplete", "cost", "costExpr", "baseCost", "ballDeltas", "pillars", "ballDetail")
_MANUAL_HIT_RE = re.compile(r"中 (\d+)")


class BallDetailIn(BaseModel):
    n: int
    cars: float
    base: float | None = None   # 每注成本(絕對值);None = 版盤口


class BatchEditItemIn(BaseModel):
    id: int
    selectedBalls: list[int] = Field(default_factory=list)
    units: float = 0
    base_cost: float | None = Field(   # 每單位基礎成本(二合每注/1800每注/連碰每碰…);None=吃版盤口
        default=None, description="這筆的每單位基礎成本,覆蓋版盤口")
    ball_deltas: dict[str, float] = Field(   # 1組/2組 個別號碼的每注基礎加價(號→+N)
        default_factory=dict, description="二合每個號碼的每注基礎加價;其餘下法忽略")
    ball_detail: list[BallDetailIn] = Field(   # 1組/2組 逐顆車數 + 每注成本;有給就取代 selectedBalls/units
        default_factory=list, description="二合逐顆 [{n, cars, base}];其餘下法忽略")
    hit_balls: list[int] | None = Field(   # 手填紀錄改成逐顆(各顆車數不同)時,點選中哪幾顆
        default=None, description="手填中獎號碼;None = 沿用紀錄裡存的 hitBalls")


class BatchEditIn(BaseModel):
    items: list[BatchEditItemIn] = Field(default_factory=list)
    dry_run: bool = Field(default=False, description="只試算(回舊/新對照)不寫入")


def _resettle_edited(new: dict, old: dict, g: GameConfig,
                     hit_balls: list[int] | None = None) -> dict:
    """編輯後重新對獎,沿用原本的對獎方式:

    - 原本是手填中獎(result 帶「手填」)→ 有點選中獎號碼(hit_balls,或紀錄存的 hitBalls)
      就依各顆車數算;否則依原手填中獎數重算(手填數只存在 result 文字裡)。各顆車數
      不同又沒點選 → settle 丟 ValueError(中 k 顆不唯一);
    - 原本已對到開獎號 → 依同一組開獎號重算;
    - 原本待開獎 → 該期(或該日)已開就對,沒開維持待開獎。
    """
    result = str(old.get("result") or "")
    if "手填" in result:
        hb = hit_balls if hit_balls is not None else old.get("hitBalls")
        if hb is not None and new.get("mode") in ("single", "multi"):
            return settle.settle(new, None, g, hit_balls=hb)
        m = _MANUAL_HIT_RE.search(result)
        return settle.settle(new, None, g, hit_count=int(m.group(1)) if m else 0)
    draw = old.get("drawBalls") or []
    if draw:
        return settle.settle(new, [int(x) for x in draw], g)
    return autosettle.settle_record_if_drawn(
        {**new, "result": autosettle.PENDING, "payout": 0, "pnl": 0}, g)


def _edited_record(old: dict, mode: str, it: BatchEditItemIn) -> dict:
    """依編輯內容重算一筆:成本走 _recost、對獎走 _resettle_edited。算不出來丟 ValueError。"""
    g = games_mod.by_name(str(old.get("game") or ""))   # 紀錄存遊戲名稱;與 ledger 改期對獎同一查法
    play_type = str(old.get("playType") or "")
    if mode == "combo" and not play_type.startswith("星碰"):
        # 舊連碰家族(全碰/立柱/拖膽)不是 _recost 的星碰算式,改了會變成星碰
        raise ValueError("這筆連碰不是星碰格式,不支援編輯")
    stars = int(old.get("stars") or 0) or (settle._stars_of(play_type) if mode == "combo" else 0)
    odds = edition_store.get_odds(settle._edition(old), g.key)
    item = _recost(g, odds, mode, it.selectedBalls, it.units, stars,
                   base=it.base_cost, ball_deltas=it.ball_deltas,
                   pillars=old.get("pillars") or [],
                   ball_detail=[d.model_dump() for d in it.ball_detail])
    fresh = to_record(item, g, str(old.get("date") or ""), str(old.get("issue") or ""),
                      edition=settle._edition(old))
    new = {**old, **{k: fresh[k] for k in _EDIT_KEYS}}
    return _resettle_edited(new, old, g, it.hit_balls)


def _num0(v) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


@router.post("/batch-edit")
def batch_edit(body: BatchEditIn, user: str = Depends(current_user)):
    """週期帳下注明細編輯器:一次改多筆(可混合下法)的號碼 / 車支數 / 成本。

    每筆成本後端重算(_recost)、依原對獎方式重新結算;回傳每筆 old / new 整筆與
    cost_diff / pnl_diff,dry_run 只試算不寫入。只能改自己的紀錄(有一筆不是就 404)。
    任何一筆算不出來就整批不寫(errors 帶 id),避免存一半。
    一次儲存 = 操作歷史一筆 bet_edit,作廢時整批還原成編輯前。
    """
    mine = {e["id"]: e for e in ledger_store.list_entries(user)}
    if any(it.id not in mine for it in body.items):
        raise HTTPException(status_code=404, detail="找不到這筆紀錄")

    out, errors = [], []
    for i, it in enumerate(body.items, start=1):
        entry = mine[it.id]
        old = entry.get("record") or {}
        try:
            new = _edited_record(old, entry["mode"], it)
        except ValueError as e:
            errors.append({"id": it.id, "line_no": i, "message": str(e)})
            continue
        out.append({
            "id": it.id, "mode": entry["mode"], "old": old, "new": new,
            "cost_diff": round(_num0(new.get("cost")) - _num0(old.get("cost"))),
            "pnl_diff": round(_num0(new.get("pnl")) - _num0(old.get("pnl"))),
        })

    if body.dry_run or errors or not out:
        return {"dry_run": body.dry_run, "saved": 0, "items": out, "errors": errors}

    olds = []
    for o in out:
        res = ledger_store.update_entry(user, o["id"], o["new"])
        if res:
            olds.append(res[1])
    old_cost = sum(_num0(e["record"].get("cost")) for e in olds)
    new_cost = sum(_num0(o["new"].get("cost")) for o in out)
    audit_store.log(
        user, "bet_edit",
        target_id=out[0]["id"] if len(out) == 1 else None,
        summary=(f"編輯 {len(olds)} 筆下注:成本 {round(old_cost):,} → {round(new_cost):,}"
                 f"(差額 {round(new_cost - old_cost):+,})"
                 + (f" · {audit_store.summarize_record(out[0]['mode'], out[0]['new'])}"
                    if len(out) == 1 else "")),
        reverse_data={"entries": olds},
    )
    return {"dry_run": False, "saved": len(olds), "items": out, "errors": []}
