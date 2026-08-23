"""排程提醒:偵測到新開獎後,檢查各款「區間組合斷檔」,達門檻就推 Telegram。

設定讀 backend.watch_store(全站公共),計算走 core.stats.combo_cooccurrence_alerts,
推播走 core.notify(讀環境變數的 token / chat_id,沒設就安靜跳過)。

只在「有新開獎」時檢查(見 backend/main.py 的 on_added 掛鉤),所以每款頂多一天
提醒一次,不會洗版。任何錯誤都吞掉,不拖垮排程。
"""
from __future__ import annotations

from backend import watch_store
from backend.data import all_games, get_game, load_df
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


# ── /提醒 指令:回目前各款區間組合的斷檔現況(唯讀,不只警示的) ──────
def reminder_text() -> str:
    """`/提醒` 的回覆:每款各組「距上次全部同時開出幾期」+ 是否達門檻。"""
    lines = ["🔔 <b>區間組合斷檔現況</b>"]
    for g in all_games():
        combos = watch_store.get_combos(g.key)
        if not combos:
            continue
        try:
            df = load_df(g.key)
        except Exception:       # noqa: BLE001 — 讀不到資料就跳過該款
            continue
        rows = []
        for c in combos:
            thr = int(c.get("threshold", watch_store.DEFAULT_THRESHOLD))
            for r in stats.combo_cooccurrence_alerts(df, [c], threshold=thr):
                mark = "⚠️ " if r["alert"] else ""
                rows.append(
                    f"・{mark}{r['label']}:目前 <b>{r['streak']}</b> 期沒一起開"
                    f"(門檻 {thr}、史上最長 {r['max_gap']} 期)")
        if rows:
            lines.append(f"\n【{g.name}】")
            lines.extend(rows)
    return "\n".join(lines)


def handle_command(text: str) -> str | None:
    """把收到的訊息文字對應到回覆;認得的指令才回,其他回 None。

    支援 /提醒 與 /提醒@botname(群組裡指令會被 Telegram 加上 @bot)。
    """
    cmd = (text or "").strip().split()[0] if text and text.strip() else ""
    cmd = cmd.split("@", 1)[0]          # 去掉 @botname
    if cmd in ("/提醒", "/remind", "/reminder"):
        return reminder_text()
    return None
