// 損益佔比分配(每個版一組以上:本人 + 往下分的人,佔比總和固定 100%)。
//
// 佔比可以中途加入 / 變更:每組有「生效日」since('' = 從最早起),某天的損益套用
// 「since ≤ 當天」最新那組。沒有任何一組生效的日子 = 本人 100%。
//
// 金額守恆:先把總損益四捨五入成整數 T(與全站 money() 同一種 Math.round),
// 各人精確應得 = Σ(各段損益 × 該段佔比);先全部取整數部分(floor),差的幾塊依
// 「小數部分大→小」一塊一塊補(最大餘數法,同分時本人/排前面的先拿)。
// 所以各人金額加總永遠 = T,不會出現 ±1 的尾差。一週內佔比改過也一樣,
// 是整週一起湊,不是每天各自四捨五入再相加。
// 全程整數運算:損益換成「分」(×100)、佔比用萬分點 bps,精確值單位 = 1/1e6 元。

export interface ShareDTO {
  name: string;
  pct: number;     // 百分比,最多兩位小數
  self: boolean;   // 本人
}
export interface ShareVersionDTO {
  since: string;   // 生效日 YYYY-MM-DD;'' = 從最早起
  shares: ShareDTO[];
}
export interface AllocRow { name: string; self: boolean; amount: number; }

export const pctToBps = (pct: number): number => Math.round(pct * 100);

const SELF_ONLY: ShareDTO[] = [{ name: '本人', pct: 100, self: true }];
const SCALE = 100 * 10000;   // 分 × bps

// 某天適用的佔比(since ≤ ymd 的最新一組);versions 需依 since 舊→新。
export function sharesOn(versions: ShareVersionDTO[] | undefined, ymd: string): ShareVersionDTO {
  let hit: ShareVersionDTO = { since: '', shares: SELF_ONLY };
  for (const v of versions ?? []) if (v.since <= ymd) hit = v;
  return hit;
}

// 多段損益(每段各自一組佔比)合併分配;回傳依首次出現順序(本人一定第一)。
export function allocateSegments(segs: { pnl: number; shares: ShareDTO[] }[]): AllocRow[] {
  const total = segs.reduce((a, s) => a + s.pnl, 0);
  const T = Math.round(total) || 0;
  const order: string[] = ['本人'];
  const exact = new Map<string, number>([['本人', 0]]);   // 單位 1/SCALE 元
  for (const s of segs) {
    const cents = Math.round(s.pnl * 100);
    for (const sh of s.shares) {
      if (!exact.has(sh.name)) { exact.set(sh.name, 0); order.push(sh.name); }
      const v = cents * pctToBps(sh.pct);
      exact.set(sh.name, exact.get(sh.name)! + v);
    }
  }
  // 各段佔比總和 100% → 精確值加總 = 總損益;取整後差的幾塊用最大餘數補齊
  const parts = order.map((name, i) => {
    const v = exact.get(name)!;
    const floor = Math.floor(v / SCALE);
    return { i, name, floor, rem: v - floor * SCALE };
  });
  let left = T - parts.reduce((a, p) => a + p.floor, 0);
  const byRem = [...parts].sort((a, b) => b.rem - a.rem || a.i - b.i);
  for (const p of byRem) {
    if (left <= 0) break;
    p.floor += 1;
    left -= 1;
  }
  return parts.map(p => ({ name: p.name, self: p.name === '本人', amount: p.floor || 0 }));
}

// 單段(一組佔比)分配,附上各人佔比 —— 設定頁試算用。
export function allocatePnl(total: number, shares: ShareDTO[]): (ShareDTO & { amount: number })[] {
  const rows = allocateSegments([{ pnl: total, shares }]);
  return shares.map(s => ({ ...s, amount: rows.find(r => r.name === s.name)?.amount ?? 0 }));
}
