import React, { useEffect, useMemo, useState } from 'react';
import { Sparkles, RefreshCw, Info, ChevronRight, Trophy, ListOrdered } from 'lucide-react';
import { api, PredictReviewDTO, PredictStrategyDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';

const SET_OPTIONS = [1, 3, 5] as const;
const REVIEW_OPTIONS = [10, 20, 50] as const;
const MEDALS = ['🥇', '🥈', '🥉'];

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

// band = 本期預測(沒有中不中的問題,照十位分色);
// hit / miss = 回顧區,綠底實心代表押中,灰底代表沒中 —— 跟舊版的【NN】綠標同一個視覺。
type BallTone = 'band' | 'hit' | 'miss';

const TONE: Record<Exclude<BallTone, 'band'>, string> = {
  hit: 'bg-emerald-600 text-white',
  miss:
    'bg-black/[0.04] dark:bg-white/[0.06] text-neutral-500 dark:text-neutral-400 ' +
    'border border-black/[0.06] dark:border-white/[0.08]',
};

const Ball: React.FC<{ n: number; tone?: BallTone; size?: 'sm' | 'md' }> = ({
  n,
  tone = 'band',
  size = 'md',
}) => (
  <span
    className={`inline-flex items-center justify-center rounded-full font-mono font-bold ${
      size === 'sm' ? 'w-6 h-6 text-[10px]' : 'w-8 h-8 text-xs'
    } ${tone === 'band' ? bandBall(n) : TONE[tone]}`}
  >
    {pad2(n)}
  </span>
);

/** 本期預測:一個策略一列 —— 號球排開,底下附白話說明。 */
const StrategyRow: React.FC<{ s: PredictStrategyDTO }> = ({ s }) => (
  <div className="py-3.5 first:pt-0 last:pb-0 border-b last:border-b-0 border-black/[0.06] dark:border-white/[0.06]">
    <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-4">
      <div className="sm:w-32 shrink-0">
        <div className="text-xs font-display font-bold text-neutral-900 dark:text-white tracking-wide">
          {s.label}
        </div>
        <div className="text-[10px] font-mono uppercase tracking-[0.18em] text-neutral-400 mt-0.5">
          {s.key}
        </div>
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        {s.error ? (
          <div className="text-xs text-rose-500">這個策略算不出來:{s.error}</div>
        ) : (
          s.sets.map((nums, i) => (
            <div key={i} className="flex items-center gap-2 flex-wrap">
              {s.sets.length > 1 && (
                <span className="w-7 shrink-0 text-[10px] font-mono text-neutral-400">
                  #{i + 1}
                </span>
              )}
              {nums.map(n => (
                <Ball key={n} n={n} />
              ))}
            </div>
          ))
        )}
        <p className="text-[11px] leading-relaxed text-neutral-500 dark:text-neutral-400">
          {s.desc}
        </p>
      </div>
    </div>
  </div>
);

export const PredictionView: React.FC = () => {
  const { gameKey, game } = useGame();
  const [sets, setSets] = useState<number>(1);
  // seed 為 undefined 時後端依「下一期期號」出號(同一期可重現);
  // 按「重新抽一組」才換 seed。
  const [seed, setSeed] = useState<number | undefined>(undefined);
  const [reviewN, setReviewN] = useState<number>(20);
  const [open, setOpen] = useState<string | null>(null);

  const pred = useAsync(() => api.predict(gameKey, sets, seed), [gameKey, sets, seed]);
  const review = useAsync<PredictReviewDTO | null>(
    () => api.predictReview(gameKey, reviewN),
    [gameKey, reviewN],
  );

  // 開獎數據更新 → 自動產生新預測:predict 的 seed 綁「下一期期號」,新一期進來
  // 期號一變,重抓就會拿到新號碼。這裡定時(每 3 分鐘)+ 回到視窗時重抓;
  // 只有「用預設 seed(沒手動抽)」時才自動刷新,免得蓋掉使用者剛按的那組。
  useEffect(() => {
    if (seed !== undefined) return;
    const tick = () => {
      pred.reload();
      review.reload();
    };
    const timer = window.setInterval(tick, 3 * 60 * 1000);
    window.addEventListener('focus', tick);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('focus', tick);
    };
  }, [seed, pred.reload, review.reload]);

  const numMax = pred.data?.num_max ?? game?.num_max ?? 39;
  const pick = pred.data?.pick ?? game?.pick ?? 5;
  const gameName = pred.data?.game_name ?? game?.short_name ?? '本遊戲';

  // 逐期明細裡的策略順序與名稱,跟排行/出號一致
  const strategies = useMemo(() => review.data?.strategies ?? [], [review.data]);

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
              五策略參考選號 / 預測比對
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {gameName}(01~{pad2(numMax)},每期 {pick} 顆)
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
            '五種策略的期望中獎率完全相同,下面的排行只是把運氣視覺化,不代表哪個策略比較會中。理性娛樂、量力而為。'}
        </p>
      </div>

      {/* ── 1. 本期預測 ───────────────────────────────── */}
      <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div>
            <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              本期預測
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
              目標期:
              <span className="font-semibold text-neutral-800 dark:text-neutral-200">
                {pred.data?.target.label ?? '—'}
              </span>
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
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
                  {n} 組
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
        </div>

        {pred.loading && <div className="text-xs text-neutral-400">出號中…</div>}
        {pred.error && <div className="text-xs text-rose-500">{pred.error}</div>}

        <div>
          {(pred.data?.strategies ?? []).map(s => (
            <StrategyRow key={s.key} s={s} />
          ))}
        </div>

        {pred.data && (
          <p className="text-[11px] text-neutral-400 dark:text-neutral-500">
            同一期重整頁面會拿到同一組號碼(seed 由期號推導,目前 seed {pred.data.seed});
            按「重新抽一組」才會換號。
          </p>
        )}
      </div>

      {/* ── 2. 策略累計戰績 ───────────────────────────── */}
      <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
            <Trophy className="w-4 h-4 text-neutral-400" />
            策略累計戰績(只計已開獎的期)
          </h3>
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
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-neutral-400">
                    <th className="text-left font-semibold py-1.5 w-16">名次</th>
                    <th className="text-left font-semibold py-1.5">策略</th>
                    <th className="text-right font-semibold py-1.5">期數</th>
                    <th className="text-right font-semibold py-1.5">總命中</th>
                    <th className="text-right font-semibold py-1.5">平均每期</th>
                    <th className="text-right font-semibold py-1.5">單期最佳</th>
                  </tr>
                </thead>
                <tbody>
                  {[...review.data.ranking]
                    .sort((a, b) => b.avg - a.avg)
                    .map((r, i) => (
                      <tr
                        key={r.strategy}
                        className="border-t border-black/[0.05] dark:border-white/[0.05]"
                      >
                        <td className="py-2 text-neutral-500">
                          {i < MEDALS.length ? (
                            <span className="text-base leading-none">{MEDALS[i]}</span>
                          ) : (
                            `第 ${i + 1} 名`
                          )}
                        </td>
                        <td className="py-2 text-neutral-800 dark:text-neutral-200 font-semibold">
                          {r.label}
                        </td>
                        <td className="py-2 text-right font-mono text-neutral-500">
                          {r.periods}
                        </td>
                        <td className="py-2 text-right font-mono text-neutral-500">
                          {r.total_hits} 顆
                        </td>
                        <td className="py-2 text-right font-mono font-bold text-neutral-900 dark:text-white">
                          {r.avg.toFixed(2)} 顆
                        </td>
                        <td className="py-2 text-right font-mono text-neutral-500">
                          {r.best} 顆
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-neutral-400">
              參考基準:每期開 {review.data.pick} 顆、{review.data.num_max} 選{' '}
              {review.data.pick},隨便選 {review.data.pick} 顆的期望命中是{' '}
              {review.data.expected_avg.toFixed(2)} 顆。期數這麼少,誰在前面純屬偶然。
            </p>
          </>
        )}
      </div>

      {/* ── 3. 逐期明細 ───────────────────────────────── */}
      <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
          <ListOrdered className="w-4 h-4 text-neutral-400" />
          逐期明細
        </h3>
        <p className="text-[11px] text-neutral-400">
          點開某一期,看該期各策略分別押了哪些號碼 —— 綠底就是押中的號碼。
          每期都只用「該期之前」的資料重新出號再比對,不偷看答案。
        </p>

        {review.data?.rows.length === 0 && (
          <div className="text-xs text-neutral-400">這段期間沒有可回顧的資料。</div>
        )}

        <div className="space-y-2">
          {(review.data?.rows ?? []).map(row => {
            const id = (row.issue ?? '') + '|' + (row.date ?? '');
            const picks = strategies.map(s => ({ s, p: row.picks[s.key] }));
            const hitAny = new Set<number>();
            picks.forEach(({ p }) => p?.matched.forEach(n => hitAny.add(n)));
            const best = picks.reduce((m, { p }) => Math.max(m, p?.hits ?? 0), 0);
            const expanded = open === id;
            return (
              <div
                key={id}
                className="rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] overflow-hidden"
              >
                <button
                  type="button"
                  onClick={() => setOpen(expanded ? null : id)}
                  className="w-full px-3.5 py-3 flex items-center gap-3 flex-wrap text-left hover:bg-black/[0.03] dark:hover:bg-white/[0.04] transition-colors"
                >
                  <ChevronRight
                    className={`w-3.5 h-3.5 shrink-0 text-neutral-400 transition-transform ${
                      expanded ? 'rotate-90' : ''
                    }`}
                  />
                  <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">
                    {row.label}
                  </span>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {row.drawn.map(n => (
                      <Ball key={n} n={n} size="sm" tone={hitAny.has(n) ? 'hit' : 'miss'} />
                    ))}
                  </div>
                  <span className="ml-auto text-[10px] font-mono uppercase tracking-wider text-neutral-400">
                    最佳 {best} 顆
                  </span>
                </button>

                {expanded && (
                  <div className="px-3.5 pb-3.5 pt-1 space-y-2 border-t border-black/[0.06] dark:border-white/[0.06]">
                    {picks.map(({ s, p }) => {
                      if (!p) return null;
                      const hit = new Set(p.matched);
                      return (
                        <div key={s.key} className="flex items-center gap-2 flex-wrap">
                          <span className="w-24 shrink-0 text-[11px] font-semibold text-neutral-600 dark:text-neutral-300">
                            {s.label}
                          </span>
                          <div className="flex gap-1.5 flex-wrap">
                            {p.numbers.map(n => (
                              <Ball
                                key={n}
                                n={n}
                                size="sm"
                                tone={hit.has(n) ? 'hit' : 'miss'}
                              />
                            ))}
                          </div>
                          <span
                            className={`text-[10px] font-mono font-bold ${
                              p.hits > 0
                                ? 'text-emerald-600 dark:text-emerald-400'
                                : 'text-neutral-400'
                            }`}
                          >
                            {p.hits} 顆
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
