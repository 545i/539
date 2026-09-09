"""極簡 WebSocket 廣播中樞:資料變動(開獎 / 自動對獎)後通知前端即時刷新。

前端連 /api/ws;後端在資料變動時 publish 一則 JSON,所有連線都收到 → 前端重抓
流水 / 開獎。排程跑在背景執行緒,所以 publish 用 run_coroutine_threadsafe 丟回
主事件迴圈廣播。這個系統用的人少,連線數與訊息量都很小,常駐成本可忽略。
"""
from __future__ import annotations

import asyncio

from fastapi import WebSocket


class Hub:
    def __init__(self) -> None:
        self._conns: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """啟動時把主事件迴圈記起來,背景執行緒才有辦法丟訊息回來廣播。"""
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._conns.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._conns.discard(ws)

    async def _send_all(self, msg: dict) -> None:
        for ws in list(self._conns):
            try:
                await ws.send_json(msg)
            except Exception:       # noqa: BLE001 — 送不出去的連線直接丟掉
                self._conns.discard(ws)

    def publish(self, msg: dict) -> None:
        """任何執行緒都可呼叫(排程在背景緒):丟回主迴圈廣播;沒有迴圈就跳過。"""
        loop = self._loop
        if loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._send_all(msg), loop)
        except Exception:           # noqa: BLE001 — 廣播失敗不能影響呼叫端
            pass


hub = Hub()
