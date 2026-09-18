# 決策矩陣 — 落差稽核(gap-matrix)

> 稽核員:決策矩陣落差稽核。範圍:華爾街八大 + 東方十大 + 五裁決。
> 對照:`docs/yahong/spec-core.md`(真相) × `core/yahong/matrix.py`(後端) ×
> `frontend/src/components/views/yahong/MatrixPanel.tsx`(+`format.tsx`) × `backend/routers/yahong.py` / `docs/yahong/API.md`。
> 稽核日期:2026-09-18。**只讀不改**(本檔除外)。

## 總結

- **演算法本體(analyzeSpace + 五裁決)= 逐行忠實移植,0 個 BUG、0 個 MISSING。**
  常數、三個 loop、Z/Bayes/EV/Kelly/回撤公式、五分支條件與順序、mult 0/1/2、
  data 取用(新→舊、slice 1500、1800 puffs≥3、9000 pass=puffs>0)全部與 spec 對齊。
- 找到 **6 個落差**,全屬顯示層,嚴重度皆為**低/極低**;其中 1 個是 API.md 刻意重新定義。
- 前端渲染(八大/十大/五裁決橫幅上色/mode 切換/資料不足)皆到位,無漏。

### 最重要的 3 個(皆為外觀,無高危)
1. **[COSMETIC 中]** `理論平均遺漏 geomMean` 缺「期」單位 —— spec 明列格式「一位小數 **期**」,實作 `fmt=num1` 只印數字。
2. **[COSMETIC/INTENTIONAL 低]** `資金回撤壓力` 第二值:spec 為「元 / **比率%**」,實作(依 API.md)改成「當前元 / 最大**元**」。
3. **[COSMETIC 低]** `🔴 聯合否決` 標題用紅圈 emoji,但 banner `color=slate`(灰),色與 emoji 不一致(其餘四裁決一致)。

---

## 逐項比對

### A. 常數 / 牌局設定 —— 全部 [OK]
| 項目 | spec | matrix.py | 判定 |
|------|------|-----------|------|
| 1800 cfg | unitBet1/basePuffs1800/rebate37/unitPrize570 | `_CONFIGS["1800"]` 相同 | OK |
| 9000 cfg | unitBet1/basePuffs9000/rebate50/unitPrize8000 | `_CONFIGS["9000"]` 相同 | OK |
| baseP | 0.5536 / 0.2736 | `base_p` 相同 | OK |
| expectedPrizePuffs | 3.5576 / 2.0 | 相同 | OK |
| bayes 權重 | ma14×0.3 + ma30×0.2 + pMarkov×0.5 | 相同(matrix.py:142) | OK |
| Z 加成 | z≥0.8 時 `+= z×0.035` | 相同(:143-144) | OK |
| maxAllowedProb | min(baseP×1.6, 0.99) | 相同(:140) | OK |
| kellyScale | turbulent 0 / dd>max×0.5 0.03 / else 0.10 | 相同(:152) | OK |
| isTurbulent | maxDD>cost×5 且 curDD≥maxDD×0.75 | 相同(:151) | OK |
| EV/Kelly/b/回撤 公式 | 見 spec:117-123 | 相同(:147-153) | OK |
| Z clamp | max(-3, min(rawZ, 3)) | 相同(:135) | OK |
| geomMean/geomStd | (1-p)/p、√(1-p)/p | 相同(:132-133) | OK |
| pMarkov | (hit+baseP×2)/(hit+miss+2) | 相同(:139) | OK |

### B. 中獎判定 —— 全部 [OK]
- `check1800`:柱界 10–18 / 20–29 / 其餘,puffs=p1·p2·p3,**isWin=puffs≥3** → 與 spec 完全一致。
- `check9000`:四區 1-9/10-19/20-29/30-39,**pass=puffs>0** → 一致。

### C. 三個 loop —— 全部 [OK]
- **Loop1(舊→新)**:理論權益曲線 / peak / maxDrawdown / missingHistory / tempMiss —— 與 spec:68-76 完全一致。
- **Loop2(新→舊)**:wins / wins14/30/120/500 / losingStreak(countingStreak 旗標)—— 一致。
- **Loop3(舊→新)**:markovHit/Miss,`i>0 且 mMissTracker==losingStreak` 時計數,mMissTracker win 歸零否則 +1 —— 一致。

### D. data 取用 —— [OK]
- `_draws_new_old`:`reversed(draws_as_lists(...))[:1500]` = 新→舊、取最新 1500;`analyze_space` 再 `data[::-1]` 還原舊→新。
  與 spec「getFilteredData slice(0,1500) 後 `reversedData=reverse`」順序一致(先切再反轉),**無 off-by-one / 順序錯**。

### E. 五裁決 —— 分支/順序/mult/color 全部 [OK](color 為新增,見落差 #3)
| 條件(spec 順序) | title | mult | matrix color |
|---|---|---|---|
| totalDraws<5 | ⏳ 歷史數據不足 | 0 | slate |
| !passEV && !passZ | 🔴 系統否決 (期望值為負) | 0 | red |
| !passDD | 🟡 亂流防禦 (波動率限制) | 0 | amber |
| z≥1.2 && passEV | 🔥 黃金狙擊 (乖離 Z>1.2) | 2 | gold |
| ma30≥ma120 && passEV | 🟢 標準多頭佈局 | 1 | green |
| else | 🔴 聯合否決 (條件未齊) | 0 | slate |

- passZ/passDD/passEV 定義與 spec:138-140 一致(`0.8≤z≤3.0` / `not isTurbulent` / `EV>0`)。
- verdict 讀 `analyze_space` 未四捨五入的原值,**不受顯示 rounding 影響** → 正確。
- <5 期守門 spec §3 要求 `totalDraws>=5`,實作 `a["totalDraws"] < 5` 一致(需 ≥5)。

---

## 落差清單(全為顯示層)

### #1 [COSMETIC 中] geomMean 缺「期」單位
- spec §4 東方#7:`理論平均遺漏 geomMean` 格式 =「**一位小數 期**」。
- 實作:`matrix.py:254` 給 `fmt:"num1"`;`format.tsx:11` `num1 → value.toFixed(1)`,**不附「期」**。
- 影響:顯示 `0.8` 而非 `0.8 期`;與同表其他「期」欄(streak/totalDraws 用 `period` 有「期」)風格不一致。
- 修法建議:改 `geomMean` 用能帶單位的格式。最小改動 = 後端把 geomMean 的 `fmt` 改成新的一位小數帶「期」格式(例如新增 `fmt:"period1"`,`format.tsx` 加 `case 'period1': return ${'`'}${'{'}value.toFixed(1){'}'} 期${'`'};`);或維持 num1 但接受無單位(需與原站截圖確認)。

### #2 [COSMETIC / INTENTIONAL 低] 資金回撤壓力第二值:比率% → 絕對元
- spec §4 華爾街#5:值 `currentDrawdown / maxDrawdown`,格式「**元 / 比率%**」。
- 實作:`API.md` 明文重新定義為 `value=current(元), extra=max(元)`;`matrix.py:241-242` 照此輸出;`MatrixPanel.tsx:12-13` 顯示 `$current / 最大 $max`(兩者皆元)。
- 影響:第二段顯示歷史最大回撤的**絕對金額**,而非 spec 的「當前佔最大回撤的**比率%**」。屬 API.md 有意決策,但與 spec-core 有出入,列此供最終定奪。
- 修法建議:若要貼齊原站,將 extra 改為 `currentDrawdown/maxDrawdown×100`、`fmt` 改 `pct100`,前端顯示「$current / 佔比 xx.x%」。否則於 spec/API 加註「已刻意改為絕對元」以消歧義。

### #3 [COSMETIC 低] 聯合否決 emoji 與 banner 色不一致
- `matrix.py:195-196`:`🔴 聯合否決` 標題含紅圈,但 `color:"slate"`(灰);`format.tsx:27` slate=灰。
- 其餘四裁決 emoji 與 banner 色一致(紅🔴/黃🟡/金🔥/綠🟢),唯此項 emoji 紅、底色灰。
- 修法建議:二擇一 —— 把標題 emoji 改中性(如 ⚪/⏸),或把 color 改 `red`。屬觀感,無功能影響(spec 無 color 欄,本屬新增)。

### #4 [COSMETIC 極低] $ 前綴不一致
- EV(`money`)經 `format.tsx:10` 無 `$`;drawdown 於 `MatrixPanel.tsx:12` 硬加 `$`。同為金額,一有一無。
- 修法建議:統一(EV 也加 `$`,或 drawdown 去 `$`)。

### #5 [COSMETIC 極低] 標籤空格差異
- spec「生存極限 PR **值**」(PR 與值間有空格),實作「生存極限 PR值」(`matrix.py:256`)。純字面,可忽略。

### #6 [COSMETIC 極低 / 邊界] 空資料時 P_emp 顯示 0 而非 baseP
- spec `empWinRate` 當 `total==0` 回退 baseP;但 `analyze_space` 在 `total==0` 提前 `return None`,`matrix_response` 的 None 分支把 `pemp` 硬設 0(`matrix.py:223`)。
- 影響:僅「完全無開獎資料」時 P_emp 顯示 0%(正式環境不會發生)。與「port 本身邏輯」一致(baseP 回退在原 JS 也到不了),僅顯示預設值差異。可不處理。

---

## 判定統計
- **[OK 已對齊]**:常數全項、中獎判定、三 loop、data 取用、五裁決分支/順序/mult、八大+十大全欄位齊全、前端八大/十大/橫幅上色/mode 切換/資料不足提示。
- **[BUG 錯誤]**:0
- **[MISSING 漏做]**:0
- **[COSMETIC 外觀]**:#1(中)、#2(低,亦屬 INTENTIONAL)、#3(低)、#4/#5/#6(極低)
- **[INTENTIONAL 刻意]**:#2 的 API.md 重定義(元/元)。
