"""今彩539 統計分析工具 — 進入點。

執行:python main.py
進入後以方向鍵 ↑↓ 選擇功能。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ui import menu  # noqa: E402


def main() -> None:
    try:
        menu.run()
    except (KeyboardInterrupt, EOFError):
        print("\n已取消。")


if __name__ == "__main__":
    main()
