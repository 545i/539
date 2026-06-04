# 今彩539 統計分析工具 — 設計文件

日期:2026-06-04

## 核心立場(誠實聲明)

今彩539 每期開獎為**獨立同分布隨機事件**,數學上**沒有任何方法能預測下一期號碼**。
本工具**不是**預測神器,而是一個**透明、教育性質的統計分析與娛樂選號工具**。

- 長期期望報酬率約 **−44.16%**(每注 NT$50,長期平均拿回約 NT$28)。
- 所有「選號策略」(隨機/熱號/冷號/頻率/均衡)**期望中獎率完全相同**,差異只是運氣(變異數),不是策略優劣。
- 工具會在顯眼處揭露上述事實,把「為什麼任何策略都贏不過隨機」當成核心教育價值。

## 已查證的遊戲規則與獎金結構(來源:台灣彩券官網 + 第三方對照 + 組合數驗算)

- 玩法:01~39 選 5 個號碼;**週一至週六**開獎(週日不開)。
- 每注:NT$50。
- 頭獎固定 800 萬,但全期上限 2,400 萬(超過 3 注頭獎則均分)。

| 獎別 | 中幾碼 | 獎金(NTD) | 組合數 ways | 理論機率 |
|------|--------|-----------|------------|----------|
| 頭獎 | 5 | 8,000,000 | 1 | 1/575,757 |
| 貳獎 | 4 | 20,000 | 170 | 170/575,757 |
| 參獎 | 3 | 300 | 5,610 | 5,610/575,757 |
| 肆獎 | 2 | 50 | 59,840 | 59,840/575,757 |
| 無獎 | 1 | 0 | 231,880 | — |
| 無獎 | 0 | 0 | 278,256 | — |

`C(39,5)=575,757`;`ways(k)=C(5,k)·C(34,5−k)`。每注期望獎金 ≈ NT$27.92 → 報酬率 ≈ −44.16%。

## 介面

進入程式後以 **方向鍵 ↑↓ 選單**(questionary)操作,不使用命令列參數。
主選單:
1. 統計分析
2. 產生參考號碼
3. 策略回測
4. 更新資料(爬蟲)
5. 關於 / 免責聲明
6. 離開

圖表:`plotext` 在終端機直接畫長條圖/直方圖;`rich` 畫表格與彩色共現矩陣。**不存 PNG**。

## 專案結構

```
lotto539/
├── main.py                 # 進入點 → ui.menu.run()
├── requirements.txt
├── data/history.csv        # 開獎資料:date,n1,n2,n3,n4,n5
├── core/
│   ├── constants.py        # 獎金/機率/規則常數
│   ├── loader.py           # 讀取/驗證 CSV、合併資料、產生範例資料
│   ├── scraper.py          # 台灣彩券爬蟲(混合來源的更新功能)
│   ├── stats.py            # 全部統計分析
│   ├── picker.py           # 5 種選號策略
│   └── backtest.py         # 回測引擎
├── ui/
│   ├── menu.py             # questionary 方向鍵選單流程
│   └── charts.py           # plotext / rich 呈現
└── tests/                  # pytest
```

## 各模組職責

### core/constants.py
匯出:`NUM_MIN=1, NUM_MAX=39, PICK=5, TICKET_PRICE=50`、`PRIZE` dict、`WAYS` dict、`TOTAL_COMB=575757`、`EXPECTED_RETURN≈-0.4416`、免責聲明文字。

### core/loader.py
- `load_history(path) -> pandas.DataFrame`:讀 CSV,驗證每列 5 個號碼皆在 1~39 且不重複、日期可解析;錯誤列回報。
- `merge(df, new_rows)`:依日期去重合併。
- `generate_sample(n, seed) -> DataFrame`:產生 n 期**均勻隨機**範例資料(seed 固定,可重現),讓工具立即可 demo。

### core/scraper.py
- `fetch_latest(since_date) -> list[draw]`:抓官網最新開獎。官網為 JS 動態載入,改抓其公開 JSON/API 或第三方;抓不到時優雅失敗並提示使用者改用 CSV。**爬蟲為加值功能,核心不依賴它。**

### core/stats.py(全部 A~G)
- `frequency(df)`:每號 01~39 出現次數與排名。
- `hot_cold(df, window)`:近 window 期最常/最少出現。
- `missing(df)`:每號目前遺漏期數 + 歷史最大遺漏。
- `gaps_consecutive(df)`:每期 5 號間隔分布、連號出現比例。
- `parity_size_sum(df)`:奇偶比、大小比(以 20 為界)、和值分布。
- `chi_square(df)`:卡方適合度檢定。**自由度=38**;期望次數 E=期數×5/39;期數<約39 時警告期望次數不足、結果不可靠。回傳 χ²、p 值、結論(且結論不得暗示可預測)。
- `cooccurrence(df)`:39×39 共現矩陣,供 rich 彩色呈現。

### core/picker.py
策略列舉:`random`(等機率基準)、`hot`、`cold`、`frequency`、`balanced`。
- `pick(df, strategy, sets) -> list[tuple]`:回傳 sets 組、每組 5 個不重複號。
- `balanced`:過濾奇偶比與和值落在歷史常見區間。
- 每次輸出附固定提醒:各策略期望值相同、僅供娛樂。
- 隨機性:用 `random.Random(seed)`,seed 由呼叫端傳入(避免 `Math.random` 之類不可重現)。

### core/backtest.py
- `run(df, strategy, start_date, bet, seed) -> BacktestResult`:
  - 對 start_date 起每一期,**只用該期之前的資料**選號(防 look-ahead bias),與當期實際開獎比中幾碼。
  - 累計命中分布(0~5)、總投注、總回收、報酬率。
  - 頭獎以固定 800 萬計(單注不觸發均分,文件註明)。
- `compare(df, strategies, ...)`:同段歷史多策略 PK,證明都收斂到 ≈ −44%。

### ui/menu.py
questionary 主選單與子流程;呼叫 core 並交給 charts 呈現;啟動時顯示免責橫幅。

### ui/charts.py
- `bar(labels, values, title)`:plotext 長條圖。
- `hist(values, title)`:plotext 直方圖(和值分布)。
- `table(...)` / `matrix(...)`:rich 表格與彩色共現矩陣。

## 資料流

CSV(+ 可選爬蟲更新)→ loader 驗證 → DataFrame →(stats / picker / backtest)→ charts 終端呈現。

## 錯誤處理

- CSV 缺檔/格式錯:提示並提供「產生範例資料」選項。
- 爬蟲失敗:警告但不中斷,核心功能照常。
- 期數不足以做卡方:明確警告而非靜默。

## 測試(pytest)

- constants:期望報酬率由 PRIZE/WAYS 反算 ≈ −0.4416。
- loader:合法/非法 CSV、去重、範例資料可重現。
- stats:已知小資料集驗證頻率/遺漏/和值/卡方數值;卡方自由度=38。
- picker:每組 5 個不重複且在範圍內;balanced 符合條件;固定 seed 可重現。
- backtest:命中數計算正確;look-ahead 防護(選號不得用到當期);大樣本報酬率收斂到 ≈ −44%。

## 不做(YAGNI)

- 不做 Web UI、不存圖檔、不做帳號/雲端、不做即時推播。
- 不宣稱任何預測能力。
```
