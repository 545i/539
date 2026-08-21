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

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend import audit_store, group_store, ledger_store
from backend.data import get_game
from backend.deps import current_user
from core import combo as combo_mod
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

# 02x50車 / 09_15_19_20x20車 —— x 前面是號碼(可含底線),後面是車數
_CAR_RE = re.compile(r"^([0-9]{1,2}(?:_[0-9]{1,2})*)\s*x\s*([0-9]+)\s*車$")
# 一行純號碼(有底線)= 選號,或 1800碰 的柱別行(10_18、20_29)
_PICK_RE = re.compile(r"^[0-9]{1,2}(?:_[0-9]{1,2})+$")
# 八顆三星1200 / 三星1200 / 8顆3星1200 —— 第一個 group 是宣告顆數(可省略)
_STAR_RE = re.compile(
    r"^(?:([一二三四五六七八九十0-9]+)\s*顆)?\s*([二三四234])\s*星\s*([0-9]+)$")
# 其他400 —— 1800碰 那一組的收尾行,金額在這裡
_OTHER_RE = re.compile(r"^其[他它餘余]\s*([0-9]+)$")

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
    """`09_15_19_20` → [9, 15, 19, 20](保留輸入順序,去重)。"""
    out: list[int] = []
    for part in text.split("_"):
        n = int(part)
        if n not in out:
            out.append(n)
    return out


def _units(amount: int) -> float:
    """金額 → 支數;整數支就回 int,讓 JSON 出去是 12 而不是 12.0。"""
    u = amount / UNITS_PER_AMOUNT
    return int(u) if u == int(u) else u


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


@dataclass
class _State:
    """逐行解析的中間狀態。"""
    items: list[_Item] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    picks: list[int] = field(default_factory=list)      # 最近一行選號
    pick_line: str = ""
    pending: list[str] = field(default_factory=list)    # 還沒被用掉的純號碼行
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


# ── 各種下法的成本(全部走 core,不寫死金額)──────────────────
def _erhe_cost(g: GameConfig, n_balls: int, cars: float) -> float:
    """二合:成本 = 押幾顆 × 車數 × 每車成本(同 backend/routers/erhe.py 的 plan)。

"""
    # 每顆每車成本 = 二合單顆成本(72.5 × 38 = 2755),單顆多顆一致
    return n_balls * cars * g.default_cost_per_car


def _star_item(g: GameConfig, stars: int, picks: list[int], units: float,
               line: str, incomplete: bool = False) -> _Item:
    """星碰:碰數 = star_bets(星, 選幾顆),成本 = 支數 × 碰數 × 每碰成本。

    picks 是(已向上補足的)最終號碼;incomplete 代表補足後仍不到宣告顆數,
    交給前端提醒使用者手動補後再上傳。
    """
    bets = combo_mod.star_bets(stars, len(picks))
    if bets <= 0 and not incomplete:
        raise ValueError(f"選 {len(picks)} 顆湊不出{combo_mod.star_name(stars)}碰")
    # 走 market_cost 而不是直接讀 MARKET_COST —— 後台改過的價要吃得到
    per_bet = float(combo_mod.market_cost(stars, g.default_bet_cost))
    return _Item(
        mode="combo",
        play_type=f"星碰 {combo_mod.star_name(stars)}({bets} 碰/支)",
        balls=picks,
        units=units,
        # 碰數欄比照連碰分頁:記「一支幾碰」,支數另外一欄,兩者不相乘
        bets_count=bets,
        cost=units * bets * per_bet,
        line=line,
        stars=stars,
        incomplete=incomplete,
    )


def _pillar_item(g: GameConfig, units: float, line: str) -> _Item:
    """1800碰:注數 = total_bets × 支數,每注成本用該款的 default_bet_cost。"""
    if not pillar_mod.supports(g):
        raise ValueError(f"{g.name}不適用 1800碰(三柱結構綁定 39 選 5)")
    total = pillar_mod.total_bets(g.num_max)
    return _Item(
        mode="pillar1800",
        play_type=f"1800碰({total:,} 注)",
        balls=[],
        units=units,
        bets_count=int(round(units * total)),
        cost=pillar_mod.round_cost(g.default_bet_cost, 1, g.num_max) * units,
        line=line,
    )


# ── 解析 ─────────────────────────────────────────────────
def parse(text: str, g: GameConfig) -> tuple[list[_Item], list[dict]]:
    """把整段文字翻成待寫入的紀錄;認不出來的行收進 errors,不中斷。"""
    st = _State()
    for line_no, raw in enumerate(_SPLIT_RE.split(text or ""), start=1):
        line = _norm(raw)
        if not line:
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
            st.items.append(_Item(
                mode=grp["mode"],
                play_type=f"{grp['name']} {cars} 車({len(balls)} 顆)",
                balls=balls,
                units=cars,
                bets_count=len(balls),
                cost=_erhe_cost(g, len(balls), cars),
                line=line,
            ))
            continue

        m = _OTHER_RE.match(line)
        if m:
            # 1800碰 一整組(10_18 / 20_29 / 其他400)算一筆;柱別行只是標示,
            # 不是選號,所以這裡把 pending 清掉不讓它被後面的星碰行撿去用。
            whole = " / ".join(st.pending[-2:] + [line])   # 只取緊鄰的兩行柱別
            st.pending, st.picks, st.pick_line = [], [], ""
            try:
                st.items.append(_pillar_item(g, _units(int(m.group(1))), whole))
            except ValueError as e:
                st.fail(line_no, whole, str(e))
            continue

        m = _STAR_RE.match(line)
        if m:
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
                    _star_item(g, stars, balls, _units(int(m.group(3))), whole,
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
            st.number_lines.append(picks)
            continue

        st.fail(line_no, line, "看不懂這一行")

    return st.items, st.errors


def to_record(item: _Item, g: GameConfig, bet_date: str, issue: str) -> dict:
    """_Item → 前端的 BetRecord(id / index / cumPnl 由前端依順序補)。

    多帶 stars / incomplete 兩個欄位:提交時後端要靠 stars 重算連碰成本,
    incomplete 讓前端把「補足仍不夠」的列標出來提醒手動補。
    """
    return {
        "date": bet_date,
        "issue": issue,
        "game": g.name,
        "mode": item.mode,
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
        "payout": 0,
        "pnl": 0,
    }


def _recost(g: GameConfig, mode: str, balls: list[int], units: float,
            stars: int) -> _Item:
    """依(可能被前端編輯過的)mode / 號碼 / 支或車 / 星數重算一筆的成本。

    money 一律後端算 —— 前端只送使用者改完的號碼與支/車,金額不讓前端決定。
    """
    balls = [int(b) for b in balls]
    bad = [n for n in balls if not 1 <= n <= g.num_max]
    if bad:
        raise ValueError(f"{g.name} 只有 1~{g.num_max} 號,不認得 {bad}")
    if units <= 0:
        raise ValueError("支數 / 車數要大於 0")

    if mode == "combo":
        return _star_item(g, int(stars), balls, units, "", incomplete=False)
    if mode == "pillar1800":
        return _pillar_item(g, units, "")
    if mode in group_store.MODE_TO_GID:
        if not balls:
            raise ValueError("這一組至少要選 1 顆號碼")
        grp = group_store.get_group(group_store.MODE_TO_GID[mode])
        name = grp["name"] if grp else mode
        return _Item(
            mode=mode,
            play_type=f"{name} {int(units)} 車({len(balls)} 顆)",
            balls=balls,
            units=units,
            bets_count=len(balls),
            cost=_erhe_cost(g, len(balls), units),
            line="",
        )
    raise ValueError(f"未知的下注模式:{mode}")


class QuickImportIn(BaseModel):
    game: str
    text: str = ""
    dry_run: bool = Field(default=False, description="只解析不寫入(前端預覽用)")
    date: str | None = Field(default=None, description="下注日期;不給就用今天")
    issue: str = Field(default="", description="期別;不知道就留空")


@router.post("/quick-import")
def quick_import(body: QuickImportIn, user: str = Depends(current_user)):
    """貼一段下注文字 → 解析(dry_run)或解析並寫進自己的記帳流水。

    回傳 items(每筆的玩法 / 球 / 支或車 / 碰數 / 成本,寫入後含資料庫 id)
    與 errors(認不出來的行)。errors 不影響其他筆 —— 認得幾筆就記幾筆。
    """
    g = get_game(body.game)
    bet_date = body.date or _date.today().isoformat()
    items, errors = parse(body.text, g)

    out = []
    saved: list[dict] = []
    for it in items:
        record = to_record(it, g, bet_date, body.issue)
        entry_id = None
        if not body.dry_run:
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
    }


class CommitItemIn(BaseModel):
    mode: str
    selectedBalls: list[int] = Field(default_factory=list)
    units: float = 0
    stars: int = 0


class QuickImportCommitIn(BaseModel):
    game: str
    items: list[CommitItemIn] = Field(default_factory=list)
    date: str | None = None
    issue: str = ""


@router.post("/quick-import/commit")
def quick_import_commit(body: QuickImportCommitIn, user: str = Depends(current_user)):
    """把(使用者在預覽裡編輯過的)items 寫進記帳流水,成本後端重算。

    與 /quick-import 不同:這裡收的是結構化、可能被手動改過的解析結果,不是原始
    文字。每筆依 mode / 號碼 / 支或車 / 星數重算成本(見 _recost),money 不讓
    前端決定。哪筆算不出來收進 errors,其他筆照記。
    """
    g = get_game(body.game)
    bet_date = body.date or _date.today().isoformat()

    out, saved, errors = [], [], []
    for i, it in enumerate(body.items, start=1):
        try:
            item = _recost(g, it.mode, it.selectedBalls, it.units, it.stars)
        except ValueError as e:
            errors.append({"line_no": i, "line": "", "message": str(e)})
            continue
        record = to_record(item, g, bet_date, body.issue)
        entry = ledger_store.add_entry(user, item.mode, record)
        saved.append(entry)
        out.append({"id": entry["id"], "mode": item.mode, "record": record})

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
    }
