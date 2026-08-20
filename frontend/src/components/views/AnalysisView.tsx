import React, { useMemo, useState } from 'react';
import { BarChart3, Flame, Snowflake, LayoutGrid } from 'lucide-react';
import { api, PillarInfoDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';

const WINDOW = 830; // 冷熱號取樣上限(資料不足時以實際期數為準)
const HIST_OPTIONS = [20, 30, 50, 100] as const;

// 依十位分段上色:01~09 / 10~19 / 20~29 / 30~39 / 40~49(六合彩才有最後一段)
const BAND_DOT = [
  'bg-neutral-900 text-white dark:bg-white dark:text-black',
  'bg-blue-600 text-white',
  'bg-amber-600 text-white',
  'bg-emerald-600 text-white',
  'bg-fuchsia-600 text-white',
];
const BAND_LEGEND = [
  'bg-neutral-900 dark:bg-white',
  'bg-blue-600',
  'bg-amber-600',
  'bg-emerald-600',
  'bg-fuchsia-600',
];

const bandIndex = (n: number) => (n <= 9 ? 0 : Math.floor(n / 10));
const bandDot = (n: number) => BAND_DOT[bandIndex(n)] ?? BAND_DOT[BAND_DOT.length - 1];
const pad2 = (n: number) => n.toString().padStart(2, '0');

export const AnalysisView: React.FC = () => {
  const { gameKey, game } = useGame();
  const [activeTab, setActiveTab] = useState<'draw_history' | 'hot_cold' | 'pillar_dist' | 'odd_even'>('draw_history');
  const [histN, setHistN] = useState<number>(30);

  // 號碼上限跟著遊戲走(今彩539/天天樂 39、六合彩 49);後端還沒回來前先用 39 撐版面
  const numMax = game?.num_max ?? 39;
  const pick = game?.pick ?? 5;
  const supportsPillar = game?.supports_pillar ?? true;
  const gameName = game?.short_name ?? '本遊戲';
  const allNums = useMemo(() => Array.from({ length: numMax }, (_, i) => i + 1), [numMax]);
  // 圖例段數:39 顆到 30~39、49 顆多一段 40~49
  const bands = useMemo(() => {
    const out: { c: string; t: string }[] = [];
    for (let i = 0; i <= bandIndex(numMax); i++) {
      const lo = i === 0 ? 1 : i * 10;
      const hi = Math.min(i * 10 + 9, numMax);
      out.push({ c: BAND_LEGEND[i] ?? BAND_LEGEND[BAND_LEGEND.length - 1], t: `${pad2(lo)}~${pad2(hi)}` });
    }
    return out;
  }, [numMax]);

  const hotCold = useAsync(() => api.hotCold(gameKey, WINDOW, 6), [gameKey]);
  const history = useAsync(() => api.history(gameKey), [gameKey]);
  // 六合彩沒有三柱玩法 —— 直接不打端點,免得拿 400 當錯誤顯示
  const pillarInfo = useAsync<PillarInfoDTO | null>(
    () => (supportsPillar ? api.pillarInfo(gameKey) : Promise.resolve(null)),
    [gameKey, supportsPillar],
  );
  const parity = useAsync(() => api.parity(gameKey), [gameKey]);
  const drawHist = useAsync(() => api.history(gameKey, histN), [gameKey, histN]);

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

  // 三柱實際開出率:全歷史每期開出的號碼落在各柱的比例
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
  const pillarTotal = sizes ? sizes[0] + sizes[1] + sizes[2] : 0;
  const theoryRate = (i: number) =>
    sizes && pillarTotal > 0 ? `${((sizes[i] / pillarTotal) * 100).toFixed(2)}%` : '—';
  const actualRate = (i: number) =>
    pillarActual ? `${pillarActual[i].toFixed(1)}%` : '—';

  // 柱別標題直接從後端給的號碼組推:連號就寫區間,不連號(第三柱)就寫顆數
  const pillarLabel = (i: number) => {
    const p = pillarInfo.data?.pillars?.[i];
    if (!p || p.length === 0) return `第 ${i + 1} 柱`;
    const lo = Math.min(...p);
    const hi = Math.max(...p);
    return p.length === hi - lo + 1
      ? `第 ${i + 1} 柱 (${lo}-${hi})`
      : `第 ${i + 1} 柱 (其餘 ${p.length} 顆)`;
  };

  const pillarLoading = pillarInfo.loading || history.loading;
  const pillarError = pillarInfo.error || history.error;

  // 單號 / 大號比例:Σ(k × 期數) ÷ (每期 pick 顆 × 總期數)
  const parityPct = useMemo(() => {
    const d = parity.data;
    if (!d) return null;
    const draws = Object.values(d.odd_dist).reduce((a, b) => a + b, 0);
    if (draws === 0) return null;
    const weighted = (dist: Record<string, number>) =>
      Object.entries(dist).reduce((a, [k, v]) => a + Number(k) * v, 0);
    return {
      odd: (weighted(d.odd_dist) / (pick * draws)) * 100,
      big: (weighted(d.big_dist) / (pick * draws)) * 100,
    };
  }, [parity.data, pick]);

  // 大小的切點由後端給(539 是 19,六合彩是 24),不要自己假設
  const split = parity.data?.size_split;

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
              目前分析 {gameName}(01~{pad2(numMax)},每期 {pick} 顆)
              {history.data ? ` — 共 ${history.data.count.toLocaleString()} 期` : ''}
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
              <span>開獎歷史分佈走勢(01~{pad2(numMax)} × 開獎日期)</span>
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
            {bands.map(l => (
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
                    {allNums.map(n => (
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
                        {allNums.map(n => (
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
                    {allNums.map(n => {
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
          {!supportsPillar ? (
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] text-xs text-neutral-500 dark:text-neutral-400">
              {gameName}不適用三柱 —— 三柱 1800 碰是為 39 選 5 的盤設計的,
              換回今彩539 或天天樂才會有這頁的統計。
            </div>
          ) : (
            <>
              {pillarLoading && <div className="text-xs text-neutral-400">載入中…</div>}
              {pillarError && <div className="text-xs text-rose-500">{pillarError}</div>}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[0, 1, 2].map(i => (
                  <div key={i} className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                    <div className="text-[10px] uppercase tracking-wider text-neutral-400">{pillarLabel(i)}</div>
                    <div className="text-2xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{actualRate(i)}</div>
                    <div className="text-[10px] text-neutral-400 mt-1">理論開出率 {theoryRate(i)}</div>
                  </div>
                ))}
              </div>
            </>
          )}
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
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">
                {split
                  ? `大號 (${pad2(split + 1)}-${pad2(numMax)}) vs 小號 (01-${pad2(split)})`
                  : '大號 vs 小號'}
              </div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{ratioText(parityPct?.big)}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
