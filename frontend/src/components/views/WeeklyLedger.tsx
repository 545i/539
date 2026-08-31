import React, { useMemo, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { useAllLedger } from '../../api/useLedger';
import { useEditions } from '../../api/useEditions';
import { useGame } from '../../api/useGame';
import { LedgerMode } from '../../api/client';
import { MODE_LABEL, money } from '../uploadHistory';

const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''));
  return Number.isFinite(n) ? n : 0;
};

const isPending = (result: string) => !result || result.includes('待開') || result.includes('待對');

// 帶正負號的金額(綠賺紅賠)
const pnlCls = (v: number) =>
  v > 0 ? 'text-emerald-600 dark:text-emerald-400'
    : v < 0 ? 'text-rose-600 dark:text-rose-400'
      : 'text-neutral-400';
const signedMoney = (v: number) => (v >= 0 ? '+' : '') + money(v);

// YYYY-MM-DD → 該週週一(以 UTC 計算避開時區位移);週日 = 週一 +6。
const ymdOf = (raw: string): string => {
  const s = String(raw ?? '');
  return /^\d{4}-\d{2}-\d{2}/.test(s) ? s.slice(0, 10) : '';
};
const addDays = (ymd: string, n: number): string => {
  const [y, m, d] = ymd.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
};
const mondayOf = (ymd: string): string => {
  const [y, m, d] = ymd.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  const dow = dt.getUTCDay();            // 0=日 … 6=六
  return addDays(ymd, dow === 0 ? -6 : 1 - dow); // 回推到週一
};
const WD = ['日', '一', '二', '三', '四', '五', '六'];
const weekdayOf = (ymd: string): string => {
  const [y, m, d] = ymd.split('-').map(Number);
  return WD[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
};

interface BetRow {
  gameShort: string;
  modeLabel: string;
  playType: string;
  balls: number[];
  cost: number;
  payout: number;
  pnl: number;
  result: string;
  pending: boolean;
}
interface Bucket { cost: number; payout: number; pnl: number; pendingCount: number; count: number; }
interface DayGroup extends Bucket { ymd: string; rows: BetRow[]; }
interface WeekGroup extends Bucket { monday: string; sunday: string; days: DayGroup[]; }

const blank = (): Bucket => ({ cost: 0, payout: 0, pnl: 0, pendingCount: 0, count: 0 });
const fold = (b: Bucket, cost: number, payout: number, pending: boolean) => {
  b.cost += cost; b.payout += payout; b.pnl += payout - cost;
  b.count += 1; if (pending) b.pendingCount += 1;
};

// 每週總帳:全部下注流水(排除模擬版)依開獎日期歸「週一~週日」的週,
// 週 → 展開看每日小計 → 再展開看當天逐筆。派彩/盈虧直接取自各筆已結算紀錄。
export const WeeklyLedger: React.FC = () => {
  const { entries, loading, loggedIn } = useAllLedger();
  const { editions } = useEditions();
  const { games } = useGame();

  const simEids = useMemo(
    () => new Set(editions.filter(e => e.simulated).map(e => e.eid)),
    [editions],
  );
  const gameShort = (key: string) =>
    games.find(g => g.key === key)?.short_name ?? games.find(g => g.key === key)?.name ?? '';

  const [selEd, setSelEd] = useState<number | 'all'>('all');
  const [openWeeks, setOpenWeeks] = useState<Set<string>>(new Set());
  const [openDays, setOpenDays] = useState<Set<string>>(new Set());
  const toggle = (set: Set<string>, k: string, setter: (s: Set<string>) => void) => {
    const n = new Set(set); n.has(k) ? n.delete(k) : n.add(k); setter(n);
  };

  const usedEds = useMemo(() => {
    const s = new Set<number>();
    for (const e of entries) s.add(num((e.record as Record<string, unknown>).edition) || 1);
    return Array.from(s).sort((a, b) => a - b);
  }, [entries]);
  const edName = (ed: number) => editions.find(x => x.eid === ed)?.name ?? `版${ed}`;

  // 篩選:'all' = 全部版但排除模擬版;選特定版就只看那版(含模擬版)
  const shown = useMemo(() => entries.filter(e => {
    const ed = num((e.record as Record<string, unknown>).edition) || 1;
    return selEd === 'all' ? !simEids.has(ed) : ed === selEd;
  }), [entries, selEd, simEids]);

  // 分組:週(週一) → 日 → 逐筆
  const weeks = useMemo(() => {
    const wmap = new Map<string, WeekGroup>();
    for (const e of shown) {
      const r = e.record as Record<string, unknown>;
      const ymd = ymdOf(String(r.date ?? ''));
      const monday = ymd ? mondayOf(ymd) : '';
      const result = String(r.result ?? '');
      const pending = isPending(result);
      const cost = num(r.cost);
      const payout = pending ? 0 : num(r.payout);
      const row: BetRow = {
        gameShort: gameShort(String(r.game ?? '')),
        modeLabel: MODE_LABEL[r.mode as LedgerMode] ?? String(r.mode ?? ''),
        playType: String(r.playType ?? ''),
        balls: (r.selectedBalls as number[]) ?? [],
        cost, payout, pnl: payout - cost, result, pending,
      };
      let w = wmap.get(monday);
      if (!w) {
        w = { ...blank(), monday, sunday: monday ? addDays(monday, 6) : '', days: [] };
        wmap.set(monday, w);
      }
      fold(w, cost, payout, pending);
      let day = w.days.find(d => d.ymd === ymd);
      if (!day) { day = { ...blank(), ymd, rows: [] }; w.days.push(day); }
      fold(day, cost, payout, pending);
      day.rows.push(row);
    }
    const list = Array.from(wmap.values());
    // 週:新→舊(無日期擺最後);週內日:舊→新(週一→週日順讀);日內逐筆:遊戲→下法
    list.sort((a, b) => (a.monday && b.monday ? b.monday.localeCompare(a.monday) : a.monday ? -1 : 1));
    for (const w of list) {
      w.days.sort((a, b) => a.ymd.localeCompare(b.ymd));
      for (const d of w.days) {
        d.rows.sort((a, b) => a.gameShort.localeCompare(b.gameShort) || a.modeLabel.localeCompare(b.modeLabel));
      }
    }
    return list;
  }, [shown, games]);

  // 頁頂總計(目前篩選下所有週合計)
  const grand = useMemo(() => {
    const g = blank();
    for (const w of weeks) { g.cost += w.cost; g.payout += w.payout; g.pnl += w.pnl; g.count += w.count; g.pendingCount += w.pendingCount; }
    return g;
  }, [weeks]);

  const weekLabel = (w: WeekGroup) =>
    w.monday ? `${w.monday.replace(/-/g, '/')} ~ ${w.sunday.slice(5).replace('-', '/')}` : '(無日期)';

  if (!loggedIn) {
    return <div className="text-[12px] text-neutral-500 p-4">登入後才有跨裝置的下注流水可彙整成週總帳。</div>;
  }

  return (
    <div className="space-y-4">
      <p className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-relaxed">
        全部下注流水(含快速上傳與手動記錄,排除模擬版)依開獎日期歸「週一~週日」的週。
        點<strong>週</strong>展開看每日小計,再點<strong>某日</strong>看當天逐筆的下注方式 / 組合 / 成本 / 派彩 / 盈虧。
      </p>

      {/* 版篩選 */}
      {usedEds.length > 1 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">版</span>
          {(['all', ...usedEds] as (number | 'all')[]).map(ed => (
            <button
              key={String(ed)}
              type="button"
              onClick={() => setSelEd(ed)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                selEd === ed
                  ? 'bg-black text-white dark:bg-white dark:text-black'
                  : 'border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
              }`}
            >
              {ed === 'all' ? '全部版(排除模擬)' : edName(ed as number)}
            </button>
          ))}
        </div>
      )}

      {/* 頁頂總計 */}
      {weeks.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {([
            ['總成本', money(grand.cost), 'text-neutral-900 dark:text-white'],
            ['總派彩', money(grand.payout), 'text-emerald-600 dark:text-emerald-400'],
            ['總盈虧', signedMoney(grand.pnl), pnlCls(grand.pnl)],
          ] as const).map(([label, val, cls]) => (
            <div key={label} className="rounded-xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#121212] px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">{label}</div>
              <div className={`font-mono font-bold text-sm ${cls}`}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {loading && weeks.length === 0 && (
        <div className="text-[12px] text-neutral-400 p-4">載入流水中…</div>
      )}
      {!loading && weeks.length === 0 && (
        <div className="text-[11px] text-neutral-400 dark:text-neutral-500 leading-relaxed p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
          目前這個篩選下沒有下注流水。
        </div>
      )}

      <div className="space-y-3">
        {weeks.map(w => {
          const wOpen = openWeeks.has(w.monday);
          return (
          <div key={w.monday || 'nodate'} className="rounded-xl border border-black/15 dark:border-white/15 bg-white dark:bg-[#121212] overflow-hidden shadow-sm">
            {/* 週父列 */}
            <button
              type="button"
              onClick={() => toggle(openWeeks, w.monday, setOpenWeeks)}
              className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-black/[0.02] dark:hover:bg-white/[0.03] transition-colors"
            >
              <span className="text-[11px] w-3 shrink-0 text-center text-neutral-400">{wOpen ? '▾' : '▸'}</span>
              <div className="min-w-0 flex-1">
                <div className="text-[12px] font-semibold text-neutral-800 dark:text-neutral-100 font-mono">
                  {weekLabel(w)}
                  <span className="ml-1.5 font-sans font-normal text-neutral-400 text-[10px]">{w.count} 筆</span>
                  {w.pendingCount > 0 && (
                    <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 text-[9px] font-semibold">
                      {w.pendingCount} 筆待開獎
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3 text-[10px] font-mono shrink-0">
                <span className="text-neutral-500">成本 <span className="font-bold text-neutral-800 dark:text-neutral-200">{money(w.cost)}</span></span>
                <span className="text-neutral-500">派彩 <span className="font-bold text-emerald-600 dark:text-emerald-400">{money(w.payout)}</span></span>
                <span className="text-neutral-500">盈虧 <span className={`font-bold ${pnlCls(w.pnl)}`}>{signedMoney(w.pnl)}</span></span>
              </div>
            </button>

            {/* 每日小計 */}
            {wOpen && (
              <div className="border-t border-black/[0.06] dark:border-white/[0.06]">
                {w.days.map(day => {
                  const dOpen = openDays.has(day.ymd);
                  return (
                  <div key={day.ymd || 'nodate'} className="border-b border-black/[0.04] dark:border-white/[0.04] last:border-b-0">
                    <button
                      type="button"
                      onClick={() => toggle(openDays, day.ymd, setOpenDays)}
                      className="w-full flex items-center gap-2 px-3 py-2 pl-6 text-left hover:bg-black/[0.02] dark:hover:bg-white/[0.03] transition-colors"
                    >
                      <span className="text-[10px] w-3 shrink-0 text-center text-neutral-400">{dOpen ? '▾' : '▸'}</span>
                      <div className="min-w-0 flex-1 text-[11px] font-mono text-neutral-700 dark:text-neutral-300">
                        {day.ymd ? `${day.ymd.slice(5).replace('-', '/')}(${weekdayOf(day.ymd)})` : '(無日期)'}
                        <span className="ml-1.5 font-sans text-neutral-400 text-[10px]">{day.count} 筆</span>
                        {day.pendingCount > 0 && (
                          <span className="ml-1.5 text-amber-600 dark:text-amber-400 text-[9px]">{day.pendingCount} 待開</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-[10px] font-mono shrink-0">
                        <span className="text-neutral-500">{money(day.cost)}</span>
                        <span className="text-emerald-600 dark:text-emerald-400">{money(day.payout)}</span>
                        <span className={`font-bold ${pnlCls(day.pnl)}`}>{signedMoney(day.pnl)}</span>
                      </div>
                    </button>

                    {/* 當天逐筆 */}
                    {dOpen && (
                      <div className="overflow-x-auto bg-black/[0.015] dark:bg-white/[0.02]">
                        <table className="w-full text-[11px] whitespace-nowrap">
                          <thead className="text-[9px] uppercase tracking-wider text-neutral-400">
                            <tr>
                              <th className="px-3 py-1 pl-9 text-left font-semibold">下注方式</th>
                              <th className="px-3 py-1 text-left font-semibold">下注組合</th>
                              <th className="px-3 py-1 text-right font-semibold">成本</th>
                              <th className="px-3 py-1 text-right font-semibold">派彩</th>
                              <th className="px-3 py-1 text-right font-semibold">盈虧</th>
                            </tr>
                          </thead>
                          <tbody className="font-mono">
                            {day.rows.map((v, i) => (
                              <tr key={i} className="border-t border-black/[0.05] dark:border-white/[0.05]">
                                <td className="px-3 py-1 pl-9 align-top">
                                  {v.gameShort && (
                                    <span className="px-1.5 py-0.5 rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400 text-[9px] mr-1 font-sans">{v.gameShort}</span>
                                  )}
                                  <span className="px-1.5 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-[10px] mr-1.5 font-sans">{v.modeLabel}</span>
                                  <span className="font-sans text-neutral-600 dark:text-neutral-400">{v.playType}</span>
                                  {v.result && (
                                    <span className={`ml-1.5 font-sans text-[9px] px-1.5 py-0.5 rounded-full ${
                                      v.pending
                                        ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                                        : v.payout > 0
                                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                                          : 'bg-black/5 dark:bg-white/10 text-neutral-500'
                                    }`}>{v.result}</span>
                                  )}
                                </td>
                                <td className="px-3 py-1 align-top text-neutral-700 dark:text-neutral-300">
                                  {v.balls.length > 0 ? v.balls.map(n => String(n).padStart(2, '0')).join(' ') : '—'}
                                </td>
                                <td className="px-3 py-1 align-top text-right font-bold text-neutral-900 dark:text-white">{money(v.cost)}</td>
                                <td className="px-3 py-1 align-top text-right text-emerald-600 dark:text-emerald-400">
                                  {v.pending ? <span className="text-neutral-400">待開獎</span> : money(v.payout)}
                                </td>
                                <td className={`px-3 py-1 align-top text-right font-bold ${v.pending ? 'text-neutral-400' : pnlCls(v.pnl)}`}>
                                  {v.pending ? '—' : signedMoney(v.pnl)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                  );
                })}
              </div>
            )}
          </div>
          );
        })}
      </div>

      <div className="flex items-start gap-1.5 text-[10px] text-neutral-500 dark:text-neutral-400 leading-relaxed pt-1">
        <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0 text-neutral-400" />
        <span>
          <strong>成本</strong> = 每注基礎成本 × 支/注數;
          <strong>派彩</strong> = 開獎對獎後「中的碰/顆/注數 × 車數 × 該版每碰派彩(盤口)」,未中或未開獎為 0;
          <strong>盈虧</strong> = 派彩 − 成本。待開獎的筆不計入派彩合計,開獎後自動補上。
        </span>
      </div>
    </div>
  );
};
