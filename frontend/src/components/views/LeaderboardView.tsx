import React from 'react';
import { Trophy } from 'lucide-react';

export const LeaderboardView: React.FC = () => {
  // TODO(api): 排行榜端點 —— 後端目前沒有策略回測/排行的端點,
  // 下面這份是參考設計 v2 的示範資料,不是真實回測結果。
  // 端點補上後改成 useAsync(() => api.leaderboard(game), [game]),欄位需含
  // name / win_rate / roi / score / badge。
  const strategies = [
    { rank: 1, name: '單顆下注 (追平停利)', winRate: '12.8%', roi: '-12.4%', score: 92, badge: '推薦資金控管' },
    { rank: 2, name: '三柱 1800碰 (穩定過關)', winRate: '55.4%', roi: '-1.0%', score: 88, badge: '過關率最高' },
    { rank: 3, name: '連碰 拖膽 8顆', winRate: '4.9%', roi: '-18.5%', score: 79, badge: '爆發力高' },
    { rank: 4, name: '多顆下注 20顆', winRate: '51.3%', roi: '-24.8%', score: 72, badge: '回本較慢' },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <Trophy className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              選號策略與績效排行榜
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              各策略回測期望值與抗連敗破產係數綜合排行
            </p>
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {strategies.map((item) => (
          <div
            key={item.rank}
            className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] flex items-center justify-between gap-4"
          >
            <div className="flex items-center gap-4">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center font-display font-bold text-xs ${
                item.rank === 1 ? 'bg-black text-white dark:bg-white dark:text-black' :
                'border border-black/15 dark:border-white/15 text-neutral-700 dark:text-neutral-300'
              }`}>
                0{item.rank}
              </div>
              <div>
                <div className="font-bold text-sm text-neutral-900 dark:text-white flex items-center gap-2">
                  <span>{item.name}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300 font-mono">
                    {item.badge}
                  </span>
                </div>
                <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
                  勝率: <strong className="font-mono text-neutral-800 dark:text-neutral-200">{item.winRate}</strong> | 理論期望返還: <strong className="font-mono">{item.roi}</strong>
                </div>
              </div>
            </div>

            <div className="text-right">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">綜合評分</div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white">{item.score}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
