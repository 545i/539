import React, { useState } from 'react';
import { Wallet } from 'lucide-react';
import { api, GameKey, YahongPlanKind } from '../../../api/client';
import { useAsync } from '../../../api/useAsync';
import { Disclaimer, Loading, ErrorBox, cardClass, money } from './format';

const KINDS: { id: YahongPlanKind; label: string; days: number }[] = [
  { id: 'single', label: '單碼目標倍投', days: 15 },
  { id: 'four', label: '4 碼目標倍投', days: 6 },
  { id: 'tier', label: '階梯均注', days: 15 },
];

// 一個數字輸入格
const NumField: React.FC<{ label: string; value: number; onChange: (v: number) => void; step?: number }> = ({
  label, value, onChange, step = 1,
}) => (
  <label className="flex flex-col gap-1">
    <span className="text-[10px] uppercase tracking-wider text-neutral-400">{label}</span>
    <input
      type="number"
      step={step}
      value={value}
      onChange={e => onChange(Number(e.target.value))}
      className="w-full px-2.5 py-1.5 rounded-lg bg-white dark:bg-[#0d0d0d] border border-black/[0.12] dark:border-white/[0.12] text-sm font-mono text-neutral-900 dark:text-white focus:outline-none focus:border-black/30 dark:focus:border-white/30"
    />
  </label>
);

export const PlanPanel: React.FC<{ game: GameKey }> = ({ game }) => {
  const [kind, setKind] = useState<YahongPlanKind>('single');
  const [units, setUnits] = useState(1);
  const [target, setTarget] = useState(18440);
  const [days, setDays] = useState(15);
  const [cost, setCost] = useState(2755);
  const [prize, setPrize] = useState(21200);
  const [tierMode, setTierMode] = useState<'single' | 'four'>('single');

  const switchKind = (k: YahongPlanKind) => {
    setKind(k);
    setDays(KINDS.find(x => x.id === k)?.days ?? 15);
  };

  const { data, loading, error } = useAsync(
    () => api.yahongPlan(game, {
      kind, units, target, days, cost, prize,
      ...(kind === 'tier' ? { tierMode } : {}),
    }),
    [game, kind, units, target, days, cost, prize, tierMode],
  );

  const showDouble = kind === 'four';

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <Disclaimer />

      {/* kind 切換 */}
      <div className="flex gap-2 flex-wrap">
        {KINDS.map(k => (
          <button
            key={k.id}
            type="button"
            onClick={() => switchKind(k.id)}
            className={`px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all ${
              kind === k.id
                ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                : 'bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
            }`}
          >
            {k.label}
          </button>
        ))}
      </div>

      {/* 參數輸入 */}
      <div className={`${cardClass} space-y-4`}>
        <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
          <Wallet className="w-4 h-4 text-neutral-500" />
          <span>資金規劃參數</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <NumField label="起步車數" value={units} onChange={setUnits} step={0.05} />
          {kind !== 'tier' && <NumField label="每期目標淨利" value={target} onChange={setTarget} step={100} />}
          <NumField label="期數" value={days} onChange={setDays} />
          <NumField label="每車成本" value={cost} onChange={setCost} step={5} />
          <NumField label="中獎彩金" value={prize} onChange={setPrize} step={100} />
          {kind === 'tier' && (
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-wider text-neutral-400">階梯模式</span>
              <select
                value={tierMode}
                onChange={e => setTierMode(e.target.value as 'single' | 'four')}
                className="w-full px-2.5 py-1.5 rounded-lg bg-white dark:bg-[#0d0d0d] border border-black/[0.12] dark:border-white/[0.12] text-sm text-neutral-900 dark:text-white focus:outline-none focus:border-black/30 dark:focus:border-white/30"
              >
                <option value="single">單碼(3 期一階)</option>
                <option value="four">4 碼(2 期一階)</option>
              </select>
            </label>
          )}
        </div>
      </div>

      {loading && <Loading />}
      {error && <ErrorBox msg={error} />}

      {/* 結果表 */}
      {data && (
        <div className={`${cardClass} overflow-x-auto`}>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-neutral-400">
                <th className="px-2 py-2">天數</th>
                <th className="px-2 py-2 text-right">目標累計淨利</th>
                <th className="px-2 py-2 text-right">下注車數</th>
                <th className="px-2 py-2 text-right">當期成本</th>
                <th className="px-2 py-2 text-right">累計投入</th>
                <th className="px-2 py-2 text-right">中獎彩金</th>
                <th className="px-2 py-2 text-right">結算淨利</th>
                {showDouble && <th className="px-2 py-2 text-right">中 2 碼暴利</th>}
              </tr>
            </thead>
            <tbody className="font-mono">
              {data.rows.map(r => (
                <tr key={r.day} className="border-t border-black/[0.05] dark:border-white/[0.05] hover:bg-black/[0.02] dark:hover:bg-white/[0.02]">
                  <td className="px-2 py-2 font-bold text-neutral-900 dark:text-white">{r.day}</td>
                  <td className="px-2 py-2 text-right text-neutral-500 tabular-nums">{money(r.target)}</td>
                  <td className="px-2 py-2 text-right text-neutral-900 dark:text-white tabular-nums">{r.units.toFixed(2)} 車</td>
                  <td className="px-2 py-2 text-right text-neutral-500 tabular-nums">{money(r.dailyCost)}</td>
                  <td className="px-2 py-2 text-right text-neutral-500 tabular-nums">{money(r.accCost)}</td>
                  <td className="px-2 py-2 text-right text-neutral-500 tabular-nums">{money(r.winPrize)}</td>
                  <td className={`px-2 py-2 text-right font-bold tabular-nums ${
                    r.netProfit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'
                  }`}>{money(r.netProfit)}</td>
                  {showDouble && (
                    <td className="px-2 py-2 text-right text-purple-600 dark:text-purple-400 tabular-nums">
                      {r.doubleWin !== undefined ? money(r.doubleWin) : '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-neutral-400 mt-3">
            車數一律向上取整到 0.05;「保證賺錢」為無上限馬丁格爾加碼的話術,本金爆掉風險未計入。
          </p>
        </div>
      )}
    </div>
  );
};
