# 「雅宏策略」五三九分析 — 演算法規格書

> 來源檔案：`/tmp/yh_index5.html`（今彩 539 光量子 AI 科技對決擂台・百分比期望值旗艦版，約 1388 行）
> 對應功能：**📊 五三九分析**（今彩 539，每期開 5 顆號碼，號碼範圍 1~39）
> 本文件忠實拆解原頁**所有概念、算式、常數、門檻**，供 Python 重寫；已忽略 Firebase / apiKey / CSS / DOM 動畫等樣板。

---

## ① 功能總覽

原頁是一個「AI vs 我」的 539 預測對決記錄與分析總表，實際包含的分析／工具模組如下：

| 區塊 | 名稱 | 性質 |
|------|------|------|
| A | 倍投／階梯資金規劃表（單碼目標、4碼目標、階梯均注追蹤） | 純資金管理計算，與號碼無關 |
| B | 1800 碰 / 9000 碰 柱碰即時看板 | 遺漏統計 + 幾何機率 |
| C | 熱門號（近 50 期 TOP 8） | 頻率統計 |
| D | 冷門號（連續未開 TOP 8） | 遺漏統計 |
| E | 機率評分 `probScore`（頻率 + 反彈加權） | 綜合評分（推薦號池的排序依據） |
| F | 四大模式三星／四星推薦矩陣 | 依 `probScore` 池做加權隨機抽樣 |
| G | 量子矩陣抽號機 | 純亂數（1~39 取 5 不重複） |
| H | AI vs 我 命中對決計算與統計戰力板 | 命中數比較 + 平均命中率霸主判定 |
| I | 資料輸入／解析（單筆補填、多期貼上匯入、民國年轉換） | 資料清洗 |

> **重要定位**：所謂「量子算牌 / 貝氏 / AI 必開」在程式碼中**幾乎都是行銷噱頭**。真正有計算的只有：遺漏 gap 統計、近 50 期頻率、幾何分布反彈機率、以及 `probScore` 這個「頻率 0.65 + 反彈分 0.35」的加權評分。推薦號碼本體是**加權隨機抽樣**（洗牌取前 N），並非最佳化。看板上多個「EV 百分比」「+18.5% EV」等是**寫死在 HTML 的固定文字**，非計算結果。Python 重寫時應據實呈現。

---

## ② 資料模型

```
記錄 record = {
  id: string,            // 時間戳字串
  date: "YYYY-MM-DD",
  ai:  number[],         // AI 預測號碼 (1~39, 去重升冪; 可 0~多顆)
  my:  number[],         // 我的預測號碼 (同上); 舊欄位 p1 會被搬到 my
  draw: number[],        // 實際開獎，剛好 5 顆 (1~39, 去重升冪)
  aiHits: number,        // ai ∩ draw 的顆數
  myHits: number,        // my ∩ draw 的顆數
  winner: string,        // 見 ②H winner 判定
  isPending: boolean     // 尚未開獎 (draw 不足 5 顆)
}
歷史 battleHistory = record[]  // 依 date 由新到舊排序 (date 相同則 id 字串大者在前)
```

- **完成期（completedDraws）**：`!isPending && draw && draw.length === 5`。所有統計皆只用完成期，且 `completedDraws[0]` = 最新一期。
- 排序：`new Date(b.date) - new Date(a.date)`（新→舊）；同日期以 `id` 字串 `localeCompare` 反向。

---

## ③ 指標清單

### A. 倍投／階梯資金規劃（Modal 三分頁）

共用常數（預設值，皆可由使用者輸入覆寫）：

| 參數 | 預設 | 說明 |
|------|------|------|
| 每全車成本 `cost` | 2755 | 一整車（全 39 碼三星柱碰之類）成本，元 |
| 每全車彩金 `prize` | 21200 | 中一碼／中一注的彩金，元 |
| 每期目標增量淨利 `target` | 18440 | 每期要「多賺」的淨利 |
| 車數步進 | 0.05 | 所有車數一律向上取整到 0.05 的倍數 |

#### A-1. 單碼目標倍投 `calculateSingleTargetPlan`

輸入：`units`(第1期起步車數,預設1)、`target`(18440)、`days`(15)、`cost`(2755)、`prize`(21200)。

```js
accumulatedCost = 0
for i in 1..days:
    currentTarget = target * i                              // 目標累計淨利
    reqU = (currentTarget + accumulatedCost) / (prize - cost)
    if (i === 1 && units >= reqU) reqU = units              // 第1期若起步車數已夠就沿用
    else reqU = Math.ceil(reqU / 0.05) * 0.05               // 否則向上取 0.05
    if (reqU < 0.01) reqU = 0.05
    dailyCost   = reqU * cost
    accumulatedCost += dailyCost
    winPrize    = reqU * prize
    netProfit   = winPrize - accumulatedCost                // 該期中獎後的結算淨利
```
輸出欄位：天數 / 目標累計淨利 / 下注車數(`reqU.toFixed(2)` 車) / 當期成本 / 累計總投入 / 中獎彩金 / 結算淨利。金額 `Math.round` 後 `toLocaleString()`（千分位、整數）。

#### A-2. 4碼目標倍投 `calculateFourTargetPlan`

同 A-1，差別：**同時押 4 個號碼**，故分母扣 `4*cost`、成本 `×4`。

```js
reqU = (currentTarget + accumulatedCost) / (prize - 4 * cost)
if (i === 1 && units >= reqU) reqU = units
else reqU = Math.ceil(reqU / 0.05) * 0.05
dailyCost = reqU * cost * 4
accumulatedCost += dailyCost
winPrize  = reqU * prize                    // 中 1 碼彩金
netProfit = winPrize - accumulatedCost      // 保底(中1碼)結算淨利
doubleWin = winPrize * 2 - accumulatedCost  // 「雙停」中 2 碼暴利
```
預設 `days = 6`。輸出多一欄「若中 2 碼（雙停暴利）」= `doubleWin`。

#### A-3. 階梯均注追蹤 `renderTierTable` / `calculateTierNextUnits`

兩種子模式：`single`（單碼，**3 期一階**）、`four`（4碼，**2 期一階**）。

- `costUnit = mode==='single' ? 2755 : 2755*4`
- `prize` 固定 **21200**（此分頁寫死，不讀輸入）
- 起始車數 `baseU`（預設1）、總期數 `totalDays`（預設15）

進階公式（每跨一階重算車數）：
```js
function calculateTierNextUnits(prevCost, prevU, mode):
    costUnit = mode==='single' ? 2755 : 2755*4
    u = prevCost / (21200 - costUnit) * 1.05    // 用「已累計成本」回推 + 5% 緩衝
    u = Math.ceil(u / 0.05) * 0.05
    if (u <= prevU) u = prevU + 0.05            // 至少比上一階多 0.05 車
    return round(u, 2)
```
表格生成：
```js
step = mode==='single' ? 3 : 2
accCost = 0; curU = baseU; tier = 1
for i in 1..totalDays:
    if (i > 1 && (i-1) % step === 0):           // 跨階
        tier++; curU = calculateTierNextUnits(accCost, curU, mode)
    dailyCost = curU * costUnit
    accCost  += dailyCost
    netProfit = curU * 21200 - accCost          // 「保證賺錢」的結算淨利
```
互動狀態機 `tierState = {mode, day, tier, units, accumulatedCost}`：
- `recordTierResult(true)`（過關）→ `resetTierGame()`：day=1, tier=1, units=baseU, accumulatedCost = units*costUnit。
- `recordTierResult(false)`（沒過）→ `day++`；若 `(day-1)%step===0` 則 `tier++` 並用 `calculateTierNextUnits` 更新 units；`accumulatedCost += units*costUnit`。

> 「保證賺錢／不限期」是行銷話術：其實是無上限馬丁格爾（Martingale）加碼，本金爆掉風險未計入。

---

### B. 1800 碰 / 9000 碰 柱碰看板

**柱位（column）定義**（號碼→柱）：

- **1800 碰（三星柱碰・9×10×20）** — 需三柱各至少開 1 顆：
  - 第1柱：`10–18`
  - 第2柱：`20–29`
  - 第3柱：`01–09` 或 `=19` 或 `30–39`
  ```js
  isHit1800(draw): hasCol1 && hasCol2 && hasCol3
  ```
- **9000 碰（四星柱碰・9×10×10×10）** — 需四柱各至少開 1 顆：
  - 第1柱：`01–09`；第2柱：`10–19`；第3柱：`20–29`；第4柱：`30–39`
  ```js
  isHit9000(draw): hasCol1 && hasCol2 && hasCol3 && hasCol4
  ```

**連續未開期數（miss）**：從最新期往回數，遇到第一個命中就停：
```js
miss = 0
for d in 0..len-1:
    if (isHit(completedDraws[d].draw)) break
    miss++
```

**下一期「極限反彈機率」**（幾何分布累積：連錯 miss 期後，下一期至少開出的機率）：
```js
baseP1800 = 0.5536
baseP9000 = 0.2736
nextProb = (1 - (1 - baseP)^(miss + 1)) * 100     // 百分比，toFixed(2)
```
> 數學上這是「連續 miss+1 期至少中 1 次」的機率，並非「下一期單獨命中」機率——命名誇大（賭徒謬誤），但公式如上照抄即可。

**狀態徽章門檻**：

| 類別 | badge-alert（🚨 必出/必開） | badge-ready（⚡ 蓄勢/高期望） | badge-ok（✅ 安全） |
|------|------|------|------|
| 1800 | `nextProb > 95` → 「🚨 極限警戒必出」 | `> 80` → 「⚡ 蓄勢開出中」 | 其餘「✅ 安全常規區間」 |
| 9000 | `nextProb > 85` → 「🚨 嚴重偏離必開」 | `> 70` → 「⚡ 進入高期望期」 | 其餘「✅ 安全常規區間」 |

**看板寫死文字（非計算，Python 重寫可選擇重算或標記為固定）**：
- 1800：「精準中 3 碰 24.5% / 中 4 碰 30.9%」、「近 50 期 AI 歷史期望值 +18.5% EV」、「下一期數學期望值 +21.4%（強勢正收益）」
- 9000：「單期開出機率 27.36%」、「近 50 期 AI 歷史期望值 +32.8% EV」、「下一期數學期望值 +28.6%（高賠率爆發）」
- `baseP9000 = 0.2736` 與「27.36%」一致；`0.5536` 與 24.5%+30.9% 無直接關係（純標示）。

---

### C. 熱門號（近 50 期 TOP 8）

每號統計三個量（見 §E 的 `numStats`）。熱門排序：
```js
hotNumbers = statsArray.sort((a,b) =>
    b.recent50Count - a.recent50Count      // 主：近50期出現次數多者在前
    || a.missingStreak - b.missingStreak   // 次：遺漏少者在前
).slice(0, 8)
```
- 顯示：號碼（2位補零）+「開 N 次」（N = `recent50Count`）。
- 若最新期開出該號 → 加 `hit-today` 標記（右上角「開」）。
- 標題摘要：`[<最新日期> 開出 <hotHitCount> 顆]`，`hotHitCount` = TOP8 熱門中在最新期開出的顆數。

### D. 冷門號（連續未開 TOP 8）

```js
coldNumbers = statsArray.sort((a,b) =>
    b.missingStreak - a.missingStreak      // 主：遺漏多者在前
    || a.recent50Count - b.recent50Count   // 次：近50期少者在前
).slice(0, 8)
```
- 顯示：號碼 +（`missingStreak===0 ? '今日開出' : '漏 N 期'`）。
- 摘要同 C（`coldHitCount`）。

---

### E. 機率評分 `probScore`（`analyzeHotColdNumbers` 核心）

每號初始化：`{num, totalCount:0, recent50Count:0, missingStreak:999}`。

1. **遺漏 `missingStreak`**：從最新期往回找第一次出現的索引 `d`（`streak=d`）；若整段歷史都沒出現 → `missingStreak = completedDraws.length`。（注意：最新期就開出 → 0；上一期開出 → 1。）
2. **近50頻率 `recent50Count`**：`max50 = min(50, len)`，前 `max50` 期中該號出現次數。
3. **總頻率 `totalCount`**：全歷史出現次數（僅存，未用於評分）。

評分：
```js
freqScore = (recent50Count / max50) * 100            // 0~100
reboundScore = 50                                     // 預設
if (missingStreak >= 5 && missingStreak <= 12) reboundScore = 95   // 甜蜜反彈區
else if (missingStreak === 0) reboundScore = 75      // 剛開出(熱延續)
else if (missingStreak > 20) reboundScore = 35       // 太久沒開(懲罰)
// 註：missingStreak 1~4、13~20 → 維持 50

probScore = freqScore * 0.65 + reboundScore * 0.35
```
`probabilityRankedBalls` = 全 39 號依 `probScore` 由高到低排序（供 §F 推薦號池）。

---

### F. 四大模式三星／四星推薦矩陣 `refreshRecommendationsWithSuspense`

**號池 `pool`**：`probabilityRankedBalls.length >= 15` 時 = 依 probScore 排序後的號碼陣列；否則 = `[1..39]`。
`getRandomPicks(source, count)` = 洗牌（`sort(()=>0.5-Math.random())`）後取前 `count`、去重、升冪。

| 模式 | 三星（3碼） | 四星（4碼） | 池來源 |
|------|------|------|------|
| 1. 搖球機物理模式 | `getRandomPicks([1..39], 3)` | `getRandomPicks([1..39], 4)` | 全盤純亂數 |
| 2. 歷史紀錄出牌模式 | `getRandomPicks(pool[0:16], 3)` | `getRandomPicks(pool[0:16], 4)` | 前 16 高分 |
| 3. 尋找AI必開牌（旗艦主力） | 2×`top` + 1×`mid` | 2×`top` + 2×`mid` | `top=pool[0:5]`, `mid=pool[5:12]` |
| 4. AI必開加強矩陣（極限防守） | 2×`pool1` + 1×`pool2` | 2×`pool1` + 2×`pool2` | `pool1=pool[1:7]`, `pool2=pool[6:15]` |

- 模式 3/4 各段用 `getRandomPicks` 取，再合併 `sort` 升冪。
- 每張卡顏色：模式1 金 `c-gold/q-gold`、模式2 玫 `c-rose/q-rose`、模式3 青 `c-cyan/q-cyan`、模式4 紫 `c-purple/q-purple`。
- 卡上有「入 AI / 入 我的」按鈕，把號碼字串（2位補零、逗號分隔）帶入輸入欄。
- 純顯示的行銷副標（貝氏、共振、拖牌…）**無對應計算**。

> 本質：模式 1 全隨機；模式 2~4 是在「probScore 高分子集」裡做加權隨機抽樣。並非最佳化或真貝氏。

---

### G. 量子矩陣抽號機 `startNewMachineRoll`

純亂數，與歷史無關：
```js
resultNums = []                       // 取 5 顆不重複
while resultNums.length < 5:
    r = floor(random()*39)+1
    if r not in resultNums: push
sort 升冪
```
只有動畫（每顆 600+i*150 ms 滾動）與「是否帶入開獎欄」的確認框。

---

### H. AI vs 我 對決計算與統計戰力板

**單期命中／勝負 `calculateResult(aiNums, myNums, drawNums)`**：
```js
aiHits = ai.filter(n => draw.includes(n)).length
myHits = my.filter(n => draw.includes(n)).length
hasAi = ai.length > 0 ; hasMy = my.length > 0
winner (僅當 draw.length === 5 才判，否則 "等待開獎"):
    !hasAi && !hasMy → "無人預測"
    hasAi && !hasMy  → "僅 AI"
    !hasAi && hasMy  → "僅 我"
    else: aiHits>myHits→"AI 勝"; myHits>aiHits→"我 勝"; 相等→"平手"
```

**全域統計 `renderAll`**（只計完成期）：
```js
totalRounds++      每個完成期
if (ai.length>0): aiRounds++; totalAiHits += aiHits
if (my.length>0): myRounds++; totalMyHits += myHits
aiAvg = aiRounds>0 ? totalAiHits/aiRounds : 0     // 場均命中，toFixed(2)
myAvg = myRounds>0 ? totalMyHits/myRounds : 0
```
**霸主判定（依平均命中率）**：
- `totalRounds===0` 或（aiAvg===0 且 myAvg===0）→「等待開獎」
- `aiAvg > myAvg` →「🤖 AI 領先」；`myAvg > aiAvg` →「🧑 人類(我)領先」；相等→「平分秋色」

戰力板顯示：已結算期數、AI 總命中 + 參賽期數 + 場均、我 總命中 + 場均、勝率霸主。
歷史表格分頁：`displayLimit` 初始 20，「顯示更多」每次 +30。

---

### I. 資料輸入／解析

**`parseNumbers(str)`**：抽 `\d+` → 轉整數 → 篩 `1~39` → 去重升冪。

**`extractMultiDrawsFromText(rawText)`**（多期整頁貼上）：
- 逐行；行首優先匹配日期 `^(\d{2,4}[-/]\d{1,2}[-/]\d{1,2})`，否則行內匹配。
- **民國年轉西元**：日期年份部分長度 === 3（如 `115`）→ `+1911`。分隔符 `/`→`-`。
- 日期後段抽號碼 `\b(0?[1-9]|[1-3][0-9])\b` → 篩 1~39 去重；需 `>=5` 顆，取前 5 升冪。
- 同日期只留第一筆（`uniqueMap`）。

**`getValid539DrawDate()`**：今天；若 `getDay()===0`（週日）→ +1 天（順延週一）。格式 `YYYY-MM-DD`。

**寫入授權**：所有寫入（單筆補填、多期匯入、改期、刪除）皆需密碼 `"110119110"`（前端明碼比對，Python 重寫請改為後端驗證）。多期匯入以 400 筆為一批 `writeBatch` commit。

**補填規則 `addRecordWithAuth`**：draw 有填則必須剛好 5 碼；`isPending = draw.length !== 5`（新建時 `draw.length===0`）；既有記錄未填欄位沿用舊值。

---

## ④ 推薦 / 裁決邏輯彙整

| 判斷 | 條件 → 結果 |
|------|------|
| 1800 徽章 | `nextProb>95` 必出 / `>80` 蓄勢 / 其餘 安全 |
| 9000 徽章 | `nextProb>85` 必開 / `>70` 高期望 / 其餘 安全 |
| 反彈加分 `reboundScore` | 遺漏 5~12 →95；=0 →75；>20 →35；其餘 →50 |
| 綜合分 `probScore` | `freqScore*0.65 + reboundScore*0.35` |
| 熱門排序 | 近50次數↓，遺漏↑；取前 8 |
| 冷門排序 | 遺漏↓，近50次數↑；取前 8 |
| 推薦號池 | probScore 排序，`pool` 切片（模式2:0-16 / 模式3:0-5,5-12 / 模式4:1-7,6-15）後加權隨機 |
| 單期勝負 | 比 `aiHits` vs `myHits`（見 §H） |
| 總霸主 | 比 `aiAvg` vs `myAvg`（平均命中率） |
| 倍投車數 | `ceil(reqU/0.05)*0.05`，最小 0.05 |
| 階梯跨階 | single 每 3 期、four 每 2 期；車數 `prevCost/(21200-costUnit)*1.05` 取整、至少 +0.05 |

**沒有「單一最終裁決」**：頁面不會輸出「今天就買這 5 碼」的唯一結論。推薦是 8 組（4 模式 × 三星/四星）並列，靠使用者自選。

---

## ⑤ 顯示欄位 / 區塊對照表

| DOM id / 區塊 | 內容 | 格式 |
|------|------|------|
| `total-rounds` | 已結算期數 | 整數 |
| `ai-hits` / `my-hits` | 總命中 | 整數 |
| `ai-rounds` / `my-rounds` | 參賽期數 | 整數 |
| `ai-avg` / `my-avg` | 場均命中 | `toFixed(2)` |
| `pk-winner` | 勝率霸主 | 文字，含顏色 |
| `t1800-miss-count` / `t9000-miss-count` | 連續未開期數 | 整數 |
| `t1800-prob-val` / `t9000-prob-val` | 極限反彈機率 | `%`，2 位小數 |
| `t1800-badge` / `t9000-badge` | 狀態徽章 | 文字 + class |
| `hot-numbers` / `cold-numbers` | TOP8 徽章 | 號碼2位補零 + 描述 |
| `hot-hit-summary` / `cold-hit-summary` | `[日期 開出 N 顆]` | 文字 |
| `recom-container` | 8 張推薦卡 | 每卡 3 或 4 顆量子球 |
| `st-plan-tbody` / `ft-plan-tbody` / `tier-table-body` | 倍投／階梯表 | 金額千分位整數、車數 2 位小數 |
| 開獎球樣式 | 命中 `hit`（紅）、開獎 `draw`（金）、待開獎「⏳ 待開獎」 | — |

**顏色語意**：熱/命中=紅玫 `#fb7185`，冷/AI=青 `#38bdf8`，我/獲利=綠 `#10b981`，開獎/警示=金 `#f59e0b`，量子/階梯=紫 `#a855f7`。

---

## 重寫注意事項（給 Python 版）

1. `probScore`、遺漏、近50頻率、幾何反彈機率為**唯一真計算**，務必照常數重現（0.65/0.35、reboundScore 門檻 5/12/0/20、baseP 0.5536/0.2736）。
2. 推薦號碼有隨機性；若要可重現需固定亂數種子，或改為「依 probScore 直接取前 N」。
3. 看板上多個 EV/百分比為**寫死文字**，非計算——重寫時建議實算或明確標示。
4. 車數一律 `ceil 到 0.05`；階梯與倍投的 `prize=21200`、`cost=2755` 為預設常數，可外部化為設定。
5. 密碼 `110119110`、Firebase collection `539_battle_history` 屬前端實作細節，後端重寫請改為正規驗證與資料表。
