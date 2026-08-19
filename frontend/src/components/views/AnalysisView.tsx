import React, { useMemo, useState } from 'react';
import { BarChart3, Flame, Snowflake, LayoutGrid } from 'lucide-react';
import { api } from '../../api/client';
import { useAsync } from '../../api/useAsync';

const GAME = 'lotto539' as const;
const WINDOW = 830; // 冷熱號取樣期數(資料不足時以實際期數為準)
const PICK = 5;
const NUM_MAX = 39; // 今彩539 號碼 01~39
const ALL_NUMS = Array.from({ length: NUM_MAX }, (_, i) => i + 1);
const HIST_OPTIONS = [20, 30, 50, 100] as const;

// 依十位分四段上色(與「區間組合提醒」同一套分組):01~09 / 10~19 / 20~29 / 30~39
function bandDot(n: number): string {
  if (n <= 9) return 'bg-neutral-900 text-white dark:bg-white dark:text-black';
  if (n <= 19) return 'bg-blue-600 text-white';
  if (n <= 29) return 'bg-amber-600 text-white';
  return 'bg-emerald-600 text-white';
}

export const AnalysisView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'draw_history' | 'hot_cold' | 'pillar_dist' | 'odd_even'>('draw_history');
  const [histN, setHistN] = useState<number>(30);

  const hotCold = useAsync(() => api.hotCold(GAME, WINDOW, 6), []);
  const history = useAsync(() => api.history(GAME), []);
  const pillarInfo = useAsync(() => api.pillarInfo(GAME), []);
  const parity = useAsync(() => api.parity(GAME), []);
  const drawHist = useAsync(() => api.history(GAME, histN), [histN]);

  // 開獎歷史走勢:最新一期排最上面
  const histRows = useMemo(
    () => [...(drawHist.data?.draws ?? [])].reverse(),
    [drawHist.data],
  );
  // 各號在這段期數內的出現次數(欄位分佈統計)
  const histFreq = useMemo(() => {
    const f = new Map<number, number>();
    for (const d of drawHist.data?.draws ?? [])
      for (const n of d.nums) f.set(n, (f.get(n) ?? 0) + 1);
    return f;
  }, [drawHist.data]);

  // 出現率的分母:近 WINDOW 期,但資料不足時用實際總期數
  const periods = history.data ? Math.min(WINDOW, history.data.count) : WINDOW;
  const toRate = (count: number) =>
    periods > 0 ? `${((count / periods) * 100).toFixed(1)}%` : '—';

  const hotNumbers = (hotCold.data?.hot ?? []).map(item => ({
    num: item.num,
    count: item.count,
    rate: toRate(item.count),
  }));

  const coldNumbers = (hotCold.data?.cold ?? []).map(item => ({
    num: item.num,
    count: item.count,
    rate: toRate(item.count),
  }));

  const hotColdLoading = hotCold.loading || history.loading;
  const hotColdError = hotCold.error || history.error;

  // 三柱實際開出率:全歷史每期 5 顆號碼落在各柱的比例
  const pillarActual = useMemo(() => {
    const pillars = pillarInfo.data?.pillars;
    const draws = history.data?.draws;
    if (!pillars || !draws || draws.length === 0) return null;
    const which = new Map<number, number>();
    pillars.forEach((p, i) => p.forEach(n => which.set(n, i)));
    const counts = [0, 0, 0];
    let total = 0;
    for (const d of draws) {
      for (const n of d.nums) {
        const i = which.get(n);
        if (i !== undefined) {
          counts[i] += 1;
          total += 1;
        }
      }
    }
    return total > 0 ? counts.map(c => (c / total) * 100) : null;
  }, [pillarInfo.data, history.data]);

  const sizes = pillarInfo.data?.sizes;
  const numMax = sizes ? sizes[0] + sizes[1] + sizes[2] : 0;
  const theoryRate = (i: number) =>
    sizes && numMax > 0 ? `${((sizes[i] / numMax) * 100).toFixed(2)}%` : '—';
  const actualRate = (i: number) =>
    pillarActual ? `${pillarActual[i].toFixed(1)}%` : '—';

  const pillarLoading = pillarInfo.loading || history.loading;
  const pillarError = pillarInfo.error || history.error;

  // 單號 / 大號比例:Σ(k × 期數) ÷ (每期 5 顆 × 總期數)
  const parityPct = useMemo(() => {
    const d = parity.data;
    if (!d) return null;
    const draws = Object.values(d.odd_dist).reduce((a, b) => a + b, 0);
    if (draws === 0) return null;
    const weighted = (dist: Record<string, number>) =>
      Object.entries(dist).reduce((a, [k, v]) => a + Number(k) * v, 0);
    return {
      odd: (weighted(d.odd_dist) / (PICK * draws)) * 100,
      big: (weighted(d.big_dist) / (PICK * draws)) * 100,
    };
  }, [parity.data]);

  const ratioText = (pct: number | undefined) =>
    pct === undefined ? '—' : `${pct.toFixed(1)}% : ${(100 - pct).toFixed(1)}%`;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Title */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              歷史開獎數據與統計分析
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              分析 今彩539 / 天天樂 / 六合彩 冷熱號分佈與三柱統計
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-black/[0.08] dark:border-white/[0.08] pb-2">
        {[
          { id: 'draw_history', label: '開獎歷史' },
          { id: 'hot_cold', label: '冷熱號統計' },
          { id: 'pillar_dist', label: '三柱分佈統計' },
          { id: 'odd_even', label: '單雙/大小比' }
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as any)}
            className={`px-4 py-2 text-xs uppercase tracking-wider font-semibold rounded-full transition-all ${
              activeTab === t.id
                ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                : 'text-neutral-600 dark:text-neutral-400 hover:bg-black/5 dark:hover:bg-white/5'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Draw History Distribution Matrix */}
      {activeTab === 'draw_history' && (
        <div className="p-4 sm:p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <LayoutGrid className="w-4 h-4 text-neutral-500" />
              <span>開獎歷史分佈走勢(01~39 × 開獎日期)</span>
            </div>
            <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
              {HIST_OPTIONS.map(n => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setHistN(n)}
                  className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                    histN === n
                      ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                      : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                  }`}
                >
                  近 {n} 期
                </button>
              ))}
            </div>
          </div>

          {/* 分色圖例(依十位) */}
          <div className="flex flex-wrap gap-3 text-[10px] text-neutral-500 dark:text-neutral-400">
            {[
              { c: 'bg-neutral-900 dark:bg-white', t: '01~09' },
              { c: 'bg-blue-600', t: '10~19' },
              { c: 'bg-amber-600', t: '20~29' },
              { c: 'bg-emerald-600', t: '30~39' },
            ].map(l => (
              <span key={l.t} className="inline-flex items-center gap-1">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${l.c}`} />
                {l.t}
              </span>
            ))}
          </div>

          {drawHist.loading && <div className="text-xs text-neutral-400">載入開獎歷史…</div>}
          {drawHist.error && <div className="text-xs text-rose-500">{drawHist.error}</div>}

          {!drawHist.loading && !drawHist.error && (
            <div className="overflow-x-auto -mx-1 px-1">
              <table className="border-separate border-spacing-0 text-center">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 bg-white dark:bg-[#121212] px-2 py-1.5 text-left text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                      開獎日期
                    </th>
                    {ALL_NUMS.map(n => (
                      <th
                        key={n}
                        className="px-0.5 py-1.5 text-[9px] font-mono text-neutral-400 dark:text-neutral-500 min-w-[1.35rem]"
                      >
                        {n.toString().padStart(2, '0')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {histRows.map(d => {
                    const hit = new Set(d.nums);
                    return (
                      <tr key={d.date + (d.issue ?? '')} className="hover:bg-black/[0.02] dark:hover:bg-white/[0.02]">
                        <td className="sticky left-0 z-10 bg-white dark:bg-[#121212] px-2 py-1 text-left whitespace-nowrap border-t border-black/[0.05] dark:border-white/[0.05]">
                          <span className="font-mono text-[11px] text-neutral-700 dark:text-neutral-300">{d.date}</span>
                        </td>
                        {ALL_NUMS.map(n => (
                          <td key={n} className="px-0.5 py-1 border-t border-black/[0.05] dark:border-white/[0.05]">
                            {hit.has(n) ? (
                              <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[9px] font-mono font-bold ${bandDot(n)}`}>
                                {n.toString().padStart(2, '0')}
                              </span>
                            ) : (
                              <span className="inline-block w-1 h-1 rounded-full bg-black/10 dark:bg-white/10" />
                            )}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr>
                    <td className="sticky left-0 z-10 bg-black/[0.02] dark:bg-white/[0.03] px-2 py-1.5 text-left text-[10px] uppercase tracking-wider text-neutral-400 font-semibold border-t border-black/[0.08] dark:border-white/[0.08]">
                      出現次數
                    </td>
                    {ALL_NUMS.map(n => {
                      const c = histFreq.get(n) ?? 0;
                      return (
                        <td
                          key={n}
                          className={`px-0.5 py-1.5 text-[10px] font-mono border-t border-black/[0.08] dark:border-white/[0.08] ${
                            c === 0 ? 'text-neutral-300 dark:text-neutral-600' : 'text-neutral-900 dark:text-white font-bold'
                          }`}
                        >
                          {c}
                        </td>
                      );
                    })}
                  </tr>
                </tfoot>
              </table>
            </div>
          )}

          <p className="text-[11px] text-neutral-400 dark:text-neutral-500">
            每一列為一期開獎,圓點標出當期開出的號碼(依十位分色);最下方為該號在近 {histN} 期的出現次數分佈。
          </p>
        </div>
      )}

      {/* Hot & Cold View */}
      {activeTab === 'hot_cold' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Hot numbers */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Flame className="w-4 h-4 text-amber-500" />
              <span>近 {periods} 期最熱門號碼 TOP 6</span>
            </div>
            <div className="space-y-2">
              {hotColdLoading && <div className="text-xs text-neutral-400">載入中…</div>}
              {hotColdError && <div className="text-xs text-rose-500">{hotColdError}</div>}
              {hotNumbers.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-full bg-black text-white dark:bg-white dark:text-black font-mono font-bold text-xs flex items-center justify-center">
                      {item.num.toString().padStart(2, '0')}
                    </span>
                    <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">開出 {item.count} 次</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">{item.rate}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Cold numbers */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Snowflake className="w-4 h-4 text-neutral-400" />
              <span>近 {periods} 期最冷門號碼 TOP 6</span>
            </div>
            <div className="space-y-2">
              {hotColdLoading && <div className="text-xs text-neutral-400">載入中…</div>}
              {hotColdError && <div className="text-xs text-rose-500">{hotColdError}</div>}
              {coldNumbers.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-full border border-black/20 dark:border-white/20 text-neutral-700 dark:text-neutral-300 font-mono font-bold text-xs flex items-center justify-center">
                      {item.num.toString().padStart(2, '0')}
                    </span>
                    <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">開出 {item.count} 次</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-neutral-500">{item.rate}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Pillar Distribution View */}
      {activeTab === 'pillar_dist' && (
        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">三柱開出頻率與過關比率</h3>
          {pillarLoading && <div className="text-xs text-neutral-400">載入中…</div>}
          {pillarError && <div className="text-xs text-rose-500">{pillarError}</div>}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">第一柱 (10-18)</div>
              <div className="text-2xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{actualRate(0)}</div>
              <div className="text-[10px] text-neutral-400 mt-1">理論開出率 {theoryRate(0)}</div>
            </div>
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">第二柱 (20-29)</div>
              <div className="text-2xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{actualRate(1)}</div>
              <div className="text-[10px] text-neutral-400 mt-1">理論開出率 {theoryRate(1)}</div>
            </div>
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">第三柱 (其餘20顆)</div>
              <div className="text-2xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{actualRate(2)}</div>
              <div className="text-[10px] text-neutral-400 mt-1">理論開出率 {theoryRate(2)}</div>
            </div>
          </div>
        </div>
      )}

      {/* Odd Even View */}
      {activeTab === 'odd_even' && (
        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">單雙比與大小比分析</h3>
          {parity.loading && <div className="text-xs text-neutral-400">載入中…</div>}
          {parity.error && <div className="text-xs text-rose-500">{parity.error}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">單號 vs 雙號</div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{ratioText(parityPct?.odd)}</div>
            </div>
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">大號 (20-39) vs 小號 (01-19)</div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{ratioText(parityPct?.big)}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
