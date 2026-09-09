import React from 'react';
import { X, BookOpen, AlertTriangle, ShieldCheck, CheckCircle2 } from 'lucide-react';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  type?: 'formula' | 'disclaimer';
}

export const FormulaModal: React.FC<Props> = ({
  isOpen,
  onClose,
  type = 'formula',
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        id="formula-modal-content"
        className="w-full max-w-2xl max-h-[85vh] overflow-y-auto bg-white dark:bg-[#121212] border border-black/10 dark:border-white/10 rounded-2xl shadow-2xl flex flex-col text-neutral-800 dark:text-neutral-200"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.08] dark:border-white/[0.08] sticky top-0 bg-white/95 dark:bg-[#121212]/95 backdrop-blur-xs z-10">
          <div className="flex items-center gap-2 font-display font-bold text-base text-neutral-900 dark:text-white uppercase tracking-wide">
            {type === 'formula' ? (
              <BookOpen className="w-4 h-4 text-neutral-500" />
            ) : (
              <ShieldCheck className="w-4 h-4 text-neutral-500" />
            )}
            <span>{type === 'formula' ? '數學矩陣與盤口算式說明' : '免責聲明與期望值常識'}</span>
          </div>
          <button
            onClick={onClose}
            id="close-formula-modal-btn"
            className="p-1.5 rounded-full text-neutral-400 hover:text-neutral-700 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-6 text-xs sm:text-sm leading-relaxed text-neutral-700 dark:text-neutral-300">
          {type === 'formula' ? (
            <>
              {/* Section 1: 3-Pillars Formula */}
              <div className="space-y-3">
                <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                  01 / 三柱 1800 碰 組合算式
                </h3>
                <div className="bg-black/[0.02] dark:bg-white/[0.03] p-4 rounded-xl border border-black/[0.06] dark:border-white/[0.06] font-mono text-xs text-neutral-800 dark:text-neutral-200 space-y-1">
                  <p>總注數 = 第1柱 (9顆) × 第2柱 (10顆) × 第3柱 (20顆) = 1,800 注</p>
                  <p>每期中獎注數 = n₁ × n₂ × n₃ (各柱命中顆數)</p>
                  <p>單支成本 = 1,800 注 × 63 元 = 113,400 元</p>
                  <p>期望過關率 = 55.3619% (任一柱掛蛋即槓龜)</p>
                </div>
              </div>

              {/* Section 2: Break-even Cars Formula */}
              <div className="space-y-3">
                <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                  02 / 建議追平車數計算
                </h3>
                <div className="bg-black/[0.02] dark:bg-white/[0.03] p-4 rounded-xl border border-black/[0.06] dark:border-white/[0.06] font-mono text-xs text-neutral-800 dark:text-neutral-200 space-y-2">
                  <p><strong>單顆下注車數:</strong></p>
                  <p>車數 = ⌈ (目前累積虧損 + 今日其他款成本) ÷ (中1顆獎金 - 每車單顆成本) ⌉</p>
                  <p className="text-neutral-400">例: 今彩539 單顆每車成本 2,755, 中 1 顆得 21,200, 淨利 = 18,445</p>
                </div>
              </div>

              {/* Section 3: Odds comparison */}
              <div className="space-y-3">
                <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                  03 / 單顆 vs 多顆 (k 成長因子)
                </h3>
                <p className="text-neutral-500 text-xs">
                  k = (押幾顆 × 每車成本) ÷ 中獎獎金。k 越小，連敗時追本車數成長越緩慢；k 越接近 1，追平所需資金將呈現幾何級數飆升。
                </p>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3.5 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                    <div className="font-bold text-neutral-900 dark:text-white">單顆下注 (k ≈ 0.13)</div>
                    <div className="text-neutral-500 mt-1">連敗成長係數: 1.15x</div>
                    <div className="text-neutral-400 text-[11px]">資本耐受度高，回本快</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                    <div className="font-bold text-neutral-900 dark:text-white">多顆下注 20顆 (k ≈ 0.52)</div>
                    <div className="text-neutral-500 mt-1">連敗成長係數: 2.08x</div>
                    <div className="text-neutral-400 text-[11px]">中得勤但回本慢</div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Disclaimer */}
              <div className="space-y-4">
                <div className="flex items-start gap-3 p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] text-neutral-800 dark:text-neutral-200">
                  <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5 text-neutral-500" />
                  <div className="text-xs space-y-1">
                    <p className="font-bold uppercase tracking-wide">數學常識與期望值告知</p>
                    <p>彩券開獎為獨立隨機事件，在數學理論上無法預測下一期開獎號碼。期望報酬率恆為負值，所有選號策略期望值完全相同。</p>
                  </div>
                </div>

                <div className="space-y-2 text-xs text-neutral-600 dark:text-neutral-400">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                    <span><strong>今彩539</strong> (39選5): 台灣彩券官方固定獎金，單注期望報酬率約 -44.16%。</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                    <span><strong>天天樂 (加州 Fantasy 5)</strong>: 加州官方開獎結果。</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-neutral-400 shrink-0" />
                    <span><strong>香港六合彩</strong> (49選6): 香港馬會開獎結果。</span>
                  </div>
                </div>

                <p className="text-xs text-neutral-400 italic">
                  本系統僅供統計學習與個人記帳娛樂用途，請理性娛樂、量力而為。
                </p>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-black/[0.08] dark:border-white/[0.08] flex justify-end bg-black/[0.01] dark:bg-white/[0.01]">
          <button
            type="button"
            id="close-modal-action-btn"
            onClick={onClose}
            className="px-5 py-2 text-xs uppercase tracking-wider font-semibold rounded-full bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity"
          >
            關閉視窗
          </button>
        </div>
      </div>
    </div>
  );
};
