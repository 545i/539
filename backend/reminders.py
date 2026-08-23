"""排程提醒:偵測到新開獎後,檢查各款「區間組合斷檔」,達門檻就推 Telegram。

設定讀 backend.watch_store(全站公共),計算走 core.stats.combo_cooccurrence_alerts,
推播走 core.notify(讀環境變數的 token / chat_id,沒設就安靜跳過)。

只在「有新開獎」時檢查(見 backend/main.py 的 on_added 掛鉤),所以每款頂多一天
提醒一次,不會洗版。任何錯誤都吞掉,不拖垮排程。
"""
from __future__ import annotations

from backend import watch_store
from backend.data import get_game, load_df
from core import notify, stats


def check_combo_watch(game_key: str) -> list[dict]:
    """回這款目前達斷檔門檻的組合(各自用自己的 threshold)。"""
    combos = watch_store.get_combos(game_key)
    if not combos:
        return []
    df = load_df(game_key)
    alerts: list[dict] = []
    for c in combos:
        thr = int(c.get("threshold", watch_store.DEFAULT_THRESHOLD))
        for r in stats.combo_cooccurrence_alerts(df, [c], threshold=thr):
            if r["alert"]:
                alerts.append({**r, "threshold": thr})
    return alerts


def notify_combo_watch(game_key: str) -> bool:
    """有斷檔就推一則 Telegram(整款彙整成一則);沒設定 / 沒斷檔回 False。"""
    if not notify.enabled():
        return False
    try:
        alerts = check_combo_watch(game_key)
    except Exception:       # noqa: BLE001 — 提醒失敗不能影響排程
        return False
    if not alerts:
        return False
    g = get_game(game_key)
    lines = [f"🔔 <b>{g.name} 區間組合斷檔提醒</b>"]
    for a in alerts:
        lines.append(
            f"・{a['label']}:已連續 <b>{a['streak']}</b> 期沒有全部同時開出"
            f"(門檻 {a['threshold']} 期)")
    return notify.send("\n".join(lines))


def on_new_draw(game_key: str) -> None:
    """排程偵測到新開獎時的掛鉤(見 core.autoupdate 的 on_added)。"""
    notify_combo_watch(game_key)
