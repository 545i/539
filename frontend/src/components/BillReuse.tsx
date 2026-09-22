import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ClipboardList, X, ChevronDown, ChevronRight, RotateCcw } from 'lucide-react';
import { useAllLedger } from '../api/useLedger';
import { useEditions } from '../api/useEditions';
import { api, LedgerMode } from '../api/client';
import { BetRecord } from '../types';
import { MODE_LABEL } from './uploadHistory';
import { weekMonday, weekRangeLabel, distinctWeeks } from '../weeks';

// 整合「帳單挑選」= 一次調整要算進「建議車支數」赤字基準的帳單:
//   · 本週帳單:預設納入,取消勾選 = 排除(寫 excludedIds,原「排除變更」語意)
//   · 之前週期:預設不納入,勾選 = 沿用併入(寫 reuseSet,原「帳單沿用」語意)
// 沿用集合與排除一樣存到帳號(跨裝置):BillReuseProvider 登入後從 api.recoverReuseGet 載入,
// 按「儲存並套用」時 api.recoverReuseSet 覆寫。排除的儲存仍由 WeeklyLedger 管、以 props 傳入。
// 赤字過濾維持:!excludedIds && (本週 || reuseSet)。

const money = (n: number) => `${n >= 0 ? '+' : ''}${Math.round(n).toLocaleString()}`;
const fmtBalls = (balls: number[] | undefined) =>
  (balls ?? []).map(b => String(b).padStart(2, '0')).join(' ');

/** entry.record → BetRecord;id 用 ledger 的 id(沿用/排除都靠它)。 */
function entryToRecord(id: number | string, record: Record<string, unknown>): BetRecord {
  return { ...(record as unknown as BetRecord), id: String(id), index: 0, cumPnl: 0 };
}

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

interface BillReuseValue {
  reuseIds: string[];               // 被沿用的 ledger 紀錄 id(已濾掉不存在的)
  reuseRecords: BetRecord[];        // 解析成實際紀錄(依目前 ledger cache)
  reusePnl: number;                 // 被沿用帳單的 pnl 合計
  count: number;                    // 已沿用幾筆
  isReused: (id: string) => boolean;
  toggle: (id: string) => void;
  setMany: (ids: string[], on: boolean) => void;
  clearAll: () => void;
  reuseDirty: boolean;              // 有未存到帳號的沿用變更
  reuseSaveState: SaveState;
  saveReuse: () => void;            // 把沿用清單存到帳號(跨裝置)
}
const Ctx = createContext<BillReuseValue | null>(null);

/** 包在 <LedgerProvider> 內:管理「已沿用帳單」的 id 集合(登入後同步帳號),並解析成實際紀錄。 */
export const BillReuseProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [ids, setIds] = useState<Set<string>>(() => new Set());
  const [savedIds, setSavedIds] = useState<Set<string>>(() => new Set());   // 上次存到帳號的那份
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const loadedRef = useRef(false);
  const { entries, loggedIn } = useAllLedger();

  // 登入後從帳號載入沿用清單(跨裝置);只載一次。
  useEffect(() => {
    if (!loggedIn || loadedRef.current) return;
    loadedRef.current = true;
    let alive = true;
    api.recoverReuseGet()
      .then(r => { if (alive) { const s = new Set((r.ids ?? []).map(String)); setIds(s); setSavedIds(new Set(s)); } })
      .catch(() => { /* 讀不到就用空的 */ });
    return () => { alive = false; };
  }, [loggedIn]);

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
  // 有沒有未存到帳號的變更(比對目前集合 vs 上次存的)
  const reuseDirty = useMemo(() => {
    if (ids.size !== savedIds.size) return true;
    for (const id of ids) if (!savedIds.has(id)) return true;
    return false;
  }, [ids, savedIds]);

  const mutate = (fn: (s: Set<string>) => void) =>
    setIds(prev => { const next = new Set(prev); fn(next); return next; });

  const value = useMemo<BillReuseValue>(() => ({
    reuseIds,
    reuseRecords,
    reusePnl,
    count: reuseIds.length,
    isReused: (id: string) => ids.has(id),
    toggle: (id: string) => { mutate(s => { s.has(id) ? s.delete(id) : s.add(id); }); setSaveState('idle'); },
    setMany: (list: string[], on: boolean) => { mutate(s => { for (const id of list) (on ? s.add(id) : s.delete(id)); }); setSaveState('idle'); },
    clearAll: () => { setIds(new Set()); setSaveState('idle'); },
    reuseDirty,
    reuseSaveState: saveState,
    saveReuse: async () => {
      setSaveState('saving');
      try {
        await api.recoverReuseSet(reuseIds);
        setIds(new Set(reuseIds));          // 順手剔除已不存在的 id
        setSavedIds(new Set(reuseIds));
        setSaveState('saved');
        setTimeout(() => setSaveState(s => (s === 'saved' ? 'idle' : s)), 2500);
      } catch {
        setSaveState('error');
      }
    },
  }), [reuseIds, reuseRecords, reusePnl, ids, reuseDirty, saveState]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
};

export function useBillReuse(): BillReuseValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useBillReuse 必須包在 <BillReuseProvider> 內');
  return ctx;
}

const modeLabel = (m: string) => MODE_LABEL[m as LedgerMode] ?? m;
// 遊戲短名(record.game 是完整中文名,篩選鈕用短名比較省版面)
const gameShort = (g: string) =>
  g.includes('539') ? '539'
    : (g.includes('天天樂') || g.includes('Fantasy')) ? '天天樂'
    : g.includes('六合') ? '六合彩' : g;
const chipCls = (active: boolean) =>
  `px-2 py-0.5 rounded-lg text-[10px] font-semibold transition-all ${
    active
      ? 'bg-black text-white dark:bg-white dark:text-black'
      : 'border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
  }`;

interface BillPickerProps {
  focusWeek: string;                              // 目前聚焦週(本週,預設納入)
  // 以下排除相關由 WeeklyLedger 傳入;已從導覽移除的策略分頁沒有排除狀態,故選用 + 安全預設。
  excluded?: Set<string>;                         // 本週被排除的 id
  onToggleExclude?: (id: string) => void;         // 切換本週某筆排除
  onExcludeMany?: (ids: string[], excluded: boolean) => void;  // 批次設定本週排除
  excludeDirty?: boolean;
  excludeSaveState?: SaveState;
  onSaveExclude?: () => void;                      // 把排除清單存到帳號
}

const EMPTY_EXCLUDED: Set<string> = new Set();

/** 週選擇器右側的「帳單挑選」按鈕 + 整合挑選彈窗。 */
export const BillReuseButton: React.FC<BillPickerProps> = ({
  focusWeek,
  excluded = EMPTY_EXCLUDED,
  onToggleExclude = () => {},
  onExcludeMany = () => {},
  excludeDirty = false,
  excludeSaveState = 'idle',
  onSaveExclude = () => {},
}) => {
  const { isReused, toggle, setMany, clearAll, reuseDirty, reuseSaveState, saveReuse } = useBillReuse();
  const { entries, loggedIn } = useAllLedger();
  const { editions } = useEditions();
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());  // 直板機:週手風琴展開
  const [detailWeek, setDetailWeek] = useState<string>('');                // 寬板機:右側明細看哪一週
  const [modeFilter, setModeFilter] = useState<LedgerMode | 'all'>('all'); // 下法篩選
  const [edFilter, setEdFilter] = useState<number | 'all'>('all');         // 板名(版)篩選
  const [gameFilter, setGameFilter] = useState<string>('all');             // 遊戲篩選

  const isFocusWk = (wk: string) => wk === focusWeek;
  // 某筆是否「算進赤字」:本週 = 沒被排除;之前週期 = 有勾沿用。
  const included = (r: BetRecord) => (isFocusWk(weekMonday(r.date)) ? !excluded.has(r.id) : isReused(r.id));

  const all = useMemo(
    () => entries.map(e => entryToRecord(e.id, e.record)).filter(r => /^\d{4}-\d{2}-\d{2}/.test(String(r.date ?? ''))),
    [entries],
  );
  const edOf = (r: BetRecord) => Number(r.edition) || 1;
  const edName = (eid: number) => editions.find(e => e.eid === eid)?.name ?? `版${eid}`;
  const edOptions = useMemo(() => Array.from(new Set(all.map(edOf))).sort((a, b) => a - b), [all]);
  const gameOptions = useMemo(() => Array.from(new Set(all.map(r => r.game).filter(Boolean))), [all]);
  const passFilters = (r: BetRecord) =>
    (modeFilter === 'all' || r.mode === modeFilter) &&
    (edFilter === 'all' || edOf(r) === edFilter) &&
    (gameFilter === 'all' || r.game === gameFilter);

  // 池:本週 + 之前週期都納入(供瀏覽/勾選);再套三個篩選。
  const pool = useMemo(() => all.filter(passFilters), [all, modeFilter, edFilter, gameFilter]);
  const byWeek = useMemo(() => {
    const m = new Map<string, BetRecord[]>();
    for (const r of pool) {
      const wk = weekMonday(r.date);
      (m.get(wk) ?? m.set(wk, []).get(wk)!).push(r);
    }
    for (const list of m.values()) list.sort((a, b) => String(a.date).localeCompare(String(b.date)));
    return m;
  }, [pool]);
  // 週序:本週釘最前,其餘之前週期新→舊。
  const weeks = useMemo(() => {
    const others = distinctWeeks(pool.filter(r => !isFocusWk(weekMonday(r.date))).map(r => r.date)).filter(Boolean);
    return byWeek.has(focusWeek) ? [focusWeek, ...others] : others;
  }, [pool, byWeek, focusWeek]);

  // 摘要(跨版整體;真正的建議車支數在各卡即時重算)。用「全部紀錄」不受篩選影響。
  const summary = useMemo(() => {
    const focusAll = all.filter(r => isFocusWk(weekMonday(r.date)));
    const reuseAll = all.filter(r => !isFocusWk(weekMonday(r.date)));
    const focusIncl = focusAll.filter(r => !excluded.has(r.id));
    const reuseIncl = reuseAll.filter(r => isReused(r.id));
    const focusPnl = focusIncl.reduce((a, r) => a + (Number(r.pnl) || 0), 0);
    const reusePnlV = reuseIncl.reduce((a, r) => a + (Number(r.pnl) || 0), 0);
    return {
      focusPnl, reusePnl: reusePnlV, deficit: focusPnl + reusePnlV,
      focusCount: focusIncl.length, excludedCount: focusAll.length - focusIncl.length,
      reuseCount: reuseIncl.length,
    };
  }, [all, excluded, focusWeek, isReused]);

  const toggleExpand = (wk: string) =>
    setExpanded(prev => { const next = new Set(prev); next.has(wk) ? next.delete(wk) : next.add(wk); return next; });

  const idsOf = (rows: BetRecord[]) => rows.map(r => r.id);
  const allSelected = (rows: BetRecord[]) => rows.length > 0 && rows.every(included);
  const someSelected = (rows: BetRecord[]) => rows.some(included);
  const pnlOf = (rows: BetRecord[]) => rows.reduce((a, r) => a + (Number(r.pnl) || 0), 0);
  // 批次設「納入 on / 不納入」:本週走排除、之前週期走沿用。
  const setRows = (wk: string, rows: BetRecord[], on: boolean) =>
    isFocusWk(wk) ? onExcludeMany(idsOf(rows), !on) : setMany(idsOf(rows), on);
  const toggleOne = (wk: string, id: string) => (isFocusWk(wk) ? onToggleExclude(id) : toggle(id));

  const activeWeek = (detailWeek && byWeek.has(detailWeek)) ? detailWeek : (weeks[0] ?? '');

  const FILTERS: { key: LedgerMode | 'all'; label: string }[] = [
    { key: 'all', label: '全部' }, { key: 'single', label: '1組' }, { key: 'multi', label: '2組' },
    { key: 'pillar1800', label: '1800碰' }, { key: 'combo9000', label: '9000碰' }, { key: 'combo', label: '連碰' },
  ];

  // 某週明細(逐日 → 逐筆)。本週:勾=納入(取消=排除);之前週期:勾=沿用。
  const renderDetail = (wk: string, rows: BetRecord[]) => {
    const focus = isFocusWk(wk);
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
              type="checkbox" checked={dAll}
              ref={el => { if (el) el.indeterminate = !dAll && dSome; }}
              onChange={e => setRows(wk, dayRows, e.target.checked)}
              className={`w-3.5 h-3.5 shrink-0 ${focus ? 'accent-emerald-600' : 'accent-indigo-600'}`}
            />
            <span className="flex-1 text-[11px] font-mono text-neutral-500">{day.slice(5)}</span>
            <span className={`text-[10px] font-mono shrink-0 ${pnlOf(dayRows) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {money(pnlOf(dayRows))}
            </span>
          </div>
          {dayRows.map(r => {
            const on = included(r);
            const tag = focus
              ? (on ? null : <span className="px-1 py-0.5 rounded text-[9px] font-semibold bg-rose-500/12 text-rose-600 dark:text-rose-400 shrink-0">已排除</span>)
              : (on ? <span className="px-1 py-0.5 rounded text-[9px] font-semibold bg-indigo-500/15 text-indigo-600 dark:text-indigo-400 shrink-0">已沿用</span> : null);
            return (
              <label key={r.id} className={`flex items-center gap-2 px-3 py-1.5 pl-6 cursor-pointer hover:bg-black/[0.03] dark:hover:bg-white/[0.04] transition-colors ${!on ? 'opacity-55' : ''}`}>
                <input
                  type="checkbox" checked={on}
                  onChange={() => toggleOne(wk, r.id)}
                  className={`w-3.5 h-3.5 shrink-0 ${focus ? 'accent-emerald-600' : 'accent-indigo-600'}`}
                />
                <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-black/[0.06] dark:bg-white/10 text-neutral-600 dark:text-neutral-300 shrink-0">{modeLabel(r.mode)}</span>
                <span className="px-1 py-0.5 rounded text-[9px] bg-black/[0.04] dark:bg-white/[0.06] text-neutral-500 shrink-0">{gameShort(String(r.game ?? ''))}</span>
                <span className={`text-[10px] font-mono text-neutral-500 truncate flex-1 ${!on ? 'line-through' : ''}`}>
                  {fmtBalls(r.selectedBalls) || r.result || '—'}
                </span>
                {tag}
                <span className={`text-[10px] font-mono font-bold shrink-0 ${r.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{money(r.pnl)}</span>
              </label>
            );
          })}
        </div>
      );
    });
  };

  const renderWeekHeader = (wk: string, rows: BetRecord[]) => {
    const focus = isFocusWk(wk);
    const wkAll = allSelected(rows);
    const wkSome = someSelected(rows);
    const active = wk === activeWeek || expanded.has(wk);
    return (
      <div className={`flex items-center gap-2 px-3 py-2 transition-colors ${
        active ? (focus ? 'bg-emerald-500/10' : 'bg-indigo-500/10')
               : (focus ? 'bg-emerald-500/[0.05]' : 'bg-black/[0.02] dark:bg-white/[0.03]')
      }`}>
        <input
          type="checkbox" checked={wkAll}
          ref={el => { if (el) el.indeterminate = !wkAll && wkSome; }}
          onChange={e => setRows(wk, rows, e.target.checked)}
          className={`w-4 h-4 shrink-0 ${focus ? 'accent-emerald-600' : 'accent-indigo-600'}`}
        />
        <button type="button" onClick={() => { toggleExpand(wk); setDetailWeek(wk); }}
          className="flex-1 flex items-center gap-1.5 text-left text-[12px] font-semibold min-w-0">
          <span className="md:hidden">{expanded.has(wk) ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}</span>
          <ChevronRight className="hidden md:inline w-3.5 h-3.5" />
          <span className="truncate">{weekRangeLabel(wk)}</span>
          {focus
            ? <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 shrink-0">本週 · 預設納入</span>
            : <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-500/12 text-indigo-600 dark:text-indigo-400 shrink-0">之前週期</span>}
          <span className="text-[10px] font-mono font-normal text-neutral-400 shrink-0">{rows.filter(included).length}/{rows.length}</span>
        </button>
        <span className={`text-[11px] font-mono font-bold shrink-0 ${pnlOf(rows) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{money(pnlOf(rows))}</span>
      </div>
    );
  };

  const dirty = excludeDirty || reuseDirty;
  const saving = excludeSaveState === 'saving' || reuseSaveState === 'saving';
  const savedOk = !dirty && (excludeSaveState === 'saved' || reuseSaveState === 'saved');
  const saveErr = excludeSaveState === 'error' || reuseSaveState === 'error';
  const doSave = () => { onSaveExclude(); saveReuse(); };
  const doReset = () => {
    // 本週全納入(清排除)+ 清掉所有沿用
    const focusIds = all.filter(r => isFocusWk(weekMonday(r.date))).map(r => r.id);
    onExcludeMany(focusIds, false);
    clearAll();
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="挑選要算進建議車支數的帳單:本週可排除、之前週期可沿用併入"
        className={`px-2 py-1 rounded-md text-[11px] font-semibold flex items-center gap-1 transition-colors ${
          summary.reuseCount > 0 || summary.excludedCount > 0
            ? 'bg-indigo-600 text-white hover:bg-indigo-700'
            : 'bg-black/[0.04] dark:bg-white/[0.06] text-neutral-600 dark:text-neutral-300 hover:bg-black/10 dark:hover:bg-white/10'
        }`}
      >
        <ClipboardList className="w-3.5 h-3.5" />
        帳單挑選
        {(summary.reuseCount > 0 || summary.excludedCount > 0) && (
          <span className="font-mono">
            (沿用 {summary.reuseCount}・排除 {summary.excludedCount})
          </span>
        )}
      </button>

      {open && createPortal((
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150" onClick={() => setOpen(false)}>
          <div
            className="w-full max-w-lg md:max-w-4xl lg:max-w-6xl 2xl:max-w-[88rem] max-h-[90vh] flex flex-col bg-white dark:bg-[#161616] rounded-2xl border border-black/10 dark:border-white/10 shadow-2xl text-neutral-800 dark:text-neutral-200 overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            {/* 標題列 */}
            <div className="flex items-center justify-between gap-2 p-4 border-b border-black/[0.06] dark:border-white/[0.08]">
              <div className="flex items-center gap-2 text-sm font-bold">
                <ClipboardList className="w-4.5 h-4.5 text-indigo-500" />
                建議車支數基準 · 帳單挑選
              </div>
              <button type="button" onClick={() => setOpen(false)}
                className="w-7 h-7 flex items-center justify-center rounded-lg text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* 說明 + 即時摘要 */}
            <div className="px-4 pt-3 pb-2 border-b border-black/[0.05] dark:border-white/[0.06]">
              <p className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-relaxed">
                勾選要算進赤字的帳單。<span className="text-emerald-600 dark:text-emerald-400 font-semibold">本週</span>預設全勾(取消=排除,例如大贏那筆先落袋);
                <span className="text-indigo-600 dark:text-indigo-400 font-semibold">之前週期</span>預設不勾(勾選=沿用,把沒追回的舊赤字併進本週)。不影響週期帳本身,建議車支數會即時重算。
              </p>
              <div className="mt-2.5 grid grid-cols-3 gap-2">
                <div className="rounded-xl bg-emerald-500/[0.06] border border-emerald-500/20 px-3 py-2">
                  <div className="text-[10px] text-emerald-700/70 dark:text-emerald-400/70">本週(納入)</div>
                  <div className={`font-mono text-sm font-bold ${summary.focusPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{money(summary.focusPnl)}</div>
                  <div className="text-[9px] text-neutral-400">{summary.focusCount} 筆納入 · {summary.excludedCount} 筆排除</div>
                </div>
                <div className="rounded-xl bg-indigo-500/[0.06] border border-indigo-500/20 px-3 py-2">
                  <div className="text-[10px] text-indigo-700/70 dark:text-indigo-400/70">沿用之前週期</div>
                  <div className={`font-mono text-sm font-bold ${summary.reusePnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{money(summary.reusePnl)}</div>
                  <div className="text-[9px] text-neutral-400">{summary.reuseCount} 筆併入</div>
                </div>
                <div className="rounded-xl bg-black/[0.03] dark:bg-white/[0.05] border border-black/10 dark:border-white/10 px-3 py-2">
                  <div className="text-[10px] text-neutral-500">綜合赤字基準(跨版)</div>
                  <div className={`font-mono text-sm font-bold ${summary.deficit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{money(summary.deficit)}</div>
                  <div className="text-[9px] text-neutral-400">本週 + 沿用 − 排除</div>
                </div>
              </div>
            </div>

            {/* 篩選:下法 / 板名 / 遊戲 */}
            <div className="px-4 py-2 border-b border-black/[0.05] dark:border-white/[0.06] space-y-1.5">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold w-8 shrink-0">下法</span>
                {FILTERS.map(f => (
                  <button key={f.key} type="button" onClick={() => setModeFilter(f.key)} className={chipCls(modeFilter === f.key)}>{f.label}</button>
                ))}
              </div>
              {edOptions.length > 1 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold w-8 shrink-0">板名</span>
                  <button type="button" onClick={() => setEdFilter('all')} className={chipCls(edFilter === 'all')}>全部</button>
                  {edOptions.map(eid => (
                    <button key={eid} type="button" onClick={() => setEdFilter(eid)} className={chipCls(edFilter === eid)}>{edName(eid)}</button>
                  ))}
                </div>
              )}
              {gameOptions.length > 1 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold w-8 shrink-0">遊戲</span>
                  <button type="button" onClick={() => setGameFilter('all')} className={chipCls(gameFilter === 'all')}>全部</button>
                  {gameOptions.map(g => (
                    <button key={g} type="button" onClick={() => setGameFilter(g)} className={chipCls(gameFilter === g)}>{gameShort(g)}</button>
                  ))}
                </div>
              )}
            </div>

            {/* 本體:直板機單欄手風琴 / 寬板機左右雙欄 */}
            <div className="flex-1 min-h-0 flex flex-col md:flex-row border-t border-black/[0.06] dark:border-white/[0.08]">
              {!loggedIn ? (
                <div className="flex-1 text-[11px] text-neutral-400 py-10 text-center">未登入:沒有帳單可挑選(帳單存在登入帳號)。</div>
              ) : weeks.length === 0 ? (
                <div className="flex-1 text-[11px] text-neutral-400 py-10 text-center">目前篩選下沒有帳單(換下法 / 板名 / 遊戲看看)。</div>
              ) : (
                <>
                  <div className="flex-1 min-h-0 md:flex-none md:w-72 lg:w-80 xl:w-96 md:shrink-0 md:border-r border-black/[0.06] dark:border-white/[0.08] overflow-y-auto p-3 space-y-2 md:space-y-0 md:p-0">
                    {weeks.map(wk => {
                      const rows = byWeek.get(wk) ?? [];
                      return (
                        <div key={wk} className="rounded-xl md:rounded-none border md:border-0 md:border-b border-black/[0.08] dark:border-white/[0.10] overflow-hidden">
                          {renderWeekHeader(wk, rows)}
                          {expanded.has(wk) && <div className="md:hidden">{renderDetail(wk, rows)}</div>}
                        </div>
                      );
                    })}
                  </div>
                  <div className="hidden md:flex md:flex-col flex-1 min-w-0 overflow-y-auto">
                    {activeWeek ? (
                      <>
                        <div className="sticky top-0 z-10 flex items-center justify-between gap-2 px-3 py-2 bg-white dark:bg-[#161616] border-b border-black/[0.06] dark:border-white/[0.08]">
                          <span className="text-[12px] font-semibold truncate">
                            {weekRangeLabel(activeWeek)} 明細
                            <span className={`ml-1 text-[10px] font-normal ${isFocusWk(activeWeek) ? 'text-emerald-600 dark:text-emerald-400' : 'text-indigo-600 dark:text-indigo-400'}`}>
                              {isFocusWk(activeWeek) ? '(取消勾選 = 排除)' : '(勾選 = 沿用)'}
                            </span>
                          </span>
                          <span className={`text-[11px] font-mono font-bold shrink-0 ${pnlOf(byWeek.get(activeWeek) ?? []) >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                            {money(pnlOf(byWeek.get(activeWeek) ?? []))}
                          </span>
                        </div>
                        <div>{renderDetail(activeWeek, byWeek.get(activeWeek) ?? [])}</div>
                      </>
                    ) : (
                      <div className="flex-1 text-[11px] text-neutral-400 py-10 text-center">左側選一個週期看明細</div>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* 底部:合計 + 重設 + 儲存並套用 */}
            <div className="flex items-center justify-between gap-2 p-4 border-t border-black/[0.06] dark:border-white/[0.08]">
              <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
                共納入 <strong className="text-neutral-800 dark:text-neutral-200">{summary.focusCount + summary.reuseCount}</strong> 筆
                (本週 {summary.focusCount} · 沿用 {summary.reuseCount}) · 排除 {summary.excludedCount} 筆
                <span className="ml-2 text-[10px]">
                  {dirty ? '有未儲存變更' : savedOk ? '已同步到帳號' : saveErr ? '儲存失敗' : ''}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button type="button" onClick={doReset}
                  className="py-2 px-3 rounded-xl text-xs font-semibold border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors flex items-center gap-1">
                  <RotateCcw className="w-3.5 h-3.5" /> 重設
                </button>
                <button type="button" onClick={doSave} disabled={saving || (!dirty && !saveErr)}
                  className={`py-2 px-4 rounded-xl text-xs font-semibold transition-colors disabled:opacity-40 ${
                    saveErr ? 'bg-rose-500/15 text-rose-700 dark:text-rose-300 hover:bg-rose-500/25'
                            : savedOk ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300'
                                      : 'bg-black text-white dark:bg-white dark:text-black hover:opacity-90'
                  }`}>
                  {saving ? '儲存中…' : saveErr ? '儲存失敗,重試' : savedOk ? '已儲存 ✓' : '儲存並套用'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ), document.body)}
    </>
  );
};
