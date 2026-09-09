"""把資料 JSON 注入設計好的 HTML 模板,用 Chromium 截成 PNG(best-effort)。

版面 = backend/templates/reminder_card.html(資料驅動);資料 = backend.reminder_image
.build_card_data()。這裡只做「注入 + 渲染」:

  1. 讀模板,把 <script id="card-data"> 的 __CARD_JSON__ 換成傳入的 JSON。
  2. 用 Chromium 截 #card 這個元素成透明底 PNG。

渲染引擎兩條路,先 Playwright(伺服器裝這個,截元素、精準裁切),失敗退回系統
chrome/chromium 的 headless CLI(本機開發用)。兩條都是 Chromium 截圖。**任何錯誤
都吞掉回 None**,呼叫端(reminders.push_game_update)就退回純文字,提醒不會因此發不出去。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_TEMPLATE = Path(__file__).resolve().parent.parent / "backend" / "templates" / "reminder_card.html"
_TOKEN = "__CARD_JSON__"


def _inject(data: dict) -> str:
    """把資料包成 JSON 塞進模板;跳脫 `<` 避免提前關掉 <script>。"""
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    html = _TEMPLATE.read_text(encoding="utf-8")
    # 只換第一處(<script id="card-data"> 的佔位);JS 裡同名的哨兵字串要留著,
    # 那是「未注入 → 吃 DEMO」的判斷依據。
    return html.replace(_TOKEN, payload, 1)


def _render_playwright(html_path: str) -> bytes | None:
    """Playwright(sync)截 #card 元素,透明底。沒裝 / 跑不起來回 None。"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:       # noqa: BLE001 — 沒裝 playwright 就走備援
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"])
            try:
                page = browser.new_page(device_scale_factor=2)
                page.goto(f"file://{html_path}")
                page.wait_for_selector("#card[data-ready], html[data-ready] #card",
                                       timeout=5000)
                png = page.locator("#card").screenshot(omit_background=True)
            finally:
                browser.close()
        return png
    except Exception:       # noqa: BLE001
        return None


def _chrome_bin() -> str | None:
    """找一顆可用的 Chromium/Chrome 執行檔(CHROME_BIN 優先)。"""
    env = (os.environ.get("CHROME_BIN") or "").strip()
    if env and Path(env).exists():
        return env
    for name in ("chromium", "chromium-browser", "google-chrome",
                 "google-chrome-stable", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _render_chrome_cli(html_path: str) -> bytes | None:
    """系統 chrome/chromium 的 headless 截圖(備援);抓不到執行檔回 None。"""
    binary = _chrome_bin()
    if not binary:
        return None
    out = html_path + ".png"
    try:
        subprocess.run(
            [binary, "--headless=new", "--no-sandbox", "--hide-scrollbars",
             "--force-device-scale-factor=2",
             "--default-background-color=00000000",
             "--window-size=768,1400", f"--screenshot={out}", f"file://{html_path}"],
            check=True, capture_output=True, timeout=30)
        png = Path(out).read_bytes()
        return png
    except Exception:       # noqa: BLE001
        return None
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass


def render_card(data: dict) -> bytes | None:
    """資料 → PNG bytes(透明底);渲不出來回 None(呼叫端退純文字)。"""
    try:
        html = _inject(data)
    except Exception:       # noqa: BLE001 — 連模板都讀不到就放棄
        return None
    fd, path = tempfile.mkstemp(suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(html)
        return _render_playwright(path) or _render_chrome_cli(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
