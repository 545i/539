import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { weekMonday, weekAddDays, weekRangeLabel, distinctWeeks } from '../weeks';

// 流水週導覽(各下注分頁共用):‹ › 方向鍵依「日曆」一週一週前後移(不管該週有沒有
// 紀錄都能移),中間顯示「第 N 週(MMDD~MMDD)」;點中間切「全部週」。

interface WithDate { date: string; cost: number; payout: number; }

/** 週導覽狀態 + 依聚焦週過濾出的 flowRecords。records 需帶 date/cost/payout。 */
export function useWeekNav<T extends WithDate>(records: T[]) {
  const [focusMonday, setFocusMonday] = React.useState(''); // '' = 自動聚焦最新有紀錄的週
  const [allWeeks, setAllWeeks] = React.useState(false);
  const weekKeys = distinctWeeks(records.map(r => r.date)).filter(Boolean); // 有紀錄的週(新→舊)
  const todayMonday = weekMonday(new Date().toISOString().slice(0, 10));
  const focusWeek = focusMonday || weekKeys[0] || todayMonday;    // 預設:最新有紀錄的週 / 本週
  const goWeek = (deltaWeeks: number) => {
    setAllWeeks(false);
    setFocusMonday(weekAddDays(focusWeek, deltaWeeks * 7));
  };
  const canNext = focusWeek < todayMonday;                        // 不讓跳到未來週
  const flowRecords = allWeeks ? records : records.filter(r => weekMonday(r.date) === focusWeek);
  const label = allWeeks ? '全部週' : weekRangeLabel(focusWeek);
  return { focusWeek, allWeeks, setAllWeeks, goWeek, canNext, flowRecords, label };
}

export const WeekNav: React.FC<{
  focusWeek: string;
  allWeeks: boolean;
  canNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  onToggleAll: () => void;
}> = ({ focusWeek, allWeeks, canNext, onPrev, onNext, onToggleAll }) => (
  <div className="flex items-center gap-1">
    <button
      type="button"
      onClick={onPrev}
      title="上一週(較舊)"
      className="w-6 h-6 flex items-center justify-center rounded-md text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
    >
      <ChevronLeft className="w-4 h-4" />
    </button>
    <button
      type="button"
      onClick={onToggleAll}
      title={allWeeks ? '點此改看單週' : '點此看全部週'}
      className={`px-2 py-1 rounded-md text-[11px] font-mono font-semibold min-w-[8.5rem] text-center transition-colors ${
        allWeeks
          ? 'bg-black text-white dark:bg-white dark:text-black'
          : 'bg-black/[0.04] dark:bg-white/[0.06] text-neutral-800 dark:text-neutral-100 hover:bg-black/10 dark:hover:bg-white/10'
      }`}
    >
      {allWeeks ? '全部週' : weekRangeLabel(focusWeek)}
    </button>
    <button
      type="button"
      onClick={onNext}
      disabled={!allWeeks && !canNext}
      title="下一週(較新)"
      className="w-6 h-6 flex items-center justify-center rounded-md text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 transition-colors"
    >
      <ChevronRight className="w-4 h-4" />
    </button>
  </div>
);

/** 該週(或全部週)小計:局數 / 過關 / 投入 / 回收 / 損益。 */
export const WeekSubtotal: React.FC<{
  records: { cost: number; payout: number }[];
  label: string;
  unit?: string;
}> = ({ records, label, unit = '局' }) => {
  if (records.length === 0) return null;
  const cost = records.reduce((a, r) => a + r.cost, 0);
  const ret = records.reduce((a, r) => a + r.payout, 0);
  const win = records.filter(r => r.payout > 0).length;
  const pnl = ret - cost;
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] font-mono text-neutral-500 dark:text-neutral-400">
      <span className="font-sans font-semibold text-neutral-600 dark:text-neutral-300">{label}</span>
      <span>{records.length} {unit}・過關 {win}</span>
      <span>投入 <span className="text-neutral-800 dark:text-neutral-200 font-bold">{cost.toLocaleString()}</span></span>
      <span>回收 <span className="text-emerald-600 dark:text-emerald-400 font-bold">{ret.toLocaleString()}</span></span>
      <span>損益 <span className={`font-bold ${pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{pnl >= 0 ? '+' : ''}{pnl.toLocaleString()}</span></span>
    </div>
  );
};
