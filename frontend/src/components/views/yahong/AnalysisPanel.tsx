import React from 'react';
import { LayoutGrid, Flame, Snowflake, ListOrdered, Sparkles } from 'lucide-react';
import { api, GameKey, YahongPillarDTO, YahongRecommendDTO } from '../../../api/client';
import { useAsync } from '../../../api/useAsync';
import { Disclaimer, Loading, ErrorBox, cardClass, pad2, BADGE_META, RECOMMEND_META } from './format';

// 柱碰卡:539 顯示 連漏 / 理論機率 / 極限反彈機率;
// 天天樂多顯示 平均週期 / 歷史機率,爆發率標「AI 爆發率」(對齊原站五格)。
const PillarCard: React.FC<{ title: string; p: YahongPillarDTO; isFantasy: boolean }> = ({ title, p, isFantasy }) => {
  const cells: { label: string; value: string }[] = [
    { label: '連漏', value: `${p.miss} 期` },
    ...(isFantasy && p.avgCycle !== undefined ? [{ label: '平均週期', value: `${p.avgCycle.toFixed(1)} 期` }] : []),
    { label: '理論機率', value: `${p.theoProb.toFixed(1)}%` },
    ...(isFantasy && p.histProb !== undefined ? [{ label: '歷史機率', value: `${p.histProb.toFixed(1)}%` }] : []),
    { label: isFantasy ? 'AI 爆發率' : '極限反彈機率', value: `${p.nextProb.toFixed(isFantasy ? 1 : 2)}%` },
  ];
  return (
    <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-display font-bold text-neutral-900 dark:text-white">{title}</span>
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${BADGE_META[p.badge]}`}>{p.badgeText}</span>
      </div>
      <div className={`grid gap-2 ${cells.length >= 5 ? 'grid-cols-3 sm:grid-cols-5' : 'grid-cols-3'}`}>
        {cells.map(c => (
          <div key={c.label}>
            <div className="text-[10px] uppercase tracking-wider text-neutral-400 truncate">{c.label}</div>
            <div className="text-base font-mono font-bold text-neutral-900 dark:text-white tabular-nums">{c.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

const RecommendCard: React.FC<{ r: YahongRecommendDTO }> = ({ r }) => {
  const meta = RECOMMEND_META[r.color] ?? RECOMMEND_META.gold;
  const balls = (nums: number[]) => (
    <div className="flex flex-wrap gap-1.5">
      {nums.map(n => (
        <span key={n} className={`inline-flex items-center justify-center w-8 h-8 rounded-full font-mono font-bold text-xs ${meta.ball}`}>
          {pad2(n)}
        </span>
      ))}
    </div>
  );
  return (
    <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-3">
      <div className={`text-sm font-display font-bold ${meta.text}`}>{r.name}</div>
      <div className="space-y-2">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-neutral-400 mb-1">三星(3 碼)</div>
          {balls(r.star3)}
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-wider text-neutral-400 mb-1">四星(4 碼)</div>
          {balls(r.star4)}
        </div>
      </div>
    </div>
  );
};

export const AnalysisPanel: React.FC<{ game: GameKey }> = ({ game }) => {
  const { data, loading, error } = useAsync(() => api.yahongAnalysis(game), [game]);
  const isFantasy = game === 'fantasy5';

  // probScore 表頭:539 用近50 + 權重 0.65/0.35;天天樂用近15 + 權重 0.35/0.35/0.30
  const recentLabel = isFantasy ? '近15' : '近50';
  const weightNote = isFantasy
    ? 'freq 0.35 + recent 0.35 + rebound 0.30'
    : 'freq 0.65 + rebound 0.35';

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <Disclaimer />

      {loading && <Loading />}
      {error && <ErrorBox msg={error} />}

      {data && (
        <>
          {/* 柱碰看板 */}
          <div className={`${cardClass} space-y-4`}>
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <LayoutGrid className="w-4 h-4 text-neutral-500" />
              <span>柱碰即時看板</span>
              {data.latestDate && (
                <span className="text-[10px] font-mono text-neutral-400 normal-case">最新 {data.latestDate} · 共 {data.totalDraws} 期</span>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <PillarCard title="1800 碰(三星柱碰)" p={data.pillars.p1800} isFantasy={isFantasy} />
              <PillarCard title="9000 碰(四星柱碰)" p={data.pillars.p9000} isFantasy={isFantasy} />
            </div>
          </div>

          {/* 熱門 / 冷門 TOP8 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className={`${cardClass} space-y-3`}>
              <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
                <Flame className="w-4 h-4 text-amber-500" />
                <span>熱門號(近 {isFantasy ? 15 : 50} 期 TOP 8)</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.hot.map(h => (
                  <div key={h.num} className="relative inline-flex flex-col items-center px-2 py-1.5 rounded-xl bg-rose-500/10 border border-rose-500/20">
                    {h.today && <span className="absolute -top-1.5 -right-1.5 text-[8px] px-1 rounded bg-amber-500 text-white font-bold">開</span>}
                    <span className="font-mono font-bold text-sm text-rose-700 dark:text-rose-300">{pad2(h.num)}</span>
                    <span className="text-[10px] text-neutral-500">開 {h.count} 次</span>
                  </div>
                ))}
              </div>
            </div>

            <div className={`${cardClass} space-y-3`}>
              <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
                <Snowflake className="w-4 h-4 text-cyan-500" />
                <span>冷門號(連續未開 TOP 8)</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {data.cold.map(c => (
                  <div key={c.num} className="inline-flex flex-col items-center px-2 py-1.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20">
                    <span className="font-mono font-bold text-sm text-cyan-700 dark:text-cyan-300">{pad2(c.num)}</span>
                    <span className="text-[10px] text-neutral-500">{c.miss === 0 ? '今日開出' : `漏 ${c.miss} 期`}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* probScore 排名表(欄位隨 game) */}
          <div className={`${cardClass} space-y-3`}>
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <ListOrdered className="w-4 h-4 text-neutral-500" />
              <span>機率評分 probScore({weightNote})</span>
            </div>
            <div className="overflow-x-auto -mx-1 px-1">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wider text-neutral-400">
                    <th className="px-2 py-1.5">號碼</th>
                    <th className="px-2 py-1.5 text-right">綜合分</th>
                    <th className="px-2 py-1.5 text-right">頻率分</th>
                    <th className="px-2 py-1.5 text-right">反彈分</th>
                    <th className="px-2 py-1.5 text-right">遺漏</th>
                    <th className="px-2 py-1.5 text-right">{recentLabel}</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {data.probScore.map(row => (
                    <tr key={row.num} className="border-t border-black/[0.05] dark:border-white/[0.05] hover:bg-black/[0.02] dark:hover:bg-white/[0.02]">
                      <td className="px-2 py-1.5 font-bold text-neutral-900 dark:text-white">{pad2(row.num)}</td>
                      <td className="px-2 py-1.5 text-right font-bold text-neutral-900 dark:text-white tabular-nums">{row.score.toFixed(1)}</td>
                      <td className="px-2 py-1.5 text-right text-neutral-500 tabular-nums">{row.freq.toFixed(1)}</td>
                      <td className="px-2 py-1.5 text-right text-neutral-500 tabular-nums">{row.rebound.toFixed(0)}</td>
                      <td className="px-2 py-1.5 text-right text-neutral-500 tabular-nums">{row.miss}</td>
                      <td className="px-2 py-1.5 text-right text-neutral-500 tabular-nums">
                        {(isFantasy ? row.recent : row.recent50) ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 推薦卡:直接 map 後端陣列(539=4、天天樂=3) */}
          <div className={`${cardClass} space-y-4`}>
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Sparkles className="w-4 h-4 text-neutral-500" />
              <span>{data.recommend.length} 大模式推薦矩陣</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {data.recommend.map(r => <RecommendCard key={r.mode} r={r} />)}
            </div>
            <p className="text-[10px] text-neutral-400">模式 1 為全盤純亂數;其餘為 probScore 高分子集的加權隨機抽樣,非最佳化。</p>
          </div>
        </>
      )}
    </div>
  );
};
