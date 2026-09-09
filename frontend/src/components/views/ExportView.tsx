import React, { useState } from 'react';
import { Download, FileSpreadsheet, FileJson, BarChart3 } from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../api/useAuth';
import { useGame } from '../../api/useGame';

// 匯出走後端 /export/*:流水帳(xlsx / json)要登入,開獎分析報表不用。
// 下載本身由 client.ts 的 download() 處理(fetch → blob → <a download>),
// 因為要帶 Authorization,單純開連結是帶不了標頭的。

export const ExportView: React.FC = () => {
  const { loggedIn } = useAuth();
  // 匯出哪個遊戲的報表跟著頁首的全域切換器走
  const { gameKey, game } = useGame();
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (key: string, fn: () => Promise<string>) => {
    setBusy(key);
    setMsg(null);
    setError(null);
    try {
      setMsg(`已下載 ${await fn()}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const btn = 'w-full py-2.5 px-4 rounded-full text-xs uppercase tracking-wider font-semibold transition-opacity disabled:opacity-40 disabled:cursor-not-allowed';
  const btnSolid = `${btn} bg-black text-white dark:bg-white dark:text-black hover:opacity-90`;
  const btnGhost = `${btn} border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-800 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5`;

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
              匯出個人下注流水帳(Excel / JSON)與開獎資料統計報表(Excel)
            </p>
          </div>
        </div>
      </div>

      {!loggedIn && (
        <div className="p-4 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
          流水帳匯出需要登入(紀錄存在自己的帳號下);開獎分析報表不用登入即可下載。
        </div>
      )}
      {msg && (
        <div className="p-4 rounded-2xl bg-white dark:bg-[#121212] border border-emerald-500/30 text-xs text-emerald-600 dark:text-emerald-400">
          {msg}
        </div>
      )}
      {error && (
        <div className="p-4 rounded-2xl bg-white dark:bg-[#121212] border border-rose-500/30 text-xs text-rose-600 dark:text-rose-400">
          匯出失敗:{error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-bold text-sm text-neutral-900 dark:text-white uppercase tracking-wide">匯出 Excel 流水帳</div>
              <div className="text-xs text-neutral-500">單顆、多顆、三柱、連碰各一張工作表,含成本/回收/累積損益</div>
            </div>
          </div>
          <button
            onClick={() => run('xlsx', api.exportLedgerXlsx)}
            disabled={!loggedIn || busy !== null}
            className={btnSolid}
          >
            {busy === 'xlsx' ? '產生中…' : '下載 Excel 流水帳'}
          </button>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
              <FileJson className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-bold text-sm text-neutral-900 dark:text-white uppercase tracking-wide">匯出 JSON 完整備份</div>
              <div className="text-xs text-neutral-500">後端存的原始紀錄(含編號、下法、記錄時間),可留存備查</div>
            </div>
          </div>
          <button
            onClick={() => run('json', api.exportLedgerJson)}
            disabled={!loggedIn || busy !== null}
            className={btnGhost}
          >
            {busy === 'json' ? '產生中…' : '下載 JSON 備份檔'}
          </button>
        </div>

        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4 md:col-span-2">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-bold text-sm text-neutral-900 dark:text-white uppercase tracking-wide">匯出開獎分析報表 (Excel)</div>
              <div className="text-xs text-neutral-500">免責聲明、全部開獎資料、號碼頻率(含 Excel 原生長條圖)、凱莉投報分析</div>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="sm:w-64 px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white">
              匯出對象:<strong>{game?.name ?? '載入中…'}</strong>
              <div className="text-[10px] text-neutral-500 mt-0.5">要換遊戲請用頁首的切換器</div>
            </div>
            <button
              onClick={() => run('report', () => api.exportReport(gameKey))}
              disabled={busy !== null}
              className={`${btnSolid} sm:flex-1`}
            >
              {busy === 'report' ? '產生中…' : '下載 Excel 分析報表'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
