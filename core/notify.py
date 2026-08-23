"""Telegram 提醒推播(讀環境變數,best-effort)。

**Token 與 chat_id 一律走環境變數,不寫進程式、不進版控**:
    TELEGRAM_BOT_TOKEN   BotFather 給的 token
    TELEGRAM_CHAT_ID     要推到哪個群組 / 私訊的 chat_id(群組是負數)

設計成「有設就發、沒設就安靜跳過」,而且**任何錯誤都吞掉**(網路斷、Telegram
掛掉都不該讓下注 / 排程流程壞掉)—— 提醒是加分,不是關鍵路徑。

只用標準庫 urllib,不加相依。要發圖 / 更複雜互動再擴充。
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def _chat_id() -> str:
    return (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()


def enabled() -> bool:
    """token 與 chat_id 都設了才會真的發。"""
    return bool(_token() and _chat_id())


def _call(method: str, params: dict, timeout: float = 8.0) -> dict | None:
    token = _token()
    if not token:
        return None
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:       # noqa: BLE001 — 推播失敗絕不能拖垮呼叫端
        return None


def send(text: str, chat_id: str | None = None, parse_mode: str = "HTML",
         disable_preview: bool = True, reply_markup: dict | None = None) -> bool:
    """發一則訊息;回傳是否成功。沒設定或失敗都回 False(不丟例外)。

    reply_markup 可帶 inline_keyboard(例如「清除」按鈕)。
    """
    cid = (chat_id or _chat_id()).strip()
    if not (_token() and cid and text):
        return False
    params = {
        "chat_id": cid,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": "true" if disable_preview else "false",
    }
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup)
    res = _call("sendMessage", params)
    return bool(res and res.get("ok"))


def delete_message(chat_id, message_id) -> bool:
    """刪掉某則訊息(「清除」按鈕用)。"""
    res = _call("deleteMessage", {"chat_id": str(chat_id), "message_id": int(message_id)})
    return bool(res and res.get("ok"))


def answer_callback(callback_query_id: str, text: str = "") -> bool:
    """回應 inline 按鈕點擊(讓 Telegram 停止轉圈)。"""
    res = _call("answerCallbackQuery",
                {"callback_query_id": str(callback_query_id), "text": text})
    return bool(res and res.get("ok"))


def get_updates(offset: int | None = None, timeout: float = 0,
                http_timeout: float = 8.0) -> list[dict]:
    """抓 updates;offset 用來確認上一批(long polling),timeout 為 long-poll 秒數。"""
    params: dict = {}
    if offset is not None:
        params["offset"] = int(offset)
    if timeout:
        params["timeout"] = int(timeout)
    res = _call("getUpdates", params, timeout=max(http_timeout, timeout + 5))
    return res.get("result", []) if res else []


def discover_chats() -> list[dict]:
    """從 getUpdates 整理出出現過的 chat:{id, type, title}。

    把 bot 加進群組後,在群裡打個指令(例如 /start@你的bot),再呼叫這個就看得到
    群組的 chat_id(群組是負數,超級群組是 -100 開頭)。
    """
    seen: dict[str, dict] = {}
    for u in get_updates():
        msg = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        if cid is not None:
            seen[str(cid)] = {
                "id": cid,
                "type": chat.get("type", ""),
                "title": chat.get("title") or chat.get("username")
                or chat.get("first_name") or "",
            }
    return list(seen.values())
