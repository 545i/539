# 今彩539 統計分析工具

> **v2:Web 版(Streamlit)**

一個**透明、教育性質**的今彩539 統計分析與娛樂選號工具(Python TUI / Streamlit Web 版)。

> ⚠️ **誠實聲明**:今彩539 每期開獎為獨立隨機事件,**數學上無法預測下一期號碼**。
> 長期期望報酬率約 **−44%**。本工具不是預測神器,而是用來「親眼看見任何策略都贏不過隨機」的統計教學與娛樂工具。

## 功能

進入後用**方向鍵 ↑↓ 選擇**(不用打指令):

1. **統計分析** — 頻率、冷熱號、遺漏值、間隔/連號、奇偶/大小/和值、卡方檢定、共現配對
2. **產生參考號碼** — 5 種策略(隨機/熱號/冷號/頻率/均衡),可選組數
3. **策略回測** — 5 種策略同台 PK,計算真實獎金結構下的報酬率(防 look-ahead bias)
4. **更新資料** — 從台灣彩券抓最新開獎(加值功能,核心不依賴)
5. **關於 / 免責聲明**

圖表用 `plotext` 直接畫在終端機,表格用 `rich`,**不存任何圖檔**。

## 安裝與執行

```powershell
cd lotto539
python -m pip install -r requirements.txt
python main.py
```

首次執行若沒有資料,會詢問是否產生 500 期均勻隨機範例資料(可立即試用)。

## Web 版啟動

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
bash run_web.sh
```

啟動後在瀏覽器開 <http://localhost:8501> 即可使用 Web 版介面。

## 凱莉公式投報計算

凱莉公式(Kelly Criterion)用來計算「在正期望值賭局下」的最佳投注比例。

但今彩539 的長期期望報酬率約為 **−44%**(負 EV),凱莉公式套用在負期望值賭局時,
**算出的最佳投注比例為 0%** — 也就是**數學上最正確的選擇是不該下注**。

Web 版用**資金曲線**示範這個事實:無論用哪種策略、下注多少注,長期模擬的資金曲線
都會向下傾斜,親眼看見「任何投注比例 > 0% 都會慢慢輸光本金」。

## Excel 報表

Web 版可一鍵輸出含圖表的 `.xlsx` 報表,內容包含:

- **開獎資料** — 歷史開獎號碼
- **頻率** — 各號碼出現次數
- **回測** — 各策略報酬率比較
- **凱莉分析** — 期望值、凱莉比例(0%)與資金曲線示範

圖表直接嵌入 Excel,方便離線檢視與分享。

## 真實資料

把開獎資料放到 `data/history.csv`,格式:

```csv
date,n1,n2,n3,n4,n5
2026-06-03,3,11,18,25,39
```

或在程式內選「更新資料」自動抓取(API 隨官網改版可能失效,屆時改用 CSV 匯入)。

## 已查證的獎金結構(每注 NT$50)

| 中幾碼 | 獎金 | 機率 |
|---|---|---|
| 5 | $8,000,000 | 1/575,757 |
| 4 | $20,000 | 170/575,757 |
| 3 | $300 | 5,610/575,757 |
| 2 | $50 | 59,840/575,757 |
| 1 / 0 | 無獎 | — |

每注期望獎金 ≈ NT$27.92 → 報酬率 ≈ **−44.16%**。

## 測試

```powershell
python -m pytest -q
```

## 打包成 Windows 單一 exe(用 Wine 在 Linux 上)

把 Web 版打包成單一 `lotto539.exe`(雙擊即啟動 Streamlit + 開瀏覽器):

```bash
bash packaging/build_windows_exe.sh
# 產物:dist/lotto539.exe(約 159 MB,單檔)
```

打包機制與重點:

- `packaging/launch_app.py` — exe 進入點,用內嵌的 Streamlit 跑 `app.py`。
- `packaging/lotto539.spec` — PyInstaller 設定(`console=False` windowed、收集 streamlit/plotly 等資源、把 app/core/ui/data 一起打包)。
- **NumPy 必須鎖 1.26.x**:Wine 9.0 的 ucrtbase 未實作 `crealf`,NumPy 2.x 會在 Wine 下崩潰(真 Windows 不受影響)。
- `app.py` 為 frozen-aware:打包後 `data/history.csv` 讀寫在 exe 旁邊,並內附種子資料。

> 真正在 Windows 上雙擊即可執行;若要在 Linux/Wine 測試,用 `wine start /unix dist/lotto539.exe` 模擬雙擊(直接從管線啟動會因 Wine 的 std handle 問題失敗)。

## 測試

```powershell
python -m pytest -q
```

## 專案結構

```
lotto539/
├── main.py            TUI 進入點(舊版,仍可用)
├── app.py             Streamlit Web 版進入點
├── core/              constants / loader / scraper / stats / picker / backtest / kelly / excel_report
├── ui/                menu(方向鍵選單)/ charts / docs(算式說明頁)
├── data/history.csv   開獎資料
├── packaging/         launch_app.py / lotto539.spec / build_windows_exe.sh
├── tests/             pytest
└── docs/superpowers/specs/  設計文件
```
