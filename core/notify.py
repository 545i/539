"""Telegram 提醒推播(讀環境變數,best-effort)。

**Token 與 chat_id 一律走環境變數,不寫進程式、不進版控**:
    TELEGRAM_BOT_TOKEN   BotFather 給的 token
    TELEGRAM_CHAT_ID     要推到哪個群組 / 私訊的 chat_id(群組是負數)

設計成「有設就發、沒設就安靜跳過」,而且**任何錯誤都吞掉**(網路斷、Telegram
掛掉都不該讓下注 / 排程流程壞掉)—— 提醒是加分,不是關鍵路徑。

只用標準庫 urllib,不加相依。要發圖 / 更複雜互動再擴充。
"""
from __future__ import annotations

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"

TG_LIMIT = 4096          # Telegram 單則訊息字數上限
_TAG_RE = re.compile(r"<[^>]+>")

# 最後一次 API 失敗的原因(供診斷「提醒為何發不出來」;成功時清空)。
# 提醒仍是 best-effort:任何錯誤都不丟例外,只把原因記在這裡。
_last_error: str = ""


def last_error() -> str:
    """最後一次推播失敗的原因(HTML 解析錯、超長、網路斷…);成功後為空字串。"""
    return _last_error


def _token() -> str:
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()


def _chat_id() -> str:
    return (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()


def enabled() -> bool:
    """token 與 chat_id 都設了才會真的發。"""
    return bool(_token() and _chat_id())


def _call(method: str, params: dict, timeout: float = 8.0) -> dict | None:
    """呼叫 Telegram API;成功/失敗都回傳解析後的 JSON(供呼叫端判斷 ok)。

    只有連 JSON 都拿不到(網路斷、逾時)才回 None。失敗原因寫進 _last_error。
    Telegram 對 HTML 解析錯等會回 HTTP 400 + JSON body(含 description),
    這裡特別把 400 的 body 讀出來,才知道到底哪裡不合法。
    """
    global _last_error
    token = _token()
    if not token:
        _last_error = "未設定 TELEGRAM_BOT_TOKEN"
        return None
    url = API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=timeout) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            res = json.loads(e.read().decode())      # 400 的 body 有 description
        except Exception:       # noqa: BLE001
            _last_error = f"HTTP {e.code}"
            return None
    except Exception as e:      # noqa: BLE001 — 推播失敗絕不能拖垮呼叫端
        _last_error = str(e) or e.__class__.__name__
        return None
    _last_error = "" if res.get("ok") else str(res.get("description", "not ok"))
    return res


def _strip_tags(text: str) -> str:
    """把 HTML 標籤拿掉、還原實體 → 純文字(HTML 解析失敗時的退路)。"""
    return html.unescape(_TAG_RE.sub("", text))


def _split(text: str, limit: int = TG_LIMIT) -> list[str]:
    """依行切成不超過 limit 的段;單行本身超長就硬切,確保每段都送得出去。"""
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    cur = ""
    for line in text.split("\n"):
        while len(line) > limit:                 # 單行超長 → 先收尾再硬切
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(line[:limit])
            line = line[limit:]
        piece = line if not cur else cur + "\n" + line
        if len(piece) <= limit:
            cur = piece
        else:
            chunks.append(cur)
            cur = line
    if cur:
        chunks.append(cur)
    return chunks


def _send_one(cid: str, text: str, parse_mode: str, disable_preview: bool,
              reply_markup: dict | None) -> bool:
    """送單一段;HTML 解析失敗就退回純文字重送一次(避免整則發不出來)。"""
    params = {
        "chat_id": cid,
        "text": text,
        "disable_web_page_preview": "true" if disable_preview else "false",
    }
    if parse_mode:
        params["parse_mode"] = parse_mode
    if reply_markup is not None:
        params["reply_markup"] = json.dumps(reply_markup)
    res = _call("sendMessage", params)
    if res and res.get("ok"):
        return True
    if parse_mode:                               # 多半是 HTML 不合法 → 退純文字
        params.pop("parse_mode", None)
        params["text"] = _strip_tags(text)
        res = _call("sendMessage", params)
        return bool(res and res.get("ok"))
    return False


def send(text: str, chat_id: str | None = None, parse_mode: str = "HTML",
         disable_preview: bool = True, reply_markup: dict | None = None) -> bool:
    """發一則訊息;回傳是否成功。沒設定或失敗都回 False(不丟例外)。

    三層防護,避免「提醒發不出來」:
      1. 超過 Telegram 4096 字上限 → 自動分段連發(按鈕只掛最後一段)。
      2. HTML parse_mode 不合法 → 該段自動退回純文字重送。
      3. 任何失敗原因記在 notify.last_error(),方便事後查為什麼沒發成。

    reply_markup 可帶 inline_keyboard(例如「清除」按鈕)。
    """
    cid = (chat_id or _chat_id()).strip()
    if not (_token() and cid and text):
        return False
    chunks = _split(text, TG_LIMIT)
    ok = True
    for i, chunk in enumerate(chunks):
        rm = reply_markup if i == len(chunks) - 1 else None  # 按鈕只掛最後一段
        if not _send_one(cid, chunk, parse_mode, disable_preview, rm):
            ok = False
    return ok


def _multipart(fields: dict, photo: bytes, filename: str = "card.png") -> tuple[bytes, str]:
    """組 multipart/form-data body(sendPhoto 用);回 (body, content_type)。"""
    boundary = "----lotto539" + os.urandom(8).hex()
    crlf = b"\r\n"
    parts: list[bytes] = []
    for k, v in fields.items():
        if v is None:
            continue
        parts += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{k}"'.encode(),
            b"", str(v).encode(),
        ]
    parts += [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="photo"; filename="{filename}"'.encode(),
        b"Content-Type: image/png", b"", photo,
        f"--{boundary}--".encode(), b"",
    ]
    body = crlf.join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def send_photo(photo: bytes, caption: str = "", chat_id: str | None = None,
               parse_mode: str = "HTML") -> bool:
    """發一張圖(sendPhoto);回傳是否成功。沒設定 / 沒圖 / 失敗都回 False(不丟例外)。

    caption 是圖說(Telegram 上限 1024 字,超過自動截),失敗原因記在 last_error()。
    圖發不出去時**不**自動退純文字 —— 那一層退回交給呼叫端(reminders)決定。
    """
    global _last_error
    cid = (chat_id or _chat_id()).strip()
    token = _token()
    if not (token and cid and photo):
        _last_error = "未設定 token/chat_id 或無圖"
        return False
    fields = {"chat_id": cid, "caption": (caption or "")[:1024]}
    if parse_mode:
        fields["parse_mode"] = parse_mode
    body, ctype = _multipart(fields, photo)
    url = API.format(token=token, method="sendPhoto")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            res = json.loads(e.read().decode())
        except Exception:       # noqa: BLE001
            _last_error = f"HTTP {e.code}"
            return False
    except Exception as e:      # noqa: BLE001 — 推播失敗不能拖垮呼叫端
        _last_error = str(e) or e.__class__.__name__
        return False
    _last_error = "" if res.get("ok") else str(res.get("description", "not ok"))
    return bool(res.get("ok"))


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
