import React, { useState } from 'react';
import { 
  TrendingDown, 
  TrendingUp,
  Info,
  Layers,
  ArrowUpRight,
  ShieldAlert
} from 'lucide-react';
// TODO(api): 各策略績效彙整目前仍是 client-side 流水帳,沒有後端總損益端點
import { TOTAL_STRATEGY_PERFORMANCE } from '../../data/lotteryData';
import { api, GameKey } from '../../api/client';
import { useAsync } from '../../api/useAsync';

// 追平方案的「哪一款 × 哪種下法 × 幾車」沿用 v2 原本的 client-side 設定,
// 只有每車成本 / 每車彩金改讀後端 GameDTO。
// TODO(api): 需要追平車數試算端點(目前 api.pillarRecovery 只涵蓋三柱 1800碰)
const RECOVERY_PLANS: {
  key: GameKey;
  label: string;
  mode: 'single' | 'multi';
  balls?: number;
  cars: number;
}[] = [
  { key: 'lotto539', label: '今彩539', mode: 'single', cars: 12 },
  { key: 'lotto539', label: '今彩539', mode: 'multi', balls: 20, cars: 48 },
  { key: 'fantasy5', label: '天天樂', mode: 'single', cars: 12 },
  { key: 'marksix', label: '六合彩', mode: 'single', cars: 10 },
  { key: 'marksix', label: '六合彩', mode: 'multi', balls: 20, cars: 58 },
];

export const TotalPnLTab: React.FC = () => {
  const { data: games, loading: gamesLoading, error: gamesError } = useAsync(() => api.games(), []);

  const recoveryRows = RECOVERY_PLANS.map(p => {
    const g = games?.find(x => x.key === p.key);
    const balls = p.balls ?? 1;
    // 多顆下法沿用 v2 的換算比例:每顆每車彩金 = 每車中獎可得 ÷ 4
    const perCarCost = (g?.default_cost_per_car ?? 2755) * balls;
    const perCarPrize =
      p.mode === 'multi' ? ((g?.default_win_payout ?? 21200) / 4) * balls : (g?.default_win_payout ?? 21200);
    const cost = Math.round(p.cars * perCarCost);
    const prize = Math.round(p.cars * perCarPrize);
    return {
      key: p.key,
      mode: p.mode,
      game: `${g?.short_name ?? p.label} (${p.mode === 'single' ? '單顆' : `多顆 ${balls}顆`})`,
      cars: p.cars,
      cost: cost.toLocaleString(),
      prize: prize.toLocaleString(),
      afterPnl: `+${(prize - cost).toLocaleString()}`,
    };
  });

  const bestPlan = recoveryRows.find(r => r.key === 'marksix' && r.mode === 'single') ?? recoveryRows[0];

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
              全策略總帳
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
            <div className="text-xl sm:text-2xl font-mono font-bold text-rose-600 dark:text-rose-400">
              -232,386
            </div>
          </div>
          <div className="text-right text-[11px] font-mono text-neutral-400">
            4 局・中獎 2 局 (50%)
          </div>
        </div>
      </div>

      {/* 5 Overall Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 sm:gap-3">
        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] col-span-2 sm:col-span-1">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">累積淨損益</div>
          <div className="text-lg sm:text-xl font-bold font-mono text-rose-600 dark:text-rose-400 mt-0.5">
            -232,386
          </div>
          <div className="text-[10px] text-rose-500 dark:text-rose-400 mt-0.5 flex items-center gap-0.5">
            <TrendingDown className="w-3 h-3" /> 需執行追平
          </div>
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">總投入成本</div>
          <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
            311,136
          </div>
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">總回收彩金</div>
          <div className="text-base sm:text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
            78,750
          </div>
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">報酬率 (ROI)</div>
          <div className="text-base sm:text-lg font-bold font-mono text-rose-600 dark:text-rose-400 mt-0.5">
            -74.7%
          </div>
        </div>

        <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">綜合勝率</div>
          <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
            50.0%
          </div>
          <div className="text-[10px] text-emerald-600 dark:text-emerald-400 mt-0.5">
            中 2 / 4 局
          </div>
        </div>
      </div>

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
              {TOTAL_STRATEGY_PERFORMANCE.map((row, i) => (
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
                  {TOTAL_STRATEGY_PERFORMANCE.map((row, i) => (
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

                <polyline
                  fill="none"
                  stroke="currentColor"
                  className="text-neutral-900 dark:text-white"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  points="40,15 170,40 310,65 450,90"
                />

                <circle cx="40" cy="15" r="4" className="fill-neutral-900 dark:fill-white" />
                <circle cx="170" cy="40" r="4" className="fill-neutral-900 dark:fill-white" />
                <circle cx="310" cy="65" r="4" className="fill-neutral-900 dark:fill-white" />
                <circle cx="450" cy="90" r="4.5" className="fill-rose-500 stroke-white dark:stroke-black stroke-2" />

                <text x="40" y="10" textAnchor="middle" className="text-[10px] font-mono fill-neutral-400">NT$ 0</text>
                <text x="170" y="34" textAnchor="middle" className="text-[10px] font-mono fill-neutral-400">-68k</text>
                <text x="310" y="59" textAnchor="middle" className="text-[10px] font-mono fill-neutral-400">-148k</text>
                <text x="450" y="84" textAnchor="middle" className="text-[10px] font-mono font-bold fill-rose-500">-232,386</text>
              </svg>

              <div className="flex justify-between px-2 sm:px-4 text-[10px] font-mono text-neutral-400 pt-1 border-t border-black/[0.06] dark:border-white/[0.06]">
                <span>08/12 起始</span>
                <span>08/12 #196</span>
                <span>08/12 #197</span>
                <span>08/13 #196</span>
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
                目標: +232k
              </span>
            </div>

            <div className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] text-xs space-y-1">
              <div className="flex items-center gap-1.5 font-bold text-neutral-900 dark:text-white">
                <ShieldAlert className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                <span>最佳追平途徑推薦</span>
              </div>
              <p className="text-neutral-500 dark:text-neutral-400 text-[11px] leading-relaxed">
                欲一次填平 <strong>232,386</strong> 虧損，建議採用「六合彩・單顆」下注 {bestPlan.cars} 車 (成本僅 {bestPlan.cost}，命中可獲 {bestPlan.prize})，以最低風險回本。
              </p>
            </div>

            {gamesLoading && <div className="text-xs text-neutral-400">載入盤口資料…</div>}
            {gamesError && <div className="text-xs text-rose-500">{gamesError}</div>}

            {/* Mobile View: Recovery Cards */}
            <div className="space-y-2 sm:hidden">
              {recoveryRows.map((row, i) => (
                <div key={i} className="p-3 rounded-xl border border-black/[0.08] dark:border-white/[0.08] bg-black/[0.01] dark:bg-white/[0.02] space-y-1.5">
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
                    <tr key={i}>
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
