import React, { useEffect, useMemo, useState } from 'react';
import { api, PredictAnalysisDTO, PredictReviewDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';

// 預測頁只呈現「浮動策略」:先給本期建議 → 再列算式 → 紀錄。
// 熱號 / 冷號 / 歷史只當浮動的內部輸入,不單獨顯示(2026-11-10 使用者要求)。
// 冷熱範圍固定最近 50 期 —— 浮動策略的回測與參數都是在這個範圍下選的。
const FLOAT_RANGE_N = 50;
const REVIEW_OPTIONS = [10, 20, 50] as const;
const RANGE_PERIOD_OPTS = [30, 50, 100] as const;   // 統計檢定:依期數
const RANGE_DAY_OPTS = [14, 30, 90] as const;        // 統計檢定:依日期

const SRC_LABEL: Record<string, string> = { hot: '熱號', cold: '冷號', frequency: '歷史' };
const SRC_DESC: Record<string, string> = {
  hot: `最近 ${FLOAT_RANGE_N} 期出現次數最多的 5 顆`,
  cold: `最近 ${FLOAT_RANGE_N} 期出現次數最少的 5 顆`,
  frequency: '全部歷史出現次數最多的 5 顆',
};
const RULE_LABEL: Record<string, string> = { follow: '跟第一名', fade: '反跟最後一名' };

const pad2 = (n: number) => n.toString().padStart(2, '0');

type BallTone = 'main' | 'hit' | 'miss';
const TONE: Record<BallTone, string> = {
  main: 'bg-neutral-900 text-white dark:bg-white dark:text-black',
  hit: 'bg-emerald-600 text-white',
  miss: 'bg-black/[0.05] dark:bg-white/[0.07] text-neutral-500 dark:text-neutral-400',
};

const Ball: React.FC<{ n: number; tone?: BallTone; size?: 'sm' | 'md' | 'lg' }> = ({
  n, tone = 'main', size = 'md',
}) => (
  <span
    className={`inline-flex items-center justify-center rounded-full font-mono font-bold ${
      size === 'sm' ? 'w-6 h-6 text-[calc(10px*var(--fs))]'
        : size === 'lg' ? 'w-11 h-11 text-base' : 'w-8 h-8 text-xs'
    } ${TONE[tone]}`}
  >
    {pad2(n)}
  </span>
);

/** 底線 tab(扁平切換) */
function Tabs<T extends string | number>({ value, options, label, onChange }: {
  value: T; options: readonly T[]; label: (v: T) => string; onChange: (v: T) => void;
}) {
  return (
    <div className="flex gap-4">
      {options.map(o => (
        <button
          key={String(o)}
          type="button"
          onClick={() => onChange(o)}
          className={`pb-1 text-xs font-semibold border-b-2 transition-colors ${
            value === o
              ? 'border-neutral-900 dark:border-white text-neutral-900 dark:text-white'
              : 'border-transparent text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200'
          }`}
        >
          {label(o)}
        </button>
      ))}
    </div>
  );
}

const SectionTitle: React.FC<{ children: React.ReactNode; right?: React.ReactNode }> = ({ children, right }) => (
  <div className="flex items-end justify-between flex-wrap gap-3 pb-2 border-b border-black/[0.08] dark:border-white/[0.08]">
    <h3 className="text-sm font-bold text-neutral-900 dark:text-white tracking-wide">{children}</h3>
    {right}
  </div>
);

const StatItem: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <div className="py-3 space-y-1.5">
    <div className="text-xs font-semibold text-neutral-700 dark:text-neutral-200">{title}</div>
    {children}
  </div>
);

const Verdict: React.FC<{ ok: boolean; text: string }> = ({ ok, text }) => (
  <p className={`text-[calc(11px*var(--fs))] ${ok ? 'text-neutral-500' : 'text-neutral-900 dark:text-white font-semibold'}`}>
    {ok ? '✓ ' : '! '}{text}
  </p>
);

export const PredictionView: React.FC = () => {
  const { gameKey, game } = useGame();
  const [reviewN, setReviewN] = useState<number>(20);
  // 統計檢定(附錄)自己的範圍,不影響浮動
  const [rangeMode, setRangeMode] = useState<'periods' | 'days'>('periods');
  const [rangeN, setRangeN] = useState<number>(50);
  const [showStats, setShowStats] = useState(false);

  const pred = useAsync(() => api.predict(gameKey, 1, 'periods', FLOAT_RANGE_N), [gameKey]);
  const review = useAsync<PredictReviewDTO | null>(
    () => api.predictReview(gameKey, reviewN, 'periods', FLOAT_RANGE_N),
    [gameKey, reviewN],
  );
  const ana = useAsync<PredictAnalysisDTO | null>(
    () => (showStats ? api.predictAnalysis(gameKey, rangeMode, rangeN) : Promise.resolve(null)),
    [gameKey, rangeMode, rangeN, showStats],
  );

  // 新一期開獎進來 → 期號變、重抓即換號。每 3 分鐘 + 回到視窗時重抓。
  useEffect(() => {
    const tick = () => { pred.reload(); review.reload(); };
    const timer = window.setInterval(tick, 3 * 60 * 1000);
    window.addEventListener('focus', tick);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('focus', tick);
    };
  }, [pred.reload, review.reload]);

  const numMax = pred.data?.num_max ?? game?.num_max ?? 39;
  const pick = pred.data?.pick ?? game?.pick ?? 5;
  const gameName = pred.data?.game_name ?? game?.short_name ?? '本遊戲';
  const fn = review.data?.floating_next ?? null;
  const fk = review.data?.floating_k ?? 50;
  const fm = review.data?.floating_m ?? 50;

  // 本期浮動那一組 = /predict 同範圍下被選中策略的號碼
  const floatingSet = useMemo(
    () => pred.data?.strategies.find(s => s.key === fn?.strategy)?.sets[0] ?? null,
    [pred.data, fn],
  );
  const rec = review.data?.ranking.find(r => r.strategy === 'floating') ?? null;
  const floatRows = (review.data?.rows ?? []).filter(r => r.floating);

  return (
    <div className="space-y-10 animate-in fade-in duration-200 max-w-3xl">
      {/* ── 標題 ── */}
      <div>
        <h2 className="text-lg font-bold text-neutral-900 dark:text-white tracking-wide">浮動策略預測</h2>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
          {gameName}(01~{pad2(numMax)},每期 {pick} 顆)
          {pred.data ? ` · 依 ${pred.data.periods.toLocaleString()} 期歷史` : ''}
        </p>
      </div>

      {/* ── 1. 本期浮動建議 ── */}
      <section className="space-y-4">
        <SectionTitle>本期建議</SectionTitle>
        {(pred.loading || review.loading) && !floatingSet && (
          <div className="text-xs text-neutral-400">計算中…</div>
        )}
        {(pred.error || review.error) && (
          <div className="text-xs text-rose-500">{pred.error || review.error}</div>
        )}
        {review.data && !fn && (
          <div className="text-xs text-neutral-400">歷史期數不足 {fk + fm} 期,浮動策略還算不出來。</div>
        )}
        {floatingSet && fn && (
          <div className="space-y-3">
            <div className="text-xs text-neutral-500 dark:text-neutral-400">
              目標期 <span className="font-semibold text-neutral-800 dark:text-neutral-200">{pred.data?.target.label ?? '—'}</span>
            </div>
            <div className="flex items-center gap-2.5 flex-wrap">
              {floatingSet.map(n => <Ball key={n} n={n} size="lg" />)}
            </div>
            <div className="text-sm text-neutral-800 dark:text-neutral-200">
              本期採用 <b>{RULE_LABEL[fn.rule]}</b>,押 <b>{SRC_LABEL[fn.strategy]}</b>
              <span className="text-neutral-400 text-xs ml-1.5">({SRC_DESC[fn.strategy]})</span>
            </div>
          </div>
        )}
      </section>

      {/* ── 2. 算式 ── */}
      {fn && (
        <section className="space-y-3">
          <SectionTitle>算式</SectionTitle>
          <ol className="divide-y divide-black/[0.06] dark:divide-white/[0.06] text-xs text-neutral-600 dark:text-neutral-300">
            <li className="py-3 space-y-2">
              <div className="font-semibold text-neutral-800 dark:text-neutral-100">
                ① 前 {fk} 期,三種選法各自中了幾顆
              </div>
              <div className="grid grid-cols-3 gap-2 max-w-sm">
                {Object.keys(SRC_LABEL).map(k => (
                  <div key={k}>
                    <div className="text-neutral-400">{SRC_LABEL[k]}</div>
                    <div className="font-mono text-base font-bold text-neutral-900 dark:text-white">
                      {fn.scores[k] ?? 0}<span className="text-xs font-normal text-neutral-400"> 顆</span>
                    </div>
                  </div>
                ))}
              </div>
              <div>
                第一名 <b>{SRC_LABEL[fn.leader]}</b>、最後一名 <b>{SRC_LABEL[fn.loser]}</b>
              </div>
            </li>
            <li className="py-3 space-y-2">
              <div className="font-semibold text-neutral-800 dark:text-neutral-100">
                ② 最近 {fm} 期,兩條規則實際中了幾顆
              </div>
              <div className="grid grid-cols-2 gap-2 max-w-sm">
                {(['follow', 'fade'] as const).map(r => (
                  <div key={r}>
                    <div className="text-neutral-400">{RULE_LABEL[r]}<span className="text-[calc(10px*var(--fs))]">{r === 'fade' ? ' 反轉' : ' 順勢'}</span></div>
                    <div className={`font-mono text-base font-bold ${fn.rule === r ? 'text-neutral-900 dark:text-white' : 'text-neutral-400'}`}>
                      {r === 'follow' ? fn.follow_score : fn.fade_score}
                      <span className="text-xs font-normal text-neutral-400"> 顆</span>
                    </div>
                  </div>
                ))}
              </div>
              <div>
                {fn.follow_score >= fn.fade_score ? '跟第一名' : '反跟最後一名'}較多(平手算跟第一名)→ 本期用 <b>{RULE_LABEL[fn.rule]}</b>
              </div>
            </li>
            <li className="py-3">
              <span className="font-semibold text-neutral-800 dark:text-neutral-100">③ 結果:</span>
              {RULE_LABEL[fn.rule]} = <b>{SRC_LABEL[fn.strategy]}</b> → {SRC_DESC[fn.strategy]},就是上面那一組。
            </li>
          </ol>
          <p className="text-[calc(11px*var(--fs))] leading-relaxed text-neutral-400">
            參數(看 {fk} 期排名、{fm} 期規則成績)是用 539 過去 706 期回測、約 30 種規則中表現最好的:
            每期平均 0.68 顆,隨便選是 0.64 顆。從 30 種挑最好的本來就會因運氣偏高,
            所以真正準不準要看下面上線後的紀錄。每期開獎獨立,不保證會中,請量力而為。
          </p>
        </section>
      )}

      {/* ── 3. 紀錄 ── */}
      <section className="space-y-3">
        <SectionTitle
          right={<Tabs<number> value={reviewN} options={REVIEW_OPTIONS} label={n => `近 ${n} 期`} onChange={setReviewN} />}
        >
          紀錄
        </SectionTitle>

        {rec && review.data && (
          <div className="flex flex-wrap gap-x-8 gap-y-2 py-1">
            <div>
              <div className="text-[calc(10px*var(--fs))] text-neutral-400">平均每期</div>
              <div className="font-mono text-xl font-bold text-neutral-900 dark:text-white">{rec.avg.toFixed(2)} 顆</div>
            </div>
            <div>
              <div className="text-[calc(10px*var(--fs))] text-neutral-400">隨便選的期望</div>
              <div className="font-mono text-xl font-bold text-neutral-400">{review.data.expected_avg.toFixed(2)} 顆</div>
            </div>
            <div>
              <div className="text-[calc(10px*var(--fs))] text-neutral-400">總命中 / 期數</div>
              <div className="font-mono text-xl font-bold text-neutral-900 dark:text-white">
                {rec.total_hits}<span className="text-sm text-neutral-400"> / {rec.periods}</span>
              </div>
            </div>
            <div>
              <div className="text-[calc(10px*var(--fs))] text-neutral-400">單期最佳</div>
              <div className="font-mono text-xl font-bold text-neutral-900 dark:text-white">{rec.best} 顆</div>
            </div>
          </div>
        )}
        {rec && (
          <p className="text-[calc(11px*var(--fs))] text-neutral-400">
            每期都只用「該期之前」的資料重算浮動選號,不偷看答案。期數少時高低多半是運氣。
          </p>
        )}

        <div className="divide-y divide-black/[0.06] dark:divide-white/[0.06]">
          {floatRows.map(row => {
            const f = row.floating!;
            const hit = new Set(f.matched);
            return (
              <div key={(row.issue ?? '') + '|' + (row.date ?? '')} className="py-2.5 space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap text-xs">
                  <span className="font-semibold text-neutral-800 dark:text-neutral-200">{row.label}</span>
                  <span className="text-neutral-400">{RULE_LABEL[f.rule]} → {SRC_LABEL[f.strategy]}</span>
                  <span className={`ml-auto font-mono font-bold ${f.hits > 0 ? 'text-emerald-600' : 'text-neutral-400'}`}>
                    中 {f.hits} 顆
                  </span>
                </div>
                <div className="flex items-center gap-x-4 gap-y-1.5 flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[calc(10px*var(--fs))] text-neutral-400 w-6">押</span>
                    {f.numbers.map(n => <Ball key={n} n={n} size="sm" tone={hit.has(n) ? 'hit' : 'miss'} />)}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[calc(10px*var(--fs))] text-neutral-400 w-6">開</span>
                    {row.drawn.map(n => <Ball key={n} n={n} size="sm" tone={hit.has(n) ? 'hit' : 'miss'} />)}
                  </div>
                </div>
              </div>
            );
          })}
          {review.data && floatRows.length === 0 && (
            <div className="py-3 text-xs text-neutral-400">這段期間沒有可回顧的資料。</div>
          )}
        </div>
      </section>

      {/* ── 附錄:統計檢定(預設收起)── */}
      <section className="space-y-3">
        <button
          type="button"
          onClick={() => setShowStats(v => !v)}
          className="text-xs text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:underline"
        >
          {showStats ? '收起' : '展開'}附錄:開獎隨機性檢定
        </button>
        {showStats && (
          <div className="space-y-2">
            <div className="flex items-center gap-6 flex-wrap">
              <Tabs
                value={rangeMode}
                options={['periods', 'days'] as const}
                label={m => (m === 'periods' ? '依期數' : '依日期')}
                onChange={m => { setRangeMode(m); setRangeN(m === 'periods' ? 50 : 30); }}
              />
              <Tabs<number>
                value={rangeN}
                options={rangeMode === 'periods' ? RANGE_PERIOD_OPTS : RANGE_DAY_OPTS}
                label={n => `${n} ${rangeMode === 'periods' ? '期' : '天'}`}
                onChange={setRangeN}
              />
            </div>
            {ana.loading && <div className="text-xs text-neutral-400">計算中…</div>}
            {ana.error && <div className="text-xs text-rose-500">{ana.error}</div>}
            {ana.data && ana.data.periods === 0 && (
              <div className="text-xs text-neutral-400">這個範圍內沒有開獎資料,換個範圍試試。</div>
            )}
            {ana.data && ana.data.periods > 0 && (
              <div className="divide-y divide-black/[0.06] dark:divide-white/[0.06]">
                <StatItem title={`敘述性統計(範圍內 ${ana.data.periods} 期)`}>
                  {ana.data.descriptive.sum && (
                    <p className="text-[calc(11px*var(--fs))] text-neutral-600 dark:text-neutral-300">
                      和值 平均 <b>{ana.data.descriptive.sum.mean}</b> · 中位 {ana.data.descriptive.sum.median} ·
                      標準差 {ana.data.descriptive.sum.std}({ana.data.descriptive.sum.min}~{ana.data.descriptive.sum.max})
                    </p>
                  )}
                  <p className="text-[calc(11px*var(--fs))] text-neutral-600 dark:text-neutral-300">
                    每期平均 奇數 {ana.data.descriptive.odd_avg} 個、大數 {ana.data.descriptive.big_avg} 個;
                    每號期望出現 {ana.data.descriptive.expected_per_num} 次
                  </p>
                </StatItem>
                <StatItem title="均勻度檢定(χ² vs 均勻)">
                  <p className="text-[calc(11px*var(--fs))] font-mono text-neutral-600 dark:text-neutral-300">
                    χ² = {ana.data.uniformity.chi2}(自由度 {ana.data.uniformity.dof}) · p = {ana.data.uniformity.p}
                  </p>
                  <Verdict ok={ana.data.uniformity.uniform} text={ana.data.uniformity.verdict} />
                </StatItem>
                <StatItem title="獨立性檢定(前後期 χ²)">
                  <p className="text-[calc(11px*var(--fs))] font-mono text-neutral-600 dark:text-neutral-300">
                    χ² = {ana.data.independence.chi2}(自由度 {ana.data.independence.dof}) · p = {ana.data.independence.p}
                  </p>
                  <Verdict ok={ana.data.independence.independent} text={ana.data.independence.verdict} />
                </StatItem>
                <StatItem title="皮爾森相關(相鄰兩期特徵)">
                  {ana.data.pearson.features.map(f => (
                    <div key={f.feature} className="flex items-center justify-between text-[calc(11px*var(--fs))] text-neutral-600 dark:text-neutral-300">
                      <span>{f.feature}</span>
                      <span className="font-mono">r = {f.r} <span className="text-neutral-400">({f.note})</span></span>
                    </div>
                  ))}
                </StatItem>
                <StatItem title="變異數模擬(蒙地卡羅 vs 公平隨機)">
                  <p className="text-[calc(11px*var(--fs))] font-mono text-neutral-600 dark:text-neutral-300">
                    觀測變異 {ana.data.variance_sim.observed_var} · 隨機常態 {ana.data.variance_sim.sim_lo}~{ana.data.variance_sim.sim_hi}
                    · 第 {ana.data.variance_sim.percentile} 百分位
                  </p>
                  <Verdict
                    ok={ana.data.variance_sim.percentile >= 2.5 && ana.data.variance_sim.percentile <= 97.5}
                    text={ana.data.variance_sim.verdict}
                  />
                </StatItem>
                <p className="pt-2 text-[calc(11px*var(--fs))] text-neutral-400">{ana.data.notice}</p>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
};
