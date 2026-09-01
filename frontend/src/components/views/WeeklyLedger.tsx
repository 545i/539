import React, { useMemo, useState } from 'react';
import { AlertTriangle, Trash2 } from 'lucide-react';
import { useAllLedger, useLedgerActions } from '../../api/useLedger';
import { useEditions } from '../../api/useEditions';
import { useGame } from '../../api/useGame';
import { useHistoriesByGame } from '../../api/useHistories';
import { IssuePicker } from '../IssuePicker';
import { useWeekNav, WeekNav } from '../WeekNav';
import { LedgerMode } from '../../api/client';
import { MODE_LABEL, money } from '../uploadHistory';
import { weekAddDays, weekMonday } from '../../weeks';

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
// 週歸期(某日 → 該週週一)與日期加減共用 weeks.ts:weekMonday / weekAddDays。
const WD = ['日', '一', '二', '三', '四', '五', '六'];
const weekdayOf = (ymd: string): string => {
  const [y, m, d] = ymd.split('-').map(Number);
  return WD[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
};

interface BetRow {
  id: string;          // ledger 紀錄 id(逐筆對獎/撤銷用)
  issue: string;       // 期號(IssuePicker 用)
  game: string;        // 原始遊戲名(histByGame 查該款期別用)
  edition: number;     // 版 eid
  gameShort: string;
  editionName: string;
  mode: string;        // single/multi/pillar1800/combo9000/combo(快捷帳單用)
  modeLabel: string;
  playType: string;
  balls: number[];
  drawBalls: number[]; // 開獎號(快捷帳單「獎號」用)
  units: number;       // 車數 / 支數
  cars: number;        // 車數(二合碰數 = 中幾顆 × 車數 × 4)
  unitLabel: string;   // 「車」或「支」
  perUnit: number;     // 每注/每車/每支成本 = cost / units
  cost: number;
  payout: number;
  pnl: number;
  result: string;
  pending: boolean;
}

// 快捷帳單:遊戲名 → 帳單簡稱(539 / 天天 / 六合)
const billGame = (short: string): string =>
  short.includes('天天') || short.includes('Fantasy') ? '天天'
    : short.includes('六合') ? '六合'
      : short.includes('539') ? '539' : short;
// 快捷帳單:下法 → 帳單簡稱
const billMode: Record<string, string> = {
  single: '1', multi: '2', pillar1800: '1800', combo9000: '9000', combo: '連碰',
};
// 某筆中獎的「碰數」:二合 = 中幾顆 × 車數 × 4;其餘(1800/連碰/9000)直接讀 result「中 X 碰」
const winCombos = (r: BetRow): number => {
  if (r.mode === 'single' || r.mode === 'multi') {
    const m = r.result.match(/中\s*(\d+)\s*顆/);
    return m ? Number(m[1]) * r.cars * 4 : 0;
  }
  const m = r.result.match(/中\s*([\d,]+)/);
  return m ? Number(m[1].replace(/,/g, '')) : 0;
};
type GameAgg = { cost: number; payout: number; pnl: number; count: number };
interface Bucket { cost: number; payout: number; pnl: number; pendingCount: number; count: number; byGame: Map<string, GameAgg>; }
interface DayGroup extends Bucket { ymd: string; rows: BetRow[]; }
interface WeekGroup extends Bucket { monday: string; sunday: string; days: DayGroup[]; }

const blank = (): Bucket => ({ cost: 0, payout: 0, pnl: 0, pendingCount: 0, count: 0, byGame: new Map() });
const fold = (b: Bucket, cost: number, payout: number, pending: boolean, game: string) => {
  b.cost += cost; b.payout += payout; b.pnl += payout - cost;
  b.count += 1; if (pending) b.pendingCount += 1;
  const a = b.byGame.get(game) ?? { cost: 0, payout: 0, pnl: 0, count: 0 };
  a.cost += cost; a.payout += payout; a.pnl += payout - cost; a.count += 1;
  b.byGame.set(game, a);
};
// 下法對應的計數單位(顯示「N車 / N支」用)
const UNIT_LABEL: Record<string, string> = {
  single: '車', multi: '車', pillar1800: '支', combo9000: '支', combo: '支',
};

// 快捷帳單:某日的結構化帳單資料(按版 → 遊戲)。同時給「卡片 UI」和「純文字複製」用。
interface BillWin { mode: string; combos: number; payout: number; }
interface BillGameData { label: string; draw: number[]; cost: number; net: number; running: number; wins: BillWin[]; }
interface BillEditionData { edition: string; games: BillGameData[]; }

const dayMd = (ymd: string): string =>
  ymd ? `${Number(ymd.slice(5, 7))}/${Number(ymd.slice(8, 10))}` : '';

function buildDayBill(day: DayGroup): BillEditionData[] {
  const order = ['539', '天天', '六合'];
  const eds: string[] = [];
  const byEd = new Map<string, BetRow[]>();
  for (const r of day.rows) {
    if (!byEd.has(r.editionName)) { byEd.set(r.editionName, []); eds.push(r.editionName); }
    byEd.get(r.editionName)!.push(r);
  }
  return eds.map(ed => {
    const rows = byEd.get(ed)!;
    const games: string[] = [];
    const byGame = new Map<string, BetRow[]>();
    for (const r of rows) {
      if (!byGame.has(r.gameShort)) { byGame.set(r.gameShort, []); games.push(r.gameShort); }
      byGame.get(r.gameShort)!.push(r);
    }
    games.sort((a, b) => order.indexOf(billGame(a)) - order.indexOf(billGame(b)));
    let running = 0;
    const gs: BillGameData[] = games.map(g => {
      const gr = byGame.get(g)!;
      const cost = gr.reduce((s, r) => s + r.cost, 0);
      const payout = gr.reduce((s, r) => s + r.payout, 0);
      running += payout - cost;
      return {
        label: billGame(g),
        draw: gr.find(r => r.drawBalls.length)?.drawBalls ?? [],
        cost: Math.round(cost),
        net: Math.round(payout - cost),
        running: Math.round(running),
        wins: gr.filter(r => r.payout > 0)
          .map(r => ({ mode: billMode[r.mode] ?? r.modeLabel, combos: winCombos(r), payout: Math.round(r.payout) })),
      };
    });
    return { edition: ed, games: gs };
  });
}

// 單一遊戲卡 → 對接人純文字帳單(每張卡各自「複製帳單」用,與對接人帳單一致)。
// editionLabel 有值(多版時)會在最上面加【版名】,組頭才知道是哪一版。
function billGameText(g: BillGameData, md: string, editionLabel?: string): string {
  const lines = [md, `${g.label}獎號`];
  if (g.draw.length) lines.push(g.draw.map(n => String(n).padStart(2, '0')).join('.'));
  lines.push(`${g.label}牌支${g.cost}`);
  for (const w of g.wins) lines.push(`${w.mode}中${w.combos}碰+${w.payout}`);
  lines.push(`共${Math.abs(g.net)}`);
  lines.push(`合計${Math.abs(g.running)}`);
  const body = lines.join('\n');
  return editionLabel ? `【${editionLabel}】\n${body}` : body;
}

// 快捷帳單卡片:易讀版(獎號球 / 展收付上色 / 中獎綠字);每張卡各一顆「複製帳單」,
// 複製的是該卡對應的對接人純文字帳單。
const BillCards: React.FC<{ bill: BillEditionData[]; md: string }> = ({ bill, md }) => {
  const [copiedKey, setCopiedKey] = useState('');            // 剛複製的卡(edition/label)
  const multi = bill.length > 1;
  const copyCard = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(''), 1500);
    } catch { /* ignore */ }
  };
  return (
  <div className="space-y-3">
    {bill.map(e => (
      <div key={e.edition} className="space-y-2">
        {multi && (
          <div className="inline-block px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-600 dark:text-violet-400 text-[11px] font-bold">{e.edition}</div>
        )}
        <div className="grid gap-2 sm:grid-cols-2">
          {e.games.map(g => {
            const key = `${e.edition}/${g.label}`;
            return (
            <div key={g.label} className="rounded-xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] p-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                  <span className="px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-600 dark:text-sky-400 text-[11px] font-bold">{g.label}</span>
                  <span className="text-[10px] text-neutral-400 font-mono">{md}</span>
                </div>
                <span className={`font-mono text-sm font-bold ${g.net >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                  {g.net >= 0 ? '展收 ' : '展付 '}{Math.abs(g.net).toLocaleString()}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                <span className="text-[10px] text-neutral-400 mr-1">獎號</span>
                {g.draw.length ? g.draw.map(n => (
                  <span key={n} className="w-6 h-6 flex items-center justify-center rounded-full bg-black/[0.06] dark:bg-white/[0.08] text-[11px] font-mono font-semibold text-neutral-800 dark:text-neutral-100">
                    {String(n).padStart(2, '0')}
                  </span>
                )) : <span className="text-[11px] text-neutral-400">未開</span>}
              </div>
              <div className="text-[11px] font-mono space-y-0.5">
                <div className="flex justify-between"><span className="text-neutral-500">牌支(成本)</span><span className="font-semibold text-neutral-800 dark:text-neutral-100">{g.cost.toLocaleString()}</span></div>
                {g.wins.map((w, i) => (
                  <div key={i} className="flex justify-between text-emerald-600 dark:text-emerald-400">
                    <span>{w.mode} 中 {w.combos.toLocaleString()} 碰</span>
                    <span className="font-bold">+{w.payout.toLocaleString()}</span>
                  </div>
                ))}
                <div className="flex justify-between border-t border-black/[0.06] dark:border-white/[0.06] pt-0.5 mt-0.5">
                  <span className="text-neutral-500">合計(當日累計)</span>
                  <span className={`font-bold ${g.running >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                    {g.running >= 0 ? '展收 ' : '展付 '}{Math.abs(g.running).toLocaleString()}
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => copyCard(key, billGameText(g, md, multi ? e.edition : undefined))}
                className="w-full mt-1 px-2 py-1 rounded-md text-[10px] font-semibold border border-emerald-500/40 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
              >
                {copiedKey === key ? '已複製' : '複製帳單'}
              </button>
            </div>
            );
          })}
        </div>
      </div>
    ))}
  </div>
  );
};

// 各遊戲拆帳:539 / 天天樂 / 六合彩 各自的成本 / 派彩 / 盈虧(常駐顯示,不用展開)
const GameBreak: React.FC<{ byGame: Map<string, GameAgg>; className?: string }> = ({ byGame, className }) => {
  const items = Array.from(byGame.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  if (items.length === 0) return null;
  return (
    <div className={`flex flex-col gap-0.5 ${className ?? ''}`}>
      {items.map(([g, a]) => (
        <div key={g} className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] font-mono">
          <span className="inline-block min-w-[3.75rem] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-600 dark:text-sky-400 font-sans font-semibold text-center">{g}</span>
          <span className="text-neutral-500">成本 <span className="text-neutral-800 dark:text-neutral-200 font-semibold">{money(a.cost)}</span></span>
          <span className="text-neutral-500">派彩 <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{money(a.payout)}</span></span>
          <span className="text-neutral-500">盈虧 <span className={`font-bold ${pnlCls(a.pnl)}`}>{signedMoney(a.pnl)}</span></span>
        </div>
      ))}
    </div>
  );
};

// 每週總帳:全部下注流水(排除模擬版)依開獎日期歸「週一~週日」的週,
// 週 → 展開看每日小計 → 再展開看當天逐筆。派彩/盈虧直接取自各筆已結算紀錄。
export const WeeklyLedger: React.FC<{ initialMode?: LedgerMode | null }> = ({ initialMode }) => {
  const { entries, loading, loggedIn } = useAllLedger();
  const { resettle, deleteById } = useLedgerActions();   // 逐筆對獎 / 撤銷(共用 cache)
  const histByGame = useHistoriesByGame();               // 各款期別(IssuePicker 用)
  const { editions } = useEditions();
  const { games } = useGame();
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const simEids = useMemo(
    () => new Set(editions.filter(e => e.simulated).map(e => e.eid)),
    [editions],
  );
  // ledger 的 record.game 存的是「遊戲名稱」(今彩539/天天樂…),不是 key —— 用
  // key / name / short_name 都比對得到;對不到就回原字串(不要變成「其他」)。
  const gameShort = (g: string) => {
    const f = games.find(x => x.key === g || x.name === g || x.short_name === g);
    return f?.short_name ?? f?.name ?? g ?? '其他';
  };

  const [selEd, setSelEd] = useState<number | 'all'>('all');
  const [selMode, setSelMode] = useState<LedgerMode | 'all'>('all');   // 下法篩選(策略頁連結進來時預設)
  // 從策略頁「查看本週流水」連結進來時,預設篩選成該下法(之後可自行改)
  React.useEffect(() => { if (initialMode) setSelMode(initialMode); }, [initialMode]);
  const [openWeeks, setOpenWeeks] = useState<Set<string>>(new Set());
  const [openDays, setOpenDays] = useState<Set<string>>(new Set());
  const [quickDays, setQuickDays] = useState<Set<string>>(new Set()); // 哪些日切到「快捷帳單」
  const toggle = (set: Set<string>, k: string, setter: (s: Set<string>) => void) => {
    const n = new Set(set); n.has(k) ? n.delete(k) : n.add(k); setter(n);
  };

  const usedEds = useMemo(() => {
    const s = new Set<number>();
    for (const e of entries) s.add(num((e.record as Record<string, unknown>).edition) || 1);
    return Array.from(s).sort((a, b) => a - b);
  }, [entries]);
  const edName = (ed: number) => editions.find(x => x.eid === ed)?.name ?? `版${ed}`;
  // 資料裡出現過的下法(依 MODE_ROWS 順序),給下法篩選鈕用
  const usedModes = useMemo(() => {
    const order: LedgerMode[] = ['single', 'multi', 'pillar1800', 'combo9000', 'combo'];
    const s = new Set(entries.map(e => String((e.record as Record<string, unknown>).mode ?? '')));
    return order.filter(m => s.has(m));
  }, [entries]);

  // 篩選:版('all' = 全部版但排除模擬版;選特定版就只看那版含模擬版)+ 下法(mode)
  const shown = useMemo(() => entries.filter(e => {
    const r = e.record as Record<string, unknown>;
    const ed = num(r.edition) || 1;
    const okEd = selEd === 'all' ? !simEids.has(ed) : ed === selEd;
    const okMode = selMode === 'all' || String(r.mode ?? '') === selMode;
    return okEd && okMode;
  }), [entries, selEd, selMode, simEids]);

  // 分組:週(週一) → 日 → 逐筆
  const weeks = useMemo(() => {
    const wmap = new Map<string, WeekGroup>();
    for (const e of shown) {
      const r = e.record as Record<string, unknown>;
      const ymd = ymdOf(String(r.date ?? ''));
      const monday = ymd ? weekMonday(ymd) : '';
      const result = String(r.result ?? '');
      const pending = isPending(result);
      const cost = num(r.cost);
      const payout = pending ? 0 : num(r.payout);
      const mode = String(r.mode ?? '');
      const gShort = gameShort(String(r.game ?? '')) || '其他';
      const units = num(r.units);
      const row: BetRow = {
        id: String(e.id),
        issue: String(r.issue ?? ''),
        game: String(r.game ?? ''),
        edition: num(r.edition) || 1,
        gameShort: gShort,
        editionName: edName(num(r.edition) || 1),
        mode,
        modeLabel: MODE_LABEL[r.mode as LedgerMode] ?? mode,
        playType: String(r.playType ?? ''),
        balls: (r.selectedBalls as number[]) ?? [],
        drawBalls: (r.drawBalls as number[]) ?? [],
        units,
        cars: num(r.cars) || units,
        unitLabel: UNIT_LABEL[mode] ?? '注',
        perUnit: units ? Math.round(cost / units) : cost,
        cost, payout, pnl: payout - cost, result, pending,
      };
      let w = wmap.get(monday);
      if (!w) {
        w = { ...blank(), monday, sunday: monday ? weekAddDays(monday, 6) : '', days: [] };
        wmap.set(monday, w);
      }
      fold(w, cost, payout, pending, gShort);
      let day = w.days.find(d => d.ymd === ymd);
      if (!day) { day = { ...blank(), ymd, rows: [] }; w.days.push(day); }
      fold(day, cost, payout, pending, gShort);
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

  // 週導覽:接共用聚焦週(WeekFocusProvider),與五個策略頁「第 N 週」同步,切一次全部一起動。
  // 只用它的 focusWeek(週一字串)/allWeeks/goWeek;逐筆金額由本頁自己的 weeks 分組提供。
  const navRecords = useMemo(
    () => shown.map(e => ({ date: String((e.record as Record<string, unknown>).date ?? ''), cost: 0, payout: 0 })),
    [shown],
  );
  const wk = useWeekNav(navRecords);
  const focusMonday = wk.focusWeek;
  const visibleWeeks = wk.allWeeks ? weeks : weeks.filter(w => w.monday === focusMonday);

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

      {/* 下法篩選(策略頁「查看本週流水」連結進來時會預設某一種下法) */}
      {usedModes.length > 1 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">下法</span>
          {(['all', ...usedModes] as (LedgerMode | 'all')[]).map(m => (
            <button
              key={m}
              type="button"
              onClick={() => setSelMode(m)}
              className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                selMode === m
                  ? 'bg-black text-white dark:bg-white dark:text-black'
                  : 'border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
              }`}
            >
              {m === 'all' ? '全部下法' : (MODE_LABEL[m] ?? m)}
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

      {/* 週導覽(共用聚焦週,與策略頁同步):‹ › 依日曆前後移,中間點切「全部週」 */}
      {weeks.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <WeekNav
            focusWeek={wk.focusWeek}
            allWeeks={wk.allWeeks}
            canNext={wk.canNext}
            onPrev={() => wk.goWeek(-1)}
            onNext={() => wk.goWeek(1)}
            onToggleAll={() => wk.setAllWeeks(v => !v)}
          />
        </div>
      )}
      {/* 聚焦週在本篩選下沒有紀錄(日曆式切週可能落在空週) */}
      {weeks.length > 0 && !wk.allWeeks && visibleWeeks.length === 0 && (
        <div className="text-[11px] text-neutral-400 dark:text-neutral-500 p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
          {wk.label} 這個篩選下沒有紀錄。用 ‹ › 切到其他週,或點中間看「全部週」。
        </div>
      )}

      <div className="space-y-3">
        {visibleWeeks.map(w => {
          const wOpen = openWeeks.has(w.monday) || (!wk.allWeeks && w.monday === focusMonday);
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

            {/* 本週各遊戲拆帳 */}
            {wOpen && w.byGame.size > 1 && (
              <div className="px-3 py-2 pl-8 border-t border-black/[0.06] dark:border-white/[0.06] bg-black/[0.015] dark:bg-white/[0.02]">
                <div className="text-[9px] uppercase tracking-wider text-neutral-400 mb-1">本週各遊戲</div>
                <GameBreak byGame={w.byGame} />
              </div>
            )}

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

                    {/* 當天各遊戲拆帳(常駐,不用展開)*/}
                    <div className="px-3 pb-2 pl-9">
                      <GameBreak byGame={day.byGame} />
                    </div>

                    {/* 當天逐筆:明細 / 快捷帳單 */}
                    {dOpen && (
                      <div className="bg-black/[0.015] dark:bg-white/[0.02]">
                        <div className="flex items-center gap-1.5 px-3 py-1.5 pl-9">
                          {(['detail', 'quick'] as const).map(v => {
                            const on = quickDays.has(day.ymd) === (v === 'quick');
                            return (
                              <button
                                key={v}
                                type="button"
                                onClick={() => setQuickDays(prev => { const n = new Set(prev); v === 'quick' ? n.add(day.ymd) : n.delete(day.ymd); return n; })}
                                className={`px-2 py-0.5 rounded-md text-[10px] font-semibold transition-colors ${on ? 'bg-black text-white dark:bg-white dark:text-black' : 'border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'}`}
                              >
                                {v === 'detail' ? '明細' : '快捷'}
                              </button>
                            );
                          })}
                          {quickDays.has(day.ymd) && (
                            <span className="ml-1 text-[10px] text-neutral-400">每張卡各自「複製帳單」</span>
                          )}
                        </div>
                        {quickDays.has(day.ymd) ? (
                          <div className="px-3 pb-3 pl-9">
                            <BillCards bill={buildDayBill(day)} md={dayMd(day.ymd)} />
                          </div>
                        ) : (
                        <div className="overflow-x-auto">
                        <table className="w-full text-[11px] whitespace-nowrap">
                          <thead className="text-[9px] uppercase tracking-wider text-neutral-400">
                            <tr>
                              <th className="px-3 py-1 pl-9 text-left font-semibold">下注方式</th>
                              <th className="px-3 py-1 text-left font-semibold">期號 / 核對</th>
                              <th className="px-3 py-1 text-left font-semibold">下注組合</th>
                              <th className="px-3 py-1 text-right font-semibold">成本</th>
                              <th className="px-3 py-1 text-right font-semibold">派彩</th>
                              <th className="px-3 py-1 text-right font-semibold">盈虧</th>
                              <th className="px-3 py-1 text-right font-semibold">撤銷</th>
                            </tr>
                          </thead>
                          <tbody className="font-mono">
                            {day.rows.map((v) => (
                              <React.Fragment key={v.id}>
                              <tr className="border-t border-black/[0.05] dark:border-white/[0.05]">
                                <td className="px-3 pt-1.5 pb-0 pl-9 align-top">
                                  {v.gameShort && (
                                    <span className="px-1.5 py-0.5 rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400 text-[9px] mr-1 font-sans">{v.gameShort}</span>
                                  )}
                                  <span className="px-1.5 py-0.5 rounded-full bg-violet-500/10 text-violet-600 dark:text-violet-400 text-[9px] mr-1 font-sans">{v.editionName}</span>
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
                                <td className="px-3 pt-1.5 pb-0 align-top font-sans">
                                  <IssuePicker
                                    issue={v.issue}
                                    date={day.ymd}
                                    draws={histByGame[v.game]?.draws ?? []}
                                    onSelect={(iss) => resettle(v.id, iss)}
                                    extraOption={histByGame[v.game]?.next ?? undefined}
                                    showNums={false}
                                    onRefresh={() => resettle(v.id, v.issue)}
                                    onManualHit={(k) => resettle(v.id, v.issue, k)}
                                  />
                                </td>
                                <td className="px-3 pt-1.5 pb-0 align-top text-neutral-700 dark:text-neutral-300">
                                  {v.balls.length > 0 ? v.balls.map(n => String(n).padStart(2, '0')).join(' ') : '—'}
                                </td>
                                <td className="px-3 pt-1.5 pb-0 align-top text-right font-bold text-neutral-900 dark:text-white">{money(v.cost)}</td>
                                <td className="px-3 pt-1.5 pb-0 align-top text-right text-emerald-600 dark:text-emerald-400">
                                  {v.pending ? <span className="text-neutral-400">待開獎</span> : money(v.payout)}
                                </td>
                                <td className={`px-3 pt-1.5 pb-0 align-top text-right font-bold ${v.pending ? 'text-neutral-400' : pnlCls(v.pnl)}`}>
                                  {v.pending ? '—' : signedMoney(v.pnl)}
                                </td>
                                <td className="px-3 pt-1.5 pb-0 align-top text-right font-sans">
                                  {confirmDeleteId === v.id ? (
                                    <button
                                      type="button"
                                      onClick={() => { deleteById(v.id); setConfirmDeleteId(null); }}
                                      className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-rose-600 text-white hover:bg-rose-700 transition-colors"
                                    >
                                      確認?
                                    </button>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={() => setConfirmDeleteId(v.id)}
                                      title="撤銷這一筆"
                                      className="inline-flex items-center p-1 rounded-md text-neutral-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-black/5 dark:hover:bg-white/5 transition-colors active:scale-95"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                  )}
                                </td>
                              </tr>
                              {v.units > 0 && (
                                <tr>
                                  <td colSpan={7} className="px-3 pt-0 pb-1.5 pl-9 text-[10px] text-neutral-400 dark:text-neutral-500">
                                    {v.units.toLocaleString()} {v.unitLabel} × ${v.perUnit.toLocaleString()}/{v.unitLabel} = ${v.cost.toLocaleString()}
                                  </td>
                                </tr>
                              )}
                              </React.Fragment>
                            ))}
                          </tbody>
                        </table>
                        </div>
                        )}
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
