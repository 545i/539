import React, { useState } from 'react';
import { Crosshair, AlertTriangle } from 'lucide-react';
import { GameKey } from '../../api/client';
import { useGame } from '../../api/useGame';
import { MatrixPanel } from './yahong/MatrixPanel';
import { SinglePanel } from './yahong/SinglePanel';
import { Zone34Panel } from './yahong/Zone34Panel';
import { AnalysisPanel } from './yahong/AnalysisPanel';
import { PlanPanel } from './yahong/PlanPanel';
import { cardClass } from './yahong/format';

// 雅宏策略僅支援 39 選 5 的兩款(符合「碰」模型);六合彩不支援。
const SUPPORTED: GameKey[] = ['lotto539', 'fantasy5'];
const GAME_LABEL: Record<string, string> = { lotto539: '今彩 539', fantasy5: '天天樂' };

type SubTab = 'matrix' | 'single' | 'zone34' | 'analysis' | 'plan';
const SUBTABS: { id: SubTab; label: string }[] = [
  { id: 'matrix', label: '決策矩陣' },
  { id: 'single', label: '單碼必贏' },
  { id: 'zone34', label: '同區 3-4 球' },
  { id: 'analysis', label: '綜合分析' },
  { id: 'plan', label: '資金規劃' },
];

export const YahongView: React.FC = () => {
  const { gameKey, setGameKey, games } = useGame();
  const [sub, setSub] = useState<SubTab>('matrix');

  const labelOf = (k: GameKey) => games.find(g => g.key === k)?.short_name ?? GAME_LABEL[k] ?? k;
  const supported = SUPPORTED.includes(gameKey);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Title */}
      <div className={cardClass}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <Crosshair className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              雅宏策略 · 量化操盤系統
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              決策矩陣 / 單碼必贏 / 同區 3-4 球 / 綜合分析 / 資金規劃(僅支援 39 選 5 的今彩 539 與天天樂)
            </p>
          </div>
        </div>
      </div>

      {/* 遊戲切換(限 lotto539 / fantasy5) */}
      <div className="flex gap-2">
        {SUPPORTED.map(k => (
          <button
            key={k}
            type="button"
            onClick={() => setGameKey(k)}
            className={`px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all ${
              gameKey === k
                ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                : 'bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
            }`}
          >
            {labelOf(k)}
          </button>
        ))}
      </div>

      {/* 六合彩不支援:提示 + 切換 */}
      {!supported ? (
        <div className={`${cardClass} space-y-3`}>
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-semibold text-sm">
            <AlertTriangle className="w-4 h-4" />
            <span>雅宏策略僅支援 539 / 天天樂</span>
          </div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            目前選的是{labelOf(gameKey)}(49 選 6),不符合「碰」模型。請切換到下列遊戲:
          </p>
          <div className="flex gap-2">
            {SUPPORTED.map(k => (
              <button
                key={k}
                type="button"
                onClick={() => setGameKey(k)}
                className="px-4 py-2 rounded-full text-xs font-semibold bg-black text-white dark:bg-white dark:text-black transition-all active:scale-98"
              >
                切到{labelOf(k)}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          {/* 子分頁 tab bar */}
          <div className="border-b border-black/[0.08] dark:border-white/[0.08] pb-3">
            <div className="flex overflow-x-auto gap-2 no-scrollbar">
              {SUBTABS.map(t => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSub(t.id)}
                  className={`whitespace-nowrap px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all ${
                    sub === t.id
                      ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                      : 'bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* 子分頁內容(key=gameKey 讓切遊戲時重掛,狀態歸零) */}
          <div key={gameKey}>
            {sub === 'matrix' && <MatrixPanel game={gameKey} />}
            {sub === 'single' && <SinglePanel game={gameKey} />}
            {sub === 'zone34' && <Zone34Panel game={gameKey} />}
            {sub === 'analysis' && <AnalysisPanel game={gameKey} />}
            {sub === 'plan' && <PlanPanel game={gameKey} />}
          </div>
        </>
      )}
    </div>
  );
};
