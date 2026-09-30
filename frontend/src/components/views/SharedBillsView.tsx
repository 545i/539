import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, PieChart, RefreshCw } from 'lucide-react';
import { api, SharedBoardDTO } from '../../api/client';
import { useAuth } from '../../api/useAuth';
import { useGame } from '../../api/useGame';
import { money } from '../uploadHistory';
import { splitCostPayout } from '../../shares';
import { AllocList, ShareBar, StatTile, fmtSigned, pnlTone } from '../ShareUI';
import { BillCards, buildDayBill, dayMd, groupWeeks, weekdayOf, BetRow, DayGroup, WeekGroup } from './WeeklyLedger';

// 佔比帳單(被連動者唯讀):版主設定損益佔比時把我「連動帳號」,我就能在這裡看那個版、
// 我有佔比那些日子的帳單。重點三件事一眼看清楚:
// 版面刻意扁平:不用卡片框 / 底色,只用留白與細分隔線。
//   ① 下注了什麼(每天逐筆:遊戲 / 下法 / 號碼 / 支數 / 成本 / 開獎結果 / 派彩)
//   ② 我可以分到多少(派彩 × 我的佔比)
//   ③ 我需要支付多少(成本 × 我的佔比);結算 = 分到 − 支付 → 「你需支付 / 你可收」
// 成本、派彩各自守恆分配(與版主週期帳同一套),其他合夥人名字由後端遮成「其他N」。

const sinceLabel = (since: string) => (since ? `${since.replace(/-/g, '/')} 起` : '從最早起');
const md = (ymd: string) => ymd.slice(5).replace('-', '/');

// 結算一句話:淨額 > 0 你可收、< 0 你需支付
const Settle: React.FC<{ net: number; size?: 'lg' | 'sm' }> = ({ net, size = 'lg' }) => (
  <div className={`font-bold ${size === 'lg' ? 'text-xl' : 'text-sm'} ${pnlTone(net)}`}>
    {net < 0 ? '你需支付 ' : net > 0 ? '你可收 ' : '不用收付 '}
    {net !== 0 && <span className="font-mono">${Math.abs(net).toLocaleString()}</span>}
  </div>
);

// 一筆下注(唯讀):下了什麼 + 成本 + 結果
const BetLine: React.FC<{ r: BetRow }> = ({ r }) => (
  <div className="py-2 space-y-1">
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-[12px] font-bold text-sky-600 dark:text-sky-400">{r.gameShort}</span>
      <span className="text-[12px] font-semibold text-neutral-800 dark:text-neutral-100">{r.modeLabel}</span>
      {r.playType && <span className="text-[11px] text-neutral-500">{r.playType}</span>}
      <span className="text-[11px] text-neutral-500 font-mono">{r.units}{r.unitLabel}</span>
      <span className={`ml-auto text-[11px] ${
        r.pending ? 'text-amber-600 dark:text-amber-400'
          : r.payout > 0 ? 'text-emerald-600 dark:text-emerald-400 font-semibold'
            : 'text-neutral-400'}`}>{r.result || '待開獎'}</span>
    </div>
    {r.balls.length > 0 && (
      <div className="flex flex-wrap gap-x-2 gap-y-0.5">
        {r.balls.map((n, i) => {
          const hit = r.drawBalls.includes(n);
          return (
            <span key={`${n}-${i}`} className={`text-[12px] font-mono font-semibold ${
              hit ? 'text-emerald-600 dark:text-emerald-400 underline underline-offset-2' : 'text-neutral-800 dark:text-neutral-100'}`}>
              {String(n).padStart(2, '0')}
            </span>
          );
        })}
      </div>
    )}
    <div className="flex justify-between text-[11px] font-mono">
      <span className="text-neutral-500">成本 <span className="text-neutral-800 dark:text-neutral-100 font-semibold">{money(r.cost)}</span></span>
      <span className="text-neutral-500">派彩 <span className={r.payout > 0 ? 'text-emerald-600 dark:text-emerald-400 font-bold' : 'text-neutral-400'}>{money(r.payout)}</span></span>
    </div>
  </div>
);

const DayCard: React.FC<{ day: DayGroup }> = ({ day }) => {
  const [open, setOpen] = useState(false);
  const [bill, setBill] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(o => !o)} className="w-full flex items-center gap-2 py-2.5 text-left">
        {open ? <ChevronDown className="w-3.5 h-3.5 text-neutral-400" /> : <ChevronRight className="w-3.5 h-3.5 text-neutral-400" />}
        <span className="text-[13px] font-semibold font-mono text-neutral-800 dark:text-neutral-100">{md(day.ymd)}({weekdayOf(day.ymd)})</span>
        <span className="text-[10px] text-neutral-400">{day.count} 筆{day.pendingCount > 0 ? ` · ${day.pendingCount} 待開` : ''}</span>
        <span className={`ml-auto font-mono text-[13px] font-bold ${pnlTone(day.pnl)}`}>{fmtSigned(day.pnl)}</span>
      </button>
      {open && (
        <div className="pl-5 pb-3">
          <div className="flex gap-4 text-[12px]">
            {(['list', 'bill'] as const).map(v => (
              <button key={v} type="button" onClick={() => setBill(v === 'bill')}
                className={`pb-0.5 font-semibold ${bill === (v === 'bill')
                  ? 'text-neutral-900 dark:text-white border-b-2 border-current'
                  : 'text-neutral-400'}`}>
                {v === 'list' ? '下注明細' : '帳單卡片'}
              </button>
            ))}
          </div>
          {bill ? (
            <div className="pt-2"><BillCards bill={buildDayBill(day)} md={dayMd(day.ymd)} /></div>
          ) : (
            <div className="divide-y divide-black/[0.05] dark:divide-white/[0.06]">
              {day.rows.map(r => <BetLine key={r.id} r={r} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const BoardView: React.FC<{ b: SharedBoardDTO }> = ({ b }) => {
  const { games } = useGame();
  const gameShort = (g: string) => {
    const f = games.find(x => x.key === g || x.name === g || x.short_name === g);
    return f?.short_name ?? f?.name ?? g ?? '其他';
  };
  const weeks = useMemo(() => groupWeeks(b.entries, gameShort, () => b.edition_name), [b, games]);
  const [openWeek, setOpenWeek] = useState<string | null>(() => weeks[0]?.monday ?? null);

  const ownerLabel = `${b.owner}(版主)`;
  const nameOf = (n: string) => (n === '本人' ? ownerLabel : n);
  const latest = b.versions[b.versions.length - 1];
  const meName = b.versions.flatMap(v => v.shares).find(x => x.me)?.name ?? '';
  const myPct = latest?.shares.find(x => x.me)?.pct;

  const split = (w: WeekGroup) => {
    const sp = splitCostPayout(w.moneyByEd.get(b.eid) ?? new Map(), b.versions);
    const me = sp.rows.find(r => r.name === meName) ?? { cost: 0, payout: 0, net: 0 };
    return { ...sp, me };
  };
  const splits = weeks.map(split);
  const sum = splits.reduce((a, x) => ({ cost: a.cost + x.me.cost, payout: a.payout + x.me.payout, net: a.net + x.me.net }),
    { cost: 0, payout: 0, net: 0 });
  const cur = splits[0];

  return (
    <div className="space-y-4">
      {/* 總覽:我的佔比 + 最新一週要付/分到/結算 + 累計 */}
      <div className="space-y-4 pb-4 border-b border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-start gap-2">
          <div className="min-w-0">
            <div className="text-[11px] text-neutral-500">{b.owner} 的</div>
            <div className="text-lg font-bold text-neutral-900 dark:text-white">{b.edition_name}</div>
          </div>
          <div className="ml-auto text-right">
            <div className="text-[11px] text-neutral-500">你的佔比</div>
            <div className="text-2xl font-bold font-mono text-violet-600 dark:text-violet-400">{myPct !== undefined ? `${myPct}%` : '—'}</div>
            {latest && <div className="text-[10px] text-neutral-400">{myPct !== undefined ? sinceLabel(latest.since) : '已停止分配'}</div>}
          </div>
        </div>
        {latest && <ShareBar items={latest.shares} />}

        {cur && (
          <div className="space-y-2">
            <div className="text-[11px] text-neutral-500">
              最新一週 <span className="font-mono">{md(weeks[0].monday)} ~ {md(weeks[0].sunday)}</span>
              {weeks[0].pendingCount > 0 && <span className="ml-1 text-amber-600 dark:text-amber-400">({weeks[0].pendingCount} 筆待開獎,派彩未計)</span>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <StatTile label="你要支付(成本)" value={money(cur.me.cost)} />
              <StatTile label="你分到(派彩)" value={money(cur.me.payout)} tone={cur.me.payout > 0 ? 1 : undefined} />
            </div>
            <div>
              <div className="text-[10px] text-neutral-500">本週結算(分到 − 支付)</div>
              <Settle net={cur.me.net} />
            </div>
          </div>
        )}

        {weeks.length > 1 && (
          <div className="grid grid-cols-3 gap-4 pt-3 border-t border-black/[0.05] dark:border-white/[0.06]">
            <div><div className="text-[10px] text-neutral-500">累計支付</div><div className="font-mono text-[13px] font-bold">{money(sum.cost)}</div></div>
            <div><div className="text-[10px] text-neutral-500">累計分到</div><div className="font-mono text-[13px] font-bold text-emerald-600 dark:text-emerald-400">{money(sum.payout)}</div></div>
            <div><div className="text-[10px] text-neutral-500">累計結算</div><div className={`font-mono text-[13px] font-bold ${pnlTone(sum.net)}`}>{fmtSigned(sum.net)}</div></div>
          </div>
        )}
      </div>

      {weeks.length === 0 && (
        <div className="text-[12px] text-neutral-400 py-4">
          目前還沒有帳單(只顯示你有佔比那些日子的下注)。
        </div>
      )}

      {/* 每週 */}
      {weeks.map((w, wi) => {
        const sp = splits[wi];
        const open = openWeek === w.monday;
        return (
          <div key={w.monday} className="border-b border-black/[0.08] dark:border-white/[0.08]">
            <button type="button" onClick={() => setOpenWeek(open ? null : w.monday)} className="w-full py-3 text-left space-y-1">
              <div className="flex items-center gap-2">
                {open ? <ChevronDown className="w-4 h-4 text-neutral-400" /> : <ChevronRight className="w-4 h-4 text-neutral-400" />}
                <span className="text-[13px] font-semibold font-mono text-neutral-800 dark:text-neutral-100">{md(w.monday)} ~ {md(w.sunday)}</span>
                <span className="text-[10px] text-neutral-400">{w.count} 筆</span>
                {w.pendingCount > 0 && <span className="text-[10px] text-amber-600 dark:text-amber-400">{w.pendingCount} 待開</span>}
              </div>
              <div className="flex items-end justify-between gap-2 pl-6">
                <div className="text-[11px] text-neutral-500 font-mono">付 {money(sp.me.cost)} · 分 {money(sp.me.payout)}</div>
                <Settle net={sp.me.net} size="sm" />
              </div>
            </button>

            {open && (
              <div className="pl-6 pb-4 space-y-4">
                <div>
                  <div className="text-[10px] text-neutral-400 font-semibold mb-1">這週{b.edition_name}:成本 {money(sp.cost)} · 派彩 {money(sp.payout)} · 盈虧 <span className={pnlTone(sp.net)}>{fmtSigned(sp.net)}</span></div>
                  <AllocList
                    items={sp.rows.map(r => ({
                      name: nameOf(r.name),
                      pct: sp.segs.length === 1 ? sp.segs[0].shares.find(x => x.name === r.name)?.pct : undefined,
                      amount: r.net,
                      highlight: r.name === meName,
                      sub: `付 ${money(r.cost)} · 分 ${money(r.payout)}`,
                    }))}
                    colorIndex={(_, i) => i}
                  />
                  {sp.segs.length > 1 && (
                    <div className="text-[10px] text-neutral-400 space-y-0.5 mt-1">
                      {sp.segs.map(sg => (
                        <div key={sg.since || 'base'}>
                          <span className="font-mono">{md(sg.from)}{sg.to !== sg.from ? `~${md(sg.to)}` : ''}</span>
                          {' '}照 {sg.shares.filter(x => x.pct > 0).map(x => `${nameOf(x.name)} ${x.pct}%`).join(' / ')}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className="divide-y divide-black/[0.05] dark:divide-white/[0.06]">
                  <div className="text-[10px] text-neutral-400 font-semibold pb-1">每天下注(點開看明細 / 帳單卡片)</div>
                  {w.days.map(day => <DayCard key={day.ymd} day={day} />)}
                </div>
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
    <div className="space-y-4 animate-in fade-in duration-200 max-w-2xl">
      <div className="flex items-center gap-2">
        <PieChart className="w-4 h-4 text-violet-500" />
        <div className="text-[12px] text-neutral-500 dark:text-neutral-400 min-w-0">
          版主把你連動進佔比後,這裡看你要付多少、分到多少,和每天下了什麼。
          {loggedIn && username && <span className="ml-1 text-neutral-400">(登入:<span className="font-mono">{username}</span>)</span>}
        </div>
        {loggedIn && (
          <button type="button" onClick={() => setReloadKey(k => k + 1)} title="重新整理"
            className="ml-auto shrink-0 w-8 h-8 flex items-center justify-center text-neutral-500 hover:text-neutral-900 dark:hover:text-white">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {!loggedIn && <div className="text-[12px] text-neutral-400">請先登入。</div>}
      {err && <div className="text-[12px] text-rose-500">{err}</div>}
      {loggedIn && boards === null && !err && <div className="text-[12px] text-neutral-400">讀取中…</div>}
      {loggedIn && boards?.length === 0 && (
        <div className="text-[12px] text-neutral-400 py-4">
          目前沒有版主把你的帳號連動進損益佔比。
        </div>
      )}
      {boards && boards.length > 1 && (
        <div className="flex gap-5 overflow-x-auto">
          {boards.map((b, i) => (
            <button key={`${b.owner}/${b.eid}`} type="button" onClick={() => setSel(i)}
              className={`shrink-0 pb-1 text-[13px] font-semibold ${sel === i ? 'text-neutral-900 dark:text-white border-b-2 border-current' : 'text-neutral-400'}`}>
              {b.owner} · {b.edition_name}
            </button>
          ))}
        </div>
      )}
      {boards && boards[sel] && <BoardView key={`${boards[sel].owner}/${boards[sel].eid}`} b={boards[sel]} />}
    </div>
  );
};
