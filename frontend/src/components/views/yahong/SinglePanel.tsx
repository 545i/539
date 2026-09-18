import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { api, GameKey, YahongGrade, YahongRankRowDTO, YahongSingleTargetDTO } from '../../../api/client';
import { useAsync } from '../../../api/useAsync';
import { Disclaimer, Loading, ErrorBox, cardClass, pad2, GRADE_META } from './format';

const GRADES: YahongGrade[] = ['S', 'A', 'B', 'C'];

// 5 摘要卡的顯示格式(對照 spec-single §5.1)
const summaryCards = (s: YahongSingleTargetDTO['summary']) => [
  { label: '歷史總均線', value: `${(s.probAll * 100).toFixed(1)}%` },
  { label: '生存 PR 值', value: `${s.survivalPR.toFixed(1)}%` },
  { label: 'BIAS 乖離', value: `${s.accel >= 0 ? '+' : ''}${s.accel.toFixed(1)}%` },
  { label: '最大遺漏', value: `${s.maxMiss} 期` },
  { label: '近 30 期', value: `${(s.prob30 * 100).toFixed(1)}%` },
];

export const SinglePanel: React.FC<{ game: GameKey }> = ({ game }) => {
  const [input, setInput] = useState('');
  const [target, setTarget] = useState<number | undefined>(undefined);

  const { data, loading, error } = useAsync(() => api.yahongSingle(game, target), [game, target]);

  const submit = () => {
    const n = parseInt(input, 10);
    if (!Number.isNaN(n) && n >= 1 && n <= 39) setTarget(n);
  };

  // 全 39 分級榜依 grade 分堆(後端已 score 降序)
  const byGrade = useMemo(() => {
    const g: Record<YahongGrade, YahongRankRowDTO[]> = { S: [], A: [], B: [], C: [] };
    for (const r of data?.ranking ?? []) g[r.grade]?.push(r);
    return g;
  }, [data?.ranking]);

  const insufficient = !!data?.error;

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <Disclaimer />

      {/* 號碼輸入 */}
      <div className={`${cardClass} space-y-3`}>
        <div className="flex items-center gap-2">
          <input
            type="number"
            min={1}
            max={39}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') submit(); }}
            placeholder="輸入號碼 1~39"
            className="w-40 px-3 py-2 rounded-lg bg-white dark:bg-[#0d0d0d] border border-black/[0.12] dark:border-white/[0.12] text-sm font-mono text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:outline-none focus:border-black/30 dark:focus:border-white/30"
          />
          <button
            type="button"
            onClick={submit}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-black text-white dark:bg-white dark:text-black text-sm font-semibold transition-all active:scale-98"
          >
            <Search className="w-4 h-4" />
            透視
          </button>
          {target && (
            <button
              type="button"
              onClick={() => { setTarget(undefined); setInput(''); }}
              className="text-xs text-neutral-500 hover:text-black dark:hover:text-white"
            >
              清除
            </button>
          )}
        </div>
        <p className="text-[11px] text-neutral-400">輸入一顆號碼查看該號 18 宗師與分級;留空只看全盤分級榜。</p>
      </div>

      {loading && <Loading />}
      {error && <ErrorBox msg={error} />}

      {insufficient && (
        <div className={`${cardClass} text-xs text-neutral-500 dark:text-neutral-400`}>
          {data?.error} —— 目前僅 {data?.totalDraws ?? 0} 期,單碼必贏需 ≥ 100 期歷史才能計算。
        </div>
      )}

      {/* 單號 18 宗師明細 */}
      {data && !insufficient && data.target && (
        <div className={`${cardClass} space-y-5`}>
          {/* 分級橫幅 */}
          <div className={`p-4 rounded-2xl border flex items-center gap-4 ${GRADE_META[data.target.grade].ring}`}>
            <span className={`w-14 h-14 rounded-full flex items-center justify-center font-mono font-bold text-xl ${GRADE_META[data.target.grade].dot}`}>
              {pad2(data.target.num)}
            </span>
            <div>
              <div className={`text-lg font-display font-bold ${GRADE_META[data.target.grade].text}`}>
                {GRADE_META[data.target.grade].label} · {GRADE_META[data.target.grade].slogan}
              </div>
              <div className="text-xs text-neutral-500 dark:text-neutral-400 font-mono mt-0.5">
                綜合分 {data.target.score.toFixed(1)} · 全盤第 {data.target.rank} 名
              </div>
            </div>
          </div>

          {/* 5 摘要 */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
            {summaryCards(data.target.summary).map(c => (
              <div key={c.label} className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                <div className="text-[10px] uppercase tracking-wider text-neutral-400 truncate">{c.label}</div>
                <div className="text-base font-mono font-bold text-neutral-900 dark:text-white mt-1 tabular-nums">{c.value}</div>
              </div>
            ))}
          </div>

          {/* 18 宗師(綠燈 / 紅燈) */}
          <div>
            <div className="text-[11px] font-semibold text-neutral-600 dark:text-neutral-300 mb-2">18 宗師東西方合璧</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              {data.target.giants.map(g => (
                <div
                  key={g.key}
                  className={`p-2.5 rounded-xl border ${
                    g.green
                      ? 'bg-emerald-500/10 border-emerald-500/25'
                      : 'bg-rose-500/10 border-rose-500/25'
                  }`}
                >
                  <div className="text-[10px] text-neutral-500 dark:text-neutral-400 truncate">{g.label}</div>
                  <div className={`text-xs font-mono font-bold mt-0.5 tabular-nums ${
                    g.green ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-700 dark:text-rose-300'
                  }`}>
                    {g.display}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 全 39 分級榜 */}
      {data && !insufficient && (
        <div className={`${cardClass} space-y-4`}>
          <div className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
            全盤 39 碼分級榜
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {GRADES.map(grade => (
              <div key={grade} className={`p-3 rounded-xl border ${GRADE_META[grade].ring}`}>
                <div className={`text-xs font-bold mb-2 ${GRADE_META[grade].text}`}>
                  {GRADE_META[grade].label} · {GRADE_META[grade].slogan}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {byGrade[grade].map(r => (
                    <button
                      key={r.num}
                      type="button"
                      onClick={() => { setTarget(r.num); setInput(String(r.num)); }}
                      title={`綜合分 ${r.score.toFixed(1)}`}
                      className={`inline-flex flex-col items-center px-1.5 py-1 rounded-lg text-[10px] font-mono transition-all hover:scale-105 ${GRADE_META[grade].dot}`}
                    >
                      <span className="font-bold text-xs">{pad2(r.num)}</span>
                      <span className="opacity-80">{r.score.toFixed(1)}</span>
                    </button>
                  ))}
                  {byGrade[grade].length === 0 && (
                    <span className="text-[10px] text-neutral-400">—</span>
                  )}
                </div>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-neutral-400">點任一號碼可回填並查看該號 18 宗師明細。分級為名次制(前 3 / 4~9 / 10~25 / 26+)。</p>
        </div>
      )}
    </div>
  );
};
