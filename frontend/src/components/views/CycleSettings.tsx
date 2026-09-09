import React from 'react';
import { CalendarClock } from 'lucide-react';

// 週期性紀錄:已改為「全自動週期」——每週一~週日為一期,依開獎日期自動歸期,
// 過了下一週自動另立一期,跨週自動保存。不再需要手動開始 / 結算週期。
// 各週損益在「紀錄下注 → 總損益 → 各週損益」表;逐日 / 逐筆明細在「上傳歷史 → 每週總帳」。
export const CycleSettings: React.FC = () => (
  <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
    <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
      <CalendarClock className="w-4 h-4" />
      <span>週期性紀錄(全自動)</span>
    </h3>
    <div className="text-[12px] text-neutral-600 dark:text-neutral-300 leading-relaxed space-y-2">
      <p>
        週期已改為<strong className="text-neutral-900 dark:text-white">全自動</strong>:
        以<strong>週一~週日</strong>為一期,系統依每筆下注的<strong>開獎日期</strong>自動歸期。
        過了下一週,前一週自動封存、新一週自動另立一期 —— <strong>跨週自動保存</strong>,不必手動開始或結算。
      </p>
      <ul className="list-disc pl-5 space-y-1 text-neutral-500 dark:text-neutral-400">
        <li>看每一週的成本 / 派彩 / 盈虧:<strong>紀錄下注 → 總損益 → 各週損益</strong>。</li>
        <li>看某一週的逐日小計與逐筆明細:<strong>上傳歷史 → 每週總帳</strong>。</li>
      </ul>
    </div>
  </div>
);
