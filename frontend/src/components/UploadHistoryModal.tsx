import React, { useEffect, useState } from 'react';
import { X, History, Trash2, CornerDownLeft } from 'lucide-react';
import {
  UploadHistoryEntry, MODE_LABEL, loadHistory, saveHistory, fmtTime, money,
} from './uploadHistory';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onRefill?: (text: string) => void; // 「填回快速上傳」:把某批文本帶回上傳文字框
}

// 快速上傳歷史(獨立彈窗):查看每批上傳的原始文本、下注明細/成本、總下注成本。
// 資料存在 localStorage(見 uploadHistory.ts),重開瀏覽器仍在。
export const UploadHistoryModal: React.FC<Props> = ({ isOpen, onClose, onRefill }) => {
  const [history, setHistory] = useState<UploadHistoryEntry[]>([]);

  // 每次開啟重讀一次(可能剛在快速上傳新增了一批)
  useEffect(() => {
    if (isOpen) setHistory(loadHistory());
  }, [isOpen]);

  if (!isOpen) return null;

  const historyTotal = history.reduce((s, h) => s + h.totalCost, 0);
  const clearHistory = () => { setHistory([]); saveHistory([]); };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-2xl max-h-[90vh] bg-white dark:bg-[#121212] border border-black/10 dark:border-white/10 rounded-2xl shadow-2xl flex flex-col text-neutral-800 dark:text-neutral-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.08] dark:border-white/[0.08] shrink-0">
          <div className="flex items-center gap-2 font-display font-bold text-base text-neutral-900 dark:text-white uppercase tracking-wide">
            <History className="w-4 h-4 text-neutral-500" />
            <span>快速上傳歷史</span>
            {history.length > 0 && (
              <span className="font-mono text-xs font-normal text-neutral-400">
                {history.length} 批・累計 {money(historyTotal)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {history.length > 0 && (
              <button
                type="button"
                onClick={clearHistory}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-semibold text-neutral-500 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <Trash2 className="w-3 h-3" />
                清除歷史
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-full text-neutral-400 hover:text-neutral-700 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-3 overflow-y-auto">
          {history.length === 0 && (
            <div className="text-[11px] text-neutral-400 dark:text-neutral-500 leading-relaxed p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03]">
              目前沒有上傳紀錄。到「快速上傳」貼下注文字、按<strong>「確認上傳」</strong>後,
              這裡會保留該批的<strong>原始文本</strong>、每筆<strong>下注明細與成本</strong>,
              以及<strong>總下注成本</strong>(存在本機瀏覽器,重開仍在)。
            </div>
          )}

          {history.map(h => (
            <div
              key={h.ts}
              className="rounded-xl border border-black/[0.08] dark:border-white/[0.08] bg-black/[0.02] dark:bg-white/[0.03] overflow-hidden"
            >
              <div className="flex items-center justify-between px-3 py-2 border-b border-black/[0.06] dark:border-white/[0.06]">
                <div className="text-[11px] font-semibold text-neutral-700 dark:text-neutral-300">
                  {h.gameName}・{h.editionName}
                  {h.issue ? `・第 ${h.issue} 期` : ''}
                  <span className="ml-1.5 font-normal text-neutral-400">{h.count} 筆</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-neutral-400 font-mono">{fmtTime(h.ts)}</span>
                  {onRefill && (
                    <button
                      type="button"
                      onClick={() => onRefill(h.text)}
                      title="把這批文本帶回快速上傳文字框"
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold text-neutral-500 hover:text-black dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                    >
                      <CornerDownLeft className="w-3 h-3" />
                      填回
                    </button>
                  )}
                </div>
              </div>

              {/* 原始文本 */}
              {h.text && (
                <pre className="px-3 py-2 text-[10px] font-mono whitespace-pre-wrap break-all text-neutral-500 dark:text-neutral-400 border-b border-black/[0.06] dark:border-white/[0.06] max-h-28 overflow-y-auto">
                  {h.text}
                </pre>
              )}

              {/* 下注明細 + 成本 */}
              <table className="w-full text-[11px]">
                <tbody className="font-mono">
                  {h.items.map((it, i) => (
                    <React.Fragment key={i}>
                      <tr className="border-t border-black/[0.05] dark:border-white/[0.05] first:border-t-0">
                        <td className="px-3 pt-1.5 pb-0 align-top">
                          <span className="px-1.5 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-[10px] mr-1.5 font-sans">
                            {MODE_LABEL[it.mode]}
                          </span>
                          <span className="font-sans text-neutral-600 dark:text-neutral-400">{it.playType}</span>
                        </td>
                        <td className="px-3 pt-1.5 pb-0 align-top text-neutral-700 dark:text-neutral-300">
                          {it.balls.length > 0
                            ? it.balls.map(n => String(n).padStart(2, '0')).join(' ')
                            : '—'}
                        </td>
                        <td className="px-3 pt-1.5 pb-0 align-top text-right whitespace-nowrap font-bold text-neutral-900 dark:text-white">
                          {money(it.cost)}
                        </td>
                      </tr>
                      {it.costExpr && (
                        <tr>
                          <td colSpan={3} className="px-3 pt-0 pb-1.5 text-[10px] text-neutral-400 dark:text-neutral-500">
                            {it.costExpr}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.05]">
                    <td className="px-3 py-1.5 font-sans font-semibold text-neutral-600 dark:text-neutral-300" colSpan={2}>
                      總下注成本
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono font-bold text-neutral-900 dark:text-white">
                      {money(h.totalCost)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
