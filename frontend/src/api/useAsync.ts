import {useCallback, useEffect, useState} from 'react';

// 極簡資料抓取 hook:給各頁面元件用。deps 變動就重抓。
// 用法:const {data, loading, error, reload} = useAsync(() => api.missing(game), [game]);
export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[],
): {data: T | null; loading: boolean; error: string | null; reload: () => void} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick(t => t + 1), []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const memoFn = useCallback(fn, deps);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    memoFn()
      .then(d => {
        if (alive) setData(d);
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
  }, [memoFn, tick]);

  return {data, loading, error, reload};
}
