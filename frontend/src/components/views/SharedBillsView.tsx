import React, { useEffect, useMemo, useState } from 'react';
import { PieChart, RefreshCw } from 'lucide-react';
import { api, SharedBoardDTO } from '../../api/client';
import { useAuth } from '../../api/useAuth';
import { useGame } from '../../api/useGame';
import { money } from '../uploadHistory';
import { allocateSegments, daySegments } from '../../shares';
import {
  BillCards, buildDayBill, dayMd, GameBreak, groupWeeks, pnlCls, signedMoney, weekdayOf, WeekGroup,
} from './WeeklyLedger';

// 佔比帳單(被連動者唯讀):版主設定損益佔比時把我「連動帳號」,我就能在這裡看那個版、
// 我有佔比那些日子的帳單 —— 每週該版盈虧、我分到多少(與版主看到的同一套守恆分配),
// 展開看每天的快捷帳單卡片(可複製)。其他合夥人名字已由後端遮成「其他N」。

const sinceLabel = (since: string) => (since ? `${since.replace(/-/g, '/')} 起` : '從最早起');

const BoardView: React.FC<{ b: SharedBoardDTO }> = ({ b }) => {
  const { games } = useGame();
  const gameShort = (g: string) => {
    const f = games.find(x => x.key === g || x.name === g || x.short_name === g);
    return f?.short_name ?? f?.name ?? g ?? '其他';
  };
  const weeks = useMemo(
    () => groupWeeks(b.entries, gameShort, () => b.edition_name),
    [b, games],
  );
  const [openWeeks, setOpenWeeks] = useState<Set<string>>(() => new Set(weeks[0] ? [weeks[0].monday] : []));
  const [openDays, setOpenDays] = useState<Set<string>>(new Set());
  const toggle = (set: Set<string>, k: string, setter: (s: Set<string>) => void) => {
    const n = new Set(set); n.has(k) ? n.delete(k) : n.add(k); setter(n);
  };
  const ownerLabel = `${b.owner}(版主)`;
  const nameOf = (n: string) => (n === '本人' ? ownerLabel : n);

  // 每週:依生效日切段 → 守恆分配 → 取「我」那一份
  const split = (w: WeekGroup) => {
    const days = w.pnlByEd.get(b.eid) ?? new Map<string, number>();
    const segs = daySegments(days.entries(), b.versions);
    const rows = allocateSegments(segs);
    const meName = segs.flatMap(sg => sg.shares).find(x => x.me)?.name;
    return { segs, rows, mine: rows.find(r => r.name === meName)?.amount ?? 0 };
  };
  const splits = weeks.map(split);
  const myTotal = splits.reduce((a, x) => a + x.mine, 0);
  const latest = b.versions[b.versions.length - 1];
  const myPct = latest?.shares.find(x => x.me)?.pct;

  return (
    <div className="space-y-3">
      <div className="p-4 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-1.5">
        <div className="text-sm font-bold text-neutral-900 dark:text-white">
          {b.owner} · <span className="text-violet-600 dark:text-violet-400">{b.edition_name}</span>
        </div>
        <div className="text-[11px] text-neutral-500 flex flex-wrap gap-x-4 gap-y-1">
          <span>目前我的佔比:<strong className="text-neutral-800 dark:text-neutral-100 font-mono">{myPct !== undefined ? `${myPct}%` : '已停止'}</strong>
            {latest && <span className="ml-1 text-neutral-400">({sinceLabel(latest.since)})</span>}</span>
          <span>累計我分到:<strong className={`font-mono ${pnlCls(myTotal)}`}>{signedMoney(myTotal)}</strong></span>
        </div>
        <div className="text-[10px] text-neutral-400 space-y-0.5">
          {b.versions.filter(v => v.shares.some(x => x.me)).map(v => (
            <div key={v.since || 'base'}>
              {sinceLabel(v.since)}:{v.shares.filter(x => x.pct > 0).map(x => `${nameOf(x.name)} ${x.pct}%`).join(' / ')}
            </div>
          ))}
        </div>
      </div>

      {weeks.length === 0 && (
        <div className="text-[11px] text-neutral-400 p-3 rounded-xl border border-black/[0.06] dark:border-white/[0.06]">
          目前還沒有帳單(只顯示你有佔比那些日子的下注)。
        </div>
      )}

      {weeks.map((w, wi) => {
        const wOpen = openWeeks.has(w.monday);
        const sp = splits[wi];
        return (
          <div key={w.monday || 'nodate'} className="rounded-xl border border-black/15 dark:border-white/15 bg-white dark:bg-[#121212] overflow-hidden shadow-sm">
            <button type="button" onClick={() => toggle(openWeeks, w.monday, setOpenWeeks)}
              className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-black/[0.02] dark:hover:bg-white/[0.03]">
              <span className="text-[11px] w-3 shrink-0 text-center text-neutral-400">{wOpen ? '▾' : '▸'}</span>
              <div className="min-w-0 flex-1 text-[12px] font-semibold text-neutral-800 dark:text-neutral-100 font-mono">
                {w.monday.replace(/-/g, '/')} ~ {w.sunday.slice(5).replace('-', '/')}
                <span className="ml-1.5 font-sans font-normal text-neutral-400 text-[10px]">{w.count} 筆</span>
                {w.pendingCount > 0 && <span className="ml-1.5 text-amber-600 dark:text-amber-400 text-[9px] font-sans">{w.pendingCount} 待開</span>}
              </div>
              <div className="flex items-center gap-3 text-[10px] font-mono shrink-0">
                <span className="text-neutral-500">該版盈虧 <span className={`font-bold ${pnlCls(w.pnl)}`}>{signedMoney(w.pnl)}</span></span>
                <span className="text-neutral-500">我分到 <span className={`font-bold ${pnlCls(sp.mine)}`}>{signedMoney(sp.mine)}</span></span>
              </div>
            </button>

            {wOpen && (
              <div className="px-3 py-2 pl-8 border-t border-black/[0.06] dark:border-white/[0.06] bg-black/[0.015] dark:bg-white/[0.02] space-y-1 text-[10px] font-mono">
                <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                  {sp.rows.map(r => (
                    <span key={r.name} className="text-neutral-500">
                      {nameOf(r.name)} <span className={`font-bold ${pnlCls(r.amount)}`}>{signedMoney(r.amount)}</span>
                    </span>
                  ))}
                </div>
                {sp.segs.map(sg => (
                  <div key={sg.since || 'base'} className="text-[9px] text-neutral-400 font-sans">
                    <span className="font-mono">{sg.from.slice(5).replace('-', '/')}{sg.to !== sg.from ? `~${sg.to.slice(5).replace('-', '/')}` : ''}</span>
                    {' '}<span className={`font-mono ${pnlCls(sg.pnl)}`}>{signedMoney(sg.pnl)}</span>
                    {' '}照 {sg.shares.filter(x => x.pct > 0).map(x => `${nameOf(x.name)}${x.pct}%`).join(' / ')}
                  </div>
                ))}
                {w.byGame.size > 1 && <GameBreak byGame={w.byGame} />}
              </div>
            )}

            {wOpen && (
              <div className="border-t border-black/[0.06] dark:border-white/[0.06]">
                {w.days.map(day => {
                  const dOpen = openDays.has(day.ymd);
                  return (
                    <div key={day.ymd} className="border-b border-black/[0.04] dark:border-white/[0.04] last:border-b-0">
                      <button type="button" onClick={() => toggle(openDays, day.ymd, setOpenDays)}
                        className="w-full flex items-center gap-2 px-3 py-2 pl-6 text-left hover:bg-black/[0.02] dark:hover:bg-white/[0.03]">
                        <span className="text-[10px] w-3 shrink-0 text-center text-neutral-400">{dOpen ? '▾' : '▸'}</span>
                        <div className="min-w-0 flex-1 text-[11px] font-mono text-neutral-700 dark:text-neutral-300">
                          {day.ymd.slice(5).replace('-', '/')}({weekdayOf(day.ymd)})
                          <span className="ml-1.5 font-sans text-neutral-400 text-[10px]">{day.count} 筆</span>
                        </div>
                        <div className="flex items-center gap-3 text-[10px] font-mono shrink-0">
                          <span className="text-neutral-500">{money(day.cost)}</span>
                          <span className="text-emerald-600 dark:text-emerald-400">{money(day.payout)}</span>
                          <span className={`font-bold ${pnlCls(day.pnl)}`}>{signedMoney(day.pnl)}</span>
                        </div>
                      </button>
                      {dOpen && (
                        <div className="px-3 pb-3 pl-9">
                          <BillCards bill={buildDayBill(day)} md={dayMd(day.ymd)} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export const SharedBillsView: React.FC = () => {
  const { loggedIn, username } = useAuth();
  const [boards, setBoards] = useState<SharedBoardDTO[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);

  // 依「目前登入的帳號」抓:同一個瀏覽器直接換帳號登入(loggedIn 一直是 true)也要重抓,
  // 否則會一直顯示上一個帳號的結果。
  useEffect(() => {
    setErr(null);
    if (!loggedIn) { setBoards([]); return; }
    setBoards(null);
    let alive = true;
    api.sharedBoards()
      .then(r => { if (alive) { setBoards(r); setSel(0); } })
      .catch(e => { if (alive) setErr((e as Error).message); });
    return () => { alive = false; };
  }, [loggedIn, username, reloadKey]);

  return (
    <div className="space-y-4 animate-in fade-in duration-200">
      <div className="text-[11px] text-neutral-500 dark:text-neutral-400 flex items-start gap-1.5">
        <PieChart className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>版主在「損益佔比」把你連動進去後,這裡會出現那個版、你有佔比那些日子的帳單(唯讀,隨時可看)。
          點週展開看分配,點某天看快捷帳單卡片。</span>
        {loggedIn && (
          <button type="button" onClick={() => setReloadKey(k => k + 1)}
            className="ml-auto shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 flex items-center gap-1">
            <RefreshCw className="w-3 h-3" />重新整理
          </button>
        )}
      </div>
      {loggedIn && username && <div className="text-[10px] text-neutral-400">目前登入:<span className="font-mono">{username}</span></div>}
      {!loggedIn && <div className="text-[11px] text-neutral-400">請先登入。</div>}
      {err && <div className="text-[11px] text-rose-500">{err}</div>}
      {loggedIn && boards === null && !err && <div className="text-[11px] text-neutral-400">讀取中…</div>}
      {loggedIn && boards?.length === 0 && (
        <div className="text-[11px] text-neutral-400 p-3 rounded-xl border border-black/[0.06] dark:border-white/[0.06]">
          目前沒有版主把你的帳號連動進損益佔比。
        </div>
      )}
      {boards && boards.length > 1 && (
        <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1 flex-wrap">
          {boards.map((b, i) => (
            <button key={`${b.owner}/${b.eid}`} type="button" onClick={() => setSel(i)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold ${sel === i ? 'bg-black text-white dark:bg-white dark:text-black' : 'text-neutral-600 dark:text-neutral-400'}`}>
              {b.owner} · {b.edition_name}
            </button>
          ))}
        </div>
      )}
      {boards && boards[sel] && <BoardView key={`${boards[sel].owner}/${boards[sel].eid}`} b={boards[sel]} />}
    </div>
  );
};
