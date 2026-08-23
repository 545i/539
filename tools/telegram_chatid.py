#!/usr/bin/env python3
"""列出 Telegram bot 最近看到的 chat(用來找群組 chat_id),並可發一則測試訊息。

用法(token 走環境變數,不要寫進檔案):
    export TELEGRAM_BOT_TOKEN='...'
    python tools/telegram_chatid.py            # 列出最近出現過的 chat
    python tools/telegram_chatid.py <chat_id>  # 對該 chat 發一則測試訊息

步驟:把 bot 加進群組 → 在群裡打一則指令(例如 /start@你的bot,隱私模式下 bot
只看得到指令)→ 跑本工具就會看到群組的 chat_id(群組是負數)。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import notify  # noqa: E402


def main() -> int:
    if not notify._token():
        print("請先設 TELEGRAM_BOT_TOKEN 環境變數。")
        return 1

    if len(sys.argv) > 1:
        chat_id = sys.argv[1]
        ok = notify.send("✅ 539 提醒機器人測試訊息(收到代表 chat_id 正確)。",
                         chat_id=chat_id, parse_mode="")
        print("已發送。" if ok else "發送失敗(chat_id 錯、或 bot 不在該群/被踢)。")
        return 0 if ok else 1

    chats = notify.discover_chats()
    if not chats:
        print("getUpdates 沒有任何 chat。把 bot 加進群組後,在群裡打一則指令再試。")
        return 0
    print("最近出現過的 chat:")
    for c in chats:
        print(f"  chat_id={c['id']:<16} type={c['type']:<10} {c['title']}")
    print("\n群組的 chat_id 是負數(超級群組 -100 開頭)。把它設成 TELEGRAM_CHAT_ID。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
