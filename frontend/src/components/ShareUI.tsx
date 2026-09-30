import React from 'react';

// 損益佔比共用 UI:佔比長條 + 分配清單(名字/佔比在左、金額在右,手機直排不擠)。
// 設定佔比彈窗、週期帳「本週損益佔比」、佔比帳單三處共用。
// 刻意近乎單色:層次靠字重 / 大小 / 灰階;顏色只留給「結算」(收付)這種真正要看的地方。

const signed = (v: number) => `${v > 0 ? '+' : v < 0 ? '-' : ''}$${Math.abs(Math.round(v)).toLocaleString()}`;
// 收付顏色(紅付綠收)—— 只在結算數字用
const pnlText = (v: number) =>
  v > 0 ? 'text-emerald-600 dark:text-emerald-400' : v < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-neutral-400';

// 佔比長條:灰階分段,highlight 那段(我 / 正在看的人)用前景色,其餘淺灰;段與段間留 1px 縫
export const ShareBar: React.FC<{ items: { name: string; pct: number }[]; highlight?: string; className?: string }> = ({ items, highlight, className }) => (
  <div className={`flex h-1.5 w-full gap-px overflow-hidden rounded-full ${className ?? ''}`}>
    {items.map((x, i) => x.pct > 0 && (
      <div key={x.name} title={`${x.name} ${x.pct}%`} style={{ width: `${Math.min(100, x.pct)}%` }}
        className={`h-full ${x.name === highlight
          ? 'bg-neutral-900 dark:bg-white'
          : i === 0 ? 'bg-neutral-400 dark:bg-neutral-500' : 'bg-neutral-300 dark:bg-neutral-700'}`} />
    ))}
  </div>
);

export interface AllocItem {
  name: string;
  pct?: number;        // 有給就顯示 xx%
  amount: number;
  highlight?: boolean; // 「我」:名字加粗、金額加大
  sub?: string;        // 名字下方小字(例如付/分、連動帳號)
}

// 分配清單:一人一列,金額靠右;highlight 那列(我)用字重與大小區分,不加色
export const AllocList: React.FC<{ items: AllocItem[] }> = ({ items }) => (
  <div className="divide-y divide-black/[0.05] dark:divide-white/[0.06]">
    {items.map(r => (
      <div key={r.name} className="flex items-center gap-2 py-1.5">
        <div className="min-w-0 flex-1">
          <div className={`truncate ${r.highlight ? 'text-[13px] font-bold text-neutral-900 dark:text-white' : 'text-[12px] text-neutral-600 dark:text-neutral-300'}`}>
            {r.name}{r.highlight && <span className="ml-1 text-[10px] font-normal text-neutral-400">(你)</span>}
            {r.pct !== undefined && <span className="ml-1.5 text-[11px] font-mono font-normal text-neutral-400">{r.pct}%</span>}
          </div>
          {r.sub && <div className="text-[10px] text-neutral-400 font-mono truncate">{r.sub}</div>}
        </div>
        <span className={`font-mono shrink-0 ${r.highlight ? 'text-base font-bold text-neutral-900 dark:text-white' : 'text-[13px] font-semibold text-neutral-700 dark:text-neutral-200'}`}>
          {signed(r.amount)}
        </span>
      </div>
    ))}
  </div>
);

// 大數字統計(標籤在上、數字大字;不加框、不上色)
export const StatTile: React.FC<{ label: string; value: React.ReactNode; big?: boolean }> = ({ label, value, big }) => (
  <div className="min-w-0">
    <div className="text-[10px] text-neutral-500 dark:text-neutral-400">{label}</div>
    <div className={`font-mono font-bold truncate text-neutral-900 dark:text-white ${big ? 'text-2xl' : 'text-lg'}`}>{value}</div>
  </div>
);

export const fmtSigned = signed;
export const pnlTone = pnlText;
