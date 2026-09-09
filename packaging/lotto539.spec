# -*- mode: python ; coding: utf-8 -*-
"""今彩539 Web 版 PyInstaller 打包設定(單一 exe)。

在 wine 內執行:
  wine python -m PyInstaller packaging/lotto539.spec --noconfirm
"""
import os

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

# 專案根目錄:spec 位於 <root>/packaging/,故 root = SPECPATH 的上一層。
# 全部改用絕對路徑,避免 PyInstaller 以 spec 目錄為基準造成路徑雙層。
PROJECT = os.path.dirname(SPECPATH)  # noqa: F821 (SPECPATH 由 PyInstaller 注入)


def P(*parts):
    return os.path.join(PROJECT, *parts)

datas = []
binaries = []
hiddenimports = []

# 需要完整收集靜態檔/資料/相依的套件
for pkg in [
    "streamlit",
    "altair",
    "pandas",
    "numpy",
    "scipy",
    "openpyxl",
    "bs4",
    "requests",
    "pyarrow",
    "pydeck",
    "narwhals",
]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# plotly:不用 collect_all,因 plotly.matplotlylib 會嘗試 import matplotlib,
# 在 wine 隔離子行程下會崩潰。改為收集資料檔 + 過濾掉 matplotlylib 子模組。
datas += collect_data_files("plotly")
hiddenimports += collect_submodules(
    "plotly", filter=lambda name: "matplotlylib" not in name
)

# Streamlit 執行期會用 importlib.metadata 讀版本,需附帶 metadata
for pkg in [
    "streamlit",
    "altair",
    "plotly",
    "pandas",
    "numpy",
    "scipy",
    "openpyxl",
    "requests",
    "beautifulsoup4",
    "pyarrow",
    "click",
    "tornado",
    "gitpython",
    "pympler",
    "rich",
]:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# 應用程式本體:app.py 與專案套件、資料、設定一起打包到 _MEIPASS 根層
datas += [
    (P("app.py"), "."),
    (P("core"), "core"),
    (P("ui"), "ui"),
    (P("data"), "data"),
    (P(".streamlit"), ".streamlit"),
]

# 確保專案自有套件被視為模組
hiddenimports += [
    "core", "core.constants", "core.loader", "core.stats", "core.picker",
    "core.backtest", "core.scraper", "core.kelly", "core.excel_report",
    "ui", "ui.docs", "ui.charts", "ui.menu",
]

block_cipher = None

a = Analysis(
    [P("packaging", "launch_app.py")],
    pathex=[PROJECT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "questionary", "plotext", "matplotlib", "plotly.matplotlylib"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="lotto539",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,  # windowed:無 console 視窗,避開 Wine 下 bootloader 的 std 串流初始化問題
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
