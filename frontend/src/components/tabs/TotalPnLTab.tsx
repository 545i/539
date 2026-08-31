import React, { useEffect, useMemo, useState } from 'react';
import {
  TrendingDown,
  TrendingUp,
  Info,
  Layers,
  CalendarClock,
  ArrowUpRight,
  ShieldAlert
} from 'lucide-react';
// 未登入時沒有後端流水可彙整,沿用 v2 的示範數字
import { TOTAL_STRATEGY_PERFORMANCE } from '../../data/lotteryData';
import { GameKey, LedgerMode } from '../../api/client';
import { useGame } from '../../api/useGame';
import { useAllLedger } from '../../api/useLedger';
import { useEditions } from '../../api/useEditions';

// 追平方案的「哪一款 × 哪種下法 × 幾車」沿用 v2 原本的 client-side 設定,
// 只有每車成本 / 每車彩金改讀後端 GameDTO。
// 這一頁是跨遊戲的總帳,追平矩陣刻意把三款都列出來比 —— 不跟著全域切換走,
// 只把目前選的那款標出來(下方 isCurrent)。
// TODO(api): 需要追平車數試算端點(目前 api.pillarRecovery 只涵蓋三柱 1800碰)
const RECOVERY_PLANS: {
  key: GameKey;
  mode: 'single' | 'multi';
  balls?: number;
  cars: number;
}[] = [
  { key: 'lotto539', mode: 'single', cars: 12 },
  { key: 'lotto539', mode: 'multi', balls: 20, cars: 48 },
  { key: 'fantasy5', mode: 'single', cars: 12 },
  { key: 'marksix', mode: 'single', cars: 10 },
  { key: 'marksix', mode: 'multi', balls: 20, cars: 58 },
];

// 四種下法在績效表上的顯示順序與名稱
const MODE_ROWS: { mode: LedgerMode; name: string }[] = [
  { mode: 'single', name: '1組' },
  { mode: 'multi', name: '2組' },
  { mode: 'pillar1800', name: '三柱1800碰' },
  { mode: 'combo9000', name: '9000碰' },
  { mode: 'combo', name: '連碰 (星碰/立柱)' },
];

const num = (v: unknown): number => (typeof v === 'number' && isFinite(v) ? v : 0);
const signed = (v: number) => (v >= 0 ? `+${v.toLocaleString()}` : v.toLocaleString());

// 週期 = 週一~週日,全自動由開獎日期推導(不靠手動 cycle,跨週自動歸期)。
// 以 UTC 計算避開時區把日期挪錯天;週日(getUTCDay()===0)歸到前一個週一。
const _addDays = (ymd: string, n: number): string => {
  const [y, m, d] = ymd.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
};
const weekMonday = (raw: string): string => {
  const s = String(raw ?? '');
  if (!/^\d{4}-\d{2}-\d{2}/.test(s)) return '';      // 沒日期 → 未分週期
  const ymd = s.slice(0, 10);
  const [y, m, d] = ymd.split('-').map(Number);
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return _addDays(ymd, dow === 0 ? -6 : 1 - dow);
};
const weekLabel = (monday: string): string =>
  monday ? `${monday.replace(/-/g, '/')} ~ ${_addDays(monday, 6).slice(5).replace('-', '/')}` : '未分週期(無日期)';

export const TotalPnLTab: React.FC = () => {
  // 盤口資料共用全域遊戲 context 抓好的清單,不再自己打一次 /api/games
  const { games, gameKey, loading: gamesLoading } = useGame();
  // 登入時四種下法的紀錄都在後端,直接彙整;未登入退回示範數字
  const { entries, loading: ledgerLoading, error: ledgerError, loggedIn } = useAllLedger();
  const { editions } = useEditions();
  // 模擬版:不計入總損益。'all'(總版)與各版損益表都排除它;但可單獨選它檢視測試結果。
  const simEids = useMemo(
    () => new Set(editions.filter(e => e.simulated).map(e => e.eid)),
    [editions],
  );

  // 依「版」篩選整頁:'all' = 總版(全部版合併,排除模擬版);否則只看選中的版(舊紀錄沒 edition 當版 1)
  const [selEd, setSelEd] = useState<number | 'all'>('all');
  const edOf = (e: { record: Record<string, unknown> }) =>
    num((e.record as Record<string, unknown>).edition) || 1;
  const edName = (ed: number) => editions.find(x => x.eid === ed)?.name ?? `版${ed}`;
  const shownEntries = useMemo(
    () => (selEd === 'all'
      ? entries.filter(e => !simEids.has(edOf(e)))     // 總版排除模擬版
      : entries.filter(e => edOf(e) === selEd)),       // 選特定版(含模擬版)照顯示
    [entries, selEd, simEids],
  );
  // 頁面出現過的版(依 eid 排序),給切換鈕用
  const usedEds = useMemo(() => {
    const s = new Set<number>(entries.map(edOf));
    return Array.from(s).sort((a, b) => a - b);
  }, [entries]);

  // 各版損益:每一版一列(不受上方切換影響,永遠列全部版),最後一列是總版總計
  const editionRows = useMemo(() => {
    const by = new Map<number, { rounds: number; cost: number; payout: number; pnl: number }>();
    for (const e of entries) {
      const ed = edOf(e);
      if (simEids.has(ed)) continue;     // 各版損益表 + 總計排除模擬版
      const acc = by.get(ed) ?? { rounds: 0, cost: 0, payout: 0, pnl: 0 };
      acc.rounds += 1;
      acc.cost += num(e.record.cost);
      acc.payout += num(e.record.payout);
      acc.pnl += num(e.record.pnl);
      by.set(ed, acc);
    }
    return Array.from(by.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([ed, v]) => ({ ed, name: edName(ed), ...v }));
  }, [entries, editions]);

  // 各週損益(全自動週期):依開獎日期把每筆歸到「週一~週日」那一週,彙總
  // 成本/派彩/淨損益/筆數。排除模擬版(同總版原則);沒日期的歸「未分週期」。
  // 週期完全由日期推導 —— 跨週自動分期、過了下一週自動另立一列,無需手動開/結算。
  const cycleRows = useMemo(() => {
    const by = new Map<string, { rounds: number; cost: number; payout: number; pnl: number }>();
    for (const e of entries) {
      if (simEids.has(edOf(e))) continue;     // 模擬版不計入週期營利,與總版一致
      const wk = weekMonday(String(e.record.date ?? ''));
      const acc = by.get(wk) ?? { rounds: 0, cost: 0, payout: 0, pnl: 0 };
      acc.rounds += 1;
      acc.cost += num(e.record.cost);
      acc.payout += num(e.record.payout);
      acc.pnl += num(e.record.pnl);
      by.set(wk, acc);
    }
    return Array.from(by.entries())
      // 週:新→舊(未分週期的空字串排最後)
      .sort((a, b) => (a[0] && b[0] ? b[0].localeCompare(a[0]) : a[0] ? -1 : 1))
      .map(([wk, v]) => ({ key: wk || 'nodate', name: weekLabel(wk), ...v }));
  }, [entries, simEids]);

  const perfRows = useMemo(() => {
    if (!loggedIn) return TOTAL_STRATEGY_PERFORMANCE;
    return MODE_ROWS.map(({ mode, name }) => {
      const rows = shownEntries.filter(e => e.mode === mode).map(e => e.record);
      const cost = rows.reduce((a, r) => a + num(r.cost), 0);
      const payout = rows.reduce((a, r) => a + num(r.payout), 0);
      const pnl = rows.reduce((a, r) => a + num(r.pnl), 0);
      return {
        name,
        rounds: rows.length,
        hits: rows.filter(r => num(r.payout) > 0).length,
        cost,
        payout,
        pnl,
        roi: `${cost ? ((pnl / cost) * 100).toFixed(1) : '0.0'}%`,
      };
    });
  }, [loggedIn, shownEntries]);

  const totals = useMemo(() => {
    const cost = perfRows.reduce((a, r) => a + r.cost, 0);
    const payout = perfRows.reduce((a, r) => a + r.payout, 0);
    const pnl = perfRows.reduce((a, r) => a + r.pnl, 0);
    const rounds = perfRows.reduce((a, r) => a + r.rounds, 0);
    const hits = perfRows.reduce((a, r) => a + r.hits, 0);
    // 下注累積總車數:1組/2組用車數,三柱/連碰/9000碰用支數(cars 缺就取 units)
    const cars = loggedIn
      ? shownEntries.reduce((a, e) => a + num(e.record.cars ?? e.record.units), 0)
      : 0;
    return {
      cost, payout, pnl, rounds, hits, cars,
      roi: cost ? (pnl / cost) * 100 : 0,
      winRate: rounds ? (hits / rounds) * 100 : 0,
    };
  }, [perfRows, loggedIn, shownEntries]);

  // 淨值走勢:登入時依流水順序累加,未登入沒有逐筆資料就不畫(跟隨上方版切換)
  const curve = useMemo(() => {
    if (!loggedIn || shownEntries.length === 0) return null;
    let running = 0;
    const cums = [0, ...shownEntries.map(e => (running += num(e.record.pnl)))];
    const hi = Math.max(...cums);
    const lo = Math.min(...cums);
    const x = (i: number) => (cums.length > 1 ? 40 + (410 * i) / (cums.length - 1) : 245);
    const y = (v: number) => (hi === lo ? 50 : 15 + ((hi - v) * 75) / (hi - lo));
    return {
      cums,
      points: cums.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' '),
      dots: cums.map((v, i) => ({ cx: x(i), cy: y(v), v })),
      last: cums[cums.length - 1],
      firstDate: String(shownEntries[0].record.date ?? ''),
      lastDate: String(shownEntries[shownEntries.length - 1].record.date ?? ''),
    };
  }, [loggedIn, shownEntries]);

  // 盤口全部讀 GameDTO;清單還沒回來就整列不算,不拿別款的數字硬湊
  const recoveryRows = RECOVERY_PLANS.flatMap(p => {
    const g = games.find(x => x.key === p.key);
    if (!g) return [];
    const balls = p.balls ?? 1;
    // 二合盤口:每車成本 = 顆數 × 2755;中 1 顆每車 = 21200(不除以 4,單顆多顆一致)
    const perCarCost = g.default_cost_per_car * balls;
    const perCarPrize = g.default_win_payout;
    const cost = Math.round(p.cars * perCarCost);
    const prize = Math.round(p.cars * perCarPrize);
    return [{
      key: p.key,
      mode: p.mode,
      isCurrent: p.key === gameKey,
      game: `${g.short_name} (${p.mode === 'single' ? '1組' : `2組 ${balls}顆`})`,
      cars: p.cars,
      net: prize - cost,
      costNum: cost,
      cost: cost.toLocaleString(),
      prize: prize.toLocaleString(),
      afterPnl: `+${(prize - cost).toLocaleString()}`,
    }];
  });

  // 「最佳追平」= 填得平這個洞的方案裡最便宜的那個;都填不平就選淨賺最多的。
  // (以前寫死六合彩單顆,虧損金額一變就對不上。)
  const need = Math.max(0, -totals.pnl);
  const bestPlan =
    [...recoveryRows].filter(r => r.net >= need).sort((a, b) => a.costNum - b.costNum)[0] ??
    [...recoveryRows].sort((a, b) => b.net - a.net)[0];

  return (
    <div className="space-y-4 sm:space-y-5 animate-in fade-in duration-200 w-full overflow-hidden">
      {/* Top Banner Bar */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.25em] text-neutral-400 dark:text-neutral-500 font-semibold">
              Consolidated Balance & Risk Management
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              全策略總帳{loggedIn && selEd !== 'all' ? `・${edName(selEd)}` : ''}
            </span>
          </div>
          <div className="text-base sm:text-xl font-display font-bold text-neutral-900 dark:text-white mt-0.5">
            綜合損益與資金追平戰略總覽
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            單顆 + 多顆 + 三柱1800碰 + 連碰 跨策略整體資金水位與最佳追平路徑。
          </div>
        </div>

        <div className="flex items-center justify-between md:justify-end gap-4 border-t md:border-t-0 pt-2.5 md:pt-0 border-black/[0.06] dark:border-white/[0.06]">
          <div className="text-left md:text-right">
            <span className="text-[10px] uppercase tracking-wider text-neutral-400 block">整體帳號淨損益</span>
            <div className={`text-xl sm:text-2xl font-mono font-bold ${
              totals.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
            }`}>
              {signed(totals.pnl)}
            </div>
          </div>
          <div className="text-right text-[11px] font-mono text-neutral-400">
            {totals.rounds} 局・中獎 {totals.hits} 局 ({totals.winRate.toFixed(0)}%)
          </div>
        </div>
      </div>

      {/* 版切換:整頁數字依選中的版重算('全部版' = 總版合併) */}
      {loggedIn && usedEds.length > 1 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold flex items-center gap-1">
            <Layers className="w-3.5 h-3.5" /> 依版檢視
          </span>
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
              {ed === 'all' ? '全部版(總版)' : edName(ed)}
            </button>
          ))}
        </div>
      )}

      {/* 6 Overall Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-2.5 sm:gap-3">
        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] col-span-2 sm:col-span-1">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">累積淨損益</div>
          <div className={`text-lg sm:text-xl font-bold font-mono mt-0.5 ${
            totals.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
          }`}>
            {signed(totals.pnl)}
          </div>
          {totals.pnl < 0 && (
            <div className="text-[10px] text-rose-500 dark:text-rose-400 mt-0.5 flex items-center gap-0.5">
              <TrendingDown className="w-3 h-3" /> 需執行追平
            </div>
          )}
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">總投入成本</div>
          <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
            {totals.cost.toLocaleString()}
          </div>
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">總回收彩金</div>
          <div className="text-base sm:text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
            {totals.payout.toLocaleString()}
          </div>
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">報酬率 (ROI)</div>
          <div className={`text-base sm:text-lg font-bold font-mono mt-0.5 ${
            totals.roi >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
          }`}>
            {totals.roi.toFixed(1)}%
          </div>
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">綜合勝率</div>
          <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
            {totals.winRate.toFixed(1)}%
          </div>
          <div className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-0.5">
            中 {totals.hits} / {totals.rounds} 局
          </div>
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">累積總車數</div>
          <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
            {totals.cars.toLocaleString()} <span className="text-[10px] font-normal text-neutral-400">車/支</span>
          </div>
          <div className="text-[10px] text-neutral-400 mt-0.5">
            共 {totals.rounds} 局
          </div>
        </div>
      </div>

      {ledgerLoading && <div className="text-xs text-neutral-400">載入流水帳中…</div>}
      {ledgerError && <div className="text-xs text-rose-500">{ledgerError}</div>}
      {!loggedIn && (
        <div className="text-[11px] text-neutral-400">
          未登入:以下為示範數字。登入後這裡會彙整你實際記在四個分頁的流水帳。
        </div>
      )}

      {/* 各版損益:每一版一列 + 總版總計(永遠列全部版,不受上方切換影響)*/}
      {loggedIn && editionRows.length > 0 && (
        <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-neutral-500" /> 各版損益
            </h3>
            <span className="text-[10px] font-mono text-neutral-400">點上方切換鈕可只看單一版</span>
          </div>
          <div className="lt-wrap border border-black/[0.08] dark:border-white/[0.08] rounded-xl overflow-x-auto">
            <table className="lt w-full">
              <thead>
                <tr>
                  <th>版</th>
                  <th>局數</th>
                  <th>總成本</th>
                  <th>總回收</th>
                  <th>淨損益</th>
                  <th>ROI</th>
                </tr>
              </thead>
              <tbody>
                {editionRows.map(r => (
                  <tr
                    key={r.ed}
                    className={selEd === r.ed ? 'bg-black/[0.03] dark:bg-white/[0.05]' : undefined}
                  >
                    <td className="font-semibold text-xs text-neutral-900 dark:text-white">{r.name}</td>
                    <td className="font-mono text-xs">{r.rounds}</td>
                    <td className="font-mono text-xs">{r.cost.toLocaleString()}</td>
                    <td className="font-mono text-xs text-emerald-600 dark:text-emerald-400 font-bold">{r.payout.toLocaleString()}</td>
                    <td className={`font-mono text-xs font-bold ${r.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                      {signed(r.pnl)}
                    </td>
                    <td className="font-mono text-xs">{r.cost ? ((r.pnl / r.cost) * 100).toFixed(1) : '0.0'}%</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.05]">
                  <td className="font-sans font-bold text-xs text-neutral-900 dark:text-white">總版總計</td>
                  <td className="font-mono text-xs font-bold">{editionRows.reduce((a, r) => a + r.rounds, 0)}</td>
                  <td className="font-mono text-xs font-bold">{editionRows.reduce((a, r) => a + r.cost, 0).toLocaleString()}</td>
                  <td className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400">{editionRows.reduce((a, r) => a + r.payout, 0).toLocaleString()}</td>
                  {(() => {
                    const tPnl = editionRows.reduce((a, r) => a + r.pnl, 0);
                    const tCost = editionRows.reduce((a, r) => a + r.cost, 0);
                    return (
                      <>
                        <td className={`font-mono text-xs font-bold ${tPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{signed(tPnl)}</td>
                        <td className="font-mono text-xs font-bold">{tCost ? ((tPnl / tCost) * 100).toFixed(1) : '0.0'}%</td>
                      </>
                    );
                  })()}
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* 各週損益:全自動週期,每一週(週一~週日)一列(排除模擬版,同總版原則)*/}
      {loggedIn && cycleRows.length > 0 && (
        <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-1.5">
              <CalendarClock className="w-4 h-4 text-neutral-500" /> 各週損益
            </h3>
            <span className="text-[10px] font-mono text-neutral-400">週一~週日自動歸期(不計模擬版)</span>
          </div>
          <div className="lt-wrap border border-black/[0.08] dark:border-white/[0.08] rounded-xl overflow-x-auto">
            <table className="lt w-full">
              <thead>
                <tr>
                  <th>週期(週一~週日)</th>
                  <th>筆數</th>
                  <th>總成本</th>
                  <th>總派彩</th>
                  <th>淨損益</th>
                  <th>ROI</th>
                </tr>
              </thead>
              <tbody>
                {cycleRows.map(r => (
                  <tr key={r.key}>
                    <td className="font-semibold text-xs text-neutral-900 dark:text-white">{r.name}</td>
                    <td className="font-mono text-xs">{r.rounds}</td>
                    <td className="font-mono text-xs">{r.cost.toLocaleString()}</td>
                    <td className="font-mono text-xs text-emerald-600 dark:text-emerald-400 font-bold">{r.payout.toLocaleString()}</td>
                    <td className={`font-mono text-xs font-bold ${r.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                      {signed(r.pnl)}
                    </td>
                    <td className="font-mono text-xs">{r.cost ? ((r.pnl / r.cost) * 100).toFixed(1) : '0.0'}%</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.05]">
                  <td className="font-sans font-bold text-xs text-neutral-900 dark:text-white">全部週合計</td>
                  <td className="font-mono text-xs font-bold">{cycleRows.reduce((a, r) => a + r.rounds, 0)}</td>
                  <td className="font-mono text-xs font-bold">{cycleRows.reduce((a, r) => a + r.cost, 0).toLocaleString()}</td>
                  <td className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400">{cycleRows.reduce((a, r) => a + r.payout, 0).toLocaleString()}</td>
                  {(() => {
                    const tPnl = cycleRows.reduce((a, r) => a + r.pnl, 0);
                    const tCost = cycleRows.reduce((a, r) => a + r.cost, 0);
                    return (
                      <>
                        <td className={`font-mono text-xs font-bold ${tPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{signed(tPnl)}</td>
                        <td className="font-mono text-xs font-bold">{tCost ? ((tPnl / tCost) * 100).toFixed(1) : '0.0'}%</td>
                      </>
                    );
                  })()}
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Dual Column: Performance Breakdown & Recovery Planner */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-5">
        
        {/* Left Column (7/12) - Strategy Performance & Trend Chart */}
        <div className="lg:col-span-7 space-y-4">
          
          {/* Strategy Performance Section */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              01 / 4 大下注策略績效分佈
            </h3>

            {/* Mobile View: Cards */}
            <div className="space-y-2 sm:hidden">
              {perfRows.map((row, i) => (
                <div key={i} className="p-3 rounded-xl border border-black/[0.08] dark:border-white/[0.08] bg-black/[0.01] dark:bg-white/[0.02] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-neutral-900 dark:text-white">{row.name}</span>
                    <span className={`text-xs font-mono font-bold ${row.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                      {row.pnl >= 0 ? `+${row.pnl.toLocaleString()}` : row.pnl.toLocaleString()}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1 text-[10px] text-neutral-500 pt-1 border-t border-black/[0.04] dark:border-white/[0.04]">
                    <div>局數: <span className="font-mono text-neutral-800 dark:text-neutral-200">{row.rounds} (中{row.hits})</span></div>
                    <div>成本: <span className="font-mono text-neutral-800 dark:text-neutral-200">{row.cost.toLocaleString()}</span></div>
                    <div>ROI: <span className="font-mono text-neutral-800 dark:text-neutral-200">{row.roi}</span></div>
                  </div>
                </div>
              ))}
            </div>

            {/* Desktop Table View */}
            <div className="lt-wrap border border-black/[0.08] dark:border-white/[0.08] rounded-xl hidden sm:block">
              <table className="lt">
                <thead>
                  <tr>
                    <th>策略名稱</th>
                    <th>局數</th>
                    <th>中獎</th>
                    <th>總成本</th>
                    <th>總回收</th>
                    <th>淨損益</th>
                    <th>ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {perfRows.map((row, i) => (
                    <tr key={i}>
                      <td className="font-semibold text-neutral-900 dark:text-white text-xs">{row.name}</td>
                      <td className="font-mono text-xs">{row.rounds}</td>
                      <td className="font-mono text-xs">{row.hits}</td>
                      <td className="font-mono text-xs">{row.cost.toLocaleString()}</td>
                      <td className="font-mono text-xs text-emerald-600 dark:text-emerald-400 font-bold">{row.payout.toLocaleString()}</td>
                      <td className={`font-mono text-xs font-bold ${row.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {row.pnl >= 0 ? `+${row.pnl.toLocaleString()}` : row.pnl.toLocaleString()}
                      </td>
                      <td className="font-mono text-xs">{row.roi}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* SVG Trend Chart */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                02 / 帳戶淨值走勢曲線
              </h3>
              <span className="text-[10px] font-mono text-neutral-400">即時計算</span>
            </div>

            <div className="relative h-44 sm:h-48 w-full pt-4 pb-4 px-2 sm:px-3 bg-black/[0.01] dark:bg-white/[0.01] rounded-xl border border-black/[0.06] dark:border-white/[0.06] flex flex-col justify-between overflow-hidden">
              <svg className="w-full h-28 overflow-visible" viewBox="0 0 500 100">
                <line x1="20" y1="15" x2="480" y2="15" stroke="currentColor" className="text-black/[0.08] dark:text-white/[0.08]" strokeWidth="1" strokeDasharray="3 3" />
                <line x1="20" y1="50" x2="480" y2="50" stroke="currentColor" className="text-black/[0.05] dark:text-white/[0.05]" strokeWidth="1" />
                <line x1="20" y1="85" x2="480" y2="85" stroke="currentColor" className="text-black/[0.05] dark:text-white/[0.05]" strokeWidth="1" />

                {curve ? (
                  <>
                    <polyline
                      fill="none"
                      stroke="currentColor"
                      className="text-neutral-900 dark:text-white"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      points={curve.points}
                    />

                    {curve.dots.map((d, i) => (
                      <circle
                        key={i}
                        cx={d.cx}
                        cy={d.cy}
                        r={i === curve.dots.length - 1 ? 4.5 : 4}
                        className={
                          i === curve.dots.length - 1
                            ? `${curve.last >= 0 ? 'fill-emerald-500' : 'fill-rose-500'} stroke-white dark:stroke-black stroke-2`
                            : 'fill-neutral-900 dark:fill-white'
                        }
                      />
                    ))}

                    <text x={curve.dots[0].cx} y={curve.dots[0].cy - 8} textAnchor="middle" className="text-[10px] font-mono fill-neutral-400">
                      NT$ 0
                    </text>
                    <text
                      x={curve.dots[curve.dots.length - 1].cx}
                      y={curve.dots[curve.dots.length - 1].cy - 8}
                      textAnchor="end"
                      className={`text-[10px] font-mono font-bold ${curve.last >= 0 ? 'fill-emerald-500' : 'fill-rose-500'}`}
                    >
                      {signed(curve.last)}
                    </text>
                  </>
                ) : (
                  <text x="250" y="55" textAnchor="middle" className="text-[10px] font-mono fill-neutral-400">
                    {loggedIn ? '尚無流水紀錄' : '登入後顯示實際淨值走勢'}
                  </text>
                )}
              </svg>

              <div className="flex justify-between px-2 sm:px-4 text-[10px] font-mono text-neutral-400 pt-1 border-t border-black/[0.06] dark:border-white/[0.06]">
                <span>{curve ? `${curve.firstDate} 起始` : '起始'}</span>
                <span>{curve ? `${shownEntries.length} 筆紀錄` : '—'}</span>
                <span>{curve ? curve.lastDate : '最新'}</span>
              </div>
            </div>
          </div>

        </div>

        {/* Right Column (5/12) - Recovery Planner Matrix */}
        <div className="lg:col-span-5 space-y-4">
          
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                03 / 追平回本方案矩陣
              </h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 font-bold">
                目標: {signed(Math.max(0, -totals.pnl))}
              </span>
            </div>

            {bestPlan && (
              <div className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] text-xs space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-neutral-900 dark:text-white">
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                  <span>最佳追平途徑推薦</span>
                </div>
                <p className="text-neutral-500 dark:text-neutral-400 text-[11px] leading-relaxed">
                  欲一次填平 <strong>{need.toLocaleString()}</strong> 虧損，建議採用「{bestPlan.game}」下注 {bestPlan.cars} 車 (成本 {bestPlan.cost}，命中可獲 {bestPlan.prize})，以最低成本回本。
                </p>
              </div>
            )}

            {gamesLoading && <div className="text-xs text-neutral-400">載入盤口資料…</div>}
            {!gamesLoading && recoveryRows.length === 0 && (
              <div className="text-xs text-rose-500">讀不到盤口資料,請重新整理頁面。</div>
            )}

            {/* Mobile View: Recovery Cards */}
            <div className="space-y-2 sm:hidden">
              {recoveryRows.map((row, i) => (
                <div
                  key={i}
                  className={`p-3 rounded-xl border space-y-1.5 ${
                    row.isCurrent
                      ? 'border-black/20 dark:border-white/20 bg-black/[0.04] dark:bg-white/[0.06]'
                      : 'border-black/[0.08] dark:border-white/[0.08] bg-black/[0.01] dark:bg-white/[0.02]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-neutral-900 dark:text-white">{row.game}</span>
                    <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">{row.cars} 車</span>
                  </div>
                  <div className="grid grid-cols-3 gap-1 text-[10px] text-neutral-500 pt-1 border-t border-black/[0.04] dark:border-white/[0.04]">
                    <div>成本: <span className="font-mono text-neutral-800 dark:text-neutral-200">{row.cost}</span></div>
                    <div>彩金: <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">{row.prize}</span></div>
                    <div>累積: <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">{row.afterPnl}</span></div>
                  </div>
                </div>
              ))}
            </div>

            {/* Desktop Table View */}
            <div className="lt-wrap border border-black/[0.08] dark:border-white/[0.08] rounded-xl hidden sm:block">
              <table className="lt">
                <thead>
                  <tr>
                    <th>遊戲下法</th>
                    <th>車數</th>
                    <th>本局成本</th>
                    <th>中獎彩金</th>
                    <th>命中後累積</th>
                  </tr>
                </thead>
                <tbody>
                  {recoveryRows.map((row, i) => (
                    <tr key={i} className={row.isCurrent ? 'bg-black/[0.03] dark:bg-white/[0.05]' : undefined}>
                      <td className="font-semibold text-xs text-neutral-900 dark:text-white">{row.game}</td>
                      <td className="font-mono text-xs font-bold">{row.cars} 車</td>
                      <td className="font-mono text-xs">{row.cost}</td>
                      <td className="font-mono text-xs text-emerald-600 dark:text-emerald-400 font-bold">{row.prize}</td>
                      <td className="font-mono text-xs text-emerald-600 dark:text-emerald-400 font-bold">{row.afterPnl}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};
