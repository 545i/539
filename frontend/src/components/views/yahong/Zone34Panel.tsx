import React from 'react';
import { Radar, Flame, ShieldCheck, Siren, Target } from 'lucide-react';
import { api, GameKey } from '../../../api/client';
import { useAsync } from '../../../api/useAsync';
import { Disclaimer, Loading, ErrorBox, cardClass, pad2 } from './format';

const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`;

export const Zone34Panel: React.FC<{ game: GameKey }> = ({ game }) => {
  const { data, loading, error } = useAsync(() => api.yahongRadar(game), [game]);

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <Disclaimer />

      {loading && <Loading />}
      {error && <ErrorBox msg={error} />}

      {data && (
        <>
          {/* 大盤狀態:連續未出同區 3 顆以上 */}
          <div className={`${cardClass} flex items-center gap-4`}>
            <div className="p-3 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
              <Radar className="w-6 h-6" />
            </div>
            <div>
              <div className="text-[calc(11px*var(--fs))] uppercase tracking-wider text-neutral-400">連續未出同區 3 顆以上</div>
              <div className="text-3xl font-mono font-bold text-neutral-900 dark:text-white tabular-nums">
                {data.consecutiveMiss} <span className="text-base font-sans font-normal text-neutral-400">期</span>
              </div>
            </div>
          </div>

          {/* 四柱最冷號輔助顯示 */}
          {data.columns?.length > 0 && (
            <div className={`${cardClass} space-y-3`}>
              <div className="text-[calc(11px*var(--fs))] font-semibold text-neutral-600 dark:text-neutral-300">四柱最冷號</div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {data.columns.map(c => (
                  <div key={c.label} className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] text-center">
                    <div className="text-[calc(10px*var(--fs))] text-neutral-400 truncate">{c.label}</div>
                    <div className="text-2xl font-mono font-bold text-neutral-900 dark:text-white mt-1">{pad2(c.coldest)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 策略 A */}
          <div className={`p-5 rounded-2xl border ${
            data.strategyA.active ? 'bg-rose-500/10 border-rose-500/30' : cardClass
          }`}>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2 font-display font-bold text-sm text-neutral-900 dark:text-white">
                <Flame className={`w-4 h-4 ${data.strategyA.active ? 'text-rose-500' : 'text-neutral-400'}`} />
                <span>策略 A · 量化正收益</span>
              </div>
              <span className={`text-[calc(11px*var(--fs))] font-semibold px-2.5 py-1 rounded-full ${
                data.strategyA.active ? 'bg-rose-500/20 text-rose-700 dark:text-rose-300' : 'bg-black/5 dark:bg-white/10 text-neutral-500'
              }`}>
                {data.strategyA.active ? '進場時刻' : '觀望中'}
              </span>
            </div>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2">
              條件:連 {data.strategyA.threshold} 期未出同區 3 顆。打法:{data.strategyA.note}
            </p>
            {data.strategyA.active && data.strategyA.coldest && data.strategyA.coldest.length > 0 && (
              <div className="mt-3">
                <div className="text-[calc(11px*var(--fs))] font-semibold text-rose-700 dark:text-rose-300 mb-1.5">🔥 達標!建議刪除極端死號:</div>
                <div className="flex flex-wrap gap-2">
                  {data.strategyA.coldest.map(n => (
                    <span key={n} className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-rose-500 text-white font-mono font-bold text-sm">
                      {pad2(n)}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 策略 B */}
          <div className={`p-5 rounded-2xl border ${
            data.strategyB.active ? 'bg-purple-500/10 border-purple-500/30' : cardClass
          }`}>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2 font-display font-bold text-sm text-neutral-900 dark:text-white">
                <ShieldCheck className={`w-4 h-4 ${data.strategyB.active ? 'text-purple-500' : 'text-neutral-400'}`} />
                <span>策略 B · 防呆狙擊手</span>
              </div>
              <span className={`text-[calc(11px*var(--fs))] font-semibold px-2.5 py-1 rounded-full ${
                data.strategyB.active ? 'bg-purple-500/20 text-purple-700 dark:text-purple-300' : 'bg-black/5 dark:bg-white/10 text-neutral-500'
              }`}>
                {data.strategyB.active ? '重擊進場' : '觀望中'}
              </span>
            </div>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2">
              條件:連 {data.strategyB.threshold} 期未出同區 3 顆。打法:{data.strategyB.note}
            </p>
            {data.strategyB.active && (
              <div className="mt-3 text-xs font-semibold text-purple-700 dark:text-purple-300">
                🎯 狙擊時機已到!今晚不刪牌直接滿注進場,等待爆發,睡覺免煩惱!
              </div>
            )}
          </div>

          {/* 極端偏態雷達(原站主頁):同柱 3 顆以上斷柱預警 */}
          {data.extreme && data.extreme.totalDraws >= 5 && (
            <div className={`${cardClass} space-y-3`}>
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2 font-display font-bold text-sm text-neutral-900 dark:text-white">
                  <Siren className="w-4 h-4 text-rose-500" />
                  <span>同柱 3 顆以上 · 斷柱監控</span>
                </div>
                <span className="text-[calc(11px*var(--fs))] text-neutral-400">
                  已 {data.extreme.tripleStreak} 期沒開 · 統計近 {data.extreme.totalDraws} 期
                </span>
              </div>
              <div className="text-sm font-semibold text-neutral-700 dark:text-neutral-200">
                下期開出機率:<span className="font-mono text-rose-600 dark:text-rose-400">{pct1(data.extreme.tripleNextProb)}</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {data.extreme.columns.map(c => (
                  <div key={c.label} className={`p-3 rounded-xl border text-center ${
                    c.danger
                      ? 'bg-rose-500/10 border-rose-500/30'
                      : 'bg-black/[0.02] dark:bg-white/[0.03] border-black/[0.06] dark:border-white/[0.06]'
                  }`}>
                    <div className="text-[calc(10px*var(--fs))] text-neutral-400 truncate">{c.label}</div>
                    <div className={`text-xl font-mono font-bold mt-1 ${c.danger ? 'text-rose-600 dark:text-rose-400' : 'text-neutral-900 dark:text-white'}`}>
                      {pct1(c.prob)}
                    </div>
                    <div className="text-[calc(10px*var(--fs))] text-neutral-400 mt-0.5">
                      {c.streak} 期沒開 · 平常 {pct1(c.hits / data.extreme.totalDraws)}
                    </div>
                  </div>
                ))}
              </div>
              <div className="text-xs font-semibold text-rose-700 dark:text-rose-300">
                最可能開:{data.extreme.columns.filter(c => c.danger).map(c => c.label).join('、')}
              </div>
              <p className="text-[calc(10px*var(--fs))] text-neutral-400">
                機率是原站算法:越久沒開加越多。「平常」是過去實際開出的比例,可以對照著看。
              </p>
            </div>
          )}

          {/* 新系統:6 因子分區評分 → 今晚最佳打擊區(原站同區戰情室) */}
          {data.quant && (
            <div className={`${cardClass} space-y-3`}>
              <div className="flex items-center gap-2 font-display font-bold text-sm text-neutral-900 dark:text-white">
                <Target className="w-4 h-4 text-amber-500" />
                <span>今晚主攻哪一柱</span>
              </div>
              <div className="text-sm font-semibold text-neutral-700 dark:text-neutral-200">
                {data.quant.labels[data.quant.best]}
                <span className="ml-2 text-xs font-normal text-neutral-400">
                  分數佔比 <span className="font-mono text-amber-600 dark:text-amber-400">{data.quant.pct[data.quant.best]}%</span>
                </span>
              </div>
              <div className="space-y-2">
                {data.quant.pct.map((p, i) => {
                  const best = i === data.quant!.best;
                  return (
                    <div key={i}>
                      <div className="flex justify-between text-[calc(11px*var(--fs))] mb-1">
                        <span className={best ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-neutral-500'}>第{i + 1}柱</span>
                        <span className={`font-mono ${best ? 'text-amber-600 dark:text-amber-400 font-semibold' : 'text-neutral-400'}`}>{p}%</span>
                      </div>
                      <div className="h-2 rounded-full bg-black/5 dark:bg-white/10 overflow-hidden">
                        <div className={`h-full rounded-full ${best ? 'bg-amber-500' : 'bg-neutral-400/60'}`} style={{ width: `${p}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="text-[calc(10px*var(--fs))] text-neutral-400">
                看近 50 期各柱的開出量、最近 5 期走勢、上期開完後通常接哪柱等,合起來打分數。上面的策略 A/B 看要不要下、下多少,這裡看下哪一柱。
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
};
