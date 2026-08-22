import React, { useEffect, useState } from 'react';
import { Settings, Sliders, Moon, Sun, Save, RefreshCw, Database, Coins, RotateCcw, Layers } from 'lucide-react';
import { ThemeMode } from '../../types';
import { api, AutoupdateGameDTO, GroupDTO, StarCostInput } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useAuth } from '../../api/useAuth';
import { useGame } from '../../api/useGame';
import { useGroups } from '../../api/useGroups';

interface Props {
  theme: ThemeMode;
  onToggleTheme: () => void;
}

export const SettingsView: React.FC<Props> = ({ theme, onToggleTheme }) => {
  // 盤口欄位的預設值由後端 GameDTO 的 default_* 帶入,遊戲來自頁首的全域切換器;
  // 下面的字面值只是後端還沒回來前的初值,與 core/games.py 相同。
  const { gameKey, game } = useGame();
  const gameName = game?.short_name ?? '本遊戲';
  const [pillarCost, setPillarCost] = useState<number>(63);
  const [pillarPrize, setPillarPrize] = useState<number>(57000);
  const [singleCarCost, setSingleCarCost] = useState<number>(2755);
  const [singleCarPrize, setSingleCarPrize] = useState<number>(21200);
  // 記「這組欄位是照哪個遊戲填的」:同一個遊戲只帶一次(不蓋掉使用者輸入),
  // 換了遊戲就重帶那個遊戲的預設盤口。
  const [seededFor, setSeededFor] = useState<string | null>(null);

  useEffect(() => {
    if (!game || seededFor === game.key) return;
    setPillarCost(game.default_bet_cost);
    setPillarPrize(game.default_bet_prize);
    setSingleCarCost(game.default_cost_per_car);
    setSingleCarPrize(game.default_win_payout);
    setSeededFor(game.key);
  }, [game, seededFor]);

  // TODO(api): 設定儲存端點 —— 後端沒有寫入盤口參數的端點,維持 v2 的模擬儲存。
  const handleSave = () => {
    alert('已成功儲存盤口與偏好設定！');
  };

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

  // ── 連碰星數盤口(/star-cost)─────────────────────────────
  // 這一區跟上面那組不一樣:上面是前端自己的欄位,這裡改的是**後端全域**的
  // 成本與派彩 —— 存下去之後全站的連碰試算、快速上傳算出來的成本都跟著變,
  // 所以要登入才給改,旁邊也標出原本的出廠預設讓人有得對照。
  const starCost = useAsync(() => api.getStarCosts(), []);
  const [starDraft, setStarDraft] = useState<StarCostInput>({});
  const [starSaving, setStarSaving] = useState(false);
  const [starMsg, setStarMsg] = useState<string | null>(null);
  const [starErr, setStarErr] = useState<string | null>(null);

  // 後端回來就把欄位填成目前生效的值(使用者還沒動過才填,免得蓋掉輸入)
  useEffect(() => {
    if (!starCost.data) return;
    setStarDraft(prev =>
      Object.keys(prev).length
        ? prev
        : Object.fromEntries(
            Object.entries(starCost.data!.costs).map(([k, v]) => [
              k,
              { cost: v.cost, prize: v.prize },
            ]),
          ),
    );
  }, [starCost.data]);

  // 兩個欄位共用一個 setter;prev 還沒有這個星數時先補上後端目前的值,
  // 免得只送出改過的那一欄、另一欄變成 undefined 被後端擋下來。
  const setStarField = (stars: string, field: 'cost' | 'prize', value: number) =>
    setStarDraft(prev => {
      const base = prev[stars] ?? {
        cost: starCost.data?.costs[stars]?.cost ?? 0,
        prize: starCost.data?.costs[stars]?.prize ?? 0,
      };
      return { ...prev, [stars]: { ...base, [field]: value } };
    });

  const handleSaveStarCost = async () => {
    setStarSaving(true);
    setStarMsg(null);
    setStarErr(null);
    try {
      const res = await api.setStarCosts(starDraft);
      setStarDraft(
        Object.fromEntries(
          Object.entries(res.costs).map(([k, v]) => [k, { cost: v.cost, prize: v.prize }]),
        ),
      );
      starCost.reload(); // 重抓一次:讓「已自訂」標記與最後修改時間跟著更新
      setStarMsg('已儲存,全站的連碰成本與派彩立即生效。');
    } catch (e) {
      setStarErr((e as Error).message);
    } finally {
      setStarSaving(false);
    }
  };

  const handleResetStarCost = async () => {
    setStarSaving(true);
    setStarMsg(null);
    setStarErr(null);
    try {
      const res = await api.resetStarCosts();
      setStarDraft(
        Object.fromEntries(
          Object.entries(res.costs).map(([k, v]) => [k, { cost: v.cost, prize: v.prize }]),
        ),
      );
      starCost.reload();
      setStarMsg('已還原成程式內建的預設盤口。');
    } catch (e) {
      setStarErr((e as Error).message);
    } finally {
      setStarSaving(false);
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
              目前設定 {gameName} 的下注成本、派彩金額、三柱1800碰參數與外觀佈景
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

        {game && !game.supports_pillar && (
          <div className="text-[11px] text-amber-600 dark:text-amber-400">
            {gameName}沒有三柱玩法,下面這組參數對它不會生效(換回今彩539 / 天天樂才有用)。
          </div>
        )}

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
          <span>盤口設定 — 二合每車成本 (1組/2組共用・{gameName})</span>
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

      {/* 連碰星數成本設定(全域,存在後端) */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
          <Coins className="w-4 h-4" />
          <span>連碰星數成本設定</span>
        </h3>

        <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
          這一組是<strong className="text-neutral-700 dark:text-neutral-200">全站共用</strong>的盤口,不是個人偏好:
          改完之後所有人的連碰 / 星碰試算、快速上傳算出來的成本都用新的數字。
        </div>

        {starCost.loading && (
          <div className="text-[11px] text-neutral-500">載入中…</div>
        )}
        {starCost.error && (
          <div className="text-[11px] text-rose-600 dark:text-rose-400">載入失敗:{starCost.error}</div>
        )}

        <div className="space-y-3">
          {starCost.data?.stars.map(s => {
            const key = String(s);
            const row = starCost.data!.costs[key];
            const def = starCost.data!.defaults[key];
            const draft = starDraft[key] ?? { cost: row?.cost ?? 0, prize: row?.prize ?? 0 };
            return (
              <div
                key={key}
                className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-xs text-neutral-900 dark:text-white">
                    {starCost.data!.star_names[key]}
                  </div>
                  <span className={`text-[10px] px-2.5 py-1 rounded-full font-semibold whitespace-nowrap ${
                    row?.custom
                      ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                      : 'bg-black/5 dark:bg-white/10 text-neutral-500 dark:text-neutral-400'
                  }`}>
                    {row?.custom ? '已自訂' : '預設值'}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
                      每碰成本 (元)
                    </label>
                    <input
                      type="number"
                      value={draft.cost}
                      disabled={!loggedIn || starSaving}
                      onChange={e => setStarField(key, 'cost', Number(e.target.value) || 0)}
                      className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-white dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden disabled:opacity-50"
                    />
                    <div className="text-[10px] text-neutral-400 mt-1 font-mono">
                      預設 {def?.cost.toLocaleString()}
                    </div>
                  </div>

                  <div>
                    <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
                      中一碰派彩 (元)
                    </label>
                    <input
                      type="number"
                      value={draft.prize}
                      disabled={!loggedIn || starSaving}
                      onChange={e => setStarField(key, 'prize', Number(e.target.value) || 0)}
                      className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-white dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden disabled:opacity-50"
                    />
                    <div className="text-[10px] text-neutral-400 mt-1 font-mono">
                      預設 {def?.prize.toLocaleString()}
                      {draft.cost > 0 && ` / 約 1 賠 ${(draft.prize / draft.cost).toFixed(1)}`}
                    </div>
                  </div>
                </div>

                {row?.custom && row.updated && (
                  <div className="text-[10px] text-neutral-400">
                    最後修改 {row.updated}
                    {row.updated_by && ` — ${row.updated_by}`}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {starMsg && <div className="text-[11px] text-emerald-600 dark:text-emerald-400">{starMsg}</div>}
        {starErr && <div className="text-[11px] text-rose-600 dark:text-rose-400">儲存失敗:{starErr}</div>}
        {!loggedIn && (
          <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
            修改全站盤口需要登入(未登入仍看得到目前生效的數字)。
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleSaveStarCost}
            disabled={!loggedIn || starSaving || !starCost.data}
            className="px-6 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity flex items-center gap-2 shadow-xs disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Save className="w-3.5 h-3.5" />
            {starSaving ? '儲存中…' : '儲存星數盤口'}
          </button>

          <button
            type="button"
            onClick={handleResetStarCost}
            disabled={!loggedIn || starSaving || !starCost.data}
            className="px-4 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/[0.03] dark:hover:bg-white/[0.05] transition-colors flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            還原預設
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
