import React, {createContext, useCallback, useContext, useEffect, useMemo, useState} from 'react';
import {api, EditionDTO} from './client';

// 下注「版」(edition):全站選一個版,紀錄下注 / 快速上傳都記到這個版。
// combineEditions = 累積損益 / 建議車數 要「本版」還是「全部版合併」(滑塊切換)。
interface EditionsCtx {
  editions: EditionDTO[];
  eid: number;              // 目前選的版
  edition: EditionDTO | null;
  setEid: (eid: number) => void;
  combineEditions: boolean; // false = 本版、true = 全部版合併
  setCombineEditions: (v: boolean) => void;
  loading: boolean;
  reload: () => void;
}

const Ctx = createContext<EditionsCtx | null>(null);

// 版的顯示順序:阿姨排最前,其餘照 eid
const FIRST_EDITION = '阿姨';
const edRank = (e: EditionDTO) => (e.name === FIRST_EDITION ? 0 : 1);

// 依版清單順序排一串版號(清單裡沒有的版排最後、照 eid)
export function sortEdIds(ids: number[], editions: EditionDTO[]): number[] {
  const pos = (id: number) => {
    const i = editions.findIndex(e => e.eid === id);
    return i < 0 ? editions.length : i;
  };
  return [...ids].sort((a, b) => pos(a) - pos(b) || a - b);
}
const STORE_KEY = 'lotto539_edition';
const COMBINE_KEY = 'lotto539_edition_combine';

export function EditionsProvider({children}: {children: React.ReactNode}) {
  const [editions, setEditions] = useState<EditionDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [eid, setEidState] = useState<number>(
    () => Number(localStorage.getItem(STORE_KEY)) || 1,
  );
  const [combineEditions, setCombineState] = useState<boolean>(
    () => localStorage.getItem(COMBINE_KEY) === '1',
  );

  const reload = useCallback(() => {
    setLoading(true);
    api
      .getEditions()
      .then(rows => {
        setEditions([...rows].sort((a, b) => edRank(a) - edRank(b) || a.eid - b.eid));
        // 選中的版被刪了就退回第一版
        setEidState(prev => (rows.some(e => e.eid === prev) ? prev : 1));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const setEid = (v: number) => {
    localStorage.setItem(STORE_KEY, String(v));
    setEidState(v);
  };
  const setCombineEditions = (v: boolean) => {
    localStorage.setItem(COMBINE_KEY, v ? '1' : '0');
    setCombineState(v);
  };

  const value = useMemo<EditionsCtx>(
    () => ({
      editions,
      eid,
      edition: editions.find(e => e.eid === eid) ?? null,
      setEid,
      combineEditions,
      setCombineEditions,
      loading,
      reload,
    }),
    [editions, eid, combineEditions, loading, reload],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useEditions(): EditionsCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useEditions 必須在 <EditionsProvider> 內使用');
  return c;
}
