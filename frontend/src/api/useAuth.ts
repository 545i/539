import {useCallback, useSyncExternalStore} from 'react';
import {api, clearToken, getToken, getUsername, setToken, subscribeAuth} from './client';

// 全站共用的登入狀態。token 存 localStorage,client.ts 在 token 變動時通知
// 訂閱者,所以側欄登入完各分頁的流水帳會自己去後端撈,不必 reload。
export function useAuth() {
  const token = useSyncExternalStore(subscribeAuth, getToken, () => null);
  const username = useSyncExternalStore(subscribeAuth, getUsername, () => null);

  const login = useCallback(async (name: string, password: string) => {
    const res = await api.login(name, password);
    setToken(res.token, res.username);
    return res.username;
  }, []);

  // 註冊只建帳號,不會順便登入(沿用後端行為:註冊完請切到登入)
  const register = useCallback(
    (name: string, password: string, inviteCode: string) =>
      api.register(name, password, inviteCode),
    [],
  );

  const logout = useCallback(() => clearToken(), []);

  return {token, username, loggedIn: !!token, login, register, logout};
}
