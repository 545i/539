import React, {useEffect, useState} from 'react';
import {Layers, Plus, Save, RotateCcw, Trash2, Pencil, PieChart} from 'lucide-react';
import {api} from '../../api/client';
import {allocatePnl, pctToBps, ShareDTO, ShareVersionDTO, sharesOn} from '../../shares';
import {AllocList, ShareBar, shareColor} from '../ShareUI';
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
  {title: '9000碰', fields: [
    ['combo9000_cost', '每碰成本'], ['combo9000_prize', '中一碰可得'],
  ]},
];

// 損益佔比(每版可多組,不分遊戲):本人初始 100%,往下分給其他人;本人 = 100 − 其他人合計,
// 總和永遠剛好 100。合計超過 100 / 佔比 ≤ 0 / 超過兩位小數 / 名字空白或重複都不給存。
// 可中途加入:每組有「生效日」,某天的損益套用生效日 ≤ 當天的最新一組;
// 「從最早起」那組 = 第一個生效日之前的所有日子(沒設 = 本人 100%)。
const othersOf = (shares: ShareDTO[]) => shares.filter(r => !r.self).map(r => ({name: r.name, pct: String(r.pct), account: r.account ?? ''}));
const sinceLabel = (since: string) => (since ? `${since.replace(/-/g, '/')} 起` : '從最早起');
const todayYmd = () => new Date().toLocaleDateString('sv-SE');   // 本機日期 YYYY-MM-DD

export const SharesEditor: React.FC<{eid: number; edName: string; loggedIn: boolean; onSaved?: () => void}> = ({eid, edName, loggedIn, onSaved}) => {
  const [versions, setVersions] = useState<ShareVersionDTO[]>([]);
  const [since, setSince] = useState('');              // 正在編輯的那組生效日
  const [newSince, setNewSince] = useState(todayYmd);  // 「新增生效日」的日期
  const [others, setOthers] = useState<{name: string; pct: string; account: string}[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [demo, setDemo] = useState('-10000');

  // 載入後預設編輯最新(生效日最晚)那組
  const applyVersions = (vs: ShareVersionDTO[], pick?: string) => {
    setVersions(vs);
    const sel = vs.find(v => v.since === pick) ?? vs[vs.length - 1];
    setSince(sel?.since ?? '');
    setOthers(othersOf(sel?.shares ?? []));
  };
  useEffect(() => {
    setMsg(null); setErr(null);
    if (!loggedIn) { applyVersions([]); return; }   // 佔比跟著登入帳號(版主)走
    api.getShares(eid).then(vs => applyVersions(vs)).catch(e => setErr((e as Error).message));
  }, [eid, loggedIn]);
  const pickVersion = (v: ShareVersionDTO) => { setSince(v.since); setOthers(othersOf(v.shares)); setMsg(null); setErr(null); };
  // 新增一組生效日:先帶入「那天原本適用」的佔比,改完再存
  const addVersion = () => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(newSince)) { setErr('請選生效日'); return; }
    const exist = versions.find(v => v.since === newSince);
    if (exist) { pickVersion(exist); return; }
    setSince(newSince);
    setOthers(othersOf(sharesOn(versions, newSince).shares));
    setMsg(null); setErr(null);
  };
  const isNew = !versions.some(v => v.since === since);

  // 驗證(與後端同規則);bps 整數算,本人 = 10000 − 其他人
  const parsed = others.map(o => ({name: o.name.trim(), pct: Number(o.pct), account: o.account.trim()}));
  const problem = (() => {
    const seen = new Set<string>();
    for (const o of parsed) {
      if (!o.name) return '分配對象名字不能空白';
      if (o.name === '本人') return '「本人」是保留名稱,不用另外加';
      if (seen.has(o.name)) return `名字重複:${o.name}`;
      seen.add(o.name);
      if (!Number.isFinite(o.pct) || o.pct <= 0) return `${o.name} 的佔比要大於 0`;
      if (Math.abs(o.pct * 100 - pctToBps(o.pct)) > 1e-6) return `${o.name} 的佔比最多到小數兩位`;
    }
    return null;
  })();
  const usedBps = parsed.reduce((a, o) => a + (Number.isFinite(o.pct) ? pctToBps(o.pct) : 0), 0);
  const selfBps = 10000 - usedBps;
  const over = selfBps < 0;
  const shares: ShareDTO[] = [
    {name: '本人', pct: Math.max(0, selfBps) / 100, self: true},
    ...parsed.map(o => ({name: o.name || '?', pct: Number.isFinite(o.pct) ? o.pct : 0, self: false})),
  ];
  const demoRows = !problem && !over ? allocatePnl(Number(demo) || 0, shares) : [];

  const setRow = (i: number, k: 'name' | 'pct' | 'account', v: string) =>
    setOthers(prev => prev.map((o, j) => (j === i ? {...o, [k]: v} : o)));
  const save = async () => {
    setBusy(true); setMsg(null); setErr(null);
    try {
      applyVersions(await api.setShares(eid, since, parsed), since);
      setMsg(`已儲存「${edName}」${sinceLabel(since)}的損益佔比。`);
      onSaved?.();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const removeVersion = async () => {
    const what = since ? `${sinceLabel(since)}這組(該段改回沿用前一組)` : '從最早起這組(改回本人 100%)';
    if (!window.confirm(`刪除「${edName}」${what}?`)) return;
    setBusy(true); setMsg(null); setErr(null);
    try {
      applyVersions(await api.deleteShareVersion(eid, since));
      setMsg('已刪除。');
      onSaved?.();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  const inputCls = 'px-3 py-2 text-[13px] rounded-lg border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white focus:outline-hidden focus:border-violet-500/50';
  const barItems = shares.map(x => ({name: x.name, pct: x.pct}));
  return (
    <div className="space-y-4 pt-3 border-t border-black/[0.06] dark:border-white/[0.06]">
      {/* 標題 + 說明(收合) */}
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <PieChart className="w-4 h-4 text-violet-500" />
          <span className="text-sm font-bold text-neutral-900 dark:text-white">損益佔比</span>
          <span className="px-2 py-0.5 rounded-md bg-violet-500/10 text-violet-600 dark:text-violet-400 text-[11px] font-bold">{edName}</span>
        </div>
        <details className="text-[11px] text-neutral-500 dark:text-neutral-400">
          <summary className="cursor-pointer select-none text-neutral-400">怎麼算?</summary>
          <div className="mt-1 space-y-1 leading-relaxed">
            <p>本人初始 100%,往下分給其他人;本人自動 = 100 − 其他人合計,總和永遠剛好 100%(不分遊戲)。</p>
            <p>成本、派彩各自依佔比分配,四捨五入後加總一定等於總額(不會差 ±1);每人淨額 = 分到派彩 − 應付成本。</p>
            <p>中途才開始分:「新增生效日」選開始那天,那天(含)以後照新佔比,之前照舊。</p>
            <p>填「連動帳號」後,對方登入可在「佔比帳單」看這個版、他有佔比那些日子要付多少、分到多少、下了什麼(看不到其他合夥人名字)。</p>
          </div>
        </details>
      </div>

      {/* 生效日 */}
      <div className="space-y-2">
        <div className="text-[11px] font-semibold text-neutral-500">生效日</div>
        <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1">
          {versions.map(v => (
            <button key={v.since || 'base'} type="button" onClick={() => pickVersion(v)}
              className={`shrink-0 px-3 py-1.5 rounded-lg text-[12px] font-semibold border transition-all ${
                since === v.since ? 'bg-black text-white dark:bg-white dark:text-black border-transparent'
                  : 'border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'}`}>
              {sinceLabel(v.since)}
              <span className="block text-[10px] font-normal opacity-70 font-mono">
                {v.shares.filter(x => x.pct > 0).map(x => `${x.name}${x.pct}%`).join(' / ')}
              </span>
            </button>
          ))}
          {isNew && (
            <span className="shrink-0 px-3 py-1.5 rounded-lg text-[12px] font-semibold bg-violet-500/15 text-violet-600 dark:text-violet-400">
              {sinceLabel(since)}
              <span className="block text-[10px] font-normal">新,未儲存</span>
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <input type="date" value={newSince} onChange={e => setNewSince(e.target.value)} className={`${inputCls} font-mono flex-1 min-w-0`} />
          <button type="button" onClick={addVersion} disabled={!loggedIn}
            className="shrink-0 px-3 rounded-lg text-[12px] font-semibold border border-violet-500/30 text-violet-600 dark:text-violet-400 hover:bg-violet-500/10 disabled:opacity-30 flex items-center gap-1">
            <Plus className="w-3.5 h-3.5" />新增生效日
          </button>
        </div>
      </div>

      {/* 分配 */}
      <div className="space-y-2">
        <div className="flex items-baseline gap-2">
          <span className="text-[11px] font-semibold text-neutral-500">分配</span>
          <span className="text-[11px] text-neutral-400">正在編輯 <strong className="text-neutral-800 dark:text-neutral-100">{sinceLabel(since)}</strong></span>
        </div>
        <ShareBar items={barItems} className="h-3" />

        {/* 本人 */}
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-violet-500/[0.07] dark:bg-violet-400/[0.08]">
          <span className={`w-2.5 h-2.5 rounded-full ${shareColor(0)}`} />
          <span className="text-[13px] font-semibold text-neutral-800 dark:text-neutral-100">本人</span>
          <span className="text-[10px] text-neutral-400">自動 = 100 − 其他人</span>
          <span className={`ml-auto font-mono text-xl font-bold ${over ? 'text-rose-500' : 'text-violet-600 dark:text-violet-400'}`}>
            {(selfBps / 100).toFixed(2)}%
          </span>
        </div>

        {/* 其他人:一人一張卡(手機兩行,不擠) */}
        {others.map((o, i) => (
          <div key={i} className="rounded-xl border border-black/[0.08] dark:border-white/[0.08] p-2.5 space-y-2">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${shareColor(i + 1)}`} />
              <input value={o.name} placeholder="名字" onChange={e => setRow(i, 'name', e.target.value)}
                className={`${inputCls} flex-1 min-w-0`} />
              <div className="relative w-28 shrink-0">
                <input type="number" inputMode="decimal" step="0.01" min="0" max="100" value={o.pct}
                  onChange={e => setRow(i, 'pct', e.target.value)}
                  className={`${inputCls} w-full pr-7 text-right font-mono font-bold`} />
                <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[12px] text-neutral-400">%</span>
              </div>
            </div>
            <div className="flex items-center gap-2 pl-4.5">
              <input value={o.account} placeholder="連動帳號(選填,對方登入用的帳號)" onChange={e => setRow(i, 'account', e.target.value)}
                autoCapitalize="none" autoCorrect="off"
                className={`${inputCls} flex-1 min-w-0 font-mono text-[12px]`} />
              <button type="button" onClick={() => setOthers(prev => prev.filter((_, j) => j !== i))} title="移除"
                className="shrink-0 w-9 h-9 flex items-center justify-center rounded-lg text-rose-500 border border-rose-500/20 hover:bg-rose-500/10">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
        <button type="button" onClick={() => setOthers(prev => [...prev, {name: '', pct: '', account: ''}])} disabled={!loggedIn}
          className="w-full py-2.5 rounded-xl text-[12px] font-semibold border border-dashed border-black/15 dark:border-white/15 text-neutral-600 dark:text-neutral-300 hover:bg-black/[0.03] dark:hover:bg-white/[0.04] disabled:opacity-30 flex items-center justify-center gap-1">
          <Plus className="w-3.5 h-3.5" />新增分配對象
        </button>
        {over && <div className="text-[12px] text-rose-500">分出去的佔比合計 {(usedBps / 100).toFixed(2)}%,超過 100%。</div>}
        {problem && <div className="text-[12px] text-rose-500">{problem}</div>}
      </div>

      {/* 試算 */}
      {demoRows.length > 0 && (
        <div className="rounded-xl bg-black/[0.02] dark:bg-white/[0.03] p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold text-neutral-500 shrink-0">試算損益</span>
            <input type="number" inputMode="numeric" value={demo} onChange={e => setDemo(e.target.value)} className={`${inputCls} flex-1 min-w-0 font-mono`} />
          </div>
          <AllocList items={demoRows.map(r => ({name: r.name, pct: r.pct, amount: r.amount}))} />
        </div>
      )}

      {msg && <div className="text-[12px] text-emerald-600 dark:text-emerald-400">{msg}</div>}
      {err && <div className="text-[12px] text-rose-500">{err}</div>}

      {/* 動作列:手機上黏在底部 */}
      <div className="sticky bottom-0 -mx-1 px-1 py-2 bg-white/95 dark:bg-[#121212]/95 backdrop-blur-sm flex items-center gap-2">
        <button type="button" onClick={save} disabled={busy || !loggedIn || over || !!problem}
          className="flex-1 py-3 rounded-xl text-[13px] font-bold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 flex items-center justify-center gap-2">
          <Save className="w-4 h-4" />{busy ? '儲存中…' : loggedIn ? `儲存(${sinceLabel(since)})` : '登入後才能改'}
        </button>
        {!isNew && (since !== '' || others.length > 0) && (
          <button type="button" onClick={removeVersion} disabled={busy || !loggedIn} title="刪除這組生效日"
            className="shrink-0 px-3 py-3 rounded-xl text-[12px] font-semibold border border-rose-500/30 text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 disabled:opacity-30 flex items-center gap-1">
            <Trash2 className="w-3.5 h-3.5" />刪除這組
          </button>
        )}
      </div>
    </div>
  );
};

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

      {!editions.find(e => e.eid === editEid)?.simulated && (
        <SharesEditor eid={editEid} loggedIn={loggedIn}
          edName={editions.find(e => e.eid === editEid)?.name ?? String(editEid)} />
      )}
    </div>
  );
};
