"""自動對獎:把「待開獎」且該期已經開了的紀錄自動結算。

先前只有使用者手動點期號才會對獎,開獎時常常漏對。這裡在三個時機自動補上:
  1. 開獎時 —— 排程抓到新開獎(core.autoupdate 的 on_added)就結算該款所有待開獎。
  2. 啟動時 —— 服務起來先掃一次,補上停機期間錯過的。
  3. 上傳時 —— 快速上傳 / 記帳當下若那一期已經開了,直接結算(見 backend.routers.importer)。

結算邏輯全走 backend.settle(依每筆的版 × 遊戲取盤口),這裡只負責「找出該對而還沒
對的紀錄、把它對掉」。任何一筆出錯都吞掉、不影響其他筆與排程。
"""
from __future__ import annotations

from backend import data, ledger_store, settle
from core import games

PENDING = "待開獎"


def settle_record_if_drawn(record: dict, g) -> dict:
    """單筆:若『待開獎』且期數已開 → 回傳結算後的新 record;否則原樣回傳。

    money / 中碰數全由 settle 依該筆的版盤口算;查不到該期(未開)就維持待開獎。
    """
    if str(record.get("result", "")) != PENDING:
        return record
    issue = str(record.get("issue", "") or "").strip()
    if not issue:
        return record
    found = data.draw_by_issue(g.key, issue)
    if not found:
        return record
    out = settle.settle(record, found[0], g)
    out["issue"] = issue
    out["date"] = found[1]
    return out


def settle_pending(game_key: str | None = None) -> int:
    """把所有『待開獎』且該期已開的紀錄結算掉(跨所有使用者 / 版);回傳結算幾筆。

    game_key 有給就只處理那一款(開獎時只動剛更新的款)。
    """
    settled = 0
    try:
        entries = ledger_store.list_all()
    except Exception:       # noqa: BLE001 — 讀不到就當作沒有,別拖垮排程
        return 0
    for e in entries:
        rec = e.get("record") or {}
        if str(rec.get("result", "")) != PENDING:
            continue
        try:
            g = games.by_name(str(rec.get("game", "")))
        except Exception:   # noqa: BLE001 — 認不出遊戲就跳過這筆
            continue
        if game_key and g.key != game_key:
            continue
        try:
            new = settle_record_if_drawn(rec, g)
            if new.get("result") != PENDING:      # 真的對到了才寫回
                ledger_store.update_entry(e["username"], e["id"], new)
                settled += 1
        except Exception:   # noqa: BLE001 — 單筆壞掉不影響其他筆
            continue
    return settled
