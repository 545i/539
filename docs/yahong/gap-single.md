# 落差稽核報告 —「🎯 單碼必贏」(18 宗師 + finalScore + 名次分級)

> 對照四方:原始 HTML `/tmp/yh_01-39.html`(802 行)、規格書 `docs/yahong/spec-single.md`、
> 後端 `core/yahong/single.py`(+ `backend/routers/yahong.py`、`docs/yahong/API.md`)、
> 前端 `frontend/src/components/views/yahong/SinglePanel.tsx`(+ `format.tsx`、`api/client.ts`)。
> 稽核方式:18 宗師 / finalScore / 分級 / 5 摘要 逐行比對原始 JS。**只讀不改。**

## 結論摘要
- **演算法核心(後端)= 幾乎逐字忠實移植**:18 宗師每項算式、常數、綠燈門檻、finalScore 18 項權重、
  過熱熔斷、名次分級(排名制)、5 摘要,全部逐行核對通過(見下 §OK)。規格書 §6 列的 6 顆地雷全部照抄正確。
- **落差集中在「前端漏渲染原站既有區塊」與「資料量上限」**:共 **7 項落差**(2 MISSING 前端功能、
  1 MISSING 白皮書、1 BUG 資料截斷、1 極低機率 BUG、2 COSMETIC)。

### 最重要 3 個
1. **[BUG] `MAX_DRAWS=1500` 截斷天天樂全歷史** → 天天樂(fantasy5 現有 3088 期)只餵最近 1500 期,
   probAll / maxMiss / maxDD / 馬可夫 / 排名全部與原站(全歷史)不同。539(856 期)不受影響。**嚴重度:高。**
2. **[MISSING] 遺漏微型走勢圖(sparkline)前端未渲染** → 後端已回 `sparkline[]`,前端整段沒畫,
   原站的「近 10 次遺漏走勢 + 當前遺漏 + 歷史最大遺漏:X 期」視覺全失。**嚴重度:中。**
3. **[MISSING] 最近 8 期實際開獎號碼** → 原站全盤分級區塊必附「最近 8 期開獎」,後端沒回、前端沒畫,
   完全缺席。**嚴重度:中。**

---

## 逐項落差

### 1. [BUG] 天天樂被 `MAX_DRAWS=1500` 截斷,偏離原站全歷史計算 — 嚴重度:高
- 位置:`backend/routers/yahong.py:17,29`(`MAX_DRAWS=1500`、`_draws_new_old` 取 `[:1500]`)。
- 原站 `compute18Masters` 用 `N = data.length`(整段 Firestore 歷史,無上限),spec-single §1/§2 明寫「掃過整段歷史」。
- 實測:`data/history_fantasy5.csv` ≈ 3088 期 > 1500 → 天天樂只用最近 1500 期。
  受影響量:`probAll=hits/N`、`missingHistory`(→ maxMiss、avgMiss、stdDev、m4、m10、m11、m13、m18、survivalPR)、
  `maxDD`(資金曲線只跑 1500 期)、m3 馬可夫的 mHit/mMiss 統計 → **finalScore 與 39 碼排名整體位移**。
- 539(856 期)< 1500,不受影響;差異只在天天樂,但天天樂就是雙軌之一,不能忽略。
- 修法:單碼端點對 `single` 不套 1500 上限(改用全歷史),或把上限提高到足以涵蓋 fantasy5(如 ≥3500)。
  若為全站效能取捨要保留 1500,需在規格/API.md 明記「單碼分數為近 1500 期近似,非全歷史」並知會需求方確認。

### 2. [MISSING] 遺漏微型走勢圖(sparkline)前端未渲染 — 嚴重度:中
- 原站:`executeSingleBallScan` 產生 `.sparkline-wrap` 長條圖(近 10 段完成遺漏,新→舊,再補一根「當前遺漏」),
  外加右上角文字「歷史最大遺漏: {maxMiss} 期」。
- 後端**已正確計算並回傳** `target.sparkline`(`single.py:259-262`、`API.md:89`、DTO `client.ts:930`),
  演算法 `recent = reversed(missingHistory[-10:]) + [currentMiss]` 與原站一致。
- 前端 `SinglePanel.tsx` **完全沒有使用 `data.target.sparkline`**,也沒有任何 sparkline 元件 → 資料算了但畫面丟棄。
- 修法:在 18 宗師區塊下方新增一個 sparkline 迷你長條圖(可用純 div 高度%),並顯示「歷史最大遺漏: {maxMiss} 期」。
  (maxMiss 目前只出現在 5 摘要卡,原站在 sparkline 旁另有一份文字。)

### 3. [MISSING] 最近 8 期實際開獎號碼 — 嚴重度:中
- 原站:`executeSuperClassification` 除了 39 碼分級名冊外,固定附「📊 最近 8 期實際開獎號碼」(`data.slice(0,8)`,日期 + 5 顆球)。
- 後端 `single_response`(`single.py:265-292`)只回 `game/totalDraws/ranking/target`,**未提供最近開獎**。
- 前端 `SinglePanel.tsx` 有「全盤 39 碼分級榜」但**沒有最近 8 期開獎區塊**。
- 修法:後端在 single 回傳加 `recent8`(取 `data[:8]` 的日期+號碼),前端在分級榜後新增對應卡片。
  (注意 `_draws_new_old` 目前只回號碼 list,不含日期;需改回帶日期的結構,或另走既有的開獎資料來源。)

### 4. [MISSING] 18 宗師運算白皮書(toggleDoc)無對應 — 嚴重度:低
- 原站底部有可收合的「📖 18 宗師量化矩陣運算白皮書」,含西方 8 + 東方 10 每項的公式與說明卡。
- 前端只有頂部一行 `Disclaimer`(統計包裝提醒),**沒有 18 宗師公式說明**。
- 屬純說明/教育內容,不影響計算;可視需求補一個可收合的說明區。若刻意精簡則標 [INTENTIONAL]。

### 5. [BUG] 號碼從未開出時 `avg_miss` 與原站發散 — 嚴重度:極低(實務不可達)
- `single.py:86-89`:`missing_history` 為空(等價 hits==0、prob_all==0)時,後端取 `avg_miss = float(current_miss)`;
  原站 `avgMiss = 1/probAll - 1 = Infinity`。後續 m4(Z)、m12、finalScore 因此不同。
- 但 N≥100 期內某號碼「一次都沒開」機率 ~1e-6(每期 5/39),實務上不會觸發;規格書 §3.0 的 `(1/probAll-1)` 分支本身也不可達。
- 修法:若要 100% 對齊原站,可在 prob_all==0 時讓 avg_miss=∞(或極大值)。優先度極低,建議留註記即可。

### 6. [COSMETIC] 分級橫幅缺原站的細部標語 — 嚴重度:低
- 原站橫幅第二行含情境語:S「極限爆發區間!」/ A「勝率與動能具水準。」/ B「建議觀望或輕倉。」/ C「動能衰退,嚴禁買進!」。
- 前端只顯示 `GRADE_META.slogan`(絕對主將/優質副牌/中性觀望/強制冷卻)+「綜合分 X · 全盤第 N 名」。
- 標語文案缺失(情感訴求),不影響數值。可補進 `GRADE_META`。

### 7. [COSMETIC] 無效號碼輸入無提示 — 嚴重度:極低
- 原站對 <1 或 >39 `alert("❌ 請輸入 01 到 39...")`;前端 `submit()` 只在 1~39 才 setTarget,否則靜默忽略(無提示)。UX 差異,非計算落差。

---

## OK 清單(已逐行核對,與原始 HTML 一致)

### 前置回測 & 衍生量(`single.py:33-93`)— 全 [OK]
- window5 過熱偵測(push 前用「前 5 期」判斷、recentHits≥2 計入 encounters/hits)、資金曲線 +330/-100、maxDD 追蹤。
- hits/hits5/hits10/hits30 用 `data`(新→舊)近端計數;`prob10=hits10/10`、`prob30=hits30/30`(**固定除 10/30 硬編碼,照抄**)。
- `accel=(prob10-prob30)*100`、`hotStateProb`、`maxMiss=max(missingHistory或[0], currentMiss, 1)`、
  `variance/stdDev` 的 `||1` 防 0 皆對齊。

### 西方 8 宗師 — 全 [OK]
- m1 拉普拉斯 `(hits+1)/(N+2)`;m2 凱利 `prob30-(1-prob30)/3.3`;m3 馬可夫平滑 `(mHit+probAll*5)/(mHit+mMiss+5)`
  (含 `idx>0 && trk===currentMiss` 條件與 trk 更新順序);m4 Z-Score;m5=maxDD;
  m6 EV `prob30*330-(1-prob30)*100`;m7 RSI(視窗 14、losses==0→100);m8 Sharpe(視窗 30、stdRet||1)。

### 東方 10 宗師 — 全 [OK](含規格書 §6 全部地雷)
- m9 85/45;m10 40/80/95;m11 `1/(overMiss+1)*100` 否則 99;
- **m12 不對稱門檻 `Z>2.0 || Z<-1.5`**(非白皮書的 |Z|>1.5)✔;m13 `≥maxMiss*0.8`;m14 費式集合;m15 75/45;
- m16 過熱熔斷 55/95/15/60/85 分支正確;**m17 權重 0.3/0.4/0.3**;
- **m18 tenkan/kijun 預設 40 混尺度 bug 照抄**(len≥9 / len≥26 才覆寫)✔。

### finalScore 計分 & 熔斷(`single.py:177-194`)— 全 [OK]
- `kellyClamped=clamp(m2*10,0,1)*10`;zScorePts 6/4/2/0;**ddPts 用 4000/8000**(與顯示綠燈 6000 不同,照抄)✔;
  evPts 20/0;rsiPts 60/40;sharpePts 0.5/0;18 項權重逐一對齊(m10、m13 = ×0.06,m17 = ×0.05,其餘 ×0.04,m2 直接加)。
- 熔斷:`hits5>=3 → min(35)`;`hits5==2 && currentMiss==0 → -15`。在 finalScore 之後套用,順序正確。

### 名次分級(排名制)— [OK]
- 對 1~39 全算 finalScore → 由高到低排序 → 名次切級:rank<3 S / <9 A / <25 B / 26+ C(`single.py:238-256`)。
- Python `sorted(reverse=True)` 穩定排序,平手時保持號碼升序,與原站 JS 穩定排序 + 升序建表結果一致(平手序無差異)。
- 單碼查詢的 grade/rank 由同一份 ranking 查回,與全盤名冊自洽。

### 5 摘要卡 & 18 宗師顯示 & 綠燈門檻 — [OK]
- 5 摘要:probAll% / survivalPR% / accel(帶±)% / maxMiss 期 / prob30%,格式與原站一致(`format.tsx`+`SinglePanel`)。
- 18 宗師 display 字串(`single.py:213-232`)與原站 giant-card 逐項對齊;**綠燈條件全 18 項一致**,
  含 m5 顯示綠燈 `≤6000`、m7 區間 `40~75`、**m16 門檻 50**(唯一非 60)✔。
- 前端號碼輸入(1~39)、18 宗師綠/紅燈上色、全 39 榜 S/A/B/C 可點回填、雙軌以 `game` prop 區分 — 均有對應。EV 顯示 `+.0f` 與原站 `Math.round`+手動加號經驗算對 fantasy5/539 的可能取值無差異([OK])。
