import {useCallback, useEffect, useMemo, useState} from 'react';
import {api, LedgerEntryDTO, LedgerMode} from './client';
import {useAuth} from './useAuth';
import {BetRecord} from '../types';

// 各下注分頁的流水帳。
//
// **登入時**紀錄存後端(重整 / 換裝置都在),**未登入時**退回原本的前端 state
// (優雅降級,不登入照樣能試算記帳,只是關掉頁面就沒了)。
//
// index 與 cumPnl 一律由這裡依順序重算,不存進資料庫 —— 撤銷中間某一筆之後
// 編號與累積損益才不會跟流水對不起來。

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

export function useLedger(
  mode: LedgerMode,
  demoRecords: BetRecord[] = [],
  opts: {edition?: number; combine?: boolean; game?: string} = {},
) {
  const {loggedIn} = useAuth();
  const {edition, combine = false, game} = opts;
  // 未登入時用的本地流水(沿用 v2 行為,含原本的示範資料)
  const [local, setLocal] = useState<BetRecord[]>(demoRecords);
  // 登入時用的後端流水;null = 還沒載到
  const [remote, setRemote] = useState<BetRecord[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey(k => k + 1), []);

  useEffect(() => {
    if (!loggedIn) {
      setRemote(null);
      setError(null);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .ledgerList(mode)
      .then(rows => {
        if (alive) setRemote(rows.map(toRecord));
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
  }, [loggedIn, mode, reloadKey]);

  const add = useCallback(
    async (rec: NewBetRecord) => {
      if (!loggedIn) {
        setLocal(prev => [
          ...prev,
          {...rec, id: `local-${Date.now()}-${prev.length}`, index: 0, cumPnl: 0},
        ]);
        return;
      }
      setError(null);
      try {
        const entry = await api.ledgerAdd(mode, rec as unknown as Record<string, unknown>);
        setRemote(prev => [...(prev ?? []), toRecord(entry)]);
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [loggedIn, mode],
  );

  /** 撤銷最後輸入的那一筆。 */
  const undo = useCallback(async () => {
    if (!loggedIn) {
      setLocal(prev => prev.slice(0, -1));
      return;
    }
    const rows = remote ?? [];
    const last = rows[rows.length - 1];
    if (!last) return;
    setError(null);
    try {
      await api.ledgerDelete(Number(last.id));
      setRemote(prev => (prev ?? []).filter(r => r.id !== last.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [loggedIn, remote]);

  /** 改某一筆的期數並重新對獎;hitCount 有值 = 手填中獎顆數(忘記期數但記得中幾顆)。 */
  const resettle = useCallback(
    async (id: string, issue: string, hitCount?: number | null) => {
      setError(null);
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
          setError((e as Error).message);
        }
        return;
      }
      try {
        const entry = await api.ledgerResettle(Number(id), issue, hitCount);
        setRemote(prev =>
          (prev ?? []).map(r => (r.id === id ? toRecord(entry) : r)),
        );
      } catch (e) {
        setError((e as Error).message);
      }
    },
    [loggedIn, local],
  );

  /** 清空這個下法的全部紀錄。 */
  const clear = useCallback(async () => {
    if (!loggedIn) {
      setLocal([]);
      return;
    }
    setError(null);
    try {
      await api.ledgerClear(mode);
      setRemote([]);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [loggedIn, mode]);

  const records = useMemo(() => {
    const all = loggedIn ? remote ?? [] : local;
    // 依「遊戲 + 版」篩選:
    // - game:各下注分頁只看當前遊戲的流水。後端 ledgerList 只用 mode 撈,會把
    //   539 / 天天樂 / 六合彩 的同一下法混在一起;不依遊戲切分,期號選擇器就會把
    //   A 遊戲的期號套到 B 遊戲的記錄上(遊戲/期號不匹配 → 永遠對不到獎)。
    // - edition:combine=true 看全部版合併;否則只看選中的版(舊紀錄沒 edition 當第一版)。
    const filtered = all.filter(r => {
      const rec = r as BetRecord;
      const gameOk = game == null || rec.game === game;
      const edOk = combine || edition == null || (rec.edition ?? 1) === edition;
      return gameOk && edOk;
    });
    return withRunning(filtered);
  }, [loggedIn, remote, local, edition, combine, game]);

  return {records, add, undo, clear, resettle, reload, loading, error, loggedIn};
}

/** 總損益頁用:一次撈四種下法的紀錄(未登入回空陣列)。 */
export function useAllLedger() {
  const {loggedIn} = useAuth();
  const [entries, setEntries] = useState<LedgerEntryDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
  }, [loggedIn]);

  return {entries, loading, error, loggedIn};
}
