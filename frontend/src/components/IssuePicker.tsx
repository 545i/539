import React from 'react';
import { ChevronDown, RotateCw } from 'lucide-react';
import { DrawDTO } from '../api/client';

// 期數下拉選單:讓使用者手動挑「這筆記在哪一期」,選項同時顯示期號與日期。
//
// 原本四個下注分頁都把期號寫死成最新一期(latest.issue),補記舊期 / 修期就沒
// 辦法。這個共用元件吃 history 的 draws(舊→新),倒過來排成新→舊給人選;選中
// 哪期就把該期的日期一起帶回去,期號與日期永遠對得起來。
//
// 若目前的期號不在清單裡(例如預設帶到「下一期」還沒開),仍保留一個選項顯示
// 它,免得下拉框看起來是空的。

interface IssuePickerProps {
  issue: string;
  date: string;
  draws: DrawDTO[]; // 舊→新(history API 的順序)
  // 一個永遠出現在最上面的額外選項(通常是「下一期(還沒開)」)。它不在 draws 裡,
  // 帶著自己的正確日期;不管目前選到哪期都選得回來 —— 解決「切到別期後就選不回
  // 最新未開一期」。與 draws 重號時自動略過。
  extraOption?: {issue: string; date: string};
  onSelect: (issue: string, date: string) => void;
  // 給了就在下拉旁多一顆「對獎」鈕:對同一期重抓開獎號重算(核對列表用)。
  // 需要它是因為 <select> 選同一個值不會觸發 onChange —— 記帳當下就是最新期,
  // 開獎後想對「原本那一期」的獎,不按鈕根本沒機會觸發。
  onRefresh?: () => void;
  // 給了就在旁邊多一個「中N顆」小輸入 + 套用鈕:忘記期數但記得中幾顆時,直接
  // 依組公式手填結算(不查開獎號)。見 backend.settle 的 hit_count。
  onManualHit?: (hitCount: number) => void;
  // 1800碰:分幾柱填「各柱中幾顆」,中碰=各柱相乘(取代單一「中N」)。
  manualPillars?: number;
  // 下拉選項要不要一起顯示遊戲名(期號+日期+遊戲+開獎號)。
  gameLabel?: string;
  // 選到的那期是否在下拉旁邊顯示開獎號碼(預設 true)。核對表格自己有「開獎號碼」
  // 欄,旁邊再顯示一次是多餘的,那裡傳 false 關掉。
  showNums?: boolean;
  className?: string;
}

export const IssuePicker: React.FC<IssuePickerProps> = ({
  issue,
  date,
  draws,
  extraOption,
  onSelect,
  onRefresh,
  onManualHit,
  manualPillars,
  gameLabel,
  showNums = true,
  className = '',
}) => {
  // 新→舊,最新一期排最上面
  const options = React.useMemo(() => [...draws].reverse(), [draws]);
  // 永遠置頂的額外選項(下一期未開)+ 目前 issue 若不在任何清單裡的合成 fallback。
  // 兩者都不在 draws 裡、都沒有開獎號,合起來去重後排在真正的開獎期別之前。
  const extras = React.useMemo(() => {
    const list: {issue: string; date: string}[] = [];
    if (extraOption && !options.some(o => o.issue === extraOption.issue)) {
      list.push(extraOption);
    }
    if (issue && !options.some(o => o.issue === issue) &&
        !list.some(e => e.issue === issue)) {
      list.push({issue, date});
    }
    return list;
  }, [extraOption, options, issue, date]);
  // 下拉選項只顯示 期號(日期)—— 乾淨、可讀、不撐寬(號碼另在選到後旁邊顯示)
  const optionText = (o: DrawDTO): string => `${o.issue}（${o.date}）`;
  const selNums = (options.find(o => o.issue === issue)?.nums ?? [])
    .map(n => String(n).padStart(2, '0')).join(' ');
  const [hit, setHit] = React.useState('');

  // 1800碰 直接填「中幾碰」,其他玩法填「中幾顆」—— 差在標籤,值都是直接送去結算
  const isPillar = (manualPillars ?? 0) > 1;
  const hitLabel = isPillar ? '碰' : '顆';
  const hitPlaceholder = isPillar ? '中碰' : '中N';

  const applyHit = () => {
    const k = Number(hit);
    if (!onManualHit || hit === '' || Number.isNaN(k) || k < 0) return;
    onManualHit(Math.floor(k));
    setHit('');
  };

  return (
    <div className={`inline-flex items-center gap-1 ${className}`}>
      <div className="relative inline-flex items-center">
        <select
          value={issue}
          onChange={e => {
            const val = e.target.value;
            const picked = options.find(o => o.issue === val)
              ?? extras.find(o => o.issue === val);
            onSelect(val, picked?.date ?? date);
          }}
          className="appearance-none pr-6 pl-2 py-1 rounded-lg border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-[11px] font-mono font-bold text-neutral-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-black/20 dark:focus:ring-white/20 cursor-pointer"
        >
          {extras.map(o => (
            <option key={o.issue} value={o.issue}>{o.issue}（{o.date}）</option>
          ))}
          {options.map(o => (
            <option key={o.issue} value={o.issue}>
              {optionText(o)}
            </option>
          ))}
        </select>
        <ChevronDown className="w-3 h-3 text-neutral-400 absolute right-1.5 pointer-events-none" />
      </div>
      {showNums && selNums && (
        <span className="text-[11px] font-mono font-semibold text-neutral-600 dark:text-neutral-300 whitespace-nowrap">
          {selNums}
        </span>
      )}
      {onRefresh && (
        <button
          type="button"
          onClick={onRefresh}
          title="重新對獎(抓這一期開獎號重算)"
          className="shrink-0 p-1 rounded-lg border border-black/10 dark:border-white/10 text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-colors"
        >
          <RotateCw className="w-3 h-3" />
        </button>
      )}
      {onManualHit && (
        <div className="inline-flex items-center gap-0.5" title={`忘記期數?直接填中幾${hitLabel}結算`}>
          <input
            type="number"
            min={0}
            value={hit}
            placeholder={hitPlaceholder}
            onChange={e => setHit(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') applyHit(); }}
            className="w-12 px-1 py-1 rounded-lg border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-[11px] font-mono text-neutral-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-black/20 dark:focus:ring-white/20"
          />
          <button
            type="button"
            onClick={applyHit}
            title={`依填入的中獎${hitLabel}數結算(不查開獎號)`}
            className="shrink-0 px-1.5 py-1 rounded-lg border border-black/10 dark:border-white/10 text-[10px] font-semibold text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-colors"
          >
            {hitLabel}
          </button>
        </div>
      )}
    </div>
  );
};
