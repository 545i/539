// 損益佔比分配(每個版一組:本人 + 往下分的人,佔比總和固定 100%)。
//
// 金額守恆:先把總損益四捨五入成整數 T,各人理論值 = |T| × 佔比;先全部取整數部分,
// 差的幾塊依「小數部分大→小」一塊一塊補(最大餘數法,同分時本人/排前面的先拿)。
// 所以各人金額加總永遠 = T,不會出現 ±1 的尾差。負數(虧損)用絕對值分完再補負號。
// 全程整數運算(佔比用萬分點 bps),不吃浮點誤差。

export interface ShareDTO {
  name: string;
  pct: number;     // 百分比,最多兩位小數
  self: boolean;   // 本人
}

export const pctToBps = (pct: number): number => Math.round(pct * 100);

export function allocatePnl(total: number, shares: ShareDTO[]): { name: string; pct: number; self: boolean; amount: number }[] {
  const T = Math.round(total) || 0;   // 與全站 money() 同一種四捨五入,畫面上的總額 = 分配加總
  const abs = Math.abs(T);
  const sign = T < 0 ? -1 : 1;
  const parts = shares.map((s, i) => {
    const prod = abs * pctToBps(s.pct);           // |T| × bps,整數
    return { i, floor: Math.floor(prod / 10000), rem: prod % 10000 };
  });
  let left = abs - parts.reduce((a, p) => a + p.floor, 0);
  const order = [...parts].sort((a, b) => b.rem - a.rem || a.i - b.i);
  for (const p of order) {
    if (left <= 0) break;
    p.floor += 1;
    left -= 1;
  }
  return shares.map((s, i) => ({ ...s, amount: sign * parts[i].floor || 0 }));
}
