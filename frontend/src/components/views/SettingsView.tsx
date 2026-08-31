import React, { useEffect, useState } from 'react';
import { Settings, Moon, Sun, Save, RefreshCw, Database, Layers } from 'lucide-react';
import { ThemeMode } from '../../types';
import { api, AutoupdateGameDTO, GroupDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useAuth } from '../../api/useAuth';
import { useGame } from '../../api/useGame';
import { useGroups } from '../../api/useGroups';
import { EditionSettings } from './EditionSettings';
import { CycleSettings } from './CycleSettings';

interface Props {
  theme: ThemeMode;
  onToggleTheme: () => void;
}

export const SettingsView: React.FC<Props> = ({ theme, onToggleTheme }) => {
  // 盤口一律走「各版盤口」(EditionSettings);這裡只留遊戲/gameName 供其他區塊用。
  const { gameKey, game } = useGame();
  const gameName = game?.short_name ?? '本遊戲';

  // ── 下注組設定(/groups,全站共用)───────────────────────
  // 固定顆數 + 是否啟用;存下去之後分頁列 / 快速上傳 / 各組分頁一起更新。
  const { groups, reload: reloadGroups } = useGroups();
  const [groupDraft, setGroupDraft] = useState<GroupDTO[]>([]);
  const [groupSaving, setGroupSaving] = useState(false);
  const [groupMsg, setGroupMsg] = useState<string | null>(null);
  const [groupErr, setGroupErr] = useState<string | null>(null);
  useEffect(() => {
    if (groups.length) setGroupDraft(groups);
  }, [groups]);
  const setGroupField = (gid: number, patch: Partial<GroupDTO>) =>
    setGroupDraft(prev => prev.map(g => (g.gid === gid ? {...g, ...patch} : g)));
  const handleSaveGroups = async () => {
    setGroupSaving(true);
    setGroupMsg(null);
    setGroupErr(null);
    try {
      await api.setGroups(
        groupDraft.map(g => ({gid: g.gid, ball_count: g.ball_count, enabled: g.enabled})));
      reloadGroups();
      setGroupMsg('已儲存下注組設定,分頁與快速上傳已更新。');
    } catch (e) {
      setGroupErr((e as Error).message);
    } finally {
      setGroupSaving(false);
    }
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
      const res = await api.fetchNow(gameKey);
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
              盤口一律在下方「各版盤口」設定;此頁還有下注組、外觀主題與開獎資料狀態
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

      {/* 下注組設定(全站共用,存在後端) */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
          <Layers className="w-4 h-4" />
          <span>下注組設定(1組 / 2組)</span>
        </h3>
        <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
          每組可設定<strong className="text-neutral-700 dark:text-neutral-200">預設建議顆數</strong>(下注時可自由增減,無下注紀錄時當建議值)與是否
          <strong className="text-neutral-700 dark:text-neutral-200">啟用</strong>。停用的組不會出現在下注分頁,
          快速上傳歸到該組的下注行也會被擋掉。這是<strong className="text-neutral-700 dark:text-neutral-200">全站共用</strong>設定。
        </div>

        <div className="space-y-3">
          {groupDraft.map(g => (
            <div key={g.gid} className="flex flex-wrap items-end gap-4 p-3 rounded-xl border border-black/[0.06] dark:border-white/[0.06] bg-black/[0.02] dark:bg-white/[0.03]">
              <div className="font-display font-bold text-sm text-neutral-900 dark:text-white min-w-[3rem]">
                {g.name}
              </div>
              <div>
                <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                  預設建議顆數
                </label>
                <input
                  type="number"
                  min={1}
                  value={g.ball_count}
                  onChange={e => setGroupField(g.gid, {ball_count: Math.max(1, Number(e.target.value) || 1)})}
                  className="w-24 px-3 py-2 text-sm rounded-xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
                />
              </div>
              <label className="flex items-center gap-2 pb-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={g.enabled}
                  onChange={e => setGroupField(g.gid, {enabled: e.target.checked})}
                  className="w-4 h-4 accent-black dark:accent-white"
                />
                <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-300">
                  {g.enabled ? '啟用中' : '已停用'}
                </span>
              </label>
            </div>
          ))}
        </div>

        {groupMsg && <div className="text-[11px] text-emerald-600 dark:text-emerald-400">{groupMsg}</div>}
        {groupErr && <div className="text-[11px] text-rose-500">{groupErr}</div>}

        <div className="pt-1">
          <button
            type="button"
            onClick={handleSaveGroups}
            disabled={groupSaving || !loggedIn}
            className="px-6 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 transition-opacity flex items-center gap-2 shadow-xs"
          >
            <Save className="w-3.5 h-3.5" />
            {groupSaving ? '儲存中…' : loggedIn ? '儲存下注組設定' : '登入後才能改'}
          </button>
        </div>
      </div>

      {/* 下注版本與各版盤口(全站唯一的盤口設定入口) */}
      <EditionSettings />

      {/* 週期性紀錄(開/結算記帳週期) */}
      <CycleSettings />

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
              className={`flex items-center justify-between gap-3 p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border ${
                g.key === gameKey
                  ? 'border-black/30 dark:border-white/30'
                  : 'border-black/[0.06] dark:border-white/[0.06]'
              }`}
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
          {fetching ? '抓取中…' : `立即抓取 ${gameName} 最新開獎`}
        </button>
      </div>
    </div>
  );
};
