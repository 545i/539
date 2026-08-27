import React from 'react';
import { GameSwitcher } from './Header';
import { useEditions } from '../api/useEditions';

/** 下注遊戲 + 下注版本 選擇器(通用組件)。
 *  狀態來自全域 context(useGame / useEditions),各處引用共享同一選擇。 */
export const BetTargetSelector: React.FC = () => {
  const { editions, eid, setEid } = useEditions();
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] font-semibold text-neutral-500 dark:text-neutral-400">下注遊戲</span>
        <GameSwitcher />
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] font-semibold text-neutral-500 dark:text-neutral-400">下注版本</span>
        <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1 flex-wrap">
          {editions.map(e => (
            <button
              key={e.eid}
              type="button"
              onClick={() => setEid(e.eid)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                eid === e.eid
                  ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
              }`}
            >
              {e.name}
            </button>
          ))}
        </div>
        <span className="text-[10px] text-neutral-400">(在「設定」可新增版、改名、設各版盤口)</span>
      </div>
    </div>
  );
};
