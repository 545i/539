import React, { useState } from 'react';
import { Trash2, Dices, Flame, Sparkles, Keyboard, X } from 'lucide-react';

interface Props {
  selectedBalls: number[];
  onToggleBall: (ball: number) => void;
  onClear: () => void;
  onQuickSelect?: (balls: number[]) => void;
  maxBalls?: number;
  totalBalls?: number;
  label?: string;
  theme?: 'light' | 'dark';
}

export const LotteryBallPad: React.FC<Props> = ({
  selectedBalls,
  onToggleBall,
  onClear,
  onQuickSelect,
  maxBalls = 20,
  totalBalls = 39,
  label,
}) => {
  const [isKeypadOpen, setIsKeypadOpen] = useState(false);
  const [manualInput, setManualInput] = useState('');

  // Pillar 1: 10-18 (9 balls)
  const pillar1 = [10, 11, 12, 13, 14, 15, 16, 17, 18].filter(n => n <= totalBalls);
  
  // Pillar 2: 20-29 (10 balls)
  const pillar2 = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29].filter(n => n <= totalBalls);

  // Pillar 3: 01-09, 19, 30-39 (and 40-49 if totalBalls > 39)
  const pillar3Part1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 19].filter(n => n <= totalBalls);
  const pillar3Part2 = [30, 31, 32, 33, 34, 35, 36, 37, 38, 39].filter(n => n <= totalBalls);
  const pillar3Part3 = totalBalls > 39 
    ? [40, 41, 42, 43, 44, 45, 46, 47, 48, 49].filter(n => n <= totalBalls)
    : [];

  const handleRandomSelect = () => {
    if (!onQuickSelect) return;
    const all = Array.from({ length: totalBalls }, (_, i) => i + 1);
    const shuffled = [...all].sort(() => 0.5 - Math.random());
    const count = Math.min(maxBalls, 5);
    onQuickSelect(shuffled.slice(0, count));
  };

  const handleHotSelect = () => {
    if (!onQuickSelect) return;
    const hotPool = [12, 28, 5, 17, 39, 10, 23, 31].filter(n => n <= totalBalls);
    const count = Math.min(maxBalls, hotPool.length);
    onQuickSelect(hotPool.slice(0, count));
  };

  const handleApplyManual = () => {
    if (!onQuickSelect) return;
    const parsed = manualInput
      .split(/[\s,，、]+/)
      .map(s => parseInt(s.trim(), 10))
      .filter(n => !isNaN(n) && n >= 1 && n <= totalBalls);
    const unique = Array.from(new Set(parsed)).slice(0, maxBalls);
    if (unique.length > 0) {
      onQuickSelect(unique);
      setIsKeypadOpen(false);
      setManualInput('');
    }
  };

  const renderBall = (num: number, pillarType: 1 | 2 | 3) => {
    const isSelected = selectedBalls.includes(num);
    const numStr = num.toString().padStart(2, '0');

    let baseColorClasses = 'border-black/10 dark:border-white/10 text-neutral-800 dark:text-neutral-200 bg-white dark:bg-[#161616] hover:border-black/30 dark:hover:border-white/30';
    let selectedColorClasses = 'bg-black text-white dark:bg-white dark:text-black border-black dark:border-white font-bold shadow-xs scale-105';

    if (isSelected) {
      if (pillarType === 2) {
        selectedColorClasses = 'bg-amber-600 text-white dark:bg-amber-400 dark:text-black border-amber-600 dark:border-amber-400 font-bold shadow-xs scale-105';
      } else if (pillarType === 3) {
        selectedColorClasses = 'bg-emerald-700 text-white dark:bg-emerald-400 dark:text-black border-emerald-700 dark:border-emerald-400 font-bold shadow-xs scale-105';
      }
    }

    return (
      <button
        key={num}
        type="button"
        id={`ball-btn-${num}`}
        onClick={() => onToggleBall(num)}
        className={`w-8 h-8 sm:w-8 sm:h-8 rounded-full flex items-center justify-center font-bold text-xs font-mono border transition-all duration-100 active:scale-90 select-none ${
          isSelected ? selectedColorClasses : baseColorClasses
        }`}
      >
        {numStr}
      </button>
    );
  };

  return (
    <div id="lottery-ball-pad" className="space-y-3 p-3.5 sm:p-4 rounded-2xl bg-black/[0.02] dark:bg-white/[0.02] border border-black/[0.08] dark:border-white/[0.08] w-full overflow-hidden">
      {/* Top Header with Fast Preset Tools */}
      <div className="flex items-center justify-between gap-2 flex-wrap pb-2 border-b border-black/[0.06] dark:border-white/[0.06]">
        <div className="text-xs font-display font-bold uppercase tracking-wider text-neutral-800 dark:text-neutral-200">
          {label || '號碼矩陣'}
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {onQuickSelect && (
            <>
              <button
                type="button"
                onClick={handleRandomSelect}
                className="px-2.5 py-1 rounded-full text-[10px] font-semibold border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 flex items-center gap-1 transition-colors active:scale-95"
              >
                <Dices className="w-3 h-3 text-neutral-500" />
                隨機
              </button>
              <button
                type="button"
                onClick={handleHotSelect}
                className="px-2.5 py-1 rounded-full text-[10px] font-semibold border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 flex items-center gap-1 transition-colors active:scale-95"
              >
                <Flame className="w-3 h-3 text-amber-500" />
                熱門
              </button>
              <button
                type="button"
                onClick={() => setIsKeypadOpen(!isKeypadOpen)}
                className={`px-2.5 py-1 rounded-full text-[10px] font-semibold border transition-colors flex items-center gap-1 active:scale-95 ${
                  isKeypadOpen 
                    ? 'bg-black text-white dark:bg-white dark:text-black border-black dark:border-white' 
                    : 'border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-700 dark:text-neutral-300'
                }`}
              >
                <Keyboard className="w-3 h-3" />
                快速填號
              </button>
            </>
          )}
        </div>
      </div>

      {/* Fast Input Modal / Box for Mobile */}
      {isKeypadOpen && (
        <div className="p-3 rounded-xl bg-black/[0.04] dark:bg-white/[0.05] border border-black/10 dark:border-white/10 space-y-2 animate-in fade-in duration-150">
          <div className="flex items-center justify-between text-xs font-semibold text-neutral-700 dark:text-neutral-300">
            <span>直接輸入號碼 (空格或逗號隔開)</span>
            <button
              type="button"
              onClick={() => setIsKeypadOpen(false)}
              className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="例: 05 12 18 24 33"
              value={manualInput}
              onChange={e => setManualInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleApplyManual()}
              className="flex-1 px-3 py-1.5 text-xs rounded-lg border border-black/15 dark:border-white/15 bg-white dark:bg-[#121212] font-mono focus:outline-hidden"
            />
            <button
              type="button"
              onClick={handleApplyManual}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity"
            >
              套用
            </button>
          </div>
        </div>
      )}

      {/* Pillar 1 */}
      <div>
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold text-neutral-500 mb-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-neutral-900 dark:bg-white"></span>
          <span>第 1 柱 (10-18)</span>
        </div>
        <div className="flex flex-wrap gap-1.5 max-w-full">
          {pillar1.map(n => renderBall(n, 1))}
        </div>
      </div>

      {/* Pillar 2 */}
      <div>
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold text-amber-600 dark:text-amber-400 mb-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
          <span>第 2 柱 (20-29)</span>
        </div>
        <div className="flex flex-wrap gap-1.5 max-w-full">
          {pillar2.map(n => renderBall(n, 2))}
        </div>
      </div>

      {/* Pillar 3 */}
      <div>
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider font-semibold text-emerald-600 dark:text-emerald-400 mb-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
          <span>第 3 柱 (其餘號碼)</span>
        </div>
        <div className="space-y-1.5 max-w-full">
          <div className="flex flex-wrap gap-1.5">
            {pillar3Part1.map(n => renderBall(n, 3))}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {pillar3Part2.map(n => renderBall(n, 3))}
          </div>
          {pillar3Part3.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {pillar3Part3.map(n => renderBall(n, 3))}
            </div>
          )}
        </div>
      </div>

      {/* Footer / Selected counter & Clear */}
      <div className="flex items-center justify-between pt-2.5 border-t border-black/[0.06] dark:border-white/[0.06] text-xs gap-2 flex-wrap">
        <div className="text-neutral-600 dark:text-neutral-400 flex-1 min-w-0">
          {selectedBalls.length === 0 ? (
            <span className="text-neutral-400 dark:text-neutral-500 text-[11px] font-mono block truncate">
              點選號碼 (最多 {maxBalls} 顆)
            </span>
          ) : (
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[11px] font-semibold text-neutral-500">已選 ({selectedBalls.length}):</span>
              <span className="font-mono font-bold text-xs text-neutral-900 dark:text-white bg-black/5 dark:bg-white/10 px-1.5 py-0.5 rounded">
                {selectedBalls.sort((a, b) => a - b).map(n => n.toString().padStart(2, '0')).join(' ')}
              </span>
            </div>
          )}
        </div>

        <button
          type="button"
          id="clear-balls-btn"
          disabled={selectedBalls.length === 0}
          onClick={onClear}
          className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] uppercase tracking-wider font-semibold rounded-full border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 disabled:cursor-not-allowed transition-colors active:scale-95 shrink-0"
        >
          <Trash2 className="w-3 h-3" />
          清空
        </button>
      </div>
    </div>
  );
};
