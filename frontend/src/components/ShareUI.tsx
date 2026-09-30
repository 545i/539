import React from 'react';

// 損益佔比共用 UI:佔比長條 + 分配清單(名字/佔比在左、大字金額在右,手機直排不擠)。
// 設定佔比彈窗、週期帳「本週損益佔比」、佔比帳單三處共用,顏色依人在該組的順序固定。

// 本人固定紫色;其他人依序輪色
const PALETTE = ['bg-violet-500', 'bg-emerald-500', 'bg-sky-500', 'bg-amber-500', 'bg-rose-500', 'bg-teal-500', 'bg-fuchsia-500', 'bg-lime-500'];
export const shareColor = (i: number) => PALETTE[i % PALETTE.length];

const pnlText = (v: number) =>
  v > 0 ? 'text-emerald-600 dark:text-emerald-400' : v < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-neutral-400';
const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '-' : ''}$${Math.abs(Math.round(v)).toLocaleString()}`;

// 佔比長條:各人依 pct 佔寬度;pct 0 的不畫
export const ShareBar: React.FC<{ items: { name: string; pct: number }[]; className?: string }> = ({ items, className }) => (
  <div className={`flex h-2.5 w-full overflow-hidden rounded-full bg-black/[0.06] dark:bg-white/[0.08] ${className ?? ''}`}>
    {items.map((x, i) => x.pct > 0 && (
      <div key={x.name} className={`${shareColor(i)} h-full`} style={{ width: `${Math.min(100, x.pct)}%` }} title={`${x.name} ${x.pct}%`} />
    ))}
  </div>
);

export interface AllocItem {
  name: string;
  pct?: number;        // 有給就顯示 (xx%)
  amount: number;
  highlight?: boolean; // 「我」:名字上色、金額加大
  sub?: string;        // 名字下方小字(例如連動帳號)
}

// 分配清單:一人一列,金額靠右大字;highlight 那列(我)名字上色 + 金額加大(不加框)
export const AllocList: React.FC<{ items: AllocItem[]; colorIndex?: (name: string, i: number) => number }> = ({ items, colorIndex }) => (
  <div className="divide-y divide-black/[0.05] dark:divide-white/[0.06]">
    {items.map((r, i) => (
      <div key={r.name}
        className="flex items-center gap-2 py-1.5">
        <span className={`w-2 h-2 rounded-full shrink-0 ${shareColor(colorIndex ? colorIndex(r.name, i) : i)}`} />
        <div className="min-w-0 flex-1">
          <div className={`truncate ${r.highlight ? 'text-[13px] font-bold text-violet-600 dark:text-violet-400' : 'text-[12px] text-neutral-700 dark:text-neutral-200'}`}>
            {r.name}{r.highlight && <span className="ml-1 text-[10px] font-normal">(你)</span>}
            {r.pct !== undefined && <span className="ml-1 text-[11px] font-mono font-normal text-neutral-400">{r.pct}%</span>}
          </div>
          {r.sub && <div className="text-[10px] text-neutral-400 font-mono truncate">{r.sub}</div>}
        </div>
        <span className={`font-mono font-bold shrink-0 ${r.highlight ? 'text-base' : 'text-[13px]'} ${pnlText(r.amount)}`}>
          {signed(r.amount)}
        </span>
      </div>
    ))}
  </div>
);

// 大數字統計(標籤在上、數字大字;不加框)
export const StatTile: React.FC<{ label: string; value: React.ReactNode; tone?: number; big?: boolean }> = ({ label, value, tone, big }) => (
  <div className="min-w-0">
    <div className="text-[10px] text-neutral-500 dark:text-neutral-400">{label}</div>
    <div className={`font-mono font-bold truncate ${big ? 'text-2xl' : 'text-lg'} ${tone !== undefined ? pnlText(tone) : 'text-neutral-900 dark:text-white'}`}>
      {value}
    </div>
  </div>
);

export const fmtSigned = signed;
export const pnlTone = pnlText;
