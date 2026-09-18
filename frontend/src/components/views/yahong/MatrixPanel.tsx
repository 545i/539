import React, { useState } from 'react';
import { Landmark, Compass } from 'lucide-react';
import { api, GameKey, YahongMetricDTO } from '../../../api/client';
import { useAsync } from '../../../api/useAsync';
import { Disclaimer, Loading, ErrorBox, cardClass, fmtValue, VERDICT_BANNER, money } from './format';

type Mode = '1800' | '9000';

// 一格指標卡:drawdown 特別處理(value=當前回撤 / extra=歷史最大)
const MetricCell: React.FC<{ m: YahongMetricDTO }> = ({ m }) => {
  const display =
    m.key === 'drawdown' && m.extra !== undefined
      ? `$${money(m.value)} / 最大 $${money(m.extra)}`
      : fmtValue(m.value, m.fmt);
  return (
    <div className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
      <div className="text-[10px] uppercase tracking-wider text-neutral-400 truncate">{m.label}</div>
      <div className="text-lg font-mono font-bold text-neutral-900 dark:text-white mt-1 tabular-nums">
        {display}
      </div>
    </div>
  );
};

export const MatrixPanel: React.FC<{ game: GameKey }> = ({ game }) => {
  const [mode, setMode] = useState<Mode>('1800');
  const { data, loading, error } = useAsync(() => api.yahongMatrix(game, mode), [game, mode]);

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <Disclaimer />

      {/* 1800 / 9000 mode 切換 */}
      <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
        {(['1800', '9000'] as Mode[]).map(m => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`px-4 py-1.5 rounded-lg text-xs font-mono font-semibold transition-all ${
              mode === m
                ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
            }`}
          >
            {m} 碰
          </button>
        ))}
      </div>

      {loading && <Loading />}
      {error && <ErrorBox msg={error} />}

      {data && (
        <>
          {/* 五裁決橫幅 */}
          <div className={`p-5 rounded-2xl border ${VERDICT_BANNER[data.verdict.color]}`}>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <span className="text-base font-display font-bold tracking-wide">{data.verdict.title}</span>
              <span className="text-xs font-mono font-bold px-2.5 py-1 rounded-full bg-black/10 dark:bg-white/10">
                建議 {data.verdict.mult} 倍
              </span>
            </div>
            <p className="text-xs mt-2 leading-relaxed opacity-90">{data.verdict.desc}</p>
            <p className="text-[10px] mt-1 opacity-60 font-mono">累計觀測 {data.totalDraws} 期</p>
          </div>

          {/* 華爾街八大 */}
          <div className={`${cardClass} space-y-4`}>
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Landmark className="w-4 h-4 text-neutral-500" />
              <span>華爾街八大(西方量化)</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5">
              {data.wallst.map(m => <MetricCell key={m.key} m={m} />)}
            </div>
          </div>

          {/* 東方十大 */}
          <div className={`${cardClass} space-y-4`}>
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Compass className="w-4 h-4 text-neutral-500" />
              <span>東方傳統十大(盤路 / 經驗)</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
              {data.eastern.map(m => <MetricCell key={m.key} m={m} />)}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
