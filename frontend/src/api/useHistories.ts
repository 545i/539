import {useMemo} from 'react';
import {api, HistoryDTO} from './client';
import {useAsync} from './useAsync';
import {useGame} from './useGame';

// 抓「每一款遊戲」的開獎歷史,回一個以遊戲**名稱**(BetRecord.game 用的顯示名,
// 例如 '今彩539' / '天天樂(加州 Fantasy 5)')為 key 的 map。
//
// 為什麼要這個:核對表格混合顯示各遊戲的流水,每一列的期號選擇器必須用「那一列
// 記錄自己的遊戲」的期別,才不會把 A 遊戲的期號套到 B 遊戲的記錄(遊戲/期號不
// 匹配 → 永遠對不到獎)。各分頁原本只抓「當前全域遊戲」一款的期別,不夠用。
export function useHistoriesByGame(limit = 30): Record<string, HistoryDTO> {
  const {games} = useGame();
  const key = games.map(g => g.key).join(',');
  const req = useAsync(async () => {
    const pairs = await Promise.all(
      games.map(g => api.history(g.key, limit).then(h => [g.name, h] as const)),
    );
    return Object.fromEntries(pairs) as Record<string, HistoryDTO>;
    // key 由 games 推導,games 載入後 key 變動就重抓
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, limit]);
  return useMemo(() => req.data ?? {}, [req.data]);
}
