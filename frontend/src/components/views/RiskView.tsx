import React from 'react';
import { ShieldAlert, TrendingDown, Dice5, Info } from 'lucide-react';

// 風險與數學期望值提醒(獨立頁)。原本是各頁底部的摺疊區塊,改成導覽獨立頁。
// 純說明,無資料相依;提醒回本車數 / 倍投都改變不了負期望本質。

const Card: React.FC<{ icon: React.ReactNode; title: string; tone?: 'warn' | 'plain'; children: React.ReactNode }> = ({ icon, title, tone = 'plain', children }) => (
  <div className={`rounded-2xl border p-5 sm:p-6 space-y-2.5 ${
    tone === 'warn'
      ? 'border-amber-300/60 dark:border-amber-500/30 bg-amber-50/60 dark:bg-amber-500/[0.06]'
      : 'border-black/[0.08] dark:border-white/[0.08] bg-white dark:bg-[#121212]'
  }`}>
    <div className="flex items-center gap-2">
      <span className={tone === 'warn' ? 'text-amber-600 dark:text-amber-400' : 'text-neutral-500'}>{icon}</span>
      <h3 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white">{title}</h3>
    </div>
    <div className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-300 leading-relaxed space-y-2">
      {children}
    </div>
  </div>
);

export const RiskView: React.FC = () => (
  <div className="max-w-3xl space-y-4 animate-in fade-in duration-200">
    <div className="flex items-center gap-2.5">
      <ShieldAlert className="w-6 h-6 text-amber-500" />
      <div>
        <h2 className="text-lg sm:text-xl font-display font-bold text-neutral-900 dark:text-white">風險與數學期望值提醒</h2>
        <p className="text-[11px] sm:text-xs text-neutral-400">下注前必讀 · 理性娛樂</p>
      </div>
    </div>

    <Card icon={<Dice5 className="w-4 h-4" />} title="回本車數只是算術,不改變期望值">
      <p>本工具的「建議車數 / 支數」是<strong>回本試算</strong>——算出中一次要下幾車才追得回目前虧損,純屬算術推算。</p>
      <p>它<strong>無法改變每一局都是負期望值的本質</strong>:盤口抽水後,長期返還率低於 100%,玩越多局越貼近那條負線。</p>
    </Card>

    <Card icon={<TrendingDown className="w-4 h-4" />} title="連敗時虧損呈幾何級數成長" tone="warn">
      <p>用「凹 / 倍投」追號時,連敗中的累積虧損會<strong>乘上 1/(1−k)</strong> 快速膨脹。k 主要由「押選顆數 / 下注款數」決定。</p>
      <p>選號越多、下注越多款,k 越趨近於 1,<strong>資金消耗急遽加速</strong>。倍投只是把「多數小贏」換成「極少數但無上限的巨賠」,那條尾巴遲早會來。</p>
    </Card>

    <Card icon={<Info className="w-4 h-4" />} title="請理性娛樂">
      <p>長期統計仍為<strong>負期望值</strong>。任何下注順序 / 停損 / 加碼策略都改變不了盤口的抽水;真正決定盈虧的是賠率本身,不是下注技巧。</p>
      <p className="text-neutral-400">請量力而為、設好停損,把本工具當成<strong>對帳與收支管理</strong>的輔助,而非「必勝下注法」。</p>
    </Card>
  </div>
);
