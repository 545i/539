import React, { createContext, useContext, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { ClipboardList, X, ChevronDown, ChevronRight, Trash2 } from 'lucide-react';
import { useAllLedger } from '../api/useLedger';
import { LedgerMode } from '../api/client';
import { BetRecord } from '../types';
import { MODE_LABEL } from './uploadHistory';
import { weekMonday, weekRangeLabel, distinctWeeks } from '../weeks';

// 帳單沿用(全策略共用一份):在「紀錄下注」各分頁的週選擇器右側挑選「之前週期」的任何帳單,
// 把它們的損益折進「本週損益 / 建議車支數」——常見情境:上週沒追回的赤字,想併進本週的
// 建議車數一起追。選取的是 ledger 紀錄的 id(全站唯一),五個分頁共用同一批。
//
// 資料源:useAllLedger 的 entries(登入才有;未登入沒有跨週帳單可沿用)。
// 折算方式見各下注分頁:carried = 沿用帳單中「不在目前聚焦週」的那些,carryPnl 併入 cumPnl。

const money = (n: number) => `${n >= 0 ? '+' : ''}${Math.round(n).toLocaleString()}`;
const fmtBalls = (balls: number[] | undefined) =>
  (balls ?? []).map(b => String(b).padStart(2, '0')).join(' ');

/** entry.record → BetRecord;id 用 ledger 的 id(沿用要靠它)。 */
function entryToRecord(id: number | string, record: Record<string, unknown>): BetRecord {
  return { ...(record as unknown as BetRecord), id: String(id), index: 0, cumPnl: 0 };
}

interface BillReuseValue {
  reuseIds: string[];               // 被沿用的 ledger 紀錄 id(已濾掉不存在的)
  reuseRecords: BetRecord[];        // 解析成實際紀錄(依目前 ledger cache)
  reusePnl: number;                 // 被沿用帳單的 pnl 合計
  count: number;                    // 已沿用幾筆
  isReused: (id: string) => boolean;
  toggle: (id: string) => void;
  setMany: (ids: string[], on: boolean) => void;
  clearAll: () => void;
}
const Ctx = createContext<BillReuseValue | null>(null);

/** 包在 <LedgerProvider> 內:管理「已沿用帳單」的 id 集合,並解析成實際紀錄。 */
export const BillReuseProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [ids, setIds] = useState<Set<string>>(() => new Set());
  const { entries } = useAllLedger();

  // 目前 ledger cache 的 id → 紀錄。作廢 / 清空後這裡會少掉,沿用清單自動跟著剔除。
  const byId = useMemo(() => {
    const m = new Map<string, BetRecord>();
    for (const e of entries) m.set(String(e.id), entryToRecord(e.id, e.record));
    return m;
  }, [entries]);

  const reuseIds = useMemo(() => Array.from(ids).filter(id => byId.has(id)), [ids, byId]);
  const reuseRecords = useMemo(
    () => reuseIds.map(id => byId.get(id)!).filter(Boolean),
    [reuseIds, byId],
  );
  const reusePnl = useMemo(
    () => reuseRecords.reduce((a, r) => a + (Number(r.pnl) || 0), 0),
    [reuseRecords],
  );

  const value = useMemo<BillReuseValue>(() => ({
    reuseIds,
    reuseRecords,
    reusePnl,
    count: reuseIds.length,
    isReused: (id: string) => ids.has(id),
    toggle: (id: string) =>
      setIds(prev => {
        const next = new Set(prev);
        next.has(id) ? next.delete(id) : next.add(id);
        return next;
      }),
    setMany: (list: string[], on: boolean) =>
      setIds(prev => {
        const next = new Set(prev);
        for (const id of list) (on ? next.add(id) : next.delete(id));
        return next;
      }),
    clearAll: () => setIds(new Set()),
  }), [reuseIds, reuseRecords, reusePnl, ids]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
};

export function useBillReuse(): BillReuseValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useBillReuse 必須包在 <BillReuseProvider> 內');
  return ctx;
}

const modeLabel = (m: string) => MODE_LABEL[m as LedgerMode] ?? m;

/** 週選擇器右側的「帳單沿用」按鈕 + 挑選彈窗。focusWeek = 目前聚焦週(排除,只列之前週期)。 */
export const BillReuseButton: React.FC<{ focusWeek: string }> = ({ focusWeek }) => {
  const { reuseRecords, reusePnl, count, isReused, toggle, setMany, clearAll } = useBillReuse();
  const { entries, loggedIn } = useAllLedger();
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());  // 直板機:週手風琴展開
  const [detailWeek, setDetailWeek] = useState<string>('');                // 寬板機:右側明細看哪一週
  const [modeFilter, setModeFilter] = useState<LedgerMode | 'all'>('all'); // 下法篩選

  // 可沿用的帳單 = 全部 ledger 紀錄中「不在目前聚焦週」的(之前 / 其他週期),新→舊;再套下法篩選。
  const all = useMemo(
    () => entries.map(e => entryToRecord(e.id, e.record)).filter(r => /^\d{4}-\d{2}-\d{2}/.test(String(r.date ?? ''))),
    [entries],
  );
  const pool = useMemo(
    () => all.filter(r => weekMonday(r.date) !== focusWeek && (modeFilter === 'all' || r.mode === modeFilter)),
    [all, focusWeek, modeFilter],
  );

  // 週 → 日 → 逐筆
  const weeks = useMemo(() => distinctWeeks(pool.map(r => r.date)).filter(Boolean), [pool]);
  const byWeek = useMemo(() => {
    const m = new Map<string, BetRecord[]>();
    for (const r of pool) {
      const wk = weekMonday(r.date);
      (m.get(wk) ?? m.set(wk, []).get(wk)!).push(r);
    }
    for (const list of m.values())
      list.sort((a, b) => String(a.date).localeCompare(String(b.date)));
    return m;
  }, [pool]);

  const toggleExpand = (wk: string) =>
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(wk) ? next.delete(wk) : next.add(wk);
      return next;
    });

  const idsOf = (rows: BetRecord[]) => rows.map(r => r.id);
  const allSelected = (rows: BetRecord[]) => rows.length > 0 && rows.every(r => isReused(r.id));
  const someSelected = (rows: BetRecord[]) => rows.some(r => isReused(r.id));
  const pnlOf = (rows: BetRecord[]) => rows.reduce((a, r) => a + (Number(r.pnl) || 0), 0);

  // 寬板機右側明細看哪一週:優先選中的那週,選中的已不存在(篩選/切週後)就退回最新一週。
  const activeWeek = (detailWeek && byWeek.has(detailWeek)) ? detailWeek : (weeks[0] ?? '');

  const FILTERS: { key: LedgerMode | 'all'; label: string }[] = [
    { key: 'all', label: '全部' },
    { key: 'single', label: '1組' },
    { key: 'multi', label: '2組' },
    { key: 'pillar1800', label: '1800碰' },
    { key: 'combo9000', label: '9000碰' },
    { key: 'combo', label: '連碰' },
  ];

  // 某週的「逐日 → 逐筆」明細(直板機手風琴 / 寬板機右欄共用)。
  const renderDetail = (rows: BetRecord[]) => {
    const days = Array.from(new Set(rows.map(r => r.date))).sort();
    if (rows.length === 0)
      return <div className="text-[11px] text-neutral-400 py-6 text-center">這週在目前篩選下沒有帳單。</div>;
    return days.map(day => {
      const dayRows = rows.filter(r => r.date === day);
      const dAll = allSelected(dayRows);
      const dSome = someSelected(dayRows);
      return (
        <div key={day} className="border-t border-black/[0.05] dark:border-white/[0.06] first:border-t-0">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-black/[0.01] dark:bg-white/[0.015]">
            <input
              type="checkbox"
              checked={dAll}
              ref={el => { if (el) el.indeterminate = !dAll && dSome; }}
              onChange={e => setMany(idsOf(dayRows), e.target.checked)}
              className="w-3.5 h-3.5 accent-indigo-600 shrink-0"
            />
            <span className="flex-1 text-[11px] font-mono text-neutral-500">{day.slice(5)}</span>
            <span className={`text-[10px] font-mono shrink-0 ${pnlOf(dayRows) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {money(pnlOf(dayRows))}
            </span>
          </div>
          {dayRows.map(r => (
            <label
              key={r.id}
              className="flex items-center gap-2 px-3 py-1.5 pl-6 cursor-pointer hover:bg-black/[0.03] dark:hover:bg-white/[0.04] transition-colors"
            >
              <input
                type="checkbox"
                checked={isReused(r.id)}
                onChange={() => toggle(r.id)}
                className="w-3.5 h-3.5 accent-indigo-600 shrink-0"
              />
              <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 shrink-0">
                {modeLabel(r.mode)}
              </span>
              <span className="text-[10px] font-mono text-neutral-500 truncate flex-1">
                {fmtBalls(r.selectedBalls) || r.result || '—'}
              </span>
              <span className="text-[10px] font-mono text-neutral-400 shrink-0">{money(-r.cost).replace('+', '')}</span>
              <span className={`text-[10px] font-mono font-bold shrink-0 ${r.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                {money(r.pnl)}
              </span>
            </label>
          ))}
        </div>
      );
    });
  };

  // 週清單的一列(標題:全選框 + 週標 + 損益);點列 → 直板機展開手風琴、寬板機切右欄明細。
  const renderWeekHeader = (wk: string, rows: BetRecord[]) => {
    const wkAll = allSelected(rows);
    const wkSome = someSelected(rows);
    const active = wk === activeWeek || expanded.has(wk);
    return (
      <div className={`flex items-center gap-2 px-3 py-2 transition-colors ${active ? 'bg-indigo-500/10' : 'bg-black/[0.02] dark:bg-white/[0.03]'}`}>
        <input
          type="checkbox"
          checked={wkAll}
          ref={el => { if (el) el.indeterminate = !wkAll && wkSome; }}
          onChange={e => setMany(idsOf(rows), e.target.checked)}
          className="w-4 h-4 accent-indigo-600 shrink-0"
        />
        <button
          type="button"
          onClick={() => { toggleExpand(wk); setDetailWeek(wk); }}
          className="flex-1 flex items-center gap-1.5 text-left text-[12px] font-semibold min-w-0"
        >
          {/* 直板機顯示展開箭頭;寬板機用右箭頭表示「看右欄明細」 */}
          <span className="md:hidden">{expanded.has(wk) ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}</span>
          <ChevronRight className="hidden md:inline w-3.5 h-3.5" />
          <span className="truncate">{weekRangeLabel(wk)}</span>
          <span className="text-[10px] font-mono font-normal text-neutral-400 shrink-0">{rows.length} 筆</span>
        </button>
        <span className={`text-[11px] font-mono font-bold shrink-0 ${pnlOf(rows) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
          {money(pnlOf(rows))}
        </span>
      </div>
    );
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="沿用之前週期的帳單,把它們的損益併進本週損益與建議車支數"
        className={`px-2 py-1 rounded-md text-[11px] font-semibold flex items-center gap-1 transition-colors ${
          count > 0
            ? 'bg-indigo-600 text-white hover:bg-indigo-700'
            : 'bg-black/[0.04] dark:bg-white/[0.06] text-neutral-600 dark:text-neutral-300 hover:bg-black/10 dark:hover:bg-white/10'
        }`}
      >
        <ClipboardList className="w-3.5 h-3.5" />
        帳單沿用
        {count > 0 && (
          <span className="font-mono">
            (已沿用帳單:{count}・{money(reusePnl)})
          </span>
        )}
      </button>

      {open && createPortal((
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg md:max-w-4xl lg:max-w-6xl 2xl:max-w-[88rem] max-h-[88vh] flex flex-col bg-white dark:bg-[#161616] rounded-2xl border border-black/10 dark:border-white/10 shadow-2xl text-neutral-800 dark:text-neutral-200 overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* 標題列 */}
            <div className="flex items-center justify-between gap-2 p-4 border-b border-black/[0.06] dark:border-white/[0.08]">
              <div className="flex items-center gap-2 text-sm font-bold">
                <ClipboardList className="w-4.5 h-4.5 text-indigo-500" />
                帳單沿用 · 挑之前週期的帳單併進本週
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="px-4 pt-3 text-[11px] text-neutral-500 dark:text-neutral-400 leading-relaxed">
              勾選的帳單(可整週 / 整日 / 逐筆)損益會併進<strong>本週損益與建議車支數</strong>,
              五個下注分頁共用同一批。只列「本週以外」的週期。
            </p>

            {/* 下法篩選:1組/2組/1800碰/9000碰/連碰 */}
            <div className="flex flex-wrap items-center gap-1.5 px-4 pt-2 pb-2">
              <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold mr-0.5">下法</span>
              {FILTERS.map(f => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => setModeFilter(f.key)}
                  className={`px-2 py-0.5 rounded-lg text-[10px] font-semibold transition-all ${
                    modeFilter === f.key
                      ? 'bg-black text-white dark:bg-white dark:text-black'
                      : 'border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            {/* 本體:直板機=單欄(週手風琴向下展開);寬板機=左右雙欄(明細由右側邊緣向右展開),
                左右各自獨立滾動。 */}
            <div className="flex-1 min-h-0 flex flex-col md:flex-row border-t border-black/[0.06] dark:border-white/[0.08]">
              {!loggedIn ? (
                <div className="flex-1 text-[11px] text-neutral-400 py-10 text-center">
                  未登入:沒有跨週帳單可沿用(帳單存在登入帳號)。
                </div>
              ) : weeks.length === 0 ? (
                <div className="flex-1 text-[11px] text-neutral-400 py-10 text-center">
                  本週以外沒有其他帳單可沿用(或此下法無紀錄)。
                </div>
              ) : (
                <>
                  {/* 左欄:週清單(獨立滾動);直板機填滿高度可捲,寬板機固定寬 */}
                  <div className="flex-1 min-h-0 md:flex-none md:w-72 lg:w-80 xl:w-96 md:shrink-0 md:border-r border-black/[0.06] dark:border-white/[0.08] overflow-y-auto p-3 space-y-2 md:space-y-0 md:p-0">
                    {weeks.map(wk => {
                      const rows = byWeek.get(wk) ?? [];
                      return (
                        <div
                          key={wk}
                          className="rounded-xl md:rounded-none border md:border-0 md:border-b border-black/[0.08] dark:border-white/[0.10] overflow-hidden"
                        >
                          {renderWeekHeader(wk, rows)}
                          {/* 直板機:手風琴內嵌明細(寬板機隱藏,改由右欄顯示) */}
                          {expanded.has(wk) && <div className="md:hidden">{renderDetail(rows)}</div>}
                        </div>
                      );
                    })}
                  </div>

                  {/* 右欄:明細(僅寬板機;由彈窗右側向右展開,獨立滾動) */}
                  <div className="hidden md:flex md:flex-col flex-1 min-w-0 overflow-y-auto">
                    {activeWeek ? (
                      <>
                        <div className="sticky top-0 z-10 flex items-center justify-between gap-2 px-3 py-2 bg-white dark:bg-[#161616] border-b border-black/[0.06] dark:border-white/[0.08]">
                          <span className="text-[12px] font-semibold truncate">{weekRangeLabel(activeWeek)} 明細</span>
                          <span className={`text-[11px] font-mono font-bold shrink-0 ${pnlOf(byWeek.get(activeWeek) ?? []) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                            {money(pnlOf(byWeek.get(activeWeek) ?? []))}
                          </span>
                        </div>
                        <div>{renderDetail(byWeek.get(activeWeek) ?? [])}</div>
                      </>
                    ) : (
                      <div className="flex-1 text-[11px] text-neutral-400 py-10 text-center">左側選一個週期看明細</div>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* 底部:合計 + 清空 + 完成 */}
            <div className="flex items-center justify-between gap-2 p-4 border-t border-black/[0.06] dark:border-white/[0.08]">
              <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
                已沿用 <strong className="text-neutral-800 dark:text-neutral-200">{count}</strong> 筆 · 合計損益{' '}
                <strong className={reuseRecords.length && reusePnl < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-emerald-600 dark:text-emerald-400'}>
                  {money(reusePnl)}
                </strong>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={clearAll}
                  disabled={count === 0}
                  className="py-2 px-3 rounded-xl text-xs font-semibold border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-40 transition-colors flex items-center gap-1"
                >
                  <Trash2 className="w-3.5 h-3.5" /> 清空
                </button>
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  className="py-2 px-4 rounded-xl text-xs font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity"
                >
                  完成
                </button>
              </div>
            </div>
          </div>
        </div>
      ), document.body)}
    </>
  );
};
