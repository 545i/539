import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, PieChart, RefreshCw } from 'lucide-react';
import { api, SharedBoardDTO } from '../../api/client';
import { useAuth } from '../../api/useAuth';
import { useGame } from '../../api/useGame';
import { money } from '../uploadHistory';
import { apportion, sharesOn, splitCostPayout, ShareVersionDTO } from '../../shares';
import { useAllLedger } from '../../api/useLedger';
import { useEditions } from '../../api/useEditions';
import { weekAddDays } from '../../weeks';
import { AllocList, ShareBar, StatTile, fmtSigned, pnlTone } from '../ShareUI';
import { BillCards, buildDayBill, dayMd, groupWeeks, weekdayOf, BetRow, DayGroup, WeekGroup } from './WeeklyLedger';

// 佔比帳單(被連動者唯讀):版主設定損益佔比時把我「連動帳號」,我就能在這裡看那個版、
// 我有佔比那些日子的帳單。重點三件事一眼看清楚:
// 版面刻意扁平:不用卡片框 / 底色,只用留白與細分隔線。
//   ① 下注了什麼(每天逐筆:遊戲 / 下法 / 號碼 / 支數 / 成本 / 開獎結果 / 派彩)
//   ② 我可以分到多少(派彩 × 我的佔比)
//   ③ 我需要支付多少(成本 × 我的佔比);結算 = 分到 − 支付 → 「你需支付 / 你可收」
// 成本、派彩各自守恆分配(與版主週期帳同一套),其他合夥人名字由後端遮成「其他N」。

const slash = (ymd: string) => ymd.replace(/-/g, '/');
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
      <span className="text-[12px] font-bold text-neutral-900 dark:text-white">{r.gameShort}</span>
      <span className="text-[12px] font-semibold text-neutral-800 dark:text-neutral-100">{r.modeLabel}</span>
      {r.playType && <span className="text-[11px] text-neutral-500">{r.playType}</span>}
      <span className="text-[11px] text-neutral-500 font-mono">{r.units}{r.unitLabel}</span>
      <span className={`ml-auto text-[11px] ${
        r.payout > 0 && !r.pending ? 'text-neutral-900 dark:text-white font-semibold' : 'text-neutral-400'}`}>{r.result || '待開獎'}</span>
    </div>
    {r.balls.length > 0 && (
      <div className="flex flex-wrap gap-x-2 gap-y-0.5">
        {r.balls.map((n, i) => {
          const hit = r.drawBalls.includes(n);
          return (
            <span key={`${n}-${i}`} className={`text-[12px] font-mono font-semibold ${
              hit ? 'text-neutral-900 dark:text-white font-bold underline underline-offset-2' : 'text-neutral-500 dark:text-neutral-400'}`}>
              {String(n).padStart(2, '0')}
              {r.deltas[n] ? <sup className="ml-0.5 text-[9px] font-bold">+{r.deltas[n]}</sup> : null}
            </span>
          );
        })}
      </div>
    )}
    <div className="flex justify-between text-[11px] font-mono">
      <span className="text-neutral-500">成本 <span className="text-neutral-800 dark:text-neutral-100 font-semibold">{money(r.cost)}</span></span>
      <span className="text-neutral-500">派彩 <span className={r.payout > 0 ? 'text-neutral-900 dark:text-white font-bold' : 'text-neutral-400'}>{money(r.payout)}</span></span>
    </div>
  </div>
);

// 每天一列:收合時右側只顯示「你分到的損益」;點開才看當天該版總損益 + 下注明細 / 帳單卡片
const DayCard: React.FC<{ day: DayGroup; mine: number }> = ({ day, mine }) => {
  const [open, setOpen] = useState(false);
  const [bill, setBill] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(o => !o)} className="w-full flex items-center gap-2 py-2.5 text-left">
        {open ? <ChevronDown className="w-3.5 h-3.5 text-neutral-400" /> : <ChevronRight className="w-3.5 h-3.5 text-neutral-400" />}
        <span className="text-[13px] font-semibold font-mono text-neutral-800 dark:text-neutral-100">{md(day.ymd)}({weekdayOf(day.ymd)})</span>
        <span className="text-[10px] text-neutral-400">{day.count} 筆{day.pendingCount > 0 ? ` · ${day.pendingCount} 待開` : ''}</span>
        <span className="ml-auto text-[10px] text-neutral-400">你分到</span>
        <span className="font-mono text-[13px] font-bold text-neutral-900 dark:text-white">{fmtSigned(mine)}</span>
      </button>
      {open && (
        <div className="pl-5 pb-3">
          <div className="pb-2 text-[11px] font-mono text-neutral-500">
            當日總損益 <span className="font-semibold text-neutral-800 dark:text-neutral-100">{fmtSigned(day.pnl)}</span>
            <span className="ml-2">成本 {money(day.cost)} · 派彩 {money(day.payout)}</span>
          </div>
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
  // 這段參與從哪天開始:從最新一組往回找,連續都有我的那幾組裡最早的生效日;
  // 已停止時,找出停止那天(最後一組有我的下一組生效日)。
  const hasMe = (i: number) => b.versions[i].shares.some(x => x.me && x.pct > 0);
  let startSince = '';
  for (let i = b.versions.length - 1; i >= 0 && hasMe(i); i--) startSince = b.versions[i].since;
  let stopSince = '';
  if (myPct === undefined) {
    for (let i = b.versions.length - 1; i > 0; i--) if (hasMe(i - 1)) { stopSince = b.versions[i].since; break; }
  }
  const pctNote = myPct !== undefined
    ? `${startSince ? `自 ${slash(startSince)} 起生效` : '一開始就參與'}・與 ${b.owner} 合夥`
    : `${stopSince ? `已於 ${slash(stopSince)} 起停止分配` : '目前未分配'}・與 ${b.owner} 合夥`;

  const split = (w: WeekGroup) => {
    const sp = splitCostPayout(w.moneyByEd.get(b.eid) ?? new Map(), b.versions);
    const me = sp.rows.find(r => r.name === meName) ?? { cost: 0, payout: 0, net: 0 };
    // 每天你分到:用當天精確份額把「整週你分到」拆回各天(加總 = 整週,不會差 1)
    const exacts = w.days.map(d => {
      const m = w.moneyByEd.get(b.eid)?.get(d.ymd) ?? { cost: 0, payout: 0 };
      const pct = sharesOn(b.versions, d.ymd).shares.find(x => x.name === meName)?.pct ?? 0;
      return (m.payout - m.cost) * pct / 100;
    });
    const dayMine = apportion(me.net, exacts);
    return { ...sp, me, dayMine };
  };
  const splits = weeks.map(split);
  const sum = splits.reduce((a, x) => ({ cost: a.cost + x.me.cost, payout: a.payout + x.me.payout, net: a.net + x.me.net }),
    { cost: 0, payout: 0, net: 0 });
  const cur = splits[0];

  return (
    <div className="space-y-4">
      {/* 總覽:我的佔比 + 最新一週要付/分到/結算 + 累計 */}
      <div className="space-y-4 pb-4 border-b border-black/[0.08] dark:border-white/[0.08]">
        <div>
          <div className="text-[11px] text-neutral-500">你的佔比</div>
          <div className="text-4xl font-bold font-mono text-neutral-900 dark:text-white leading-tight">{myPct !== undefined ? `${myPct}%` : '0%'}</div>
          <div className="text-[11px] text-neutral-400 mt-0.5">{pctNote}</div>
        </div>
        {latest && <ShareBar items={latest.shares} highlight={meName} />}

        {cur && (
          <div className="space-y-2">
            <div className="text-[11px] text-neutral-500">
              最新一週 <span className="font-mono">{md(weeks[0].monday)} ~ {md(weeks[0].sunday)}</span>
              {weeks[0].pendingCount > 0 && <span className="ml-1 text-neutral-400">({weeks[0].pendingCount} 筆待開獎,派彩未計)</span>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <StatTile label="你要支付(成本)" value={money(cur.me.cost)} />
              <StatTile label="你分到(派彩)" value={money(cur.me.payout)} />
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
            <div><div className="text-[10px] text-neutral-500">累計分到</div><div className="font-mono text-[13px] font-bold">{money(sum.payout)}</div></div>
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
                {w.pendingCount > 0 && <span className="text-[10px] text-neutral-400">{w.pendingCount} 待開</span>}
              </div>
              <div className="flex items-end justify-between gap-2 pl-6">
                <div className="text-[11px] text-neutral-500 font-mono">付 {money(sp.me.cost)} · 分 {money(sp.me.payout)}</div>
                <Settle net={sp.me.net} size="sm" />
              </div>
            </button>

            {open && (
              <div className="pl-6 pb-4 space-y-4">
                <div>
                  <div className="text-[10px] text-neutral-400 font-semibold mb-1">這週合計:成本 {money(sp.cost)} · 派彩 {money(sp.payout)} · 盈虧 {fmtSigned(sp.net)}</div>
                  <AllocList
                    items={sp.rows.map(r => ({
                      name: nameOf(r.name),
                      pct: sp.segs.length === 1 ? sp.segs[0].shares.find(x => x.name === r.name)?.pct : undefined,
                      amount: r.net,
                      highlight: r.name === meName,
                      sub: `付 ${money(r.cost)} · 分 ${money(r.payout)}`,
                    }))}
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
                  {w.days.map((day, di) => <DayCard key={day.ymd} day={day} mine={sp.dayMine[di] ?? 0} />)}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

// ── 版主儀表板:我是版主時,跟每位合夥人要收 / 要付多少 ─────────────────────
// 用我自己的流水(排除模擬版)+ 我設定的佔比,算法與週期帳「本週損益佔比」同一套
// (成本 / 派彩各自守恆),所以金額跟週期帳、合夥人自己看到的一致。
// 合夥人淨額 = 分到派彩 − 應付成本:< 0 → 他要付我(應收)、> 0 → 我要付他(應付)。
type Money3 = { cost: number; payout: number; net: number };
const add3 = (a: Money3, b: Money3): Money3 => ({ cost: a.cost + b.cost, payout: a.payout + b.payout, net: a.net + b.net });
const zero3 = (): Money3 => ({ cost: 0, payout: 0, net: 0 });

// 從我(版主)角度的結算一句話:合夥人淨額 < 0 → 應收;> 0 → 應付
const OwnerSettle: React.FC<{ net: number; size?: 'lg' | 'sm' }> = ({ net, size = 'sm' }) => (
  <span className={`font-bold ${size === 'lg' ? 'text-xl' : 'text-[13px]'} ${pnlTone(-net)}`}>
    {net < 0 ? '應收 ' : net > 0 ? '應付 ' : '不用收付'}
    {net !== 0 && <span className="font-mono">${Math.abs(net).toLocaleString()}</span>}
  </span>
);

const OwnerDashboard: React.FC<{ reloadKey: number; onHasPartners: (v: boolean) => void }> = ({ reloadKey, onHasPartners }) => {
  const { entries } = useAllLedger();
  const { editions } = useEditions();
  const { games } = useGame();
  const [sharesByEid, setSharesByEid] = useState<Record<number, ShareVersionDTO[]>>({});
  const [selWeek, setSelWeek] = useState<string>('');          // '' = 最新一週;'all' = 全部週
  const [openP, setOpenP] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.getAllShares()
      .then(m => { if (alive) setSharesByEid(Object.fromEntries(Object.entries(m).map(([k, v]) => [Number(k), v]))); })
      .catch(() => { /* 讀不到就當沒有合夥人 */ });
    return () => { alive = false; };
  }, [reloadKey]);

  const simEids = useMemo(() => new Set(editions.filter(e => e.simulated).map(e => e.eid)), [editions]);
  const edName = (ed: number) => editions.find(x => x.eid === ed)?.name ?? `版${ed}`;
  const gameShort = (g: string) => {
    const f = games.find(x => x.key === g || x.name === g || x.short_name === g);
    return f?.short_name ?? f?.name ?? g ?? '其他';
  };
  // 有往下分的版(任一組有本人以外的人)
  const partnerEids = useMemo(() => new Set(
    Object.entries(sharesByEid)
      .filter(([, vs]) => vs.some(v => v.shares.some(x => !x.self && x.pct > 0)))
      .map(([k]) => Number(k))
      .filter(ed => !simEids.has(ed)),
  ), [sharesByEid, simEids]);
  useEffect(() => { onHasPartners(partnerEids.size > 0); }, [partnerEids, onHasPartners]);

  const weeks = useMemo(() => groupWeeks(
    entries.filter(e => partnerEids.has(Number((e.record as Record<string, unknown>).edition) || 1)),
    gameShort, edName,
  ).filter(w => w.monday), [entries, partnerEids, games, editions]);

  // 每週 × 每位合夥人 × 每版
  type Cell = Money3 & { ed: number; segs: ReturnType<typeof splitCostPayout>['segs'] };
  const perWeek = useMemo(() => weeks.map(w => {
    const byP = new Map<string, Cell[]>();
    for (const [ed, days] of w.moneyByEd) {
      if (!partnerEids.has(ed)) continue;
      const sp = splitCostPayout(days, sharesByEid[ed]);
      for (const r of sp.rows) {
        if (r.self) continue;
        const list = byP.get(r.name) ?? [];
        list.push({ ed, cost: r.cost, payout: r.payout, net: r.net, segs: sp.segs });
        byP.set(r.name, list);
      }
    }
    return { w, byP };
  }).filter(x => x.byP.size > 0), [weeks, sharesByEid, partnerEids]);   // 只留有合夥人收支的週

  if (partnerEids.size === 0) return null;

  // 合夥人資訊:連動帳號、各版目前佔比(取各版最新一組)
  const info = (name: string) => {
    const acc = new Set<string>();
    const pcts: string[] = [];
    for (const ed of partnerEids) {
      const vs = sharesByEid[ed] ?? [];
      const last = vs[vs.length - 1];
      const sh = last?.shares.find(x => x.name === name);
      if (sh && sh.pct > 0) pcts.push(`${edName(ed)} ${sh.pct}%`);
      vs.forEach(v => v.shares.forEach(x => { if (x.name === name && x.account) acc.add(x.account); }));
    }
    return { accounts: [...acc], pcts };
  };

  const weekKey = selWeek || perWeek[0]?.w.monday || '';
  const scope = weekKey === 'all' ? perWeek : perWeek.filter(x => x.w.monday === weekKey);
  // 選定範圍內每位合夥人的合計 + 各版明細
  const partners = new Map<string, { total: Money3; cells: (Cell & { monday: string })[] }>();
  for (const { w, byP } of scope) {
    for (const [name, cells] of byP) {
      const p = partners.get(name) ?? { total: zero3(), cells: [] };
      for (const c of cells) { p.total = add3(p.total, c); p.cells.push({ ...c, monday: w.monday }); }
      partners.set(name, p);
    }
  }
  const list = [...partners.entries()].sort((a, b) => Math.abs(b[1].total.net) - Math.abs(a[1].total.net));
  const receivable = list.reduce((a, [, p]) => a + (p.total.net < 0 ? -p.total.net : 0), 0);
  const payable = list.reduce((a, [, p]) => a + (p.total.net > 0 ? p.total.net : 0), 0);
  const pending = scope.reduce((a, x) => a + x.w.pendingCount, 0);

  return (
    <div className="space-y-4">
      {/* 週選擇 */}
      <div className="flex gap-4 overflow-x-auto text-[12px]">
        {[...perWeek.map(x => x.w.monday), ...(perWeek.length > 1 ? ['all'] : [])].map(k => (
          <button key={k} type="button" onClick={() => setSelWeek(k)}
            className={`shrink-0 pb-1 font-semibold font-mono ${weekKey === k ? 'text-neutral-900 dark:text-white border-b-2 border-current' : 'text-neutral-400'}`}>
            {k === 'all' ? '全部週' : `${md(k)}~${md(weekAddDays(k, 6))}`}
          </button>
        ))}
      </div>

      {/* 總覽 */}
      <div className="grid grid-cols-3 gap-4 pb-4 border-b border-black/[0.08] dark:border-white/[0.08]">
        <div>
          <div className="text-[10px] text-neutral-500">應收(合夥人付你)</div>
          <div className="text-lg font-bold font-mono text-neutral-900 dark:text-white">{money(receivable)}</div>
        </div>
        <div>
          <div className="text-[10px] text-neutral-500">應付(你付合夥人)</div>
          <div className="text-lg font-bold font-mono text-neutral-900 dark:text-white">{money(payable)}</div>
        </div>
        <div>
          <div className="text-[10px] text-neutral-500">淨額</div>
          <div className={`text-lg font-bold font-mono ${pnlTone(receivable - payable)}`}>
            {receivable - payable >= 0 ? '收 ' : '付 '}{money(Math.abs(receivable - payable))}
          </div>
        </div>
        {pending > 0 && <div className="col-span-3 text-[10px] text-neutral-400">{pending} 筆待開獎,派彩未計(開獎後自動更新)</div>}
      </div>

      {list.length === 0 && <div className="text-[12px] text-neutral-400 py-2">這段期間沒有合夥人的收支。</div>}

      {/* 每位合夥人 */}
      <div className="divide-y divide-black/[0.06] dark:divide-white/[0.06]">
        {list.map(([name, p]) => {
          const { accounts, pcts } = info(name);
          const open = openP === name;
          // 明細依 週 → 版
          const cells = [...p.cells].sort((a, b) => b.monday.localeCompare(a.monday) || a.ed - b.ed);
          return (
            <div key={name}>
              <button type="button" onClick={() => setOpenP(open ? null : name)} className="w-full flex items-center gap-2 py-3 text-left">
                {open ? <ChevronDown className="w-4 h-4 text-neutral-400 shrink-0" /> : <ChevronRight className="w-4 h-4 text-neutral-400 shrink-0" />}
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-bold text-neutral-900 dark:text-white truncate">
                    {name}{accounts.length > 0 && <span className="ml-1.5 text-[11px] font-mono font-normal text-neutral-400">{accounts.join(', ')}</span>}
                  </div>
                  <div className="text-[11px] text-neutral-500 font-mono truncate">
                    {pcts.join(' · ') || '目前未分配'} · 付 {money(p.total.cost)} · 分 {money(p.total.payout)}
                  </div>
                </div>
                <OwnerSettle net={p.total.net} />
              </button>
              {open && (
                <div className="pl-6 pb-3 space-y-1.5">
                  {cells.map((c, i) => (
                    <div key={`${c.monday}|${c.ed}|${i}`} className="text-[11px]">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-neutral-500">{md(c.monday)}~{md(weekAddDays(c.monday, 6))}</span>
                        <span className="font-semibold text-neutral-800 dark:text-neutral-100">{edName(c.ed)}</span>
                        <span className="font-mono text-neutral-500">付 {money(c.cost)} · 分 {money(c.payout)}</span>
                        <span className="ml-auto"><OwnerSettle net={c.net} /></span>
                      </div>
                      {c.segs.length > 1 && (
                        <div className="text-[10px] text-neutral-400 pl-1">
                          {c.segs.map(sg => (
                            <span key={sg.since || 'base'} className="mr-3">
                              {md(sg.from)}{sg.to !== sg.from ? `~${md(sg.to)}` : ''} 照 {sg.shares.find(x => x.name === name)?.pct ?? 0}%
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-neutral-400">
        合夥人「付」= 成本 × 佔比、「分」= 派彩 × 佔比;分 − 付 為負 → 他要付你(應收),為正 → 你要付他(應付)。
        金額與週期帳「本週損益佔比」同一套守恆分配。
      </p>
    </div>
  );
};

export const SharedBillsView: React.FC = () => {
  const { loggedIn, username } = useAuth();
  const [boards, setBoards] = useState<SharedBoardDTO[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [hasPartners, setHasPartners] = useState(false);     // 我是不是版主(有往下分的版)
  const [tab, setTab] = useState<'owner' | 'partner' | null>(null);

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

  const isPartner = (boards?.length ?? 0) > 0;
  // 預設分頁:是版主就先看儀表板,否則看我參與的
  const cur = tab ?? (hasPartners ? 'owner' : 'partner');

  return (
    <div className="space-y-4 animate-in fade-in duration-200">
      <div className="flex items-center gap-2">
        <PieChart className="w-4 h-4 text-neutral-400" />
        <div className="text-[12px] text-neutral-500 dark:text-neutral-400 min-w-0">
          {cur === 'owner'
            ? '版主儀表板:跟每位合夥人要收 / 要付多少,點名字看各週各版明細。'
            : '版主把你連動進佔比後,這裡看你要付多少、分到多少,和每天下了什麼。'}
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

      {/* 兩種身分都有才出分頁切換 */}
      {loggedIn && hasPartners && isPartner && (
        <div className="flex gap-5 text-[13px]">
          {(['owner', 'partner'] as const).map(t => (
            <button key={t} type="button" onClick={() => setTab(t)}
              className={`pb-1 font-semibold ${cur === t ? 'text-neutral-900 dark:text-white border-b-2 border-current' : 'text-neutral-400'}`}>
              {t === 'owner' ? '版主儀表板' : '我參與的'}
            </button>
          ))}
        </div>
      )}

      {/* 版主儀表板(一直掛著才能回報 hasPartners;不是這個分頁時隱藏) */}
      {loggedIn && (
        <div className={cur === 'owner' ? '' : 'hidden'}>
          <OwnerDashboard reloadKey={reloadKey} onHasPartners={setHasPartners} />
        </div>
      )}

      {cur === 'partner' && (
        <>
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
                  {b.owner}{boards.slice(0, i).some(x => x.owner === b.owner) ? ` #${boards.slice(0, i + 1).filter(x => x.owner === b.owner).length}` : ''}
                </button>
              ))}
            </div>
          )}
          {boards && boards[sel] && <BoardView key={`${boards[sel].owner}/${boards[sel].eid}`} b={boards[sel]} />}
        </>
      )}
    </div>
  );
};
