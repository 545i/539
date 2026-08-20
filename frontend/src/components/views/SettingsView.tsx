import React, { useEffect, useState } from 'react';
import { Settings, Sliders, Moon, Sun, Save, RefreshCw, Database } from 'lucide-react';
import { ThemeMode } from '../../types';
import { api, AutoupdateGameDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useAuth } from '../../api/useAuth';

interface Props {
  theme: ThemeMode;
  onToggleTheme: () => void;
}

export const SettingsView: React.FC<Props> = ({ theme, onToggleTheme }) => {
  // 盤口欄位的預設值改由後端 GameDTO 的 default_* 帶入(今彩539);
  // 下面的字面值只是後端還沒回來前的初值,與 core/games.py 相同。
  const { data: games } = useAsync(() => api.games(), []);
  const [pillarCost, setPillarCost] = useState<number>(63);
  const [pillarPrize, setPillarPrize] = useState<number>(57000);
  const [singleCarCost, setSingleCarCost] = useState<number>(2755);
  const [singleCarPrize, setSingleCarPrize] = useState<number>(21200);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (seeded || !games) return;
    const g = games.find(x => x.key === 'lotto539') ?? games[0];
    if (!g) return;
    setPillarCost(g.default_bet_cost);
    setPillarPrize(g.default_bet_prize);
    setSingleCarCost(g.default_cost_per_car);
    setSingleCarPrize(g.default_win_payout);
    setSeeded(true); // 只帶一次,之後不覆蓋使用者輸入
  }, [games, seeded]);

  // TODO(api): 設定儲存端點 —— 後端沒有寫入盤口參數的端點,維持 v2 的模擬儲存。
  const handleSave = () => {
    alert('已成功儲存盤口與偏好設定！');
  };

  // ── 開獎資料更新狀態(/settings/autoupdate)──────────────
  // stale = CSV 的最新一期比「現在應該抓得到的那一期」舊。排程每 5 分鐘檢查一次,
  // 所以剛開獎完看到 stale 是正常的;真的卡住才用下面的「立即抓取」硬抓。
  const { loggedIn } = useAuth();
  const auto = useAsync(() => api.autoupdateStatus(), []);
  const [fetched, setFetched] = useState<AutoupdateGameDTO[] | null>(null);
  const [fetching, setFetching] = useState(false);
  const [fetchMsg, setFetchMsg] = useState<string | null>(null);
  const [fetchErr, setFetchErr] = useState<string | null>(null);

  const autoGames = fetched ?? auto.data?.games ?? [];

  const handleFetchNow = async () => {
    setFetching(true);
    setFetchMsg(null);
    setFetchErr(null);
    try {
      const res = await api.fetchNow();
      setFetched(res.games);
      setFetchMsg(
        res.results
          .map(r => (r.ok ? `${r.name} 新增 ${r.added} 期` : `${r.name} 失敗:${r.error}`))
          .join('；'),
      );
    } catch (e) {
      setFetchErr((e as Error).message);
    } finally {
      setFetching(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              系統與盤口設定
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              自訂下注成本、派彩金額、外觀佈景與三柱1800碰參數
            </p>
          </div>
        </div>
      </div>

      {/* Theme Settings */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
          {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          <span>介面外觀主題 (深色 / 亮色)</span>
        </h3>

        <div className="flex items-center justify-between p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
          <div>
            <div className="font-semibold text-xs text-neutral-900 dark:text-white">
              目前模式: {theme === 'dark' ? '極致沉浸黑 (Sophisticated Dark)' : '典雅明亮白 (Editorial Light)'}
            </div>
            <div className="text-[11px] text-neutral-500 mt-0.5">高對比極簡視覺語彙，支援隨系統或手動切換</div>
          </div>
          <button
            type="button"
            onClick={onToggleTheme}
            className="px-4 py-2 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity"
          >
            切換為 {theme === 'dark' ? '亮色模式' : '深色模式'}
          </button>
        </div>
      </div>

      {/* Odds Parameters */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
          <Sliders className="w-4 h-4" />
          <span>盤口設定 — 三柱 1800 碰</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
              每注成本 (元)
            </label>
            <input
              type="number"
              value={pillarCost}
              onChange={e => setPillarCost(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
              中一注可得 (元)
            </label>
            <input
              type="number"
              value={pillarPrize}
              onChange={e => setPillarPrize(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
            />
          </div>
        </div>

        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2 pt-3 border-t border-black/[0.06] dark:border-white/[0.06]">
          <Sliders className="w-4 h-4" />
          <span>盤口設定 — 單顆下注 (今彩539)</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
              每車成本 (元)
            </label>
            <input
              type="number"
              value={singleCarCost}
              onChange={e => setSingleCarCost(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
              中獎可得 (元)
            </label>
            <input
              type="number"
              value={singleCarPrize}
              onChange={e => setSingleCarPrize(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
            />
          </div>
        </div>

        <div className="pt-3">
          <button
            type="button"
            onClick={handleSave}
            className="px-6 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity flex items-center gap-2 shadow-xs"
          >
            <Save className="w-3.5 h-3.5" />
            儲存所有設定
          </button>
        </div>
      </div>

      {/* 開獎資料更新狀態 */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
          <Database className="w-4 h-4" />
          <span>開獎資料更新狀態</span>
        </h3>

        <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
          {auto.loading && '載入中…'}
          {auto.error && <span className="text-rose-600 dark:text-rose-400">載入失敗:{auto.error}</span>}
          {auto.data && (
            <>背景排程:
              <strong className={auto.data.scheduler_running
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-rose-600 dark:text-rose-400'}>
                {auto.data.scheduler_running ? '執行中' : '未啟動'}
              </strong>
              ,每 {Math.round(auto.data.tick_seconds / 60)} 分鐘檢查一次,開獎後約 30 分鐘才抓得到。
            </>
          )}
        </div>

        <div className="space-y-2">
          {autoGames.map(g => (
            <div
              key={g.key}
              className="flex items-center justify-between gap-3 p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]"
            >
              <div>
                <div className="font-semibold text-xs text-neutral-900 dark:text-white">{g.name}</div>
                <div className="text-[11px] text-neutral-500 mt-0.5 font-mono">
                  資料已到 {g.latest ?? '—'}
                  {g.target && ` / 應到 ${g.target}`}
                </div>
                {(g.status.error || g.status.msg) && (
                  <div className={`text-[11px] mt-0.5 ${g.status.error ? 'text-rose-600 dark:text-rose-400' : 'text-neutral-500'}`}>
                    {g.status.error || g.status.msg}
                  </div>
                )}
              </div>
              <span className={`text-[10px] px-2.5 py-1 rounded-full font-semibold whitespace-nowrap ${
                g.status.running
                  ? 'bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300'
                  : g.stale
                    ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                    : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
              }`}>
                {g.status.running ? '抓取中' : g.stale ? '待更新' : '已是最新'}
              </span>
            </div>
          ))}
        </div>

        {fetchMsg && <div className="text-[11px] text-neutral-600 dark:text-neutral-300">{fetchMsg}</div>}
        {fetchErr && <div className="text-[11px] text-rose-600 dark:text-rose-400">抓取失敗:{fetchErr}</div>}
        {!loggedIn && (
          <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
            手動抓取需要登入(背景排程不受影響,仍會自動更新)。
          </div>
        )}

        <button
          type="button"
          onClick={handleFetchNow}
          disabled={!loggedIn || fetching}
          className="px-6 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity flex items-center gap-2 shadow-xs disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${fetching ? 'animate-spin' : ''}`} />
          {fetching ? '抓取中…' : '立即抓取最新開獎'}
        </button>
      </div>
    </div>
  );
};
