"""Telegram bot 收訊(long polling):處理 /提醒 指令 + 「清除」按鈕刪訊。

只在有設定 token/chat_id 時起一條 daemon 執行緒(見 backend/main.py lifespan)。
long polling 不需要對外開 webhook,遠端 uvicorn 直接跑就行。

指令回覆走 backend.reminders.handle_command;回覆帶一顆「🗑 清除」inline 按鈕,
按下去(callback_data=clear)就刪掉那則訊息(方便清掉洗版的查詢結果)。

任何錯誤都吞掉、睡一下再繼續,不讓收訊執行緒整條死掉。
"""
from __future__ import annotations

import threading
import time

from backend import reminders
from core import notify

_thread: threading.Thread | None = None
_lock = threading.Lock()

# /提醒 回覆下方的「清除」按鈕
_CLEAR_KB = {"inline_keyboard": [[{"text": "🗑 清除", "callback_data": "clear"}]]}

POLL_TIMEOUT = 25       # long-poll 秒數
_ERR_SLEEP = 5


def _handle_update(u: dict) -> None:
    # 一般訊息:對到指令才回(帶清除按鈕)
    msg = u.get("message") or u.get("channel_post")
    if msg:
        text = msg.get("text", "")
        reply = reminders.handle_command(text)
        if reply:
            chat_id = (msg.get("chat") or {}).get("id")
            notify.send(reply, chat_id=str(chat_id), reply_markup=_CLEAR_KB)
        return

    # 按鈕點擊:清除 → 刪掉按鈕所在的那則訊息
    cq = u.get("callback_query")
    if cq:
        notify.answer_callback(cq.get("id", ""))
        if cq.get("data") == "clear":
            m = cq.get("message") or {}
            chat_id = (m.get("chat") or {}).get("id")
            mid = m.get("message_id")
            if chat_id is not None and mid is not None:
                notify.delete_message(chat_id, mid)


def _loop() -> None:
    offset: int | None = None
    while True:
        try:
            updates = notify.get_updates(offset=offset, timeout=POLL_TIMEOUT)
            for u in updates:
                offset = int(u["update_id"]) + 1     # 確認這批,下次不再拿到
                try:
                    _handle_update(u)
                except Exception:       # noqa: BLE001 — 單筆壞掉不拖垮整條
                    pass
        except Exception:               # noqa: BLE001 — 網路 / API 錯就睡一下重試
            time.sleep(_ERR_SLEEP)


def start() -> bool:
    """啟動收訊執行緒(整個行程只起一條);沒設定 token/chat_id 就不起。"""
    global _thread
    if not notify.enabled():
        return False
    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _thread = threading.Thread(target=_loop, daemon=True, name="telegram-bot")
        _thread.start()
    return True
