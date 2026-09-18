import React, { useState } from 'react';
import { Wallet } from 'lucide-react';
import { api, GameKey, YahongPlanKind, YahongPlanParams, YahongPlanRowDTO } from '../../../api/client';
import { useAsync } from '../../../api/useAsync';
import { Disclaimer, Loading, ErrorBox, cardClass, money } from './format';

type TierMode = 'single' | 'four';

// 選單項:一個按鈕 → (kind, 可選 tierMode)。天天樂把階梯拆成單碼/4碼兩顆,
// 539 只給一顆「階梯均注」(kind=tier,tierMode 由 selected.tierMode 帶,預設 single)。
interface MenuItem { id: string; label: string; kind: YahongPlanKind; tierMode?: TierMode }

const MENU_539: MenuItem[] = [
  { id: 'single', label: '單碼目標倍投', kind: 'single' },
  { id: 'four', label: '4 碼目標倍投', kind: 'four' },
  { id: 'tier', label: '階梯均注', kind: 'tier' }, // tierMode 由下拉選
];
const MENU_FANTASY: MenuItem[] = [
  { id: 'single', label: '單碼目標倍投', kind: 'single' },
  { id: 'four', label: '4 碼目標倍投', kind: 'four' },
  { id: 'tier-single', label: '單碼階梯', kind: 'tier', tierMode: 'single' },
  { id: 'tier-four', label: '4 碼階梯', kind: 'tier', tierMode: 'four' },
  { id: 'pillar1800', label: '1800 立柱倍投', kind: 'pillar1800' },
  { id: 'pillar9000', label: '9000 立柱倍投', kind: 'pillar9000' },
];

const isPillar = (k: YahongPlanKind) => k === 'pillar1800' || k === 'pillar9000';

// 依 game/kind 給預設值(對齊 spec-539 §A / spec-fantasy §4)
const planDefaults = (game: GameKey, kind: YahongPlanKind) => {
  const f = game === 'fantasy5';
  if (isPillar(kind)) return { units: 1, target: 500, days: 6 };          // firstBet / targetProfit
  const units = f ? 0.1 : 1;
  const target = f ? 1844 : 18440;
  const days = kind === 'four' ? 6 : 15;
  return { units, target, days };
};

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

// 表格欄位定義(隨 kind/game 變):cell=顯示字串,profitVal=有值時依正負上色
interface Col {
  header: string;
  cell: (r: YahongPlanRowDTO) => string;
  profitVal?: (r: YahongPlanRowDTO) => number | undefined;
}
const m = (n?: number) => (n === undefined ? '—' : money(n));
const carsCell = (r: YahongPlanRowDTO) => (r.units !== undefined ? `${r.units.toFixed(2)} 車` : '—');

const columnsFor = (kind: YahongPlanKind, game: GameKey): Col[] => {
  if (kind === 'pillar1800') return [
    { header: '期數', cell: r => String(r.day) },
    { header: '下注金額', cell: r => m(r.bet) },
    { header: '當期實繳', cell: r => m(r.dailyCost) },
    { header: '累計實繳', cell: r => m(r.accCost) },
    { header: '中3碰彩金', cell: r => m(r.basePrize) },
    { header: '中3碰淨利', cell: r => m(r.baseProfit), profitVal: r => r.baseProfit },
    { header: '中4碰彩金', cell: r => m(r.bonusPrize) },
    { header: '中4碰淨利', cell: r => m(r.bonusProfit), profitVal: r => r.bonusProfit },
  ];
  if (kind === 'pillar9000') return [
    { header: '期數', cell: r => String(r.day) },
    { header: '下注金額', cell: r => m(r.bet) },
    { header: '當期實繳', cell: r => m(r.dailyCost) },
    { header: '累計實繳', cell: r => m(r.accCost) },
    { header: '中2碰滿貫彩金', cell: r => m(r.basePrize) },
    { header: '結算淨利', cell: r => m(r.baseProfit), profitVal: r => r.baseProfit },
  ];
  if (kind === 'tier') return [
    { header: '天數', cell: r => String(r.day) },
    { header: '階梯', cell: r => (r.tier !== undefined ? `第 ${r.tier} 階` : '—') },
    { header: '下注車數', cell: carsCell },
    { header: '當期成本', cell: r => m(r.dailyCost) },
    { header: '累計總成本', cell: r => m(r.accCost) },
    { header: '中獎彩金', cell: r => m(r.winPrize) },
    { header: '結算淨利', cell: r => m(r.netProfit), profitVal: r => r.netProfit },
  ];
  const cols: Col[] = [
    { header: '天數', cell: r => String(r.day) },
    { header: '目標累計淨利', cell: r => m(r.target) },
    { header: '下注車數', cell: carsCell },
    { header: '當期成本', cell: r => m(r.dailyCost) },
    { header: '累計投入', cell: r => m(r.accCost) },
    { header: '中獎彩金', cell: r => m(r.winPrize) },
    { header: '結算淨利', cell: r => m(r.netProfit), profitVal: r => r.netProfit },
  ];
  if (kind === 'four') {
    // 539 只有中 2 碼暴利(淨利);天天樂另有中 2 碼彩金
    if (game === 'fantasy5') cols.push({ header: '中 2 碼彩金', cell: r => m(r.doubleWinPrize) });
    cols.push({ header: '中 2 碼淨利', cell: r => m(r.doubleWin), profitVal: r => r.doubleWin });
  }
  return cols;
};

export const PlanPanel: React.FC<{ game: GameKey }> = ({ game }) => {
  const menu = game === 'fantasy5' ? MENU_FANTASY : MENU_539;
  const [menuId, setMenuId] = useState(menu[0].id);
  const selected = menu.find(x => x.id === menuId) ?? menu[0];
  const kind = selected.kind;

  const init = planDefaults(game, kind);
  const [units, setUnits] = useState(init.units);
  const [target, setTarget] = useState(init.target);
  const [days, setDays] = useState(init.days);
  const [cost, setCost] = useState(2755);
  const [prize, setPrize] = useState(21200);
  const [tierMode539, setTierMode539] = useState<TierMode>('single');

  // 選單切換時把 units/target/days 帶回該 kind 的預設
  const switchMenu = (item: MenuItem) => {
    setMenuId(item.id);
    const d = planDefaults(game, item.kind);
    setUnits(d.units);
    setTarget(d.target);
    setDays(d.days);
  };

  // tier 的 tierMode:天天樂由按鈕帶(selected.tierMode),539 由下拉
  const effTierMode: TierMode = selected.tierMode ?? tierMode539;

  // 依 kind 組送出的參數(pillar 不送 cost/prize —— 後端用寫死常數)
  const params: YahongPlanParams = { kind, units, days };
  if (kind === 'single' || kind === 'four') { params.target = target; params.cost = cost; params.prize = prize; }
  else if (kind === 'tier') { params.tierMode = effTierMode; }
  else if (isPillar(kind)) { params.target = target; }

  const { data, loading, error } = useAsync(
    () => api.yahongPlan(game, params),
    [game, kind, units, target, days, cost, prize, effTierMode],
  );

  const cols = columnsFor(kind, game);
  const pillar = isPillar(kind);
  const unitsStep = pillar ? 1 : game === 'fantasy5' ? 0.01 : 0.05;
  // 539 才顯示 tierMode 下拉(天天樂已用按鈕分開)
  const showTierDropdown = kind === 'tier' && selected.tierMode === undefined;

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <Disclaimer />

      {/* kind 選單 */}
      <div className="flex gap-2 flex-wrap">
        {menu.map(item => (
          <button
            key={item.id}
            type="button"
            onClick={() => switchMenu(item)}
            className={`px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all ${
              menuId === item.id
                ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                : 'bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
            }`}
          >
            {item.label}
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
          <NumField label={pillar ? '起步下注金額(元)' : '起步車數'} value={units} onChange={setUnits} step={unitsStep} />
          {kind !== 'tier' && (
            <NumField label={pillar ? '每期保底淨利' : '每期目標淨利'} value={target} onChange={setTarget} step={100} />
          )}
          <NumField label="期數" value={days} onChange={setDays} />
          {(kind === 'single' || kind === 'four') && (
            <>
              <NumField label="每車成本" value={cost} onChange={setCost} step={5} />
              <NumField label="中獎彩金" value={prize} onChange={setPrize} step={100} />
            </>
          )}
          {showTierDropdown && (
            <label className="flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-wider text-neutral-400">階梯模式</span>
              <select
                value={tierMode539}
                onChange={e => setTierMode539(e.target.value as TierMode)}
                className="w-full px-2.5 py-1.5 rounded-lg bg-white dark:bg-[#0d0d0d] border border-black/[0.12] dark:border-white/[0.12] text-sm text-neutral-900 dark:text-white focus:outline-none focus:border-black/30 dark:focus:border-white/30"
              >
                <option value="single">單碼(3 期一階)</option>
                <option value="four">4 碼(2 期一階)</option>
              </select>
            </label>
          )}
        </div>
        {pillar && (
          <p className="text-[10px] text-neutral-400">立柱倍投的每碰成本 / 彩金為寫死常數(1800:1134 / 570;9000:4545 / 8000),不受上方輸入影響。</p>
        )}
      </div>

      {loading && <Loading />}
      {error && <ErrorBox msg={error} />}

      {/* 結果表 */}
      {data && (
        <div className={`${cardClass} overflow-x-auto`}>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-neutral-400">
                {cols.map((c, i) => (
                  <th key={c.header} className={`px-2 py-2 ${i === 0 ? '' : 'text-right'}`}>{c.header}</th>
                ))}
              </tr>
            </thead>
            <tbody className="font-mono">
              {data.rows.map(r => (
                <tr key={r.day} className="border-t border-black/[0.05] dark:border-white/[0.05] hover:bg-black/[0.02] dark:hover:bg-white/[0.02]">
                  {cols.map((c, i) => {
                    const pv = c.profitVal?.(r);
                    const cls =
                      i === 0
                        ? 'px-2 py-2 font-bold text-neutral-900 dark:text-white'
                        : pv !== undefined
                          ? `px-2 py-2 text-right font-bold tabular-nums ${pv >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`
                          : 'px-2 py-2 text-right text-neutral-500 tabular-nums';
                    return <td key={c.header} className={cls}>{c.cell(r)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-[10px] text-neutral-400 mt-3">
            {pillar ? '下注金額為整數元;' : `車數一律向上取整到 ${game === 'fantasy5' ? '0.01' : '0.05'};`}
            「保證賺錢」為無上限馬丁格爾加碼的話術,本金爆掉風險未計入。
          </p>
        </div>
      )}
    </div>
  );
};
