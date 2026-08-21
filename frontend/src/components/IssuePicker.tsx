import React from 'react';
import { ChevronDown } from 'lucide-react';
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
  className?: string;
}

export const IssuePicker: React.FC<IssuePickerProps> = ({
  issue,
  date,
  draws,
  onSelect,
  className = '',
}) => {
  // 新→舊,最新一期排最上面
  const options = React.useMemo(() => [...draws].reverse(), [draws]);
  const inList = options.some(o => o.issue === issue);

  return (
    <div className={`relative inline-flex items-center ${className}`}>
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
  );
};
