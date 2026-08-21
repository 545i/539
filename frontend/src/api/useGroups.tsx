import React, {createContext, useCallback, useContext, useEffect, useMemo, useState} from 'react';
import {api, GroupDTO} from './client';

// 二合下注「組」設定(全站共用):固定顆數 + 是否啟用。一處抓、全站共用,
// 設定頁存檔後呼叫 reload() 就能讓分頁列 / 快速上傳 / 各組分頁一起更新。
interface GroupsCtx {
  groups: GroupDTO[];
  enabled: GroupDTO[]; // 只有啟用中的組(分頁列用)
  loading: boolean;
  reload: () => void;
}

const Ctx = createContext<GroupsCtx | null>(null);

export function GroupsProvider({children}: {children: React.ReactNode}) {
  const [groups, setGroups] = useState<GroupDTO[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    api
      .getGroups()
      .then(setGroups)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const value = useMemo<GroupsCtx>(
    () => ({groups, enabled: groups.filter(g => g.enabled), loading, reload}),
    [groups, loading, reload],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useGroups(): GroupsCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useGroups 必須在 <GroupsProvider> 內使用');
  return c;
}
