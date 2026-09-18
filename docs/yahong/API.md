# 雅宏策略 — 建置契約(API 合約,前後端共同依據)

> 兩個建置 agent(backend / frontend)都以本檔為準。**後端為 JSON 欄位名的最終真相**,
> 前端依此渲染、對缺欄位要防呆。算式細節見同目錄 `spec-*.md`(照抄常數,勿自行改動)。

## 支援範圍
- **遊戲**:僅 `lotto539`(今彩539)與 `fantasy5`(天天樂)——兩者皆 39選5,符合「碰」模型。
  `marksix`(49選6)**不支援**,端點對 marksix 回 `400 {detail:"雅宏策略僅支援 539 / 天天樂"}`。
- **子分頁**(YahongView 內):`matrix` 決策矩陣 / `single` 單碼必贏 / `zone34` 同區3-4球 /
  `analysis` 綜合分析 / `plan` 資金規劃。
- **略過**(與現有功能重複、需另建資料表/密碼寫入):spec-539/fantasy 的「AI vs 我 對戰紀錄輸入與統計」、
  Firebase battle_history、前端明碼密碼。抽號機(純亂數動畫)由前端自行處理,不做後端端點。

## 資料存取(後端)
```python
from backend.data import get_game, load_df       # get_game(key).num_max==39, pick==5
from core.loader import draws_as_lists            # 回 list[list[int]],舊→新
# 多數 spec 期望「新→舊」(data[0]=最新),故:
draws = list(reversed(draws_as_lists(load_df(game))))   # 新→舊
# 每筆等價 {"draw":[...5 個號...]}；日期若需要可從 df 取,但演算法多半只用 draw 序列。
```
- 檔案 `core/yahong/` 為新 package。router `backend/routers/yahong.py`,prefix `/yahong`,
  註冊進 `backend/main.py` 的 include 迴圈(加 `yahong.router`)。純計算端點**不需登入**。

---

## 端點 1:決策矩陣 `GET /api/yahong/matrix?game=&mode=`
- `game`:lotto539|fantasy5;`mode`:`1800`|`9000`。演算法見 **spec-core.md**(analyzeSpace + 五裁決)。
- 餵入 `data`=新→舊、最多 1500 期。`cfg` 依 mode:1800→{basePuffs:1800,rebate:37,unitPrize:570};9000→{basePuffs:9000,rebate:50,unitPrize:8000};unitBet:1。
- 回傳(`totalDraws<5` 時 `verdict.title="⏳ 歷史數據不足"`, mult 0,其餘欄位照算或 0):
```jsonc
{
  "game":"lotto539","mode":"1800","totalDraws":1500,
  "verdict":{"title":"🔥 黃金狙擊 (乖離 Z>1.2)","mult":2,"desc":"...","color":"gold"},
  //  color ∈ red|amber|gold|green|slate(對應五裁決,前端上色用)
  "wallst":[   // 華爾街八大,順序固定
    {"key":"bayes","label":"綜合勝率(Bayes)","value":0.58,"fmt":"pct"},
    {"key":"ev","label":"期望值(EV)","value":-11.4,"fmt":"money"},
    {"key":"kelly","label":"凱利配置(Kelly)","value":0.02,"fmt":"pct"},
    {"key":"z","label":"偏離度(Z-Score)","value":1.35,"fmt":"num2"},
    {"key":"drawdown","label":"資金回撤壓力","value":12000,"extra":34000,"fmt":"money"}, // value=current,extra=max
    {"key":"markov","label":"馬可夫反轉率","value":0.56,"fmt":"pct"},
    {"key":"rsi","label":"RSI 震盪(14期)","value":57.1,"fmt":"num1"},
    {"key":"accel","label":"動能加速(Accel)","value":0.03,"fmt":"num2"}
  ],
  "eastern":[  // 東方十大,順序固定
    {"key":"pbase","label":"物理基準 P_base","value":0.5536,"fmt":"pct"},
    {"key":"pemp","label":"大數勝率 P_emp","value":0.56,"fmt":"pct"},
    {"key":"ma30","label":"短期均線 MA30","value":0.57,"fmt":"pct"},
    {"key":"ma120","label":"中期均線 MA120","value":0.55,"fmt":"pct"},
    {"key":"ma500","label":"長期均線 MA500","value":0.55,"fmt":"pct"},
    {"key":"streak","label":"當前連槓期數","value":3,"fmt":"period"},
    {"key":"geomMean","label":"理論平均遺漏","value":0.8,"fmt":"num1"},
    {"key":"geomStd","label":"幾何標準差 σ","value":1.2,"fmt":"num2"},
    {"key":"prSurv","label":"生存極限 PR值","value":72.5,"fmt":"pct100"}, // 已是 0~100
    {"key":"totalDraws","label":"累計觀測期數","value":1500,"fmt":"period"}
  ]
}
```
- `fmt` 給前端統一格式化:`pct`=×100 加 %(1 位)、`pct100`=直接加 %、`money`=四捨五入千分位元、
  `num1`/`num2`=小數位、`period`=整數+「期」。

## 端點 2:同區3-4球 `GET /api/yahong/radar?game=`
- 演算法見 **spec-zone34.md**(對兩個 mode 資料都算;但 zone34 只需該遊戲的開獎序列即可)。
- 回傳:
```jsonc
{
  "game":"lotto539","consecutiveMiss":6,
  "strategyA":{"active":true,"threshold":5,"coldest":[7,13,24,31], // 四柱最冷號
               "note":"各區刪1冷號,壓至 756 碰"},
  "strategyB":{"active":false,"threshold":7,"note":"四區 1200 碰全包"},
  "columns":[{"label":"第1柱 (01-09)","coldest":7},...] // 顯示輔助
}
```

## 端點 3:單碼必贏 `GET /api/yahong/single?game=&target=`
- 演算法見 **spec-single.md**(18 宗師 + finalScore + 名次分級;命中=+330/未中=−100/b=3.3;需 ≥100 期)。
- `target` 省略→只回全盤分級榜;帶 1~39→另附該號完整 18 宗師明細。
- 資料 <100 期回 `{"error":"資料不足 100 期","totalDraws":N}`。
- 回傳:
```jsonc
{
  "game":"lotto539","totalDraws":1500,
  "ranking":[ {"num":7,"score":42.3,"grade":"S","rank":1}, ... 共 39 筆,score 由高到低 ],
  "target":{  // 省略 target 時為 null
    "num":7,"score":42.3,"grade":"S","rank":1,
    "summary":{"probAll":0.128,"survivalPR":72.5,"accel":3.2,"maxMiss":18,"prob30":0.133},
    "giants":[ {"key":"m1","label":"數學家(均值)","display":"12.8%","green":true}, ... 共 18 ],
    "sparkline":[3,1,5,2,...]  // 最近遺漏段(新→舊)+ 末尾當前遺漏
  }
}
```
- grade:S(前3)/A(4-9)/B(10-25)/C(26+),對應顏色 red? 用 grade 字母,前端配色。

## 端點 4:綜合分析 `GET /api/yahong/analysis?game=`
- 演算法見 **spec-539.md / spec-fantasy.md**(兩者共用,常數相同)。**只做唯讀分析**,不含對戰紀錄。
- 回傳:
```jsonc
{
  "game":"lotto539","totalDraws":1500,"latestDate":"2026-09-17",
  "pillars":{  // 柱碰看板(spec §B)
    "p1800":{"miss":4,"nextProb":93.1,"badge":"ready","badgeText":"⚡ 蓄勢開出中"}, // baseP 0.5536
    "p9000":{"miss":2,"nextProb":47.2,"badge":"ok","badgeText":"✅ 安全常規區間"}   // baseP 0.2736
  },  // badge ∈ alert|ready|ok;門檻見 spec §B(1800:95/80;9000:85/70)
  "hot":[{"num":7,"count":8,"today":true},... 8 筆],   // 近50期 TOP8(spec §C)
  "cold":[{"num":15,"miss":36},... 8 筆],               // 連漏 TOP8(spec §D)
  "probScore":[{"num":7,"score":78.5,"freq":61.5,"rebound":95,"miss":6,"recent50":8},... 全39,分數降序],
  "recommend":[  // 四模式 × 三星/四星(spec §F);seed 帶入可重現(見下)
    {"mode":1,"name":"搖球機物理模式","star3":[3,12,20],"star4":[3,12,20,25],"color":"gold"},
    {"mode":2,"name":"歷史紀錄出牌模式","star3":[...],"star4":[...],"color":"rose"},
    {"mode":3,"name":"尋找AI必開牌","star3":[...],"star4":[...],"color":"cyan"},
    {"mode":4,"name":"AI必開加強矩陣","star3":[...],"star4":[...],"color":"purple"}
  ]
}
```
- 推薦有隨機性:後端用固定 seed(例如以最新期號 hash)確保同資料同結果;可加 `?seed=` 覆寫。

## 端點 5:資金規劃 `GET /api/yahong/plan?...`(純計算,不碰開獎資料)
- 演算法見 **spec-539.md §A**(單碼目標倍投 / 4碼目標倍投 / 階梯均注)。
- 參數:`kind=single|four|tier`、`units`(起步車數,預設1)、`target`(預設18440)、`days`(single 15/four 6/tier 15)、
  `cost`(預設2755)、`prize`(預設21200)、`tierMode=single|four`(kind=tier 時)。
- 回傳 `{"kind":"single","rows":[{"day":1,"target":18440,"units":0.65,"dailyCost":1790,"accCost":1790,"winPrize":13780,"netProfit":11990},...]}`
  (four 多 `doubleWin`;金額整數,車數 2 位小數;車數一律 `ceil 到 0.05`)。

---

## 前端整合
- `types.ts`:`NavItem` 新增 `'yahong'`。
- `Sidebar.tsx`:navItems 加 `{ id:'yahong', label:'雅宏策略', icon:<某 lucide icon>, tag? }`(放在 analysis 附近)。
- `App.tsx`:`getNavTitle` 加 `case 'yahong': return '雅宏策略';`;main 區加 `{activeNav==='yahong' && <YahongView/>}`。
- `client.ts`:新增 `api.yahong*` 函式與對應 DTO 型別(依上面 JSON)。
- `components/views/YahongView.tsx`:頂部遊戲切換(用 `useGame()`,但限 lotto539/fantasy5;marksix 顯示「不支援」),
  下方子分頁 tab bar(決策矩陣/單碼必贏/同區3-4球/綜合分析/資金規劃)。決策矩陣子分頁另有 1800/9000 mode 切換。
- 每個子分頁一個元件(如 `MatrixPanel.tsx`, `SinglePanel.tsx`, `Zone34Panel.tsx`, `AnalysisPanel.tsx`, `PlanPanel.tsx`),
  用 `useAsync`(見 `api/useAsync.ts`)抓資料。樣式沿用現有 Tailwind 卡片風格(參考其他 view)。
- **中性說明**:頁面保留原數字,但每個子分頁頂端加一句灰字說明「本策略為統計包裝,樂透為獨立事件,連槓/Z/馬可夫等訊號不具預測力,僅供參考」。

## 驗收
- 後端:`.venv/bin/python -m pytest tests/test_yahong.py -q` 全過;`import backend.main` 不報錯。
- 前端:`cd frontend && npm run build` 成功(型別無誤)。
