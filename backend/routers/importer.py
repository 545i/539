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

成本一律走 core:星碰 combo.star_bets × combo.MARKET_COST、1800碰
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

from backend import ledger_store
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
MULTI_COST_DIVISOR = 20.0

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
# 八顆三星1200 / 三星1200 / 8顆3星1200
_STAR_RE = re.compile(r"^(?:.*?顆)?\s*([二三四234])\s*星\s*([0-9]+)$")
# 其他400 —— 1800碰 那一組的收尾行,金額在這裡
_OTHER_RE = re.compile(r"^其[他它餘余]\s*([0-9]+)$")

_STAR_NUM = {"二": 2, "三": 3, "四": 4, "2": 2, "3": 3, "4": 4}


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
    units: float          # 支數(星碰 / 1800碰)或 車數(單顆 / 多顆)
    bets_count: int       # 注 / 碰數
    cost: float
    line: str             # 產生這一筆的原文(1800碰 是三行併起來)


@dataclass
class _State:
    """逐行解析的中間狀態。"""
    items: list[_Item] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    picks: list[int] = field(default_factory=list)      # 最近一行選號
    pick_line: str = ""
    pending: list[str] = field(default_factory=list)    # 還沒被用掉的純號碼行

    def fail(self, line_no: int, line: str, message: str) -> None:
        self.errors.append({"line_no": line_no, "line": line, "message": message})


# ── 各種下法的成本(全部走 core,不寫死金額)──────────────────
def _erhe_cost(g: GameConfig, n_balls: int, cars: float) -> float:
    """二合:成本 = 押幾顆 × 車數 × 每車成本(同 backend/routers/erhe.py 的 plan)。

    多顆盤的每車成本要先除 MULTI_COST_DIVISOR —— 前端多顆分頁就是這樣帶給
    /erhe/plan 的,不跟著除的話同一張單子從這裡進來會比手動記的貴 20 倍。
    """
    per_car = g.default_cost_per_car
    if n_balls > 1:
        per_car /= MULTI_COST_DIVISOR
    return n_balls * cars * per_car


def _star_item(g: GameConfig, stars: int, picks: list[int], units: float,
               line: str) -> _Item:
    """星碰:碰數 = star_bets(星, 選幾顆),成本 = 支數 × 碰數 × 每碰成本。"""
    bets = combo_mod.star_bets(stars, len(picks))
    if bets <= 0:
        raise ValueError(f"選 {len(picks)} 顆湊不出{combo_mod.star_name(stars)}碰")
    per_bet = combo_mod.MARKET_COST[stars]
    return _Item(
        mode="combo",
        play_type=f"星碰 {combo_mod.star_name(stars)}({bets} 碰/支)",
        balls=picks,
        units=units,
        # 碰數欄比照連碰分頁:記「一支幾碰」,支數另外一欄,兩者不相乘
        bets_count=bets,
        cost=units * bets * per_bet,
        line=line,
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
            single = len(balls) == 1
            st.items.append(_Item(
                mode="single" if single else "multi",
                play_type=f"{'單顆' if single else f'多顆({len(balls)} 顆)'} {cars} 車",
                balls=balls,
                units=cars,
                # 注 / 碰數欄比照現有分頁:單顆記 1、多顆記顆數
                bets_count=1 if single else len(balls),
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
            stars = _STAR_NUM[m.group(1)]
            whole = f"{st.pick_line} / {line}"
            try:
                st.items.append(
                    _star_item(g, stars, list(st.picks), _units(int(m.group(2))), whole))
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
            continue

        st.fail(line_no, line, "看不懂這一行")

    return st.items, st.errors


def to_record(item: _Item, g: GameConfig, bet_date: str, issue: str) -> dict:
    """_Item → 前端的 BetRecord(id / index / cumPnl 由前端依順序補)。"""
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
        "drawBalls": [],
        "result": "待開獎",       # 這一版不結算,開獎後另外對獎
        "cost": round(item.cost),
        "payout": 0,
        "pnl": 0,
    }


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
    for it in items:
        record = to_record(it, g, bet_date, body.issue)
        entry_id = None
        if not body.dry_run:
            entry_id = ledger_store.add_entry(user, it.mode, record)["id"]
        out.append({"id": entry_id, "line": it.line, "mode": it.mode,
                    "record": record})

    return {
        "game": g.key,
        "game_name": g.name,
        "dry_run": body.dry_run,
        "parsed": len(out),
        "saved": 0 if body.dry_run else len(out),
        "items": out,
        "errors": errors,
    }
