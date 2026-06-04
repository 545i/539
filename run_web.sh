#!/usr/bin/env bash
# 今彩539 Web 版(Streamlit)啟動腳本
# 用法:bash run_web.sh  之後瀏覽器開 http://localhost:8501

set -euo pipefail

# 切換到本腳本所在目錄(專案根目錄)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PY="$SCRIPT_DIR/.venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
  echo "找不到 .venv,請先建立虛擬環境並安裝套件:" >&2
  echo "  python -m venv .venv" >&2
  echo "  .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

# 用專案內 .venv 的 python 啟動 Streamlit Web 版
exec "$VENV_PY" -m streamlit run app.py
