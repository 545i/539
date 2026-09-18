# 雅宏策略 — 核心規格(決策矩陣 + 同區盤路)

> 來源:`539-1800.vercel.app`(雙核心量化操盤系統)。本檔為**逐行還原**的權威算式,
> 供 `core/yahong.py` 照抄重寫。符號已還原為真實運算子。

## 0. 資料模型與牌局設定

每期開出 **5 個號碼(1~39)**。歷史 `data` 為一連串 `{draw:[n1..n5]}`,**由新到舊排序**
(`getFilteredData` 取 `slice(0,1500)`,即最近 1500 期)。`reversedData` = 由舊到新。

牌局設定 `spaceConfigs`(539 與 天天樂各有 1800/9000 兩種,參數只依 type 分):

| type | unitBet | basePuffs | rebate(%) | unitPrize |
|------|---------|-----------|-----------|-----------|
| 1800 | 1 | 1800 | 37 | 570 |
| 9000 | 1 | 9000 | 50 | 8000 |

## 1. 中獎判定

```js
// 1800碰:三區各是否有球，碰數 = 三區球數相乘；「贏」= puffs >= 3
function check1800(balls){
  let p1=0,p2=0,p3=0;
  for(const x of balls){ const n=Number(x);
    if(n>=10 && n<=18) p1++;        // 第一柱
    else if(n>=20 && n<=29) p2++;   // 第二柱
    else p3++;                      // 第三柱 = 01~09、19、30~39
  }
  const puffs = p1*p2*p3;
  return { puffs, p1, p2, p3 };
}
// isWin(1800) = puffs >= 3

// 9000碰:四區(1-9/10-19/20-29/30-39)是否全開；pass = 四區皆 >0
function check9000(balls){
  let q1=0,q2=0,q3=0,q4=0;
  for(const x of balls){ const n=Number(x);
    if(n>=1&&n<=9)q1++; else if(n<=19)q2++; else if(n<=29)q3++; else if(n<=39)q4++;
  }
  const puffs=q1*q2*q3*q4;
  return { pass: puffs>0, puffs, q1,q2,q3,q4 };
}
// isWin(9000) = res.pass
```

## 2. analyzeSpace — 決策矩陣主算式

```js
function analyzeSpace(cfg, data){          // data: 新→舊, 最多 1500
  const totalDraws = data.length;
  if(totalDraws===0) return null;

  const baseP_Threshold   = cfg.type==='1800' ? 0.5536 : 0.2736;   // 物理基準命中率
  const costPerRound      = cfg.unitBet * cfg.basePuffs * (1 - cfg.rebate/100);
  const expectedPrizePuffs= cfg.type==='1800' ? 3.5576 : 2.0;
  const avgPrizeWhenWin   = expectedPrizePuffs * cfg.unitPrize * cfg.unitBet;

  const isWinOf = (draw)=>{
    const res = cfg.type==='1800' ? check1800(draw) : check9000(draw);
    return (cfg.type==='1800' && res.puffs>=3) || (cfg.type==='9000' && res.pass);
  };

  const reversedData = [...data].reverse();  // 舊→新

  // ── Loop1(舊→新):理論權益曲線 + 回撤 + 遺漏史 ──
  let theoreticalEquity=0, peakTheoretical=0, maxDrawdown=0;
  const missingHistory=[]; let tempMiss=0;
  for(const item of reversedData){
    const isWin=isWinOf(item.draw);
    const roundPnL = isWin ? (avgPrizeWhenWin-costPerRound) : -costPerRound;
    theoreticalEquity += roundPnL;
    if(theoreticalEquity>peakTheoretical) peakTheoretical=theoreticalEquity;
    const dd = peakTheoretical-theoreticalEquity;
    if(dd>maxDrawdown) maxDrawdown=dd;
    if(isWin){ missingHistory.push(tempMiss); tempMiss=0; } else { tempMiss++; }
  }

  // ── Loop2(新→舊):勝場數、近 N 期勝數、當前連槓 ──
  let wins=0, wins14=0,wins30=0,wins120=0,wins500=0, losingStreak=0, countingStreak=true;
  for(let i=0;i<data.length;i++){
    const isWin=isWinOf(data[i].draw);
    if(isWin){ wins++; if(i<14)wins14++; if(i<30)wins30++; if(i<120)wins120++; if(i<500)wins500++;
               countingStreak=false; }
    else { if(countingStreak) losingStreak++; }
  }

  // ── Loop3(舊→新):馬可夫「連槓深度==目前連槓」時的下一期命中/落空 ──
  let markovHit=0, markovMiss=0, mMissTracker=0;
  for(let i=0;i<reversedData.length;i++){
    const isWin=isWinOf(reversedData[i].draw);
    if(i>0 && mMissTracker===losingStreak){ if(isWin)markovHit++; else markovMiss++; }
    if(isWin) mMissTracker=0; else mMissTracker++;
  }

  const ma14 = Math.min(totalDraws,14)>0 ? wins14/Math.min(totalDraws,14) : 0;
  const ma30 = Math.min(totalDraws,30)>0 ? wins30/Math.min(totalDraws,30) : 0;
  const ma120= Math.min(totalDraws,120)>0? wins120/Math.min(totalDraws,120):0;
  const ma500= Math.min(totalDraws,500)>0? wins500/Math.min(totalDraws,500):0;
  const rsi14= Math.min(totalDraws,14)>0 ? (wins14/Math.min(totalDraws,14))*100 : 50;
  const accel= ma30 - ma120;
  const empWinRate = totalDraws>0 ? wins/totalDraws : baseP_Threshold;

  const geomMean = baseP_Threshold>0 ? (1-baseP_Threshold)/baseP_Threshold : 0;
  const geomStd  = baseP_Threshold>0 ? Math.sqrt(1-baseP_Threshold)/baseP_Threshold : 1;
  const rawZ     = geomStd>0 ? (losingStreak-geomMean)/geomStd : 0;
  const zScore   = Math.max(-3.0, Math.min(rawZ, 3.0));

  const shorterCount = missingHistory.filter(m=>m<=losingStreak).length;
  const prSurv = missingHistory.length>0 ? (shorterCount/missingHistory.length)*100 : 50;
  const pMarkov = (markovHit + baseP_Threshold*2) / (markovHit + markovMiss + 2);
  const maxAllowedProb = Math.min(baseP_Threshold*1.6, 0.99);

  let bayesProb = ma14*0.3 + ma30*0.2 + pMarkov*0.5;
  if(zScore>=0.8) bayesProb += zScore*0.035;
  bayesProb = Math.max(0, Math.min(bayesProb, maxAllowedProb));

  const EV = bayesProb*avgPrizeWhenWin - costPerRound;
  const currentDrawdown = peakTheoretical - theoreticalEquity;
  const b = costPerRound>0 ? (avgPrizeWhenWin-costPerRound)/costPerRound : 0;
  const fullKelly = b>0 ? (bayesProb*(b+1)-1)/b : 0;
  const isTurbulent = (maxDrawdown > costPerRound*5) && (currentDrawdown >= maxDrawdown*0.75);
  const kellyScale = isTurbulent ? 0.00 : (currentDrawdown > maxDrawdown*0.5 ? 0.03 : 0.10);
  const fracKelly = Math.max(0, Math.min(fullKelly*kellyScale, 1));

  return { totalDraws, losingStreak, ma30, ma120, ma500, empWinRate, bayesProb, zScore,
           EV, costPerRound, fracKelly, currentDrawdown, maxDrawdown, isTurbulent,
           baseP_Threshold, rsi14, accel, prSurv, pMarkov, geomMean, geomStd,
           // 額外(顯示八大用):
           avgPrizeWhenWin, b };
}
```

## 3. 五裁決(下注倍數建議)

需 `totalDraws >= 5`,否則顯示「⏳ 歷史數據不足」。

```js
const passZ  = a.zScore>=0.8 && a.zScore<=3.0;
const passDD = !a.isTurbulent;
const passEV = a.EV>0;

if(!passEV && !passZ)                 verdict = { title:"🔴 系統否決 (期望值為負)", mult:0,
                                                  desc:"【風控否決】期望值 EV<0，強制 0 倍空手觀望！" };
else if(!passDD)                      verdict = { title:"🟡 亂流防禦 (波動率限制)", mult:0,
                                                  desc:"【回撤警告】資金曲線進入深水區亂流，建議 0 倍觀望。" };
else if(a.zScore>=1.2 && passEV)      verdict = { title:"🔥 黃金狙擊 (乖離 Z>1.2)", mult:2,
                                                  desc:"【精準打擊】連槓 "+a.losingStreak+" 期，Z 達標，核准 2 倍火力狙擊！" };
else if(a.ma30>=a.ma120 && passEV)    verdict = { title:"🟢 標準多頭佈局", mult:1,
                                                  desc:"【常態區】短均站上長均且 EV>0，核准 1 倍平推。" };
else                                  verdict = { title:"🔴 聯合否決 (條件未齊)", mult:0,
                                                  desc:"【觀望區】多空不明確，乖離不足補償 EV，0 倍觀望。" };
```

## 4. 兩大指標矩陣(顯示)

**華爾街八大(西方量化)**
| # | 名稱 | 值 | 格式 |
|---|------|----|------|
| 1 | 綜合勝率(Bayes) | `bayesProb` | % |
| 2 | 期望值(EV) | `EV` | 元(可負) |
| 3 | 凱利配置(Kelly) | `fracKelly` | %(注碼佔資金比) |
| 4 | 偏離度(Z-Score) | `zScore` | 兩位小數 |
| 5 | 資金回撤壓力 | `currentDrawdown` / `maxDrawdown` | 元 / 比率% |
| 6 | 馬可夫反轉率 | `pMarkov` | % |
| 7 | RSI 震盪(14期) | `rsi14` | 0~100 |
| 8 | 動能加速(Accel) | `accel` | 兩位小數(ma30−ma120) |

**東方傳統十大(盤路/經驗)**
| # | 名稱 | 值 | 格式 |
|---|------|----|------|
| 1 | 物理基準 P_base | `baseP_Threshold` | % |
| 2 | 大數勝率 P_emp | `empWinRate` | % |
| 3 | 短期均線 MA30 | `ma30` | % |
| 4 | 中期均線 MA120 | `ma120` | % |
| 5 | 長期均線 MA500 | `ma500` | % |
| 6 | 當前連槓期數 | `losingStreak` | 期 |
| 7 | 理論平均遺漏 | `geomMean` | 一位小數 期 |
| 8 | 幾何標準差 σ | `geomStd` | 兩位小數 |
| 9 | 生存極限 PR 值 | `prSurv` | % |
| 10 | 累計觀測期數 | `totalDraws` | 期 |

## 5. analyzeRadar — 同區3-4球(vercel 版,參考;正式來源以 3or4.html 規格為準)

```js
function analyzeRadar(data){                 // data: 新→舊(vercel 用 9000 空間)
  let tripleLosingStreak=0, overallHitFound=false;
  const colHits   ={q1:0,q2:0,q3:0,q4:0};
  const colStreaks={q1:0,q2:0,q3:0,q4:0};
  const colFound  ={q1:false,q2:false,q3:false,q4:false};
  for(const item of data){
    const b=item.draw; if(!Array.isArray(b)) continue;
    let q1=0,q2=0,q3=0,q4=0;
    for(const x of b){ const n=Number(x);
      if(n>=1&&n<=9)q1++; else if(n>=10&&n<=19)q2++; else if(n>=20&&n<=29)q3++; else if(n>=30&&n<=39)q4++; }
    if(q1>=3)colHits.q1++; if(q2>=3)colHits.q2++; if(q3>=3)colHits.q3++; if(q4>=3)colHits.q4++;
    const isTripleOrMore=(q1>=3||q2>=3||q3>=3||q4>=3);
    if(!overallHitFound){ if(isTripleOrMore)overallHitFound=true; else tripleLosingStreak++; }
    if(!colFound.q1){ if(q1>=3)colFound.q1=true; else colStreaks.q1++; }
    if(!colFound.q2){ if(q2>=3)colFound.q2=true; else colStreaks.q2++; }
    if(!colFound.q3){ if(q3>=3)colFound.q3=true; else colStreaks.q3++; }
    if(!colFound.q4){ if(q4>=3)colFound.q4=true; else colStreaks.q4++; }
  }
  const baseOverallTripleProb=0.357;
  const tripleNextProb=Math.min(baseOverallTripleProb + tripleLosingStreak*0.015, 0.95);
  const colProbs={};
  ['q1','q2','q3','q4'].forEach(k=>{
    const theo = k==='q1' ? 0.0702 : 0.0956;
    colProbs[k]=Math.min(theo + colStreaks[k]*0.005, 0.99);
  });
  const maxProb=Math.max(colProbs.q1,colProbs.q2,colProbs.q3,colProbs.q4);
  const dangerCols=[];
  if(colProbs.q1===maxProb)dangerCols.push("第1柱 (01-09)");
  if(colProbs.q2===maxProb)dangerCols.push("第2柱 (10-19)");
  if(colProbs.q3===maxProb)dangerCols.push("第3柱 (20-29)");
  if(colProbs.q4===maxProb)dangerCols.push("第4柱 (30-39)");
  return { tripleLosingStreak, tripleNextProb, colHits, colStreaks, colProbs, dangerCols, totalDraws:data.length };
}
```

## 6. 誠實備註(給實作者)
序列為獨立事件,以上「連槓→Z→加碼」「馬可夫反轉」本質是賭徒謬誤的量化包裝;
回測已證明擇時無法改變 EV(退水才是唯一實際變數)。本頁忠實移植其**計算與顯示**,
不代表其預測有效。頁面 UI 應保留原數字但可加中性說明。
