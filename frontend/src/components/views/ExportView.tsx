import React from 'react';
import { Download, FileSpreadsheet, FileJson } from 'lucide-react';

export const ExportView: React.FC = () => {
  // TODO(api): 匯出端點 —— 後端沒有 export 端點,這裡維持 v2 的模擬行為。
  // 端點補上後改成下載回應(CSV/JSON blob),而不是 alert。
  const handleExport = (format: string) => {
    alert(`已模擬匯出 ${format} 報表！`);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <Download className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              資料匯出與備份中心
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              支援 CSV、Excel、JSON 格式匯出全歷史注單與累積損益帳本
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-bold text-sm text-neutral-900 dark:text-white uppercase tracking-wide">匯出 CSV / Excel 流水帳</div>
              <div className="text-xs text-neutral-500">包含單顆、多顆、三柱、連碰所有下注與開獎明細</div>
            </div>
          </div>
          <button
            onClick={() => handleExport('CSV')}
            className="w-full py-2.5 px-4 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity"
          >
            下載 CSV 報表
          </button>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
              <FileJson className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-bold text-sm text-neutral-900 dark:text-white uppercase tracking-wide">匯出 JSON 完整設定與備份</div>
              <div className="text-xs text-neutral-500">包含盤口賠率參數、號碼球柱別自訂與損益池歷史</div>
            </div>
          </div>
          <button
            onClick={() => handleExport('JSON')}
            className="w-full py-2.5 px-4 rounded-full text-xs uppercase tracking-wider font-semibold border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-800 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
          >
            下載 JSON 備份檔
          </button>
        </div>
      </div>
    </div>
  );
};
