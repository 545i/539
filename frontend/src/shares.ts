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
  pct: number;       // 百分比,最多兩位小數
  self: boolean;     // 本人(版主)
  account?: string;  // 連動帳號(版主自己看才有;被連動者看不到)
  me?: boolean;      // 佔比帳單:這一筆是「我」
}
export interface ShareVersionDTO {
  since: string;   // 生效日 YYYY-MM-DD;'' = 從最早起
  shares: ShareDTO[];
}
export interface AllocRow { name: string; self: boolean; amount: number; }

export const pctToBps = (pct: number): number => Math.round(pct * 100);

export const SELF_ONLY: ShareDTO[] = [{ name: '本人', pct: 100, self: true }];
const SCALE = 100 * 10000;   // 分 × bps

// 某天適用的佔比(since ≤ ymd 的最新一組);versions 需依 since 舊→新。
export function sharesOn(versions: ShareVersionDTO[] | undefined, ymd: string): ShareVersionDTO {
  let hit: ShareVersionDTO = { since: '', shares: SELF_ONLY };
  for (const v of versions ?? []) if (v.since <= ymd) hit = v;
  return hit;
}

// 某版某段期間的逐日盈虧 → 依生效日切段(同一組佔比的日子併成一段,附起訖日)。
export interface DaySegment { since: string; shares: ShareDTO[]; pnl: number; from: string; to: string; }
export function daySegments(days: Iterable<[string, number]>, versions: ShareVersionDTO[] | undefined): DaySegment[] {
  const segMap = new Map<string, DaySegment>();
  for (const [ymd, pnl] of Array.from(days).sort((a, b) => a[0].localeCompare(b[0]))) {
    const v = sharesOn(versions, ymd);
    const seg = segMap.get(v.since) ?? { since: v.since, shares: v.shares, pnl: 0, from: ymd, to: ymd };
    seg.pnl += pnl; seg.to = ymd;
    segMap.set(v.since, seg);
  }
  return Array.from(segMap.values());
}

// 多段損益(每段各自一組佔比)合併分配;回傳依首次出現順序(本人一定第一)。
export function allocateSegments(segs: { pnl: number; shares: ShareDTO[] }[]): AllocRow[] {
  // 總額一律用「分」整數加總再四捨五入 —— 浮點直接加會把 x.5 算成 x.4999…,差 1 元
  const totalCents = segs.reduce((a, s) => a + Math.round(s.pnl * 100), 0);
  const T = Math.round(totalCents / 100) || 0;
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

// 成本 / 派彩分開守恆分配:每人「應付成本」加總 = 該版成本、「應分派彩」加總 = 該版派彩,
// 淨額 = 應分派彩 − 應付成本(加總 = 派彩 − 成本)。days = 逐日 {cost, payout}。
// 佔比帳單要讓合夥人看清楚「要付多少、分到多少」,週期帳的分配也用這套,兩邊數字一致。
export interface DayMoney { cost: number; payout: number; }
export interface SplitRow { name: string; self: boolean; cost: number; payout: number; net: number; }
export interface SplitSeg { since: string; shares: ShareDTO[]; from: string; to: string; cost: number; payout: number; }
export function splitCostPayout(days: Map<string, DayMoney>, versions: ShareVersionDTO[] | undefined) {
  const entries = Array.from(days.entries());
  const costSegs = daySegments(entries.map(([d, m]) => [d, m.cost] as [string, number]), versions);
  const paySegs = daySegments(entries.map(([d, m]) => [d, m.payout] as [string, number]), versions);
  const costRows = allocateSegments(costSegs);
  const payRows = allocateSegments(paySegs);
  const rows: SplitRow[] = costRows.map(c => {
    const payout = payRows.find(p => p.name === c.name)?.amount ?? 0;
    return { name: c.name, self: c.self, cost: c.amount, payout, net: payout - c.amount };
  });
  const segs: SplitSeg[] = costSegs.map((s, i) => ({
    since: s.since, shares: s.shares, from: s.from, to: s.to, cost: s.pnl, payout: paySegs[i]?.pnl ?? 0,
  }));
  const cost = rows.reduce((a, r) => a + r.cost, 0);
  const payout = rows.reduce((a, r) => a + r.payout, 0);
  return { rows, segs, cost, payout, net: payout - cost };
}
