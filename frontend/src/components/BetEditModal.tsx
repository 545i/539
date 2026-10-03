import React, {useEffect, useMemo, useState} from 'react';
import {createPortal} from 'react-dom';
import {X, AlertTriangle} from 'lucide-react';
import {api, BatchEditItem, BatchEditResultItem, LedgerMode} from '../api/client';
import {useLedgerActions} from '../api/useLedger';
import {MODE_LABEL, money} from './uploadHistory';

// 週期帳「下注紀錄編輯器」:逐筆列出勾選的紀錄(可混合下法),每筆可改號碼 / 車支數 /
// 成本,最後一起儲存。1組/2組 每顆號碼各自一列:自己的車數與每注成本(絕對值)。金額一律後端試算
// (POST /ledger/batch-edit dry_run),前端只顯示原成本 / 新成本 / 差額;
// 儲存後後端重新對獎、整批記一筆操作歷史(可作廢還原)。日期 / 期號 / 版不改。

export interface EditTarget {
  id: string;
  mode: LedgerMode;
  record: Record<string, unknown>;
  deltas: Record<number, number>;   // 二合個別號碼加價(舊紀錄由 costExpr 解析)
  gameShort: string;
  editionName: string;
  numMax: number;   // 該遊戲號碼上限(舊紀錄由成本反推每注基礎用:每車 = 每注 × (numMax−1))
}

interface BallRow { n: number; cars: number; base: number }   // base 0 = 版盤口每注

interface Draft {
  balls: string;
  units: number;
  base: number;      // 0 = 沿用版盤口(送 null)
  rows: BallRow[];   // 1組/2組 逐顆(號碼字串改了就跟著增減)
}

const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : parseFloat(String(v ?? ''));
  return Number.isFinite(n) ? n : 0;
};
const pad = (n: number) => String(n).padStart(2, '0');
const parseBalls = (s: string): number[] => (s.match(/\d{1,2}/g) ?? []).map(Number).filter(n => n > 0);
const isErhe = (m: LedgerMode) => m === 'single' || m === 'multi';
const hasBalls = (m: LedgerMode) => m !== 'pillar1800' && m !== 'combo9000';
const unitLabel = (m: LedgerMode) => (isErhe(m) ? '車' : '支');
const signed = (v: number) => (v > 0 ? '+' : v < 0 ? '−' : '±') + money(Math.abs(v));
const pnlCls = (v: number) =>
  v > 0 ? 'text-emerald-600 dark:text-emerald-400' : v < 0 ? 'text-rose-600 dark:text-rose-400' : 'text-neutral-400';
const isPending = (r: Record<string, unknown>) => String(r.result ?? '').includes('待開');

// 二合逐顆初值:有 ballDetail 直接用;舊紀錄 → 每顆車數 = 整筆車數、每注 = 基礎 + 加價
// (沒存 baseCost 的舊紀錄由成本反推:基礎 =(成本 ÷ 車數 ÷ (num_max−1) − Σ加價)÷ 顆數)
function initRows(t: EditTarget): BallRow[] {
  const r = t.record;
  const detail = (r.ballDetail as {n: number; cars: number; base: number}[] | undefined) ?? [];
  if (detail.length) return detail.map(d => ({n: num(d.n), cars: num(d.cars), base: num(d.base)}));
  const balls = (r.selectedBalls as number[]) ?? [];
  const units = num(r.units) || num(r.cars);
  const sumD = balls.reduce((a, n) => a + (t.deltas[n] || 0), 0);
  let base = num(r.baseCost);
  if (base <= 0 && units > 0 && balls.length > 0 && t.numMax > 1) {
    base = Math.round(((num(r.cost) / units / Math.max(1, t.numMax - 1) - sumD) / balls.length) * 10000) / 10000;
  }
  return balls.map(n => ({n, cars: units, base: base > 0 ? Math.round((base + (t.deltas[n] || 0)) * 10000) / 10000 : 0}));
}

function initDraft(t: EditTarget): Draft {
  const r = t.record;
  const rows = isErhe(t.mode) ? initRows(t) : [];
  return {
    balls: (rows.length ? rows.map(x => x.n) : ((r.selectedBalls as number[]) ?? [])).map(pad).join(' '),
    units: num(r.units) || num(r.cars),
    base: num(r.baseCost),
    rows,
  };
}

// 號碼字串改了 → 逐顆列跟著增減;既有號碼保留原車數 / 每注,新號碼沿用第一列
function syncRows(rows: BallRow[], balls: number[]): BallRow[] {
  const tpl = rows[0] ?? {n: 0, cars: 1, base: 0};
  return [...new Set(balls)].map(n => rows.find(x => x.n === n) ?? {n, cars: tpl.cars, base: tpl.base});
}

function toItem(t: EditTarget, d: Draft): BatchEditItem {
  if (isErhe(t.mode)) {
    return {
      id: Number(t.id), selectedBalls: d.rows.map(x => x.n), units: d.rows[0]?.cars ?? 0,
      ball_detail: d.rows.map(x => ({n: x.n, cars: x.cars, base: x.base > 0 ? x.base : null})),
    };
  }
  const balls = hasBalls(t.mode) ? parseBalls(d.balls) : [];
  return {id: Number(t.id), selectedBalls: balls, units: d.units, base_cost: d.base > 0 ? d.base : null};
}

export const BetEditModal: React.FC<{
  targets: EditTarget[];
  onClose: () => void;
  onSaved: (n: number) => void;
}> = ({targets, onClose, onSaved}) => {
  const {batchEdit} = useLedgerActions();
  const [drafts, setDrafts] = useState<Draft[]>(() => targets.map(initDraft));
  const [preview, setPreview] = useState<Map<string, BatchEditResultItem>>(new Map());
  const [errs, setErrs] = useState<Map<string, string>>(new Map());
  const [busy, setBusy] = useState(false);       // 試算中
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setDraft = (i: number, patch: Partial<Draft>) =>
    setDrafts(prev => prev.map((d, k) => (k === i ? {...d, ...patch} : d)));
  const setBalls = (i: number, text: string) =>
    setDrafts(prev => prev.map((d, k) => (k === i ? {...d, balls: text, rows: syncRows(d.rows, parseBalls(text))} : d)));
  const setRow = (i: number, n: number, patch: Partial<BallRow>) =>
    setDrafts(prev => prev.map((d, k) => (k === i ? {...d, rows: d.rows.map(x => (x.n === n ? {...x, ...patch} : x))} : d)));

  const items = useMemo(() => targets.map((t, i) => toItem(t, drafts[i])), [targets, drafts]);

  // 改動即後端試算(debounce 350ms):回每筆舊 / 新 record 與差額
  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    const timer = window.setTimeout(async () => {
      try {
        const res = await api.ledgerBatchEdit(items, true);
        if (cancelled) return;
        setPreview(new Map(res.items.map(it => [String(it.id), it])));
        setErrs(new Map(res.errors.map(e => [String(e.id), e.message])));
        setError(null);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setBusy(false);
      }
    }, 350);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [items]);

  // 底部合計:只加總試算成功的筆
  const totals = useMemo(() => {
    let oldCost = 0, newCost = 0, pnlDiff = 0;
    for (const t of targets) {
      const p = preview.get(t.id);
      if (!p) continue;
      oldCost += num(p.old.cost); newCost += num(p.new.cost); pnlDiff += p.pnl_diff;
    }
    return {oldCost, newCost, diff: newCost - oldCost, pnlDiff};
  }, [targets, preview]);

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await batchEdit(items);
      if (res.errors.length > 0) {
        setErrs(new Map(res.errors.map(e => [String(e.id), e.message])));
        setError(`${res.errors.length} 筆算不出來,整批沒有儲存`);
        return;
      }
      onSaved(res.saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const inputCls = 'px-2 py-1 bg-transparent border-0 border-b border-black/15 dark:border-white/15 font-mono text-neutral-900 dark:text-white outline-hidden focus:border-neutral-900 dark:focus:border-white';

  // 欄位兩種版面共用:sm 以上表格、手機直排卡片
  const head = (t: EditTarget) => {
    const r = t.record;
    return (
      <div className="font-sans">
        <div className="text-[12px] text-neutral-900 dark:text-white">
          <span className="font-semibold mr-1.5">{MODE_LABEL[t.mode] ?? t.mode}</span>
          <span className="text-neutral-600 dark:text-neutral-300">{String(preview.get(t.id)?.new.playType ?? r.playType ?? '')}</span>
        </div>
        <div className="mt-0.5 text-[10px] text-neutral-400">
          {t.gameShort} · {t.editionName} · {String(r.date ?? '').slice(0, 10)}
          {r.issue ? ` · 第 ${String(r.issue)} 期` : ''}
        </div>
      </div>
    );
  };
  const ballsField = (t: EditTarget, i: number) => {
    const d = drafts[i];
    if (t.mode === 'pillar1800') {
      const ps = (t.record.pillars as number[][]) ?? [];
      return (
        <div className="text-[11px] font-mono text-neutral-600 dark:text-neutral-300 leading-relaxed break-all">
          {ps.length === 3
            ? ps.map((p, k) => <div key={k}>{k < 2 ? `第${k + 1}柱` : '其他'}({p.length}):{p.map(pad).join(' ')}</div>)
            : '標準三柱 10~18 / 20~29 / 其他'}
          <div className="text-[10px] font-sans text-neutral-400">分柱沿用原紀錄</div>
        </div>
      );
    }
    if (t.mode === 'combo9000') return <div className="text-[11px] text-neutral-500">9000碰 四段全包(無選號)</div>;
    const defBase = num(preview.get(t.id)?.new.baseCost);
    return (
      <>
        <input value={d.balls} onChange={e => (isErhe(t.mode) ? setBalls(i, e.target.value) : setDraft(i, {balls: e.target.value}))}
          spellCheck={false} inputMode="numeric" className={`w-full ${inputCls} text-sm sm:text-[12px]`} />
        <span className="text-[10px] text-neutral-400">{parseBalls(d.balls).length} 顆{isErhe(t.mode) ? ',每顆各自車數 / 每注成本' : ''}</span>
        {isErhe(t.mode) && d.rows.length > 0 && (
          // 逐顆一列:號碼 | 車數 | 每注成本(絕對值)
          <div className="mt-1.5 divide-y divide-black/[0.05] dark:divide-white/[0.06]">
            {d.rows.map(x => (
              <div key={x.n} className="grid grid-cols-[2.5rem_1fr_1fr] items-end gap-3 py-1.5">
                <span className="font-mono font-bold text-[13px] text-neutral-900 dark:text-white pb-1">{pad(x.n)}</span>
                <label className="block">
                  <span className="block text-[9px] text-neutral-400">車數</span>
                  <input type="number" inputMode="decimal" min={0} step="0.5" value={x.cars || ''}
                    onChange={e => setRow(i, x.n, {cars: Number(e.target.value)})}
                    className={`w-full ${inputCls} text-right text-sm sm:text-[12px]`} />
                </label>
                <label className="block">
                  <span className="block text-[9px] text-neutral-400">每注成本</span>
                  <input type="number" inputMode="decimal" min={0} step="0.5" value={x.base > 0 ? x.base : ''}
                    placeholder={defBase ? String(defBase) : '盤口'}
                    onChange={e => setRow(i, x.n, {base: Number(e.target.value)})}
                    className={`w-full ${inputCls} text-right text-sm sm:text-[12px]`} />
                </label>
              </div>
            ))}
          </div>
        )}
      </>
    );
  };
  const unitsField = (t: EditTarget, i: number, cls: string) => (
    <input type="number" inputMode="decimal" min={0} step="0.5" value={drafts[i].units}
      onChange={e => setDraft(i, {units: Number(e.target.value)})}
      className={`${cls} ${inputCls} text-right`} />
  );
  const baseField = (t: EditTarget, i: number, cls: string) => (
    <input type="number" inputMode="decimal" min={0} step="0.1"
      value={drafts[i].base > 0 ? drafts[i].base : ''}
      placeholder={String(num(preview.get(t.id)?.new.baseCost) || '盤口')}
      onChange={e => setDraft(i, {base: Number(e.target.value)})}
      title={t.mode === 'pillar1800' ? '每注成本' : '每碰成本'}
      className={`${cls} ${inputCls} text-right`} />
  );
  // 審計:原成本 / 新成本 / 差額(全部後端試算結果)+ 損益變化
  const audit = (t: EditTarget) => {
    const p = preview.get(t.id);
    const err = errs.get(t.id);
    if (err) {
      return (
        <div className="flex items-start gap-1.5 text-[11px] text-rose-600 dark:text-rose-400">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" /><span>{err}</span>
        </div>
      );
    }
    const oldCost = num(t.record.cost);
    return (
      <div className="space-y-1">
        <div className="grid grid-cols-3 gap-2 text-right font-mono">
          <div>
            <div className="text-[9px] font-sans text-neutral-400">原成本</div>
            <div className="text-[12px] text-neutral-500">{money(oldCost)}</div>
          </div>
          <div>
            <div className="text-[9px] font-sans text-neutral-400">新成本</div>
            <div className="text-[12px] font-bold text-neutral-900 dark:text-white">{p ? money(num(p.new.cost)) : busy ? '…' : '—'}</div>
          </div>
          <div>
            <div className="text-[9px] font-sans text-neutral-400">差額</div>
            <div className="text-[12px] font-bold text-neutral-900 dark:text-white">{p ? signed(p.cost_diff) : '—'}</div>
          </div>
        </div>
        {p && (
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5 text-[10px] text-neutral-400">
            <span className="font-mono break-all">{String(p.new.costExpr ?? '')}</span>
            <span className="whitespace-nowrap">
              {isPending(p.new) ? '待開獎' : (
                <>
                  {String(p.new.result ?? '')} · 盈虧{' '}
                  <span className={`font-mono ${pnlCls(num(p.old.pnl))}`}>{signed(num(p.old.pnl))}</span>
                  {' → '}
                  <span className={`font-mono font-bold ${pnlCls(num(p.new.pnl))}`}>{signed(num(p.new.pnl))}</span>
                </>
              )}
            </span>
          </div>
        )}
      </div>
    );
  };

  const canSave = !saving && !busy && errs.size === 0 && preview.size === targets.length;

  return createPortal((
    <div className="fixed inset-0 z-50 flex sm:items-center sm:justify-center sm:p-4 bg-black/60">
      <div className="w-full h-[100dvh] sm:h-auto sm:max-h-[90vh] sm:max-w-4xl bg-white dark:bg-[#121212] sm:rounded-2xl shadow-2xl flex flex-col overflow-hidden text-neutral-800 dark:text-neutral-200">
        <div className="flex items-center justify-between px-4 sm:px-6 py-3 pt-[max(0.75rem,env(safe-area-inset-top))] sm:pt-3 border-b border-black/[0.08] dark:border-white/[0.08] shrink-0">
          <div>
            <div className="font-bold text-[15px] text-neutral-900 dark:text-white">編輯下注紀錄</div>
            <div className="text-[10px] text-neutral-400">{targets.length} 筆 · 可改號碼、車/支數、成本;日期 / 期號 / 版不變</div>
          </div>
          <button type="button" onClick={onClose} aria-label="關閉"
            className="p-1.5 rounded-full text-neutral-400 hover:text-neutral-700 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto">
          {/* 手機:每筆直排卡片 */}
          <div className="sm:hidden divide-y divide-black/[0.06] dark:divide-white/[0.06]">
            {targets.map((t, i) => (
              <div key={t.id} className="px-4 py-3 space-y-2.5">
                {head(t)}
                <div>{ballsField(t, i)}</div>
                {!isErhe(t.mode) && <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="block text-[10px] text-neutral-500">{unitLabel(t.mode)}數</span>
                    {unitsField(t, i, 'w-full py-1.5 text-sm')}
                  </label>
                  <label className="block">
                    <span className="block text-[10px] text-neutral-500">{t.mode === 'pillar1800' ? '每注成本' : '每碰成本'}</span>
                    {baseField(t, i, 'w-full py-1.5 text-sm')}
                  </label>
                </div>}
                {audit(t)}
              </div>
            ))}
          </div>

          {/* sm 以上:表格 */}
          <table className="hidden sm:table w-full text-[11px]">
            <thead className="text-[10px] text-neutral-400">
              <tr className="border-b border-black/[0.08] dark:border-white/[0.08]">
                <th className="px-4 py-2 text-left font-semibold">下法</th>
                <th className="px-3 py-2 text-left font-semibold">號碼</th>
                <th className="px-3 py-2 text-right font-semibold">車 / 支</th>
                <th className="px-3 py-2 text-right font-semibold">成本<br /><span className="font-normal text-[9px]">每注 / 每碰</span></th>
                <th className="px-4 py-2 text-right font-semibold w-[260px]">原成本 / 新成本 / 差額</th>
              </tr>
            </thead>
            <tbody>
              {targets.map((t, i) => (
                <tr key={t.id} className="border-b border-black/[0.06] dark:border-white/[0.06] align-top">
                  <td className="px-4 py-2.5">{head(t)}</td>
                  {isErhe(t.mode) ? (
                    <td colSpan={3} className="px-3 py-2.5 min-w-[260px]">{ballsField(t, i)}</td>
                  ) : (
                    <>
                      <td className="px-3 py-2.5 min-w-[180px]">{ballsField(t, i)}</td>
                      <td className="px-3 py-2.5 text-right">{unitsField(t, i, 'w-16 text-[12px]')}</td>
                      <td className="px-3 py-2.5 text-right">{baseField(t, i, 'w-20 text-[12px]')}</td>
                    </>
                  )}
                  <td className="px-4 py-2.5">{audit(t)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="shrink-0 border-t border-black/[0.08] dark:border-white/[0.08] px-4 sm:px-6 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:pb-3 space-y-2">
          {error && <div className="text-[11px] text-rose-600 dark:text-rose-400">{error}</div>}
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-[11px]">
            <span className="text-neutral-500">
              合計成本 <span className="font-mono">{money(totals.oldCost)}</span> →{' '}
              <span className="font-mono font-bold text-neutral-900 dark:text-white">{money(totals.newCost)}</span>
              <span className="ml-1.5 font-mono font-bold text-neutral-900 dark:text-white">({signed(totals.diff)})</span>
            </span>
            <span className="text-neutral-500">
              損益變化 <span className={`font-mono font-bold ${pnlCls(totals.pnlDiff)}`}>{signed(totals.pnlDiff)}</span>
              {busy && <span className="ml-1.5 text-neutral-400">試算中…</span>}
            </span>
          </div>
          <div className="flex items-center justify-end gap-4">
            <button type="button" onClick={onClose}
              className="text-[12px] text-neutral-500 hover:text-neutral-900 dark:hover:text-white hover:underline underline-offset-2">
              取消
            </button>
            <button type="button" disabled={!canSave} onClick={save}
              className="px-4 py-2 rounded-lg text-[12px] font-semibold bg-neutral-900 text-white dark:bg-white dark:text-black disabled:opacity-40">
              {saving ? '儲存中…' : `儲存 ${targets.length} 筆並重新對獎`}
            </button>
          </div>
          <div className="text-[10px] text-neutral-400">儲存後可在「操作歷史」作廢這次編輯,還原成原紀錄。</div>
        </div>
      </div>
    </div>
  ), document.body);
};
