import {createContext, createElement, useCallback, useContext, useEffect, useMemo, useState} from 'react';
import type {Dispatch, ReactNode, SetStateAction} from 'react';
import {api, ConflictBet, LedgerEntryDTO, LedgerMode} from './client';
import {useAuth} from './useAuth';
import {BetRecord} from '../types';

// 記帳去重:偵測到同槽衝突時,把「要記的那筆」與「將被覆蓋的既有紀錄」暫存,
// 讓分頁跳出覆蓋確認;使用者按確認 → 帶 overwrite 重送。
export type PendingConflict = {rec: NewBetRecord; conflicts: ConflictBet[]};

// 各下注分頁的流水帳。
//
// **登入時**紀錄存後端(重整 / 換裝置都在),**未登入時**退回原本的前端 state
// (優雅降級,不登入照樣能試算記帳,只是關掉頁面就沒了)。
//
// index 與 cumPnl 一律由這裡依順序重算,不存進資料庫 —— 撤銷中間某一筆之後
// 編號與累積損益才不會跟流水對不起來。
//
// 全站只抓一份 ledger:LedgerProvider 登入時一次撈回全部下法的原始紀錄(entries),
// useAllLedger 直接讀它;useLedger(mode) 從同一份依 mode 切出自己那段,mutation
// 也回寫這份共用 cache —— 各分頁 / 每週總帳 / 總損益看到的是同一份、即時同步,
// 不再各撈各的、也不必靠整段 remount 才會刷新。

// 記一筆時只給「這局發生了什麼」;編號與累積損益是推導出來的,不用自己算。
export type NewBetRecord = Omit<BetRecord, 'id' | 'index' | 'cumPnl'>;

/** 依流水順序補上編號與累積損益。 */
function withRunning(rows: BetRecord[]): BetRecord[] {
  let running = 0;
  return rows.map((r, i) => {
    running += r.pnl;
    return {...r, index: i + 1, cumPnl: running};
  });
}

/** 後端紀錄 → BetRecord;id 用資料庫給的(撤銷要靠它)。 */
function toRecord(entry: LedgerEntryDTO): BetRecord {
  return {
    ...(entry.record as unknown as BetRecord),
    id: String(entry.id),
    index: 0,
    cumPnl: 0,
  };
}

// ── 全站唯一的 ledger 資料源 ─────────────────────────────────────────────
interface LedgerCtxValue {
  entries: LedgerEntryDTO[];                                   // 全部下法的原始紀錄
  setEntries: Dispatch<SetStateAction<LedgerEntryDTO[]>>;
  loading: boolean;
  error: string | null;
  loggedIn: boolean;
  reload: () => void;
}
const LedgerCtx = createContext<LedgerCtxValue | null>(null);

/** 包在 App 外層:登入時一次撈回全部 ledger,供 useAllLedger / useLedger 共用同一份。 */
export function LedgerProvider({children}: {children: ReactNode}) {
  const {loggedIn} = useAuth();
  const [entries, setEntries] = useState<LedgerEntryDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey(k => k + 1), []);

  useEffect(() => {
    if (!loggedIn) {
      setEntries([]);
      setError(null);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .ledgerList()
      .then(rows => {
        if (alive) setEntries(rows);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [loggedIn, reloadKey]);

  const value = useMemo<LedgerCtxValue>(
    () => ({entries, setEntries, loading, error, loggedIn, reload}),
    [entries, loading, error, loggedIn, reload],
  );
  return createElement(LedgerCtx.Provider, {value}, children);
}

function useLedgerCtx(): LedgerCtxValue {
  const ctx = useContext(LedgerCtx);
  if (!ctx) throw new Error('useLedger / useAllLedger 必須包在 <LedgerProvider> 內');
  return ctx;
}

export function useLedger(
  mode: LedgerMode,
  demoRecords: BetRecord[] = [],
  opts: {edition?: number; combine?: boolean} = {},
) {
  const ctx = useLedgerCtx();
  const {loggedIn} = ctx;
  const {edition, combine = false} = opts;
  // 未登入時用的本地流水(沿用 v2 行為,含原本的示範資料)
  const [local, setLocal] = useState<BetRecord[]>(demoRecords);
  // mutation(新增/撤銷/改期…)的錯誤;初次載入的錯誤看 ctx.error
  const [mutError, setMutError] = useState<string | null>(null);

  // 登入時:從共用 cache 依 mode 切出這個下法的紀錄(server 寫入順序)
  const remote = useMemo(
    () => (loggedIn ? ctx.entries.filter(e => e.mode === mode).map(toRecord) : null),
    [loggedIn, ctx.entries, mode],
  );

  // 同槽衝突暫存(null = 無);分頁讀它決定要不要跳覆蓋確認
  const [pendingConflict, setPendingConflict] = useState<PendingConflict | null>(null);

  const add = useCallback(
    async (rec: NewBetRecord, overwrite = false) => {
      if (!loggedIn) {
        // 未登入的本地流水不做去重(只留在這個瀏覽器分頁)
        setLocal(prev => [
          ...prev,
          {...rec, id: `local-${Date.now()}-${prev.length}`, index: 0, cumPnl: 0},
        ]);
        return;
      }
      setMutError(null);
      try {
        const res = await api.ledgerAdd(
          mode, rec as unknown as Record<string, unknown>, overwrite);
        if (res.status === 'conflict') {
          setPendingConflict({rec, conflicts: res.conflicts});   // 跳確認,先不寫入
          return;
        }
        ctx.setEntries(prev => [...prev, res]);                   // 回寫共用 cache
        setPendingConflict(null);
      } catch (e) {
        setMutError((e as Error).message);
      }
    },
    [loggedIn, mode, ctx],
  );

  /** 覆蓋確認:把暫存那筆帶 overwrite 重送(刪同槽舊紀錄 + 寫新的)。 */
  const confirmOverwrite = useCallback(async () => {
    if (!pendingConflict) return;
    await add(pendingConflict.rec, true);
    // 覆蓋刪掉了舊 ledger 紀錄 → 重讀一次,列表才不會留著已被刪的那筆
    ctx.reload();
  }, [pendingConflict, add, ctx]);

  const cancelOverwrite = useCallback(() => setPendingConflict(null), []);

  /** 撤銷最後輸入的那一筆。 */
  const undo = useCallback(async () => {
    if (!loggedIn) {
      setLocal(prev => prev.slice(0, -1));
      return;
    }
    const rows = ctx.entries.filter(e => e.mode === mode);
    const last = rows[rows.length - 1];
    if (!last) return;
    setMutError(null);
    try {
      await api.ledgerDelete(Number(last.id));
      ctx.setEntries(prev => prev.filter(e => e.id !== last.id));
    } catch (e) {
      setMutError((e as Error).message);
    }
  }, [loggedIn, mode, ctx]);

  /** 撤銷指定的那一筆(核對列表每列各自撤銷用)。 */
  const deleteById = useCallback(
    async (id: string | number) => {
      if (!loggedIn) {
        setLocal(prev => prev.filter(r => String(r.id) !== String(id)));
        return;
      }
      setMutError(null);
      try {
        await api.ledgerDelete(Number(id));
        ctx.setEntries(prev => prev.filter(e => String(e.id) !== String(id)));
      } catch (e) {
        setMutError((e as Error).message);
      }
    },
    [loggedIn, ctx],
  );

  /** 改某一筆的期數並重新對獎;hitCount 有值 = 手填中獎顆數(忘記期數但記得中幾顆)。 */
  const resettle = useCallback(
    async (id: string, issue: string, hitCount?: number | null) => {
      setMutError(null);
      if (!loggedIn) {
        // 未登入:用 preview 端點算好,回填本地暫存(不寫 DB)
        const cur = local.find(r => r.id === id);
        if (!cur) return;
        try {
          const settled = await api.ledgerSettlePreview(
            cur as unknown as Record<string, unknown>, issue, hitCount,
          );
          setLocal(prev =>
            prev.map(r =>
              r.id === id
                ? {...(settled as unknown as BetRecord), id, index: 0, cumPnl: 0}
                : r,
            ),
          );
        } catch (e) {
          setMutError((e as Error).message);
        }
        return;
      }
      try {
        const entry = await api.ledgerResettle(Number(id), issue, hitCount);
        ctx.setEntries(prev =>
          prev.map(e => (String(e.id) === String(id) ? entry : e)),
        );
      } catch (e) {
        setMutError((e as Error).message);
      }
    },
    [loggedIn, local, ctx],
  );

  /** 清空這個下法的全部紀錄。 */
  const clear = useCallback(async () => {
    if (!loggedIn) {
      setLocal([]);
      return;
    }
    setMutError(null);
    try {
      await api.ledgerClear(mode);
      ctx.setEntries(prev => prev.filter(e => e.mode !== mode));
    } catch (e) {
      setMutError((e as Error).message);
    }
  }, [loggedIn, mode, ctx]);

  const records = useMemo(() => {
    const all = loggedIn ? remote ?? [] : local;
    // 依版篩選:combine=true 看全部版合併;否則只看選中的版(舊紀錄沒 edition 當第一版)。
    // 刻意不依「遊戲」篩選 —— 核對表格要混合顯示所有遊戲的流水;跨遊戲對不到期號的
    // 問題改由「每列期號選擇器認自己記錄的遊戲」解決(見各下注分頁的 IssuePicker)。
    const filtered =
      combine || edition == null
        ? all
        : all.filter(r => ((r as BetRecord).edition ?? 1) === edition);
    // 依開獎日期舊→新排(重新上傳時寫入順序≠日期順序);同日期保持原寫入順序。
    // 排序後才算累積損益,列表順序與累積累加方向才一致。
    const sorted = filtered
      .map((r, i) => [r, i] as const)
      .sort((a, b) =>
        String(a[0].date ?? '').localeCompare(String(b[0].date ?? '')) || a[1] - b[1])
      .map(([r]) => r);
    return withRunning(sorted);
  }, [loggedIn, remote, local, edition, combine]);

  return {records, add, undo, deleteById, clear, resettle, reload: ctx.reload,
    loading: ctx.loading, error: mutError ?? ctx.error,
    loggedIn, pendingConflict, confirmOverwrite, cancelOverwrite};
}

/** 一次拿全部下法的紀錄(每週總帳 / 總損益頁用);與各分頁共用同一份 cache。 */
export function useAllLedger() {
  const {entries, loading, error, loggedIn, reload} = useLedgerCtx();
  return {entries, loading, error, loggedIn, reload};
}
