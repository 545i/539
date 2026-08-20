import React, { useMemo, useState } from 'react';
import { Sparkles, RefreshCw, Info, History, Dice5 } from 'lucide-react';
import { api, PredictReviewDTO, PredictStrategyDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';

const SET_OPTIONS = [1, 3, 5] as const;
const REVIEW_OPTIONS = [10, 20, 50] as const;

// 號球依十位分色,跟統計分析頁一致(01~09 / 10~19 / … / 40~49)
const BAND_BALL = [
  'bg-neutral-900 text-white dark:bg-white dark:text-black',
  'bg-blue-600 text-white',
  'bg-amber-600 text-white',
  'bg-emerald-600 text-white',
  'bg-fuchsia-600 text-white',
];

const pad2 = (n: number) => n.toString().padStart(2, '0');
const bandBall = (n: number) =>
  BAND_BALL[n <= 9 ? 0 : Math.floor(n / 10)] ?? BAND_BALL[BAND_BALL.length - 1];

const Ball: React.FC<{ n: number; dim?: boolean; size?: 'sm' | 'md' }> = ({
  n,
  dim = false,
  size = 'md',
}) => (
  <span
    className={`inline-flex items-center justify-center rounded-full font-mono font-bold ${
      size === 'sm' ? 'w-6 h-6 text-[10px]' : 'w-8 h-8 text-xs'
    } ${
      dim
        ? 'border border-black/15 dark:border-white/20 text-neutral-500 dark:text-neutral-400'
        : bandBall(n)
    }`}
  >
    {pad2(n)}
  </span>
);

const StrategyCard: React.FC<{ s: PredictStrategyDTO }> = ({ s }) => (
  <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3.5">
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-sm font-display font-bold text-neutral-900 dark:text-white tracking-wide">
          {s.label}
        </div>
        <div className="text-[10px] font-mono uppercase tracking-[0.2em] text-neutral-400 mt-0.5">
          {s.key}
        </div>
      </div>
      <span className="shrink-0 text-[9px] px-2 py-0.5 uppercase tracking-wider rounded-full border border-black/10 dark:border-white/10 text-neutral-400">
        期望值相同
      </span>
    </div>

    {s.error ? (
      <div className="text-xs text-rose-500">這個策略算不出來:{s.error}</div>
    ) : (
      <div className="space-y-2">
        {s.sets.map((nums, i) => (
          <div
            key={i}
            className="flex items-center gap-2 p-2.5 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]"
          >
            <span className="w-8 shrink-0 text-[10px] font-mono text-neutral-400">
              #{i + 1}
            </span>
            <div className="flex flex-wrap gap-1.5">
              {nums.map(n => (
                <Ball key={n} n={n} />
              ))}
            </div>
          </div>
        ))}
      </div>
    )}

    <p className="text-[11px] leading-relaxed text-neutral-500 dark:text-neutral-400">
      {s.desc}
    </p>

    {!s.uniform && s.top_numbers.length > 0 && (
      <div className="pt-2 border-t border-black/[0.06] dark:border-white/[0.06]">
        <div className="text-[10px] uppercase tracking-wider text-neutral-400 mb-1.5">
          這個策略偏好的號碼
        </div>
        <div className="flex flex-wrap gap-1.5">
          {s.top_numbers.map(t => (
            <span
              key={t.num}
              className="px-2 py-0.5 rounded-full font-mono text-[10px] bg-black/[0.04] dark:bg-white/[0.06] text-neutral-700 dark:text-neutral-300"
            >
              {pad2(t.num)}
              <span className="text-neutral-400"> {(t.weight * 100).toFixed(1)}%</span>
            </span>
          ))}
        </div>
      </div>
    )}
    {s.uniform && (
      <div className="pt-2 border-t border-black/[0.06] dark:border-white/[0.06] text-[10px] text-neutral-400">
        本策略各號權重完全均勻 —— 沒有「偏好號碼」這回事。
      </div>
    )}
  </div>
);

export const PredictionView: React.FC = () => {
  const { gameKey, game } = useGame();
  const [tab, setTab] = useState<'picks' | 'review'>('picks');
  const [sets, setSets] = useState<number>(1);
  // seed 為 undefined 時後端依「下一期期號」出號(同一期可重現);
  // 按「重新抽一組」才換 seed。
  const [seed, setSeed] = useState<number | undefined>(undefined);
  const [reviewN, setReviewN] = useState<number>(20);

  const pred = useAsync(() => api.predict(gameKey, sets, seed), [gameKey, sets, seed]);
  // 回顧要跑回測(比出號慢),沒切到那個分頁就不打端點
  const review = useAsync<PredictReviewDTO | null>(
    () => (tab === 'review' ? api.predictReview(gameKey, reviewN) : Promise.resolve(null)),
    [gameKey, reviewN, tab],
  );

  const numMax = pred.data?.num_max ?? game?.num_max ?? 39;
  const pick = pred.data?.pick ?? game?.pick ?? 5;
  const gameName = pred.data?.game_name ?? game?.short_name ?? '本遊戲';

  const strategyKeys = useMemo(
    () => (review.data?.strategies ?? []).map(s => s.key),
    [review.data],
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Title */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              五策略參考選號 / 預測分析
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {gameName}(01~{pad2(numMax)},每期 {pick} 顆)
              {pred.data ? ` — 目標期 ${pred.data.target.label}` : ''}
              {pred.data ? ` · 依 ${pred.data.periods.toLocaleString()} 期歷史出號` : ''}
            </p>
          </div>
        </div>
      </div>

      {/* 期望值提醒 */}
      <div className="p-4 rounded-2xl border border-amber-500/30 bg-amber-500/[0.06] flex items-start gap-2.5">
        <Info className="w-4 h-4 mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
        <p className="text-[11px] sm:text-xs leading-relaxed text-neutral-700 dark:text-neutral-300">
          {pred.data?.notice ??
            '五種策略的期望中獎率完全相同,差別只有運氣。任何冷熱號 / 頻率加權都無法預測下一期,號碼僅供參考,請理性娛樂。'}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-black/[0.08] dark:border-white/[0.08] pb-2">
        {[
          { id: 'picks', label: '參考選號', icon: <Dice5 className="w-3.5 h-3.5" /> },
          { id: 'review', label: '歷史命中回顧', icon: <History className="w-3.5 h-3.5" /> },
        ].map(t => (
          <button
            key={t.id}
            type="button"
            id={`predict-tab-${t.id}`}
            onClick={() => setTab(t.id as 'picks' | 'review')}
            className={`px-4 py-2 text-xs uppercase tracking-wider font-semibold rounded-full transition-all flex items-center gap-1.5 ${
              tab === t.id
                ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                : 'text-neutral-600 dark:text-neutral-400 hover:bg-black/5 dark:hover:bg-white/5'
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'picks' && (
        <>
          {/* 控制列 */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
              {SET_OPTIONS.map(n => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setSets(n)}
                  className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                    sets === n
                      ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                      : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                  }`}
                >
                  每策略 {n} 組
                </button>
              ))}
            </div>
            <button
              type="button"
              id="predict-reroll-btn"
              onClick={() => setSeed(Date.now() % 1_000_000_007)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 text-[11px] uppercase tracking-wider font-semibold rounded-full border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors active:scale-95"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${pred.loading ? 'animate-spin' : ''}`} />
              重新抽一組
            </button>
          </div>

          {pred.loading && <div className="text-xs text-neutral-400">出號中…</div>}
          {pred.error && <div className="text-xs text-rose-500">{pred.error}</div>}

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {(pred.data?.strategies ?? []).map(s => (
              <StrategyCard key={s.key} s={s} />
            ))}
          </div>

          {pred.data && (
            <p className="text-[11px] text-neutral-400 dark:text-neutral-500">
              同一期重整頁面會拿到同一組號碼(seed 由期號推導,目前 seed {pred.data.seed});
              按「重新抽一組」才會換號。
            </p>
          )}
        </>
      )}

      {tab === 'review' && (
        <div className="space-y-5">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="text-xs text-neutral-500 dark:text-neutral-400">
              每期都只用「該期之前」的資料重新出號再比對,不偷看答案。
            </div>
            <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
              {REVIEW_OPTIONS.map(n => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setReviewN(n)}
                  className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                    reviewN === n
                      ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                      : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                  }`}
                >
                  近 {n} 期
                </button>
              ))}
            </div>
          </div>

          {review.loading && <div className="text-xs text-neutral-400">回測中…</div>}
          {review.error && <div className="text-xs text-rose-500">{review.error}</div>}

          {review.data && (
            <>
              {/* 戰績排行 */}
              <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
                <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                  近 {review.data.periods} 期各策略戰績(純隨機期望每期中{' '}
                  {review.data.expected_avg.toFixed(2)} 顆)
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wider text-neutral-400">
                        <th className="text-left font-semibold py-1.5">策略</th>
                        <th className="text-right font-semibold py-1.5">期數</th>
                        <th className="text-right font-semibold py-1.5">總命中</th>
                        <th className="text-right font-semibold py-1.5">平均</th>
                        <th className="text-right font-semibold py-1.5">最佳</th>
                      </tr>
                    </thead>
                    <tbody>
                      {review.data.ranking.map(r => (
                        <tr
                          key={r.strategy}
                          className="border-t border-black/[0.05] dark:border-white/[0.05]"
                        >
                          <td className="py-2 text-neutral-800 dark:text-neutral-200 font-semibold">
                            {r.label}
                          </td>
                          <td className="py-2 text-right font-mono text-neutral-500">
                            {r.periods}
                          </td>
                          <td className="py-2 text-right font-mono text-neutral-500">
                            {r.total_hits}
                          </td>
                          <td className="py-2 text-right font-mono font-bold text-neutral-900 dark:text-white">
                            {r.avg.toFixed(2)}
                          </td>
                          <td className="py-2 text-right font-mono text-neutral-500">
                            {r.best}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="text-[11px] text-neutral-400">
                  排名只是把運氣視覺化 —— 期數這麼少,誰在前面純屬偶然,換一段期間就會換人。
                </p>
              </div>

              {/* 逐期明細 */}
              <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
                <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                  逐期比對(中的號碼上色,沒中的留白)
                </h3>
                {review.data.rows.length === 0 && (
                  <div className="text-xs text-neutral-400">這段期間沒有可回顧的資料。</div>
                )}
                <div className="space-y-4">
                  {review.data.rows.map(row => (
                    <div
                      key={(row.issue ?? '') + (row.date ?? '')}
                      className="p-3.5 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-2.5"
                    >
                      <div className="flex items-center justify-between flex-wrap gap-2">
                        <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">
                          {row.label}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] uppercase tracking-wider text-neutral-400 mr-1">
                            開獎
                          </span>
                          {row.drawn.map(n => (
                            <Ball key={n} n={n} size="sm" />
                          ))}
                        </div>
                      </div>
                      <div className="space-y-1.5">
                        {strategyKeys.map(k => {
                          const p = row.picks[k];
                          if (!p) return null;
                          const hit = new Set(p.matched);
                          return (
                            <div key={k} className="flex items-center gap-2 flex-wrap">
                              <span className="w-20 shrink-0 text-[10px] font-mono uppercase tracking-wider text-neutral-400">
                                {k}
                              </span>
                              <div className="flex gap-1.5">
                                {p.numbers.map(n => (
                                  <Ball key={n} n={n} size="sm" dim={!hit.has(n)} />
                                ))}
                              </div>
                              <span
                                className={`text-[10px] font-mono font-bold ${
                                  p.hits > 0
                                    ? 'text-emerald-600 dark:text-emerald-400'
                                    : 'text-neutral-400'
                                }`}
                              >
                                中 {p.hits}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};
