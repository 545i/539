# 雅宏策略「🎯 單碼必贏」規格書（單碼 01~39 深度透視）

> 來源檔：`/tmp/yh_01-39.html`（802 行，單檔靜態 HTML）
> 頁面標題：「⚡ 18 宗師東西方合璧 | 終極量化操盤系統(雙軌獨立版)」
> 本規格只萃取**演算法**;Firebase 設定、CSS、DOM 樣板、動畫一律忽略。
> 目的:完整到可直接用 Python 重寫,所有常數、門檻、權重皆逐一列出。

---

## ① 功能總覽

這頁提供**單一號碼(01~39)的量化分析**,包裝成「18 宗師東西方合璧」的操盤術語。核心概念:

- 對某一顆球 `target`,掃過整段歷史開獎資料,算出 18 個「宗師」指標 + 5 個機率摘要 + 1 個最終綜合分 `finalScore`。
- 兩個獨立資料軌(**雙軌獨立**):
  - `539-9000` = 今彩 539
  - `tt-9000` = 天天樂(Fantasy5)
  - 兩軌用**完全相同**的演算法,只是餵不同資料;UI 元素以 suffix `539` / `tt` 區分。
- 三種操作:
  1. **單碼深度透視**(`executeSingleBallScan`):輸入一顆號碼 → 顯示該號碼的 5 摘要 + 18 宗師矩陣 + 綜合分級(S/A/B/C)+ 遺漏走勢微型圖。
  2. **全盤 39 碼分級**(`executeSuperClassification`):對 1~39 全算一次,依 `finalScore` 排名分成 S/A/B/C 四級名冊,並列出最近 8 期開獎。
  3. **白皮書說明**(`toggleDoc`):純文字說明,不影響計算。
- **分級的本質是排名制**(不是分數門檻):39 顆球依 `finalScore` 由高到低排序後,用名次(index)切 S/A/B/C。

輸入門檻:資料須 `>= 100` 期,否則 `alert("⚠️ 該資料庫數據不足 100 期!")`;號碼須 1~39。

---

## ② 資料模型

資料來自 Firestore collection `matrix_systems`,即時 `onSnapshot` 同步(重寫時改成讀本機/DB 即可)。程式內結構:

```js
spaceData = {
  '539-9000': [ item, item, ... ],
  'tt-9000':  [ item, item, ... ]
}
```

每筆 `item`(一期開獎):

```js
{
  id:    <字串,唯一 id,用來 upsert/去重>,
  space: '539-9000' | 'tt-9000',   // 屬於哪一軌
  date:  <可被 new Date() 解析的日期字串>,
  draw:  [n1, n2, n3, n4, n5]      // 該期開出的 5 個號碼 (整數 1~39)
}
```

**排序約定(重要)**:進入計算前一律

```js
data = [...rawData].sort((a, b) => new Date(b.date) - new Date(a.date));
// → data[0] 是「最新一期」,data 末端是最舊
```

計算函數內部又用 `reversed = [...data].reverse()`(→ 由舊到新,時間順序)來跑回測。
所以:

- `data[0..k]`(slice 前段)= **最近 k 期**。
- `reversed` forEach 的**最後一筆 = 最新一期**(遺漏累計到最後 = 當前遺漏 `currentMiss`)。

「命中」定義:`item.draw.includes(target)`,即該期 5 個號碼含 target。

賠率/損益模型常數(全域固定,539 與天天樂共用):

| 常數 | 值 | 用途 |
|------|----|------|
| 命中獲利 | `+330` | 資金曲線、EV、RSI、Sharpe 的「賺」 |
| 未中成本 | `-100` | 同上的「賠」(單注成本 100) |
| 賠率 b | `3.3`(`b_odds`) | 凱利公式的淨賠率(330/100) |

---

## ③ 指標清單(每個:名稱 → 算式 → 常數 → 輸出格式)

### 3.0 前置回測(一次掃過 `reversed`,由舊到新)

```js
let missingHistory = [];   // 每次「命中」時,記錄命中前累積的遺漏期數(完成的 gap 序列)
let tempMiss = 0;          // 目前累積遺漏
let hits=0, hits5=0, hits10=0, hits30=0;
let eqCurve = [0];         // 資金曲線,起始 0
let peak = 0, maxDD = 0;   // 資金曲線峰值與最大回撤
let hotStateEncounters = 0, hotStateHits = 0;  // 過熱狀態統計
let window5 = [];          // 最近 5 期是否命中的滑動視窗 (布林)

reversed.forEach((item, i) => {
    let isHit = item.draw.includes(target);

    // ---- 過熱狀態偵測(在 push 當期之前,用「前 5 期」判斷)----
    if (window5.length === 5) {
        let recentHits = window5.filter(x => x).length;   // 前 5 期命中數
        if (recentHits >= 2) {          // 前 5 期已命中 >=2 → 處於「過熱狀態」
            hotStateEncounters++;
            if (isHit) hotStateHits++;  // 過熱後當期又命中 → 延續
        }
    }
    window5.push(isHit);
    if (window5.length > 5) window5.shift();   // 維持長度 5

    // ---- 遺漏序列 + 資金曲線 ----
    if (isHit) {
        missingHistory.push(tempMiss);   // 收錄這一段 gap
        tempMiss = 0;
        let newEq = eqCurve[eqCurve.length-1] + 330;
        eqCurve.push(newEq);
        if (newEq > peak) peak = newEq;
    } else {
        tempMiss++;
        let newEq = eqCurve[eqCurve.length-1] - 100;
        eqCurve.push(newEq);
    }
    let dd = peak - eqCurve[eqCurve.length-1];  // 當前回撤
    if (dd > maxDD) maxDD = dd;
});

let currentMiss = tempMiss;   // 掃到最新一期後仍未歸零的尾段 = 當前遺漏
```

命中次數統計(改用 `data`,newest-first,取近端):

```js
data.forEach((item, idx) => {
    let isHit = item.draw.includes(target);
    if (isHit) hits++;
    if (idx < 5  && isHit) hits5++;
    if (idx < 10 && isHit) hits10++;
    if (idx < 30 && isHit) hits30++;
});
```

衍生統計量:

```js
let probAll = hits / N;             // 歷史總命中率
let prob10  = hits10 / 10;          // 近 10 期命中率(固定除以 10)
let prob30  = hits30 / 30;          // 近 30 期命中率(固定除以 30)
let accel   = (prob10 - prob30) * 100;   // 「動能加速度」= BIAS 乖離

let hotStateProb = hotStateEncounters > 0 ? (hotStateHits / hotStateEncounters) : probAll;
let avgMiss = missingHistory.length > 0
    ? missingHistory.reduce((a,b)=>a+b,0)/missingHistory.length
    : (1/probAll - 1);              // 無 gap 時用理論平均遺漏
let maxMiss = Math.max(...(missingHistory.length ? missingHistory : [0]), currentMiss, 1);
let variance = missingHistory.reduce((acc,val)=>acc+Math.pow(val-avgMiss,2),0) / (missingHistory.length || 1);
let stdDev   = Math.sqrt(variance || 1);
```

> 注意 Python 重寫的邊界:`prob10`、`prob30` 固定除以 10 / 30(即使資料不足也一樣;但本頁已保證 N>=100)。`variance`/`stdDev` 的 `|| 1` 是防 0。

---

### 🏛️ 西方(華爾街)8 大宗師

#### ① 數學家 — 拉普拉斯平滑均值 `m1_Laplace`
```js
m1_Laplace = (hits + 1) / (N + 2);
```
- 常數:+1 / +2(Laplace add-one)。
- 顯示:`(m1_Laplace*100).toFixed(1) + '%'`。
- 綠燈條件:`m1_Laplace > probAll`。

#### ② 資金家 — 凱利公式 `m2_Kelly`
```js
b_odds = 3.3;
m2_Kelly = prob30 - ((1 - prob30) / b_odds);
```
- 用 `prob30` 當勝率 p。
- 顯示:`f* ` + `(m2_Kelly>0 ? m2_Kelly*100 : 0).toFixed(1) + '%'`(負數顯示 0.0%)。
- 綠燈條件:`m2_Kelly > 0`。

#### ③ 贏家 — 馬可夫轉移狀態 `m3_Markov`
「在目前遺漏長度 `currentMiss` 的狀態下,下一期命中的條件機率」,含平滑:
```js
let mHit=0, mMiss=0, trk=0;
reversed.forEach((item, idx) => {
    let isHit = item.draw.includes(target);
    if (idx > 0 && trk === currentMiss) {   // 歷史上「剛好遺漏到 currentMiss」的下一步
        if (isHit) mHit++; else mMiss++;
    }
    if (isHit) trk = 0; else trk++;
});
m3_Markov = (mHit + probAll*5) / (mHit + mMiss + 5);
```
- 平滑常數:分子加 `probAll*5`,分母加 `5`。
- 顯示:`(m3_Markov*100).toFixed(1) + '%'`。
- 綠燈條件:`m3_Markov > probAll`。

#### ④ 銀行家 — Z-Score 乖離率 `m4_ZScore`
```js
m4_ZScore = stdDev > 0 ? (currentMiss - avgMiss) / stdDev : 0;
```
- 顯示:`Z = ` + `m4_ZScore.toFixed(2)`。
- 綠燈條件:`m4_ZScore > 0`(欠收 → 有利回歸)。

#### ⑤ 精算家 — 最大回撤 Drawdown `m5_DD`
```js
m5_DD = maxDD;   // 來自前置回測的資金曲線 (單位:元)
```
- 顯示:`DD $` + `Math.round(m5_DD)`。
- 綠燈條件:`m5_DD <= 6000`(注意:此處門檻 6000,與計分用的 4000/8000 不同)。

#### ⑥ 莊家 — 單注期望值 EV `m6_EV`
```js
m6_EV = (prob30 * 330) - ((1 - prob30) * 100);
```
- 顯示:`EV ` + 正號 + `Math.round(m6_EV)`。
- 綠燈條件:`m6_EV > 0`。

#### ⑦ 操盤手 — RSI 相對強弱 `m7_RSI`(視窗 14 期)
```js
let gains=0, losses=0;
let recent14 = data.slice(0, 14);        // 最近 14 期
recent14.forEach(item => {
    if (item.draw.includes(target)) gains += 330;
    else losses += 100;
});
let rs = losses === 0 ? 100 : (gains/14) / (losses/14);
m7_RSI = losses === 0 ? 100 : 100 - (100 / (1 + rs));
```
- 常數:視窗 14、gain 330、loss 100。
- 顯示:`m7_RSI.toFixed(1)`。
- 綠燈條件:`40 <= m7_RSI <= 75`(區間,非單邊)。

#### ⑧ 分析師 — Sharpe 夏普比率 `m8_Sharpe`(視窗 30 期)
```js
let recent30 = data.slice(0, 30);
let rets = recent30.map(item => item.draw.includes(target) ? 330 : -100);
let avgRet = rets.reduce((a,b)=>a+b,0) / (rets.length||1);
let varRet = rets.reduce((acc,val)=>acc+Math.pow(val-avgRet,2),0) / (rets.length||1);
let stdRet = Math.sqrt(varRet) || 1;
m8_Sharpe = avgRet / stdRet;
```
- 顯示:`m8_Sharpe.toFixed(2)`。
- 綠燈條件:`m8_Sharpe > 0`。

---

### ⛩️ 東方 10 大宗師(全部輸出「分數」,多為離散跳值)

#### ⑨ 蒙地卡羅動能(均線交叉)`m9`
```js
m9 = prob10 > probAll ? 85 : 45;
```
- 顯示:`m9.toFixed(0) 分`。綠燈:`m9 >= 60`。

#### ⑩ 傅立葉頻譜(規律共振)`m10`
```js
m10 = 40;
if (missingHistory.length >= 2) {
    if (currentMiss === missingHistory[missingHistory.length-1]) m10 = 95;       // 與上一段 gap 相同
    else if (currentMiss === missingHistory[missingHistory.length-2]) m10 = 80;  // 與上上段 gap 相同
}
```
- 常數:40 / 80 / 95。綠燈:`m10 >= 60`。

#### ⑪ 貝氏條件機率(生存者偏差)`m11`
```js
let totalOverMiss = missingHistory.filter(x => x >= currentMiss).length;
m11 = totalOverMiss > 0 ? (1 / (totalOverMiss + 1)) * 100 : 99;
```
- 顯示:`m11.toFixed(0) 分`。綠燈:`m11 >= 60`。

#### ⑫ 混沌極限理論 `m12`
```js
m12 = (m4_ZScore > 2.0 || m4_ZScore < -1.5) ? 90 : 40;
```
- 常數門檻:Z > 2.0 或 Z < -1.5(注意白皮書寫 |Z|>1.5,實作是不對稱的 2.0 / -1.5)。
- 綠燈:`m12 >= 60`。

#### ⑬ 卜瓦松絕境反轉 `m13`
```js
m13 = currentMiss >= (maxMiss * 0.8) ? 95 : 30;
```
- 常數:0.8、95/30。綠燈:`m13 >= 60`。

#### ⑭ 費波那契數列(黃金分割)`m14`
```js
m14 = [1,2,3,5,8,13,21,34].includes(currentMiss) ? 85 : 35;
```
- 常數集合固定。綠燈:`m14 >= 60`。

#### ⑮ 高斯回歸偏態 `m15`
```js
m15 = (prob10 - prob30) > 0 ? 75 : 45;
```
- 綠燈:`m15 >= 60`。

#### ⑯ 馬可夫歷史動能(過熱熔斷)`m16`
```js
m16 = 55;   // 預設
if (hits5 >= 2) {
    if (hotStateProb > probAll * 1.2)      m16 = 95;   // 過熱後延續力強 → 加分
    else if (hotStateProb < probAll * 0.8) m16 = 15;   // 過熱後續航差 → 危險
    else                                    m16 = 60;
} else if (hits10 === 0 && currentMiss > 3) {
    m16 = 85;   // 近 10 期完全沒開 + 遺漏 >3 → 醞釀反彈
}
```
- 常數:1.2 / 0.8 倍門檻、55/95/15/60/85、currentMiss>3。
- 綠燈:`m16 >= 50`(唯一用 50 當門檻的宗師)。

#### ⑰ 深度神經擬合(複合指標)`m17`
```js
m17 = (m1_Laplace*0.3 + m3_Markov*0.4 + prob30*0.3) * 100;
```
- 權重:0.3 / 0.4 / 0.3。綠燈:`m17 >= 60`。

#### ⑱ 一目均衡表(Ichimoku 突破)`m18`
```js
let tenkan = 40, kijun = 40;   // 預設(注意:預設值 40 是分數尺度,不是遺漏尺度)
if (missingHistory.length >= 9) {
    let last9 = missingHistory.slice(-9);
    tenkan = (Math.max(...last9) + Math.min(...last9)) / 2;   // 轉換線
}
if (missingHistory.length >= 26) {
    let last26 = missingHistory.slice(-26);
    kijun = (Math.max(...last26) + Math.min(...last26)) / 2;  // 基準線
}
m18 = 40;
if (currentMiss > kijun)        m18 = 90;   // 升破基準線 → 佈局
else if (currentMiss < tenkan)  m18 = 30;
else                            m18 = 60;
```
- 綠燈:`m18 >= 60`。
- ⚠️ 重寫時保留原邏輯上的怪癖:`tenkan`/`kijun` 若資料不足會停在 40,而 `currentMiss` 若 <40 幾乎都落到 `else`(60)或 `<tenkan`(30);此為原程式行為,照抄。

---

### 3.9 其他摘要量(顯示用,非宗師)

生存 PR 值:
```js
let shorterCount = missingHistory.filter(m => m <= currentMiss).length;
let survivalPR = missingHistory.length > 0 ? (shorterCount / missingHistory.length) * 100 : 50;
```
顯示:`survivalPR.toFixed(1) + '%'`。

---

## ④ 選號 / 建議邏輯

### 4.1 最終綜合分 `finalScore`

先算出各計分項(把連續指標離散化成點數):

```js
let kellyClamped = Math.max(0, Math.min(m2_Kelly * 10, 1)) * 10;
// = clamp(m2_Kelly*10, 0..1) * 10  → 值域 0~10

let zScorePts = m4_ZScore > 1.5 ? 6 : (m4_ZScore > 0.5 ? 4 : (m4_ZScore > -0.5 ? 2 : 0));
let ddPts     = m5_DD <= 4000 ? 5 : (m5_DD <= 8000 ? 3 : 0);   // 注意:計分門檻 4000/8000
let evPts     = m6_EV > 20 ? 5 : (m6_EV > 0 ? 3 : 0);
let rsiPts    = m7_RSI >= 60 ? 5 : (m7_RSI >= 40 ? 3 : 0);
let sharpePts = m8_Sharpe > 0.5 ? 5 : (m8_Sharpe > 0 ? 3 : 0);
```

加權總和:

```js
let finalScore =
    (m1_Laplace * 100 * 0.08) + kellyClamped + (m3_Markov * 100 * 0.10) +
    zScorePts + ddPts + evPts + rsiPts + sharpePts +
    (m9  * 0.04) + (m10 * 0.06) + (m11 * 0.04) + (m12 * 0.04) +
    (m13 * 0.06) + (m14 * 0.04) + (m15 * 0.04) + (m16 * 0.04) +
    (m17 * 0.05) + (m18 * 0.04);
```

權重總表(重寫務必逐字對照):

| 項目 | 進入分數的形式 | 權重/點數 |
|------|----------------|-----------|
| m1 數學家 | `m1_Laplace*100` | ×0.08 |
| m2 資金家 | `kellyClamped`(0~10) | 直接加(等效權重 1) |
| m3 贏家 | `m3_Markov*100` | ×0.10 |
| m4 銀行家 | `zScorePts`(0/2/4/6) | 直接加 |
| m5 精算家 | `ddPts`(0/3/5) | 直接加 |
| m6 莊家 | `evPts`(0/3/5) | 直接加 |
| m7 操盤手 | `rsiPts`(0/3/5) | 直接加 |
| m8 分析師 | `sharpePts`(0/3/5) | 直接加 |
| m9 蒙地卡羅 | `m9`(45/85) | ×0.04 |
| m10 傅立葉 | `m10`(40/80/95) | ×0.06 |
| m11 貝氏 | `m11`(0~99) | ×0.04 |
| m12 混沌 | `m12`(40/90) | ×0.04 |
| m13 卜瓦松 | `m13`(30/95) | ×0.06 |
| m14 費波那契 | `m14`(35/85) | ×0.04 |
| m15 高斯偏態 | `m15`(45/75) | ×0.04 |
| m16 過熱熔斷 | `m16`(15/55/60/85/95) | ×0.04 |
| m17 深度擬合 | `m17`(0~100) | ×0.05 |
| m18 一目均衡 | `m18`(30/60/90) | ×0.04 |

### 4.2 過熱熔斷防禦(在 finalScore 之後套用)

```js
if (hits5 >= 3) {
    finalScore = Math.min(finalScore, 35);   // 近 5 期開 >=3 次 → 硬壓上限 35
} else if (hits5 === 2 && currentMiss === 0) {
    finalScore = finalScore - 15;            // 近 5 期開 2 次且剛開 → 扣 15
}
```

### 4.3 分級(排名制,非分數門檻)

對 1~39 全部算 `finalScore`,由高到低排序,取 target 的名次 `rank`(0-based):

| 名次 rank(0-based) | 級別 | 標語 | 建議 |
|--------------------|------|------|------|
| `rank < 3`(前 3 名) | 🔥 S 級 | 絕對主將 | 極限爆發區間 |
| `3 <= rank < 9`(第 4~9 名) | 🟢 A 級 | 優質副牌 | 勝率與動能具水準 |
| `9 <= rank < 25`(第 10~25 名) | ⚪ B 級 | 中性觀望 | 觀望或輕倉 |
| `rank >= 25`(第 26 名以後) | 🔴 C 級 | 強制冷卻 | 動能衰退,嚴禁買進 |

- **單碼查詢**:顯示 target 的級別 + 「(全盤第 rank+1 名)」。
- **全盤分級**:同樣切 index 0-2 / 3-8 / 9-24 / 25+ 成 S/A/B/C 四個名冊,每顆球顯示 `分數.toFixed(1)分`,可點擊回填該號並重跑單碼查詢。

> 「必贏 / 放行」只是 UI 話術;實際輸出是分級與名次,沒有下注金額建議。

---

## ⑤ 顯示欄位對照表

### 5.1 頂部 5 摘要卡(`sb-prob-*`)

| 標籤 | 來源 | 格式 | 單位 |
|------|------|------|------|
| 歷史總均線 | `probAll*100` | `.toFixed(1)` + `%` | % |
| 生存 PR 值 | `survivalPR` | `.toFixed(1)` + `%` | % |
| BIAS 乖離 | `accel` | 正數補 `+`,`.toFixed(1)` + `%` | % |
| 最大遺漏 | `maxMiss` | 整數 + ` 期` | 期 |
| 近 30 期 | `prob30*100` | `.toFixed(1)` + `%` | % |

### 5.2 18 宗師矩陣卡(`sb-giants-*`)

| # | 標題(UI) | 顯示值格式 | 綠燈(highlight)條件 | 否則紅燈(danger) |
|---|-----------|-----------|----------------------|-------------------|
| ① | 數學家(均值) | `(m1*100).toFixed(1)%` | `m1_Laplace > probAll` | 反之 |
| ② | 資金家(凱利) | `f* (m2>0?m2*100:0).toFixed(1)%` | `m2_Kelly > 0` | 反之 |
| ③ | 贏家(馬可夫) | `(m3*100).toFixed(1)%` | `m3_Markov > probAll` | 反之 |
| ④ | 銀行家(偏離) | `Z = m4.toFixed(2)` | `m4_ZScore > 0` | 反之 |
| ⑤ | 精算家(壓力) | `DD $round(m5)` | `m5_DD <= 6000` | 反之 |
| ⑥ | 莊家(期望值) | `EV ±round(m6)` | `m6_EV > 0` | 反之 |
| ⑦ | 操盤手(RSI) | `m7.toFixed(1)` | `40 <= m7_RSI <= 75` | 反之 |
| ⑧ | 分析師(夏普) | `m8.toFixed(2)` | `m8_Sharpe > 0` | 反之 |
| ⑨ | 蒙地卡羅動能 | `m9.toFixed(0) 分` | `m9 >= 60` | 反之 |
| ⑩ | 傅立葉共振 | `m10.toFixed(0) 分` | `m10 >= 60` | 反之 |
| ⑪ | 貝氏條件機率 | `m11.toFixed(0) 分` | `m11 >= 60` | 反之 |
| ⑫ | 混沌極限理論 | `m12.toFixed(0) 分` | `m12 >= 60` | 反之 |
| ⑬ | 卜瓦松反轉 | `m13.toFixed(0) 分` | `m13 >= 60` | 反之 |
| ⑭ | 費波那契數列 | `m14.toFixed(0) 分` | `m14 >= 60` | 反之 |
| ⑮ | 高斯回歸偏態 | `m15.toFixed(0) 分` | `m15 >= 60` | 反之 |
| ⑯ | 馬可夫歷史狀態 | `m16.toFixed(0) 分` | `m16 >= 50` | 反之 |
| ⑰ | 深度神經擬合 | `m17.toFixed(0) 分` | `m17 >= 60` | 反之 |
| ⑱ | 一目均衡突破 | `m18.toFixed(0) 分` | `m18 >= 60` | 反之 |

### 5.3 綜合評比橫幅 & 遺漏微型走勢圖

- 評比橫幅:依 §4.3 顯示 S/A/B/C 級 + 名次。
- 微型走勢(Sparkline):
  ```js
  let recentMisses = missingHistory.slice(-10).reverse();          // 最近 10 段完成的遺漏,新→舊
  let maxDisplayMiss = Math.max(...recentMisses, currentMiss, 10); // 縮放基準(至少 10)
  // 每根 bar 高度%:Math.max((m / maxDisplayMiss) * 100, 5)
  // 最後再補一根「當前遺漏」bar(currentMiss),標記為當前色
  ```
- 「歷史最大遺漏: {maxMiss} 期」文字。

### 5.4 全盤名冊 & 最近 8 期

- 名冊:S/A/B/C 四張卡,每顆球顯示 `號碼(補零2位)` + `分數.toFixed(1)分`,可點擊回填重查。
- 最近 8 期:`data.slice(0, 8)`,每期顯示 `date` + 5 顆補零號碼球(539 金色 / 天天樂紫色,純樣式)。

---

## ⑥ 重寫時的地雷提醒(常數不一致,務必照抄)

1. **Drawdown 有兩套門檻**:顯示綠燈用 `<=6000`;`finalScore` 計分用 `<=4000 →5, <=8000 →3`。
2. **混沌 m12** 白皮書寫 `|Z|>1.5`,實作是 `Z>2.0 || Z<-1.5`(不對稱)。以實作為準。
3. **m16 綠燈門檻是 50**,其餘東方宗師都是 60。
4. **一目均衡 m18** 的 tenkan/kijun 預設 40 是分數尺度混入遺漏尺度的原始 bug,照抄以維持一致行為。
5. `prob10`、`prob30` 固定除以 10 / 30(硬編碼),不是除以實際取到的期數。
6. `kellyClamped = clamp(m2_Kelly*10, 0, 1) * 10`,值域 0~10。
7. 分級是**名次制**,不是分數門檻;必須先算完 39 顆再排序。
