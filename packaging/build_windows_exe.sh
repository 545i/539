#!/usr/bin/env bash
# 在 Linux 上用 Wine 把今彩539 Web 版打包成單一 Windows .exe。
#
# 前置需求(Ubuntu/Debian):
#   sudo dpkg --add-architecture i386
#   sudo apt-get update && sudo apt-get install -y wine wine64 wine32
#
# 用法:
#   bash packaging/build_windows_exe.sh
#
# 產出:dist/lotto539.exe(單一檔,雙擊啟動 Streamlit + 開瀏覽器)
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

export WINEPREFIX="${WINEPREFIX:-$HOME/.wine539}"
export WINEARCH=win64
export WINEDLLOVERRIDES="mscoree,mshtml="
export WINEDEBUG=-all

PYVER="3.12.7"
PYEXE="python-${PYVER}-amd64.exe"
WPY='C:\Program Files\Python312\python.exe'

# 1. 初始化 wine prefix(若尚未建立)
if [ ! -d "$WINEPREFIX" ]; then
  echo "==> 初始化 wine prefix: $WINEPREFIX"
  wineboot --init
fi

# 2. 安裝 Windows 版 Python(若尚未安裝)
if ! wine "$WPY" --version >/dev/null 2>&1; then
  echo "==> 下載並安裝 Windows Python ${PYVER}"
  [ -f "/tmp/${PYEXE}" ] || curl -sL -o "/tmp/${PYEXE}" \
    "https://www.python.org/ftp/python/${PYVER}/${PYEXE}"
  wine "/tmp/${PYEXE}" /quiet InstallAllUsers=1 PrependPath=1 \
    Include_test=0 Include_doc=0 Include_tcltk=0
fi

# 3. 安裝執行所需套件與 PyInstaller
#    注意:numpy 必須鎖在 1.26.x。NumPy 2.x 的 _multiarray_umath 會呼叫
#    ucrtbase.dll.crealf,而 Wine 9.0 未實作該函式,會導致 import numpy 直接崩潰,
#    連帶 PyInstaller 的隔離子行程(分析 pandas/scipy 時)也一起死。
#    numpy 1.26.4 不依賴 crealf,可在 Wine 下正常載入與打包。
echo "==> 安裝相依套件(numpy 鎖 1.26)+ PyInstaller"
wine "$WPY" -m pip install --upgrade pip --no-warn-script-location
wine "$WPY" -m pip install --no-warn-script-location \
  "numpy==1.26.4" streamlit pandas scipy plotly requests beautifulsoup4 openpyxl pyinstaller

# 4. 打包
echo "==> PyInstaller 打包單一 exe"
rm -rf build dist
wine "$WPY" -m PyInstaller packaging/lotto539.spec --noconfirm \
  --distpath dist --workpath build

echo "==> 完成:dist/lotto539.exe"
ls -lh dist/lotto539.exe 2>/dev/null || echo "(找不到產物,請檢查上方輸出)"
