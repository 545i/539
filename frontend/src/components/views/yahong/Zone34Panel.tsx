import React from 'react';
import { Radar, Flame, ShieldCheck } from 'lucide-react';
import { api, GameKey } from '../../../api/client';
import { useAsync } from '../../../api/useAsync';
import { Disclaimer, Loading, ErrorBox, cardClass, pad2 } from './format';

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
              <div className="text-[11px] uppercase tracking-wider text-neutral-400">連續未出同區 3 顆以上</div>
              <div className="text-3xl font-mono font-bold text-neutral-900 dark:text-white tabular-nums">
                {data.consecutiveMiss} <span className="text-base font-sans font-normal text-neutral-400">期</span>
              </div>
            </div>
          </div>

          {/* 四柱最冷號輔助顯示 */}
          {data.columns?.length > 0 && (
            <div className={`${cardClass} space-y-3`}>
              <div className="text-[11px] font-semibold text-neutral-600 dark:text-neutral-300">四柱最冷號</div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {data.columns.map(c => (
                  <div key={c.label} className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] text-center">
                    <div className="text-[10px] text-neutral-400 truncate">{c.label}</div>
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
              <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full ${
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
                <div className="text-[11px] font-semibold text-rose-700 dark:text-rose-300 mb-1.5">🔥 達標!建議刪除極端死號:</div>
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
              <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full ${
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
        </>
      )}
    </div>
  );
};
