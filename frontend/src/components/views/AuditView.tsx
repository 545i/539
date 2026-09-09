import React, { useState } from 'react';
import { History, Undo2, RotateCcw, Ban } from 'lucide-react';
import { api, AuditAction, AuditLogDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useAuth } from '../../api/useAuth';

// 操作歷史:下注 / 撤銷 / 上傳 / 清空都留一筆,而且每一筆都可以「作廢」。
//
// 作廢 = **反轉那個動作**,不是刪掉歷史:作廢「撤銷」就是把那一局救回來,
// 作廢「上傳」就是把那一批收掉。作廢自己也會變成歷史上的一筆(可以看到誰
// 在什麼時候救了什麼),所以清單只會往前長。
//
// 能不能按作廢由後端的 reversible 決定,前端不重寫一份規則。

const ACTION_ICONS: Record<AuditAction, React.ReactNode> = {
  bet_add: <Undo2 className="w-4 h-4 rotate-180" />,
  bet_delete: <Undo2 className="w-4 h-4" />,
  bet_clear: <Ban className="w-4 h-4" />,
  quick_import: <History className="w-4 h-4" />,
  void: <RotateCcw className="w-4 h-4" />,
};

/** 作廢後的一句話回饋:reverted 是實際動到的紀錄筆數。 */
const revertText = (n: number) =>
  n === 0
    ? '已作廢(目標紀錄早已不在,流水沒有變動)'
    : `已作廢,反轉了 ${n} 筆記帳紀錄`;

const Row: React.FC<{
  row: AuditLogDTO;
  busy: boolean;
  onVoid: () => void;
}> = ({ row, busy, onVoid }) => (
  <div
    className={`p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border flex items-start justify-between gap-4 ${
      row.voided
        ? 'border-black/[0.08] dark:border-white/[0.08] opacity-60'
        : 'border-black/[0.08] dark:border-white/[0.08]'
    }`}
  >
    <div className="flex items-start gap-3.5 min-w-0">
      <div
        className={`shrink-0 mt-0.5 p-2 rounded-full ${
          row.action === 'void'
            ? 'bg-black/5 dark:bg-white/10 text-neutral-500'
            : 'bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white'
        }`}
      >
        {ACTION_ICONS[row.action]}
      </div>
      <div className="min-w-0">
        <div className="font-bold text-sm text-neutral-900 dark:text-white flex items-center gap-2 flex-wrap">
          <span>{row.action_label}</span>
          {row.voided && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400 font-semibold tracking-wider">
              已作廢
            </span>
          )}
          {row.action === 'void' && row.void_of !== null && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-neutral-500 font-mono">
              #{row.void_of}
            </span>
          )}
        </div>
        <div
          className={`text-xs mt-1 break-words ${
            row.voided
              ? 'text-neutral-400 dark:text-neutral-500 line-through'
              : 'text-neutral-600 dark:text-neutral-300'
          }`}
        >
          {row.summary || '—'}
        </div>
        <div className="text-[10px] font-mono text-neutral-400 dark:text-neutral-500 mt-1.5">
          {row.created} · #{row.id}
        </div>
      </div>
    </div>

    {row.reversible && (
      <button
        type="button"
        id={`audit-void-${row.id}`}
        onClick={onVoid}
        disabled={busy}
        className="shrink-0 px-3 py-1.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors disabled:opacity-40"
      >
        {busy ? '處理中…' : '作廢'}
      </button>
    )}
  </div>
);

interface Props {
  /** 反轉成功後通知外面重抓記帳流水(App 的 ledgerVersion)。 */
  onReverted?: () => void;
}

export const AuditView: React.FC<Props> = ({ onReverted }) => {
  const { loggedIn } = useAuth();
  const { data, loading, error, reload } = useAsync<AuditLogDTO[]>(
    () => (loggedIn ? api.auditList() : Promise.resolve([])),
    [loggedIn],
  );
  // 正在作廢的那一筆(避免連點兩次送出兩個作廢)
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [voidError, setVoidError] = useState<string | null>(null);

  const rows = data ?? [];

  const handleVoid = async (row: AuditLogDTO) => {
    setBusyId(row.id);
    setNotice(null);
    setVoidError(null);
    try {
      const res = await api.auditVoid(row.id);
      setNotice(revertText(res.reverted));
      reload();
      // 記帳分頁的流水已經被改掉了,不重抓的話畫面會停在舊資料
      if (onReverted) onReverted();
    } catch (e) {
      setVoidError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              操作歷史
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              下注、撤銷、快速上傳、清空都會留痕。按「作廢」會<strong>反轉</strong>那個動作
              —— 作廢一次撤銷就等於把那一筆記帳救回來。
            </p>
          </div>
        </div>
      </div>

      {notice && (
        <div className="p-4 rounded-2xl bg-white dark:bg-[#121212] border border-emerald-500/30 text-xs text-emerald-600 dark:text-emerald-400">
          {notice}
        </div>
      )}
      {voidError && (
        <div className="p-4 rounded-2xl bg-white dark:bg-[#121212] border border-rose-500/30 text-xs text-rose-600 dark:text-rose-400">
          作廢失敗:{voidError}
        </div>
      )}

      {!loggedIn && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
          操作歷史綁定帳號,請先登入後檢視。
        </div>
      )}
      {loggedIn && loading && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500">
          載入中…
        </div>
      )}
      {loggedIn && error && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-rose-500/30 text-xs text-rose-600 dark:text-rose-400">
          載入失敗:{error}
        </div>
      )}
      {loggedIn && !loading && !error && rows.length === 0 && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
          還沒有任何操作。到「二合買牌」記幾筆帳或用「快速上傳」,這裡就會有紀錄。
        </div>
      )}

      <div className="space-y-3">
        {rows.map(row => (
          <Row
            key={row.id}
            row={row}
            busy={busyId === row.id}
            onVoid={() => handleVoid(row)}
          />
        ))}
      </div>
    </div>
  );
};
