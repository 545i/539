"""匯出:開獎分析報表(.xlsx)、個人流水帳(.xlsx / .json)。

報表沿用 core.excel_report(免責聲明 / 開獎資料 / 號碼頻率含原生 BarChart /
凱莉分析),跟舊 Streamlit 版「匯出中心」產的是同一份東西 —— 換前端不換內容。
號碼頻率的 num_max 與凱莉分析都依所選遊戲帶入,六合彩(49 選 6)才不會被
當成 39 選 5 算。

流水帳只匯出自己的(current_user),欄位就是前端 BetRecord 那幾格;累積損益
在這裡依流水順序重算,跟頁面上看到的一致。

檔名用 RFC 5987 的 filename* 帶 UTF-8,同時留一個 ASCII fallback 給舊瀏覽器。
"""
from __future__ import annotations

import io
import json
from urllib.parse import quote

import openpyxl
from fastapi import APIRouter, Depends, Query, Response

from backend import ledger_store
from backend.data import get_game, load_df
from backend.deps import current_user
from backend.routers.leaderboard import MODE_NAMES
from core import excel_report, kelly, stats

router = APIRouter(prefix="/export", tags=["export"])

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

LEDGER_HEADERS = [
    "序號", "下法", "日期", "期別", "遊戲", "玩法", "支數/車數", "注數",
    "選號", "開獎號", "柱分佈", "結果", "成本", "回收", "本局損益",
    "累積損益", "記錄時間",
]


def _attachment(data: bytes, filename: str, media_type: str) -> Response:
    """帶 Content-Disposition 的下載回應(檔名含中文也不會壞)。"""
    ascii_name = filename.encode("ascii", "ignore").decode() or "download"
    disposition = (f'attachment; filename="{ascii_name}"; '
                   f"filename*=UTF-8''{quote(filename)}")
    return Response(content=data, media_type=media_type,
                    headers={"Content-Disposition": disposition})


def _text(v) -> str:
    """把 record 裡的欄位轉成儲存格文字;list 併成 "01 02 03"。"""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(str(x) for x in v)
    return str(v)


def _number(v) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


@router.get("/report.xlsx")
def report_xlsx(game: str = Query(...), limit: int = Query(0, ge=0)):
    """某款遊戲的 Excel 分析報表;limit>0 只取最近 N 期。"""
    g = get_game(game)
    df = load_df(game)
    if limit > 0:
        df = df.tail(limit)
    data = excel_report.build_report_bytes(
        df,
        freq=stats.frequency(df, g.num_max),
        kelly_result=kelly.analyze(g),
        game=g,
    )
    return _attachment(data, f"{g.key}_report.xlsx", XLSX_MIME)


@router.get("/ledger.xlsx")
def ledger_xlsx(user: str = Depends(current_user)):
    """自己的流水帳(四種下法各一張工作表 + 一張總表)。"""
    entries = ledger_store.list_entries(user)

    wb = openpyxl.Workbook()
    ws_all = wb.active
    ws_all.title = "全部"
    sheets = {"全部": ws_all}
    for mode in ledger_store.MODES:
        sheets[mode] = wb.create_sheet(MODE_NAMES.get(mode, mode))
    for ws in sheets.values():
        ws.append(LEDGER_HEADERS)

    # 累積損益各分頁自己算一條,總表再算一條 —— 跟頁面上的流水一致
    running = {k: 0.0 for k in sheets}
    seq = {k: 0 for k in sheets}

    for e in entries:
        rec, mode = e["record"], e["mode"]
        pnl = _number(rec.get("pnl"))
        for key in ("全部", mode):
            ws = sheets.get(key)
            if ws is None:      # 資料庫裡有未知 mode(舊資料)只進總表
                continue
            running[key] += pnl
            seq[key] += 1
            ws.append([
                seq[key],
                MODE_NAMES.get(mode, mode),
                _text(rec.get("date")),
                _text(rec.get("issue")),
                _text(rec.get("game")),
                _text(rec.get("playType")),
                _number(rec.get("units")),
                _number(rec.get("betsCount")),
                _text(rec.get("selectedBalls")),
                _text(rec.get("drawBalls")),
                _text(rec.get("pillarDist")),
                _text(rec.get("result")),
                _number(rec.get("cost")),
                _number(rec.get("payout")),
                pnl,
                round(running[key], 2),
                _text(e.get("created")),
            ])

    buf = io.BytesIO()
    wb.save(buf)
    return _attachment(buf.getvalue(), f"{user}_ledger.xlsx", XLSX_MIME)


@router.get("/ledger.json")
def ledger_json(user: str = Depends(current_user)):
    """自己的流水帳原始備份:後端存什麼就給什麼(含 id / mode / created)。"""
    payload = {"username": user, "entries": ledger_store.list_entries(user)}
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return _attachment(data, f"{user}_ledger.json", "application/json")
