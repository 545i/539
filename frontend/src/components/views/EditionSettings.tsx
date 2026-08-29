import React, {useEffect, useState} from 'react';
import {Layers, Plus, Save, RotateCcw, Trash2, Pencil} from 'lucide-react';
import {api} from '../../api/client';
import {useAuth} from '../../api/useAuth';
import {useGame} from '../../api/useGame';
import {useEditions} from '../../api/useEditions';

// 下注「版」設定:新增 / 改名 / 刪除版,以及「選中的版 × 目前遊戲」的整套盤口。
// 盤口分三組:二合每車、1800碰每注、連碰各星數。第一版沒自訂時吃出廠預設。

const FIELD_GROUPS: {title: string; fields: [string, string][]}[] = [
  {title: '二合(1組/2組)', fields: [['pair_bet_cost', '每注基礎成本'], ['win_payout', '中一顆可得']]},
  {title: '三柱1800碰', fields: [['bet_cost', '每注成本'], ['bet_prize', '中一注可得']]},
  {title: '連碰 星數', fields: [
    ['combo_cost2', '二星每碰成本'], ['combo_prize2', '二星中一碰'],
    ['combo_cost3', '三星每碰成本'], ['combo_prize3', '三星中一碰'],
    ['combo_cost4', '四星每碰成本'], ['combo_prize4', '四星中一碰'],
  ]},
];

export const EditionSettings: React.FC = () => {
  const {loggedIn} = useAuth();
  const {game, gameKey} = useGame();
  const {editions, reload} = useEditions();
  const gameName = game?.short_name ?? gameKey;
  // 二合一車的注數 = num_max − 1(拖 1 膽配其餘);每車成本 = 每注基礎 × 注數
  const notesPerCar = Math.max(1, (game?.num_max ?? 39) - 1);

  const [editEid, setEditEid] = useState<number>(1);
  const [draft, setDraft] = useState<Record<string, number>>({});
  const [custom, setCustom] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // 載入「選中的版 × 目前遊戲」盤口
  useEffect(() => {
    setMsg(null); setErr(null);
    api.getEditionOdds(editEid, gameKey).then(res => {
      const d: Record<string, number> = {};
      const c: Record<string, boolean> = {};
      Object.entries(res.fields).forEach(([k, v]) => { d[k] = v.value; c[k] = v.custom; });
      setDraft(d); setCustom(c);
    }).catch(e => setErr((e as Error).message));
  }, [editEid, gameKey]);

  const setField = (k: string, v: number) => setDraft(prev => ({...prev, [k]: v}));

  const save = async () => {
    setBusy(true); setMsg(null); setErr(null);
    try {
      await api.setEditionOdds(editEid, gameKey, draft);
      reload();
      setMsg(`已儲存「${editions.find(e => e.eid === editEid)?.name ?? editEid}」的 ${gameName} 盤口。`);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const resetOdds = async () => {
    setBusy(true); setMsg(null); setErr(null);
    try {
      const res = await api.resetEditionOdds(editEid, gameKey);
      const d: Record<string, number> = {}; Object.entries(res).forEach(([k, v]) => { d[k] = v as number; });
      setDraft(d); setCustom({});
      setMsg('已還原成預設盤口。');
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const addEd = async () => {
    const name = window.prompt('新版名稱?', `第${editions.length + 1}版`);
    if (!name) return;
    const e = await api.addEdition(name); reload(); setEditEid(e.eid);
  };
  const renameEd = async () => {
    const cur = editions.find(e => e.eid === editEid);
    const name = window.prompt('改版名稱', cur?.name ?? '');
    if (!name) return;
    await api.renameEdition(editEid, name); reload();
  };
  const deleteEd = async () => {
    if (editEid === 1) { setErr('第一版不能刪除。'); return; }
    if (!window.confirm('刪除這個版?(它底下的下注紀錄不會被刪,但會失去對應盤口)')) return;
    await api.deleteEdition(editEid); reload(); setEditEid(1);
  };

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
      <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
        <Layers className="w-4 h-4" />
        <span>下注版本與各版盤口({gameName})</span>
      </h3>
      <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
        每個「版」是一套組頭盤口,<strong className="text-neutral-700 dark:text-neutral-200">全站共用</strong>、
        <strong className="text-neutral-700 dark:text-neutral-200">依版×遊戲各自設定</strong>。
        下面編輯的是「選中的版 × {gameName}」;換遊戲請用頁首的遊戲切換器。
      </div>

      {/* 版選擇 + 管理 */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1 flex-wrap">
          {editions.map(e => (
            <button key={e.eid} type="button" onClick={() => setEditEid(e.eid)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                editEid === e.eid ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                  : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'}`}>
              {e.name}
            </button>
          ))}
        </div>
        <button type="button" onClick={addEd} disabled={!loggedIn}
          className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 flex items-center gap-1">
          <Plus className="w-3 h-3" />新增版
        </button>
        <button type="button" onClick={renameEd} disabled={!loggedIn}
          className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 flex items-center gap-1">
          <Pencil className="w-3 h-3" />改名
        </button>
        <button type="button" onClick={deleteEd} disabled={!loggedIn || editEid === 1}
          className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border border-rose-500/30 text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 disabled:opacity-30 flex items-center gap-1">
          <Trash2 className="w-3 h-3" />刪除
        </button>
      </div>

      {/* 盤口欄位 */}
      {FIELD_GROUPS.map(grp => (
        <div key={grp.title} className="space-y-2">
          <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">{grp.title}</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {grp.fields.map(([k, label]) => (
              <div key={k}>
                <label className="block text-[10px] text-neutral-500 mb-1">
                  {label}{custom[k] && <span className="text-indigo-500"> ·自訂</span>}
                </label>
                <input type="number" value={draft[k] ?? 0}
                  onChange={e => setField(k, Number(e.target.value) || 0)}
                  className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden" />
                {k === 'pair_bet_cost' && (
                  <div className="mt-1 text-[10px] text-neutral-400 font-mono">
                    每車 = {(draft.pair_bet_cost ?? 0)} × {notesPerCar} = {Math.round((draft.pair_bet_cost ?? 0) * notesPerCar).toLocaleString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      {msg && <div className="text-[11px] text-emerald-600 dark:text-emerald-400">{msg}</div>}
      {err && <div className="text-[11px] text-rose-500">{err}</div>}

      <div className="flex items-center gap-2 pt-1">
        <button type="button" onClick={save} disabled={busy || !loggedIn}
          className="px-6 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 flex items-center gap-2 shadow-xs">
          <Save className="w-3.5 h-3.5" />{busy ? '儲存中…' : loggedIn ? '儲存這版盤口' : '登入後才能改'}
        </button>
        <button type="button" onClick={resetOdds} disabled={busy || !loggedIn}
          className="px-4 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 flex items-center gap-2">
          <RotateCcw className="w-3.5 h-3.5" />還原預設
        </button>
      </div>
    </div>
  );
};
