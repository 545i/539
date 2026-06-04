"""今彩539 Web 版單一執行檔啟動器。

PyInstaller 打包後,雙擊 exe 會啟動 Streamlit server 並自動開啟瀏覽器。
app.py 與 core/、ui/、data/ 皆隨 exe 一起打包;本啟動器負責用內嵌的
Streamlit 把 app.py 跑起來。
"""
from __future__ import annotations

import os
import sys


def _ensure_std_streams() -> None:
    """windowed(無 console)模式下 sys.stdout/stderr 會是 None。

    Streamlit/click 會嘗試寫入而出錯,因此把它們導到 exe 旁邊的 log 檔
    (非 frozen 時導到 os.devnull)。必須在 import streamlit 之前完成。
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    if getattr(sys, "frozen", False):
        log_path = os.path.join(os.path.dirname(sys.executable), "lotto539_log.txt")
    else:
        log_path = os.devnull
    try:
        stream = open(log_path, "a", buffering=1, encoding="utf-8", errors="replace")
    except OSError:
        stream = open(os.devnull, "w")
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def _resource(rel: str) -> str:
    """取得打包資源的絕對路徑(frozen 時位於 _MEIPASS)。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def main() -> None:
    _ensure_std_streams()
    app_path = _resource("app.py")

    # 讓 app.py 內的 from core / from ui 能在 frozen 環境解析
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and meipass not in sys.path:
        sys.path.insert(0, meipass)

    # 關閉開發模式與使用統計;非 headless 以便自動開瀏覽器
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.headless=false",
        "--browser.gatherUsageStats=false",
    ]
    from streamlit.web import cli as stcli

    sys.exit(stcli.main())


if __name__ == "__main__":
    # PyInstaller 子行程保護(Streamlit/multiprocessing 需要)
    main()
