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
  onSelect: (issue: string, date: string) => void;
  // 給了就在下拉旁多一顆「對獎」鈕:對同一期重抓開獎號重算(核對列表用)。
  // 需要它是因為 <select> 選同一個值不會觸發 onChange —— 記帳當下就是最新期,
  // 開獎後想對「原本那一期」的獎,不按鈕根本沒機會觸發。
  onRefresh?: () => void;
  className?: string;
}

export const IssuePicker: React.FC<IssuePickerProps> = ({
  issue,
  date,
  draws,
  onSelect,
  onRefresh,
  className = '',
}) => {
  // 新→舊,最新一期排最上面
  const options = React.useMemo(() => [...draws].reverse(), [draws]);
  const inList = options.some(o => o.issue === issue);

  return (
    <div className={`inline-flex items-center gap-1 ${className}`}>
      <div className="relative inline-flex items-center">
        <select
          value={issue}
          onChange={e => {
            const picked = options.find(o => o.issue === e.target.value);
            onSelect(e.target.value, picked?.date ?? date);
          }}
          className="appearance-none pr-6 pl-2 py-1 rounded-lg border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-[11px] font-mono font-bold text-neutral-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-black/20 dark:focus:ring-white/20 cursor-pointer"
        >
          {issue && !inList && (
            <option value={issue}>{issue}（{date}）</option>
          )}
          {options.map(o => (
            <option key={o.issue} value={o.issue}>
              {o.issue}（{o.date}）
            </option>
          ))}
        </select>
        <ChevronDown className="w-3 h-3 text-neutral-400 absolute right-1.5 pointer-events-none" />
      </div>
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
    </div>
  );
};
