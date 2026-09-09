import React from 'react';
import {AlertTriangle} from 'lucide-react';
import {ConflictBet} from '../api/client';
import {MODE_LABEL} from './uploadHistory';

const money = (n: number) => `$${Math.round(n).toLocaleString()}`;

// 記帳去重的覆蓋確認彈窗:列出「將被覆蓋的既有紀錄」,確認才覆蓋。
// 四個下注分頁共用(見 useLedger 的 pendingConflict / confirmOverwrite)。
export const OverwriteConfirm: React.FC<{
  conflicts: ConflictBet[];
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({conflicts, busy, onConfirm, onCancel}) => (
  <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
    <div className="w-full max-w-md bg-white dark:bg-[#161616] rounded-2xl border border-black/10 dark:border-white/10 shadow-2xl p-5 space-y-3 text-neutral-800 dark:text-neutral-200">
      <div className="flex items-start gap-2 text-sm font-bold text-amber-700 dark:text-amber-400">
        <AlertTriangle className="w-5 h-5 shrink-0" />
        <span>這一組下注已經有紀錄了</span>
      </div>
      <p className="text-[12px] text-neutral-600 dark:text-neutral-300 leading-relaxed">
        同一天、同一版、同一組玩法只能一筆。按下確認會<strong>覆蓋</strong>以下既有紀錄
        (舊的會作廢、可從操作歷史還原):
      </p>
      <div className="rounded-lg border border-black/10 dark:border-white/10 divide-y divide-black/[0.05] dark:divide-white/[0.05] max-h-48 overflow-y-auto">
        {conflicts.map(c => (
          <div key={c.id} className="px-3 py-1.5 text-[11px] flex items-center justify-between gap-2">
            <span className="font-sans text-neutral-600 dark:text-neutral-300 shrink-0">
              {MODE_LABEL[c.mode]} {c.playType}
            </span>
            <span className="font-mono text-neutral-500 truncate">
              {c.selectedBalls.map(b => String(b).padStart(2, '0')).join(' ') || '—'}
            </span>
            <span className="font-mono font-bold text-neutral-800 dark:text-neutral-200 shrink-0">{money(c.cost)}</span>
            <span className={`text-[10px] shrink-0 ${
              c.payout > 0 ? 'text-emerald-600 dark:text-emerald-400'
                : c.result === '待開獎' ? 'text-neutral-400'
                  : 'text-rose-600 dark:text-rose-400'}`}>{c.result}</span>
          </div>
        ))}
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          disabled={busy}
          onClick={onCancel}
          className="py-2 px-4 rounded-xl text-xs font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-40 transition-colors"
        >
          取消
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onConfirm}
          className="py-2 px-4 rounded-xl text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-40 transition-colors"
        >
          {busy ? '覆蓋中…' : '確認覆蓋'}
        </button>
      </div>
    </div>
  </div>
);
