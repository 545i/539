# 雅宏策略移植規格書 — 「🎯 同區 3-4 球」(同區極限偏態戰情室)

> 來源檔:`/tmp/yh_3or4.html`(292 行,單一 `<script type="module">`)
> 頁面標題:🎯 同區極限偏態狙擊戰情室 (雙引擎版)
> 本規格忠實拆解該頁**所有**演算法,供 Python 重寫。Firebase / apiKey / CSS / DOM 樣板已忽略。

---

## ① 功能總覽

這頁做的事只有一件:**監控「同區(柱)同時開出 3 顆以上」這件事已經連續幾期沒發生**,並在連槓數達到兩個門檻(5 / 7)時觸發兩套進場建議。

- **雙引擎**:同一套演算法各跑一次,分別餵入兩個資料集,獨立渲染兩個面板:
  - 今彩 539 → 資料鍵 `539-9000`,DOM 前綴 `539`
  - 天天樂 → 資料鍵 `tt-9000`,DOM 前綴 `tt`
- 每個面板顯示:
  1. 一個「大盤狀態監控」數字 = 目前**連續未出同區 3 顆以上**的期數 `consecutiveMiss`。
  2. 策略 A 卡(門檻 `>= 5`):達標時列出四柱各自「最冷號碼」建議刪除。
  3. 策略 B 卡(門檻 `>= 7`):達標時顯示固定文案(不列號碼)。
- ⚠️ **本檔沒有任何機率基準常數、每連一期加多少、機率遞增公式或 clamp 上限**。任務背景提到的那類機率遞增邏輯在此頁**不存在**;唯一的可調參數是兩個整數門檻 5 與 7。若之後要加機率,是新增功能,不是移植。

---

## ② 資料模型 / 分區

### 輸入資料結構
每個資料集是一個開獎紀錄陣列,每筆(item)欄位:

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | 任意 | 唯一識別,用於去重 |
| `date` | 字串(可字典序比較) | 期別日期,作為排序鍵 |
| `draw` | 陣列 | 該期開出的號碼(元素可能是字串,程式會 `Number()` 轉換);539/天天樂每期 5 顆,範圍 1~39 |
| `space` | 字串 | `'539-9000'` 或 `'tt-9000'`,決定歸屬哪個引擎 |

### 排序
```js
// 由舊到新(date 升冪)。原始資料未排序,務必先排。
sortedData = [...data].sort((a, b) => a.date > b.date ? 1 : -1);
```
Python 等價:`sorted(data, key=lambda x: x["date"])`(date 為可比較字串,如 `YYYY-MM-DD`)。

### 分區(四柱,固定)
把號碼 1~39 依十位數分為 4 柱:

| 柱 index | 名稱標籤 | 範圍 | 判定條件(程式原文) | 柱內號碼數 |
|----------|----------|------|----------------------|-----------|
| `zones[0]` | 第1柱 (01-09) | 01–09 | `n <= 9` | 9 |
| `zones[1]` | 第2柱 (10-19) | 10–19 | `n <= 19` | 10 |
| `zones[2]` | 第3柱 (20-29) | 20–29 | `n <= 29` | 10 |
| `zones[3]` | 第4柱 (30-39) | 30–39 | `else`(即 `>= 30`) | 10 |

> 注意:第1柱只有 9 個號(1~9),其餘三柱各 10 個。判定用「小於等於」串接的 if/else if,號碼超出 1~39 一律落入第4柱(資料保證 1~39,不需額外防呆,但 Python 版可加上界檢查)。

---

## ③ 指標與算式(含所有常數)

演算法只有一個函式 `calculateAndRender(spaceKey, prefix)`,產出三類數值:`consecutiveMiss`、四柱各自的最冷號 `c1~c4`、以及 `lastSeen` 對照表。

### 3.1 每期「同區顆數」與「是否命中」
對排序後每一期:
```js
zones = [0, 0, 0, 0]
for num in item.draw:
    n = Number(num)
    // 記錄該號最後出現的期序 index(見 3.3)
    lastSeen[n] = index
    if   n <= 9  : zones[0] += 1
    elif n <= 19 : zones[1] += 1
    elif n <= 29 : zones[2] += 1
    else         : zones[3] += 1
// 該期是否有「同區 3 顆以上」
hit = (max(zones) >= 3)
```
- **門檻常數 = 3**:某一柱在單期內出現 `>= 3` 顆即視為「同區 3 顆以上命中」。
- 因為每期只開 5 顆,一柱最多可能 5 顆,所以「同區 3 顆」與「同區 4 顆」與「同區 5 顆」在此**共用同一個判定**(都算命中),頁面標題雖叫「3-4 球」,程式並未把 3 顆和 4 顆分開統計 —— 只要 `max(zones) >= 3` 就命中。

### 3.2 連續未出計數 `consecutiveMiss`(核心指標)
逐期掃描,命中歸零、未命中累加:
```js
consecutiveMiss = 0
for each period (由舊到新):
    if max(zones) >= 3:
        consecutiveMiss = 0     // 命中 → 連槓中斷
    else:
        consecutiveMiss += 1    // 未命中 → 連槓 +1
```
- 掃完整個歷史後,`consecutiveMiss` 即代表**到最新一期為止,已連續幾期沒有任何一柱出到 3 顆以上**。
- 沒有上限 clamp,沒有加權,單純整數累加/歸零。
- 這就是面板上「連續未出 3顆以上:N 期」顯示的值。

### 3.3 各柱最冷號 `lastSeen` / `findColdest`
```js
// 初始化:1~39 全部 lastSeen = -1(代表在資料範圍內從未出現)
for i in 1..39: lastSeen[i] = -1
// 掃描期間(見 3.1)持續更新 lastSeen[n] = 當期 index

// 找某區間內「最久沒出現」的號碼
findColdest(start, end):
    minIdx = +∞           // Number.MAX_SAFE_INTEGER
    target = start        // 預設回傳區間第一個號
    for i in start..end:
        if lastSeen[i] < minIdx:
            minIdx = lastSeen[i]
            target = i
    return target         // lastSeen 最小者 = 最冷號

c1 = findColdest(1, 9)
c2 = findColdest(10, 19)
c3 = findColdest(20, 29)
c4 = findColdest(30, 39)
```
- `lastSeen[n]` 存的是該號**最後一次出現的期序 index**(0 = 最舊那期,越大越新)。
- 「最冷」= `lastSeen` 值最小者:值越小代表越久沒出;`-1`(從未出現)最冷。
- 平手時取**號碼較小者**(迴圈由小到大,只在 `<` 嚴格小於時更新)。
- 這四個號碼只在策略 A 達標時顯示。

---

## ④ 建議 / 危險柱邏輯

沒有「危險柱」這種輸出;輸出是兩張策略卡的啟用狀態與建議內容,由 `consecutiveMiss` 對兩個門檻判定。**539 與天天樂用完全相同的門檻與文案**。

### 策略 A(量化正收益)— 門檻 `consecutiveMiss >= 5`
| 狀態 | 條件 | 徽章文字 | 建議區 |
|------|------|----------|--------|
| 達標 | `>= 5` | `進場時刻`(卡片套用 `active-a` 高亮/脈動) | 顯示「🔥 達標!建議刪除極端死號:」+ 四柱最冷號清單 |
| 未達標 | `< 5` | `觀望中` | 隱藏 |

- 卡片說明文案(固定):「條件:連 5 期未出同區 3 顆。打法:**各區刪1冷號,壓至 756 碰。**」
- 達標時列出四行,每行為「柱名 + 最冷號(補零 2 位)」:
  - 第1柱 (01-09):`c1`
  - 第2柱 (10-19):`c2`
  - 第3柱 (20-29):`c3`
  - 第4柱 (30-39):`c4`

### 策略 B(防呆狙擊手)— 門檻 `consecutiveMiss >= 7`
| 狀態 | 條件 | 徽章文字 | 建議區 |
|------|------|----------|--------|
| 達標 | `>= 7` | `重擊進場`(卡片套用 `active-b` 高亮/脈動) | 顯示固定文案「🎯 狙擊時機已到!今晚不刪牌直接滿注進場,等待爆發,睡覺免煩惱!」 |
| 未達標 | `< 7` | `觀望中` | 隱藏 |

- 卡片說明文案(固定):「條件:連 7 期未出同區 3 顆。打法:**保本防呆,四區 1200 碰全包。**」
- 策略 B **不列任何號碼**,只切換文案顯示。

> 兩策略獨立判定,可同時達標:`consecutiveMiss = 8` 時 A、B 皆亮。
> 「756 碰」「1200 碰」是**固定文案標籤**,程式沒有計算,只是策略說明字串。(參考:各柱刪 1 冷號後剩 8+9+9+9=35 個號並非直接對應 756;這些數字視為既定打法標籤,重寫時照抄即可,不需推導。)

### 門檻常數彙整
| 常數 | 值 | 用途 |
|------|----|----|
| 同區命中顆數門檻 | `3` | `max(zones) >= 3` 視為命中,連槓歸零 |
| 策略 A 觸發連槓 | `5` | `consecutiveMiss >= 5` |
| 策略 B 觸發連槓 | `7` | `consecutiveMiss >= 7` |
| 柱數 | `4` | 01-09 / 10-19 / 20-29 / 30-39 |
| 每柱建議刪除冷號數 | `1`(僅策略 A) | 各柱取 1 個最冷號 |

---

## ⑤ 顯示欄位對照表

| 顯示位置 | DOM id(前綴 `539` / `tt`) | 值來源 | 格式 / 單位 |
|----------|---------------------------|--------|-------------|
| 連續未出 3顆以上 | `bias-consecutive-{prefix}` | `consecutiveMiss` | 整數,後接「期」 |
| 策略 A 徽章 | `bias-badge-a-{prefix}` | 由門檻決定 | `進場時刻` / `觀望中` |
| 策略 A 建議區顯隱 | `bias-sugg-a-{prefix}` | `>= 5` 顯示 | block / none |
| 策略 A 四柱冷號清單 | `bias-list-a-{prefix}` | `c1~c4` | 每號 `padStart(2,'0')`,即補零 2 位(如 `07`) |
| 策略 A 卡片高亮 | `bias-card-a-{prefix}` | `>= 5` | class `active-a`(紅色脈動) |
| 策略 B 徽章 | `bias-badge-b-{prefix}` | 由門檻決定 | `重擊進場` / `觀望中` |
| 策略 B 建議區顯隱 | `bias-sugg-b-{prefix}` | `>= 7` 顯示 | block / none(固定文案,無號碼) |
| 策略 B 卡片高亮 | `bias-card-b-{prefix}` | `>= 7` | class `active-b`(紫色脈動) |

### 數字格式
- `consecutiveMiss`:純整數,無小數、無百分比。
- 冷號:兩位數補零字串(`String(n).padStart(2,'0')`),Python:`f"{n:02d}"`。
- **全頁沒有任何百分比、機率、小數位輸出。**

---

## ⑥ Python 重寫提示(摘要)

```python
def analyze_zone34(rows, threshold_hit=3, thr_a=5, thr_b=7):
    # rows: list of {"date": str, "draw": list[int|str]}
    rows = sorted(rows, key=lambda r: r["date"])          # 舊→新
    last_seen = {i: -1 for i in range(1, 40)}
    consecutive_miss = 0
    for idx, r in enumerate(rows):
        zones = [0, 0, 0, 0]
        for raw in r["draw"]:
            n = int(raw)
            last_seen[n] = idx
            if   n <= 9:  zones[0] += 1
            elif n <= 19: zones[1] += 1
            elif n <= 29: zones[2] += 1
            else:         zones[3] += 1
        consecutive_miss = 0 if max(zones) >= threshold_hit else consecutive_miss + 1

    def coldest(start, end):
        # last_seen 最小者;平手取號碼小者
        return min(range(start, end + 1), key=lambda i: (last_seen[i], i))

    coldest_by_zone = [coldest(1, 9), coldest(10, 19), coldest(20, 29), coldest(30, 39)]
    return {
        "consecutive_miss": consecutive_miss,
        "coldest": coldest_by_zone,           # 供策略 A 顯示(補零)
        "strategy_a": consecutive_miss >= thr_a,
        "strategy_b": consecutive_miss >= thr_b,
    }
```

> 注意:`coldest` 用 `(last_seen[i], i)` 當 key 完全對應原檔「值最小、平手取小號」的行為(原檔嚴格 `<` 更新)。
