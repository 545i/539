# 雅宏策略 — 落差修正契約 v2(全部補齊,與原站對等)

> 依 4 份 `gap-*.md` 稽核。目標:天天樂做到與原站對等 + 補齊顯示層 + 缺字。
> 後端為 JSON 欄位最終真相;前端照此渲染。算式常數以 `spec-*.md` 為準(**照抄勿改**)。
> 兩個修復 agent 各守一層(backend / frontend),檔案不重疊。

---

## 後端(core/yahong/ + backend/routers/yahong.py)

### F1 [BUG高] 期數上限只該套用在決策矩陣
`backend/routers/yahong.py`:`MAX_DRAWS=1500` 目前也套到 single/analysis。
- **matrix**:維持 1500 上限(spec-core 忠實)。
- **single**:改用**全歷史**(原站掃全部;僅 ≥100 期門檻)。
- **analysis**:改用**全歷史**(原站用全部 completedDraws)。
- 作法:`_load` 保留給 matrix;single/analysis 改成 `list(reversed(draws_as_lists(df)))`(不截斷)。

### F2 [BUG] 推薦模式依 game 分流(天天樂只有 3 模式/6 卡)
`core/yahong/analysis.py` `_recommend`:加 `game` 參數。
- **lotto539**:維持 4 模式(spec-539 §F:搖機 / 歷史 pool[0:16] / AI top[0:5]+mid[5:12] / 加強 pool[1:7]+[6:15]),回 4 筆。
- **fantasy5**:改為 **3 模式**(spec-fantasy §3.4:①搖機 全池隨機 / ②歷史 pool[0:16] / ③AI top=pool[0:5]取2 + mid=pool[5:12];三星取2+1、四星取2+2),回 **3 筆**(mode 1/2/3),**不要**第 4 模式。名稱/顏色照 spec-fantasy(gold/rose/cyan)。

### F3 [BUG] 天天樂柱碰看板補齊顯示欄位
`analysis.py` pillar dict:兩款都補 `theoProb`(=base_p*100,1 位小數)。天天樂 `_pillar_fantasy` 已有 `avgCycle`、`histProb`,保留。最終 pillar 欄位:
- 共同:`miss, nextProb, badge, badgeText, theoProb`
- 天天樂另有:`avgCycle, histProb`(539 可不帶或帶 null)

### F4 [BUG] 天天樂資金規劃公式對齊 + 新增立柱倍投
`core/yahong/plan.py`:`plan_response` 與各 plan 函式加 `game` 參數,依 **spec-fantasy §4** 實作天天樂版:
- 天天樂 **單碼目標倍投**:預設 firstUnits=0.10、targetDaily=1844、days=15;車數 `ceil 到 0.01`(`ceil(x*100)/100`);cost=2755/prize=21200。
- 天天樂 **4碼目標倍投**:分母 `prize-4*cost`、成本×4、含 doubleWin;預設同上。
- 天天樂 **單碼階梯**:3 期一階,跨階車數規則見 spec-fantasy §4(+1000 類);**4碼階梯**:2 期一階、+1200/×2.2、負利修正 +500。
- 天天樂 **立柱倍投(新 kind)**:`kind=pillar1800` / `pillar9000`,常數 1800→成本1134/彩金570×?、9000→4545/8000(**精確公式與欄位照 spec-fantasy §4 立柱倍投分頁**,逐行抄)。
- **lotto539**:維持 spec-539 §A 的 single/four/tier(cost2755/prize21200/target18440、車數 ceil 0.05、tier single3期/four2期、u=prevCost/(21200-costUnit)*1.05)。**不要動 539 行為**。
- 端點 `plan_ep` 加 `game` Query;依 game 分流。回傳 `{kind, game, rows[...]}`;立柱 kind 的 rows 欄位照 spec-fantasy。

### F5 [BUG] single 補「最近 8 期開獎」
`single.py` `single_response` 加 `recent8: [{date, nums:[..]}]`(最新 8 期,新→舊)。
需要日期 → 由 `single_ep` 從 df 取(date 欄 + 號碼),傳進 `single_response`,或在 router 組。
`sparkline` 後端已有,保留。

### F6 [MISSING低] 白皮書:各分頁「概念說明」可用既有中性說明涵蓋,不另做 toggle(記為 backlog)。

### F7 [缺字] zone34 策略 B note
`core/yahong/zone34.py`:strategyB note 由「四區 1200 碰全包」改為「**保本防呆,**四區 1200 碰全包」。strategyA note 可補「打法:」前綴一致性(選作)。

---

## 前端(components/views/yahong/ + client.ts)

### G1 [BUG] 天天樂 probScore 表欄位對齊
`AnalysisPanel.tsx`:probScore 欄位**依 game 讀不同鍵** —— 539 讀 `recent50`(表頭「近50」+權重「freq0.65+rebound0.35」);天天樂讀 `recent`(表頭「近15」+權重「freq0.35+recent0.35+rebound0.30」)。表頭文字也要隨 game 切換,別再固定寫 539 權重。

### G2 [BUG] 推薦卡數量隨 game(3 vs 4 模式)
`AnalysisPanel.tsx`:直接 `map` 後端回的 recommend 陣列即可(539 回 4、天天樂回 3),不要寫死 4 張。確認移除任何硬編 mode4。

### G3 [BUG] 天天樂柱碰看板顯示新欄位
`AnalysisPanel.tsx`:柱碰卡片顯示 `theoProb`(理論機率)、天天樂另顯示 `avgCycle`(平均週期)、`histProb`(歷史機率)。對齊原站「連漏/平均/理論機率/歷史機率/爆發率(nextProb)+燈號」五格(539 沒 avgCycle/histProb 則少那兩格)。

### G4 [BUG] 資金規劃前端加 game + 天天樂新分頁
`PlanPanel.tsx` + `client.ts`:`api.yahongPlan` 加 `game` 參數。天天樂 kind 多兩個:`pillar1800`/`pillar9000`(立柱倍投),UI 加對應切換與參數輸入、渲染後端回的 rows 欄位。天天樂單碼/4碼預設值(0.10/1844)也帶對。539 維持原樣。

### G5 [MISSING] single sparkline + 最近 8 期
`SinglePanel.tsx`:渲染 `target.sparkline`(近 10 段遺漏走勢 + 當前遺漏 bar,附「歷史最大遺漏:X 期」);新增「最近 8 期開獎」卡片(讀 `recent8`,每期日期 + 5 顆補零號碼球)。

### G6 [缺字/外觀]
- `Zone34Panel.tsx`:策略 B 達標文案補尾句「睡覺免煩惱!」;兩策略說明補「打法:」標籤前綴(對齊原站文案)。
- `format.tsx` / `MatrixPanel.tsx`:東方十大「理論平均遺漏」加「期」單位(可在 format 對該 key 特例、或後端改 label);「🔴 聯合否決」banner 顏色由 slate 改為與紅圈 emoji 一致的 red(或把 emoji 改灰,擇一,建議改 red)。

### client.ts DTO 更新(對齊上面)
- probScore item:539 `recent50`;天天樂 `recent/recent15`(型別用可選欄位)。
- pillar:加 `theoProb`,天天樂 `avgCycle?/histProb?`。
- single:加 `recent8?: {date:string; nums:number[]}[]`;`target.sparkline` 已在。
- plan:`yahongPlan(game, kind, params)`;新增 pillar kind 的 row 型別。
- recommend:陣列長度可 3 或 4。

---

## 驗收
- 後端:`.venv/bin/python -m pytest tests/test_yahong.py -q` 全過(補天天樂 plan/推薦/期數的測試);`import backend.main` ok。
- 前端:`cd frontend && npm run build` 綠。
- 不要動 539 既有行為(回歸)。不要 git commit(team-lead 統一提交部署)。
