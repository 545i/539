# 雅宏策略 —「🚀 天天樂分析」規格書 (spec-fantasy)

> 來源檔:`/tmp/yh_index4.html`(2621 行,標題「天天樂 光量子 AI 科技對決擂台 (智能三星四星雙軌矩陣版)」)
> 對應功能:天天樂(加州 Fantasy5)綜合分析總表。此檔把單純的統計/隨機包裝成「量子 AI / 華爾街盤路 / 立柱風控」術語,底層數學其實相當單純。
> 本規格已完整到可直接照著用 Python 重寫,凡常數、門檻、四捨五入方式一律照抄。

---

## ① 功能總覽

整頁分成六大功能區:

1. **AI vs 我 對決戰績**(頁首 stats-board):累計 AI/我 兩方預測命中數,算場均命中率,判「勝率霸主」。
2. **冷熱號 + 逐號機率評分**(冷熱號區塊):頻率、近期、回歸三因子加權出 `probScore` 排名。
3. **三大模式同步推薦**(推薦矩陣):6 張推薦卡(搖機/歷史/AI × 三星/四星),本質是從不同號池隨機抽號。
4. **立柱風控矩陣**(1800碰/9000碰):把號碼分柱,算「全柱都開到」的連漏 gap、歷史命中率、與一個假的「AI 爆發率」,再給進場燈號。
5. **獲利與倍投規劃系統**(Modal,4 個分頁):單碼目標倍投、4碼目標倍投、階梯均注追蹤、1800/9000碰立柱倍投 — 全是等比/追號本金試算表。
6. **3D 量子搖號機**(PhysicsMachine):純視覺動畫 + `Math.random` 抽 5 碼,無任何分析意義。

資料儲存:Firebase Firestore collection `battle_history`(即時 `onSnapshot`)。**重寫時忽略 Firebase**,只需一個「歷史開獎 + 預測」資料表。

---

## ② 資料模型(與 539 的差異)

### 單筆紀錄(Firestore document)
```
{
  id:       string,        // 時間戳字串
  date:     "YYYY-MM-DD",
  ai:       number[],      // AI 預測號碼(3/4/5 碼,可空)
  my:       number[],      // 我的預測號碼(3/4/5 碼,可空)
  draw:     number[],      // 實際開獎,恰 5 碼
  aiHits:   number,        // ai ∩ draw 的個數
  myHits:   number,
  winner:   string,        // 見 calculateResult
  isPending:boolean        // draw 未滿 5 碼即 pending
}
// 相容處理:若舊資料有 p1 而無 my,則 my = p1(line 1234)
```

### 號碼域
- **號碼範圍 1~39,每期開 5 碼**(加州 Fantasy5,規格與台灣 539 完全相同)。
- 預測有效性 `isValidPrediction`:長度 ∈ {3, 4, 5}(注意:允許 3 碼,和一般 539 只填 5 碼不同)。
- 開獎必須恰 5 碼才算已結算。

### 與 539 的差異(重寫時注意)
| 面向 | 539 | 天天樂(本檔) |
|------|-----|----------------|
| 號碼域 | 1~39 選 5 | 1~39 選 5(**相同**) |
| 開獎時程 | 週一~六 20:30 | 加州每天 18:30(每日一期) |
| 每全車成本(預設) | (依 539 設定) | **2755 元** |
| 每全車彩金(預設) | (依 539 設定) | **21200 元** |
| 立柱玩法 | — | 1800碰(三星)、9000碰(四星),見 ④ |
| 冷熱/gap/逐號評分演算法 | 同結構 | **同結構、常數相同**(可共用) |

> 結論:**冷熱號、逐號 probScore、gap/立柱機率、推薦抽號、倍投試算**這些演算法與 539 版可共用同一套函式,差別只在「成本/彩金常數」與「立柱柱位定義」。詳見 ⑥。

---

## ③ 指標清單(逐一精確算式)

### 3.0 共用工具

**parseNumbers(inputStr)** — 解析使用者輸入
```js
nums = inputStr.match(/\d+/g)            // 抓所有數字串
     .map(parseInt)
     .filter(n => 1 <= n <= 39)
nums = 去重(Set) 後 升冪排序
// 空字串 → []
```

**extractMultiDrawsFromText(rawText)** — 多期整頁貼上解析
```
逐行:
  找日期 = /^(\d{4}[-/]\d{1,2}[-/]\d{1,2})/(找不到再用 \b...\b)
  日期字串把 / 換成 -
  日期後面的部分抓號碼 = /\b(0?[1-9]|[1-3][0-9])\b/g   // 只 1~39
  validNums = 去重 + filter(1~39)
  若 validNums.length >= 5 → 取「前 5 個、升冪排序」當作該期開獎
同一日期只保留第一筆(Map 去重)
```

---

### 3.1 命中判定與單期霸主(calculateResult)
- **輸入**:aiNums、myNums、drawNums。
- **算式**:
```
aiHits = aiNums 之中落在 draw 的個數
myHits = myNums 之中落在 draw 的個數
winner(僅在 draw.length === 5 時判定,否則 "等待開獎"):
  兩邊都無有效預測 → "無人預測"
  只有 AI 有       → "僅 AI"
  只有 我 有       → "僅 我"
  否則 aiHits>myHits → "AI 勝";myHits>aiHits → "我 勝";相等 → "平手"
```
- **輸出顯示**:歷史表每列 badge:AI 勝(藍 badge-ai)、我 勝(綠 badge-my)、pending(黃 badge-pending「⏳ 等待開獎」),其餘字串以灰底顯示。每方預測下方標「中 N 顆 (X碼)」。

---

### 3.2 對決累計統計(renderAll 頁首 stats-board)
- **輸入**:全部已結算紀錄(`!isPending && draw.length===5`)。
```
totalRounds = 已結算期數
aiRounds = 其中 isValidPrediction(ai) 的期數;totalAiHits = Σ aiHits
myRounds = 其中 isValidPrediction(my) 的期數;totalMyHits = Σ myHits
aiAvg = aiRounds>0 ? totalAiHits/aiRounds : 0     // 顯示 2 位小數
myAvg = myRounds>0 ? totalMyHits/myRounds : 0
勝率霸主:
  totalRounds===0 或 (aiAvg===0 && myAvg===0) → "等待開獎"
  aiAvg>myAvg → "🤖 AI 領先";myAvg>aiAvg → "🧑 人類(我)領先";相等 → "平分秋色"
```
- **輸出**:已結算期數、AI 總命中、我 總命中、各自「參賽 N 期 (場均 X.XX)」、勝率霸主文字(帶顏色)。

---

### 3.3 逐號機率評分 probScore(analyzeHotColdNumbers)★核心
**輸入**:已結算開獎清單 `completedDraws`,已依日期**降冪**排序(index 0 = 最新期)。
每個號碼 1~39 統計:
```
count       = 該號在全部已結算期出現總次數
lastSeenAgo = 由最新往回數,第一次出現的 index(即「距今幾期前開出」);
              從未出現 → 999;最新一期就開出 → 0
recentCount = 在最近 15 期(index < 15)內出現的次數
```
分數(視窗常數 = 15):
```
freqScore   = (count / 總期數) * 100
recentScore = (recentCount / min(15, 總期數)) * 100
reboundScore(回歸分,依 lastSeenAgo 分段):
    2 <= lastSeenAgo <= 5 → 95      // 剛好進入「該回補」甜蜜區
    lastSeenAgo ∈ {0,1}   → 80      // 剛開出仍有慣性
    其它(含 6+ 或 999)   → 40
probScore = freqScore*0.35 + recentScore*0.35 + reboundScore*0.30   // 權重 0.35/0.35/0.30
```
`probabilityRankedBalls` = 依 probScore 降冪排序的號碼陣列(供推薦區用)。

**熱門號 hotNumbers**(top 8):排序鍵 = count 降冪,平手時 lastSeenAgo 升冪。
**冷門號 coldNumbers**(top 8):排序鍵 = lastSeenAgo 降冪,平手時 count 升冪。

- **輸出格式**:
  - 熱門號徽章:號碼(補零 2 位)+「開 N 次」;紅色系。
  - 冷門號徽章:號碼 +(lastSeenAgo===999 →「未開過」;===0 →「今日開出」;否則「漏 N 期」);藍色系。
  - 若某號 = 最新一期開出,徽章加 `hit-today`(右上角紅色「開」標)。
  - 標題摘要:「[最新日期 開出 X 顆]」= 熱門/冷門 top8 與最新期交集數。

---

### 3.4 三大模式同步推薦(renderRecommendations)
**號池**:`pool = probabilityRankedBalls.map(num)`(若長度 ≥ 15),否則 `1..39`。
**抽號 getRandomPicks(source, count)**:`source` 洗牌(`sort(()=>0.5-Math.random())`),依序取不重複直到 count 個,升冪排序。

6 張卡:
```
① 🎰 搖機三星  m1_3 = 從 1..39 全池隨機 3 個        (sub「3D碰撞」,金 c-gold/q-gold)
② 🎰 搖機四星  m1_4 = 從 1..39 全池隨機 4 個        (sub「動態落點」,金)
③ 📊 歷史三星  m2_3 = 從 pool 前 16 名隨機 3 個      (sub「高頻連動」,玫 c-rose/q-rose)
④ 📊 歷史四星  m2_4 = 從 pool 前 16 名隨機 4 個      (sub「共振拖牌」,玫)
⑤ 🔥 AI必三星  m3_3 = pool 前 5(top)取 2 + pool 第 6~12(mid)取 1  (sub「爆發臨界」,青 c-cyan/q-cyan)
⑥ 🔥 AI必四星  m3_4 = top 取 2 + mid 取 2            (sub「期望權重」,青)
    其中 m3_top = pool.slice(0,5),m3_mid = pool.slice(5,12)
```
> 本質:模式①②純隨機,③④從高分池隨機,⑤⑥高分池分層抽,每次「🔄 換一組」重抽。無真正的相依性建模。輸出球號一律補零 2 位。

---

### 3.5 立柱連漏 / 機率 / 進場燈號(analyzeComboPatterns)★核心
**柱位定義(Fantasy5 專屬)**:
```
1800碰(三星立柱,需 3 柱都開):
  col1800_1 = 10~18            (9 顆)
  col1800_2 = 20~29            (10 顆)
  col1800_3 = 1~9, 19, 30~39   (20 顆)
9000碰(四星立柱,需 4 柱都開):
  col9000_1 = 1~9    (9)
  col9000_2 = 10~19  (10)
  col9000_3 = 20~29  (10)
  col9000_4 = 30~39  (10)
```
**逐期判定(completedDraws,index 0 最新)**:
```
hit1800 = (draw 至少一碼落 col1 ) && (…col2) && (…col3)     // 三柱皆命中才算 hit
hit9000 = 四柱皆命中
hits1800 = 全期 hit1800 次數;hits9000 同理
gap1800 = 從最新往回、連續「未命中」的期數(碰到第一個命中就停;found 旗標)
gap9000 同理
```
**機率(基礎機率為寫死常數)**:
```
p_base_1800 = 0.5536   // 顯示 55.4%(頁面靜態文字寫 55.3%,程式以 0.5536 計)
p_base_9000 = 0.2735   // 顯示 27.4%(頁面靜態文字寫 27.3%)
p_hist_1800 = hits1800 / 總期數 * 100      // 歷史實際命中率
p_hist_9000 = hits9000 / 總期數 * 100
avgCycle1800 = hits1800>0 ? 總期數/hits1800 : 1/p_base_1800   // 平均幾期開一次
avgCycle9000 = hits9000>0 ? 總期數/hits9000 : 1/p_base_9000
```
**「AI 爆發率」(均值回歸加成,boost 係數 = 0.15)**:
```
boost1800  = (gap1800 / avgCycle1800) * 0.15
finalProb1800 = min(p_base_1800 * (1 + boost1800), 0.99) * 100   // 上限 99%
boost9000  = (gap9000 / avgCycle9000) * 0.15
finalProb9000 = min(p_base_9000 * (1 + boost9000), 0.99) * 100
```
**進場燈號(門檻)**:
```
gap > avgCycle                     → 🚨紅燈「漏期達標」強烈建議進場(紅底)
gap === floor(avgCycle) && gap>0   → ⚠️黃燈「接近週期」可準備佈局(黃底)
否則                                → ✅綠燈「剛開出不久…建議繼續觀望」(綠底)
```
- **輸出欄位**(每個立柱一組 4 格):目前連漏「N期」、平均「X.X期」、理論機率(`p_base*100`,1 位小數)、歷史機率(`p_hist`,1 位小數)、AI 爆發率(`finalProb`,1 位小數)+ 燈號文字方塊。

---

### 3.6 3D 量子搖號機(PhysicsMachine / generate5Numbers)
- 39 顆球在圓形容器內做重力 + 碰撞牆反彈的 2D 物理動畫(重力 `vy+=0.35`,攪拌時隨機加速、限速 15,阻尼 0.98,牆反彈係數 0.8/0.9)。
- **抽號 generate5Numbers**:`Math.random`*39+1,湊 5 個不重複,升冪排序。**純隨機,無分析用途,可在 Python 版忽略或做成單純亂數推薦。**

---

## ④ 倍投 / 追號規劃邏輯(Modal 四分頁)

> 全部是「設定每期/每階目標淨利,反推需要下多少注」的追號本金表。金額四捨五入用 `Math.round`,車數進位用 `Math.ceil(x*100)/100`(無條件進位到小數 2 位)。

### 通用預設常數
```
天天樂每全車成本 costPerUnit  = 2755 元
天天樂每全車彩金 prizePerUnit = 21200 元
```

### 4.1 單碼目標倍投(calculateSingleTargetPlan)
輸入:firstUnits(第1期車數,預設 0.10)、targetDailyProfit(每日目標淨利增量,預設 1844)、days(預設 15)、costPerUnit(2755)、prizePerUnit(21200)。
```
netWinPerFullUnit = prizePerUnit - costPerUnit          // 一車淨利 = 21200-2755 = 18445
for day = 1..days:
  targetCumProfit = targetDailyProfit * day             // 目標累計淨利
  units = (day===1) ? firstUnits
                    : ceil2((cumCost + targetCumProfit) / netWinPerFullUnit)
  currentCost = round(units * costPerUnit); cumCost += currentCost
  currentPrize = round(units * prizePerUnit)
  finalNet = currentPrize - cumCost
```
輸出欄:天數 / 目標累計淨利 / 下注車數(2 位) / 當期成本 / 累計總投入 / 中獎彩金 / 結算淨利。摘要:「[N 天單碼總備援本金建議:cumCost 元]」。

### 4.2 4碼目標倍投(calculateFourTargetPlan)
輸入:firstUnits(每碼車數 0.10)、targetDailyProfit(1844)、days(預設 6)、單碼成本(2755)、單碼彩金(21200)。
```
netWinIfHitOne = prizePerUnit - 4*costPerUnit           // 中1碼淨利 = 21200 - 4*2755 = 10180
for day=1..days:
  targetCumProfit = targetDailyProfit * day
  units = (day===1)? firstUnits : ceil2((cumCost+targetCumProfit)/netWinIfHitOne)
  currentRoundCost = round(units * 4 * costPerUnit); cumCost += currentRoundCost
  prizeIfHitOne = round(units * prizePerUnit); netIfHitOne = prizeIfHitOne - cumCost
  prizeIfHitTwo = round(units * prizePerUnit * 2); netIfHitTwo = prizeIfHitTwo - cumCost
```
輸出欄:期數 / 目標累計淨利 / 每碼車數 / 當期總成本(4碼) / 累計總投入 / 中1碼彩金 / 保底淨利(中1碼) / 若中2碼(雙停暴利)。

### 4.3 階梯均注追蹤表(3.3 前的 tier 系列)
兩子模式,可用 `cfg-tier-cars`(起始車數,0.10)、`cfg-tier-total-days`(15)動態重算。

**單碼階梯 buildDynamicSingleTier(3 期一階)**:
```
costPerCar=2755, prizePerCar=21200, tierStep=3, totalTiers=ceil(days/3)
每階 cars:
  t===0 → startCars
  否則  → cars = ceil2((cumCost + 1000) / (prizePerCar - 3*costPerCar))   // 常數 +1000;分母 = 21200 - 3*2755 = 12935
          若 cars <= 上一階 cars → cars = 上一階 cars + 0.05    // 保證遞增
每階內 3 天同 cars:
  curCost=round(cars*costPerCar); cumCost+=; prize=round(cars*prizePerCar); profit=prize-cumCost
```

**4碼階梯 buildDynamicFourTier(2 期一階,「保證賺錢」)**:
```
singleCost=2755, roundFourCost=4*2755=11020, prizePerCar=21200, tierStep=2, totalTiers=ceil(days/2)
每階 cars:
  t===0 → startCars
  否則  → cars = ceil2((cumCost + 1200) / (prizePerCar - roundFourCost))   // 常數 +1200;分母 = 21200-11020 = 10180
          若 cars <= 上一階 cars → cars = ceil2(上一階 cars * 2.2)          // 跳倍係數 2.2
每階內 2 天:
  curCost=round(cars*roundFourCost); cumCost+=; prize=round(cars*prizePerCar); profit=prize-cumCost
  若 profit < 0:                       // 修正保證正淨利
    neededCars = ceil2((cumCost - curCost + 500) / (prizePerCar - roundFourCost))   // 常數 +500
    cars=neededCars; 重算 curCost、cumCost、prize、profit
```

**階梯名稱** getChineseTierName(idx):第一~二十階(超過用 idx+1)。

**追蹤器互動(recordTierResult)**:
```
過關(won)  → alert 淨利,currentTierIdx = 0(回第一階重啟循環)
沒過(!won) → currentTierIdx < 最後 ? ++ : (alert 已達最後一期、重置為 0)
```
表格輸出欄:天數/階梯/下注車數/當期成本/累計總成本/中獎彩金/結算淨利(profit<0 顯示紅色);當前列高亮 active-row。

### 4.4 1800/9000碰立柱倍投(calculateMatrixPlan)★
下拉選模式;輸入 firstBet(第1期下注元,預設 1)、targetProfit(每期保底淨利,預設 500)、days(預設 6)。
> 注意:表單裡的「每1元實付成本/彩金」input 是 readonly 顯示用,**實際計算用下列寫死常數**(不讀 input)。
```
模式 1800:  netCostPerUnit=1134, singlePrizePerUnit=570, baseHits=3
            basePrizePerUnit = 570*3 = 1710      (中 3 碰彩金/單位)
            netWinPerUnit    = 1710 - 1134 = 576
模式 9000:  netCostPerUnit=4545, singlePrizePerUnit=8000, baseHits=2
            basePrizePerUnit = 8000*2 = 16000    (過關必中 2 碰)
            netWinPerUnit    = 16000 - 4545 = 11455

for d=1..days:
  bet = (d===1)? firstBet : max(1, ceil((cumCost + targetProfit) / netWinPerUnit))   // bet 為整數元
  currentCost = bet * netCostPerUnit; cumCost += currentCost
  basePrize = bet * basePrizePerUnit; baseProfit = basePrize - cumCost
  // 僅 1800 額外算 4 碰暴利:
  bonusPrize = bet * (570 * 4) = bet*2280; bonusProfit = bonusPrize - cumCost
```
輸出欄(1800):期數/下注金額/當期實繳成本/累計總實繳/中3碰彩金/中3碰淨利(保底)/中4碰彩金/中4碰淨利(大爆發)。
輸出欄(9000):期數/下注金額/當期實繳/累計實繳/中2碰滿貫彩金(固定)/結算實得淨利(保證有贏)。

> updateMatrixFixedSpec 只改 readonly 顯示:1800→cost 1134/prize 570;9000→cost 4545/prize 8000。

---

## ⑤ 推薦 / 裁決邏輯彙整(門檻總表)

| 判斷 | 條件 | 結果 |
|------|------|------|
| 單期霸主 | draw 滿 5,比 aiHits vs myHits | AI 勝 / 我 勝 / 平手 / 僅AI / 僅我 / 無人預測 |
| 勝率霸主 | 比 aiAvg vs myAvg | AI 領先 / 人類領先 / 平分秋色 / 等待開獎 |
| reboundScore | lastSeenAgo∈[2,5]→95;∈{0,1}→80;else 40 | 逐號評分回歸因子 |
| 熱門 top8 | count↓,tie lastSeenAgo↑ | 熱門徽章 |
| 冷門 top8 | lastSeenAgo↓,tie count↑ | 冷門徽章 |
| 立柱進場燈 | gap>avgCycle→紅;gap==⌊avgCycle⌋且>0→黃;else 綠 | 進場/佈局/觀望 |
| AI 爆發率上限 | min(p_base*(1+0.15*gap/avgCycle), 0.99) | 顯示百分比 |

> **沒有**真正的 Z-score、貝式、馬可夫、均線、單雙/大小/區段比、連號分析等 —— 那些是術語包裝但本檔未實作。本檔實際只有:頻率/近期/回歸三因子評分、gap 連漏統計、寫死基礎機率 + 線性 boost、隨機抽號、與倍投試算。重寫時勿臆造未實作的指標。

---

## ⑥ 顯示欄位 / 區塊對照表

| 區塊 | DOM/函式 | 演算法 | 與 539 |
|------|----------|--------|--------|
| 對決 stats-board | renderAll | 3.2 | 天天樂特有(AI vs 我 對決,可獨立) |
| 🔥熱門/❄️冷門徽章 | analyzeHotColdNumbers → hot/cold-numbers | 3.3 | **可共用**(常數 window=15、權重 0.35/0.35/0.30、rebound 門檻皆與 539 同) |
| 🎯三大模式推薦 6 卡 | renderRecommendations | 3.4 | **可共用**(抽號邏輯與號池切法相同) |
| 立柱風控矩陣 1800/9000 | analyzeComboPatterns | 3.5 | **柱位定義為 Fantasy5 專屬**,但 gap/boost/燈號公式與 539 立柱同結構;p_base 常數(0.5536 / 0.2735)須分開 |
| 🎰 3D 搖號機 | PhysicsMachine/startRoll | 3.6 | 純動畫,可共用或忽略 |
| 單碼目標倍投 | calculateSingleTargetPlan | 4.1 | 結構共用,常數 2755/21200 為天天樂 |
| 4碼目標倍投 | calculateFourTargetPlan | 4.2 | 同上 |
| 階梯均注表 | buildDynamicSingleTier / FourTier | 4.3 | 結構共用,常數(+1000/+1200/+500、×2.2、tierStep 3/2)照抄 |
| 1800/9000碰倍投 | calculateMatrixPlan | 4.4 | 立柱倍投為天天樂特有,常數 1134/570/4545/8000 分開 |
| 歷史戰績表 | renderAll(displayLimit=10,載入更多 +30) | 3.1 顯示 | 天天樂特有 |
| 多期整頁貼上匯入 | extractMultiDrawsFromText/parseAndImportMultiDraws | 3.0 | 可共用解析器 |

### 顯示格式慣例
- 球號一律 `padStart(2,'0')`(補零 2 位)。
- 機率/百分比:1 位小數;場均命中:2 位小數;車數:2 位小數;金額:`toLocaleString()` 千分位。
- 顏色語意:紅=示警/命中/累計投入,綠=淨利/我方,藍=AI/冷號,紫=9000碰/暴利,金=車數/下注。
