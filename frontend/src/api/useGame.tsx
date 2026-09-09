import React, {createContext, useContext, useEffect, useMemo, useState} from 'react';
import {api, GameDTO, GameKey} from './client';

// 全域遊戲切換:一處選、全站跟著換。各頁面用 useGame() 取 gameKey / game,
// 不要再自己 hardcode 'lotto539' 或各記一份遊戲狀態。
interface GameCtx {
  games: GameDTO[];
  gameKey: GameKey;
  game: GameDTO | null;
  setGameKey: (k: GameKey) => void;
  loading: boolean;
}

const Ctx = createContext<GameCtx | null>(null);
const STORE_KEY = 'lotto539_game';

export function GameProvider({children}: {children: React.ReactNode}) {
  const [games, setGames] = useState<GameDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [gameKey, setGameKeyState] = useState<GameKey>(
    () => (localStorage.getItem(STORE_KEY) as GameKey) || 'lotto539',
  );

  useEffect(() => {
    api
      .games()
      .then(setGames)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const setGameKey = (k: GameKey) => {
    localStorage.setItem(STORE_KEY, k);
    setGameKeyState(k);
  };

  const value = useMemo<GameCtx>(
    () => ({
      games,
      gameKey,
      game: games.find(g => g.key === gameKey) ?? null,
      setGameKey,
      loading,
    }),
    [games, gameKey, loading],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useGame(): GameCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useGame 必須在 <GameProvider> 內使用');
  return c;
}
