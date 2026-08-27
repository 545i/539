import React, { useEffect, useState } from 'react';
import { X, History, Ban, CornerDownLeft, ClipboardCheck, AlertTriangle } from 'lucide-react';
import {
  UploadHistoryEntry, MODE_LABEL, loadHistory, updateEntry, voidEntry, fmtTime, money,
} from './uploadHistory';
import { api, ReconcileDTO } from '../api/client';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onRefill?: (text: string) => void; // 「填回快速上傳」:把某批文本帶回上傳文字框
}

const diffCls = (d: number) =>
  d === 0 ? 'text-neutral-400' : 'text-rose-600 dark:text-rose-400 font-bold';
const sign = (d: number) => (d > 0 ? '+' : '');

// 對帳報告:二/三/四桶 × 支/成本/中碰/得到,我們 vs 對接人 + 差異
const ReconReport: React.FC<{ data: ReconcileDTO }> = ({ data }) => {
  const { bill, report, records_used } = data;
  if (!report) {
    return (
      <div className="text-[11px] text-rose-600 dark:text-rose-400 space-y-0.5">
        {bill.errors.length
          ? bill.errors.map((e, i) => <div key={i}>· {e}</div>)
          : <div>帳單缺日期或遊戲,無法比對。</div>}
      </div>
    );
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-[10px] text-neutral-500">
        <span>帳單 {bill.date}・{bill.draw.map(n => String(n).padStart(2, '0')).join(' ')}</span>
        <span className="text-neutral-400">比對我們 {records_used} 筆</span>
      </div>
      {report.maybe_wrong_date && (
        <div className="text-[11px] text-amber-700 dark:text-amber-400 flex items-start gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          <span>成本落差過大(我 {money(report.total_cost_ours)} vs 他 {money(report.total_cost_theirs)})—— 這張帳單會不會是別的日期?</span>
        </div>
      )}
      {!report.have_records && (
        <div className="text-[11px] text-amber-700 dark:text-amber-400">這一版該日期沒有我們的下注紀錄可比對。</div>
      )}
      <div className="overflow-x-auto rounded-lg border border-black/10 dark:border-white/10">
        <table className="w-full text-[10px] font-mono whitespace-nowrap">
          <thead className="bg-black/[0.04] dark:bg-white/[0.06] text-neutral-500">
            <tr>
              <th className="px-2 py-1 text-left">桶</th>
              <th className="px-2 py-1 text-right">支 我/他</th>
              <th className="px-2 py-1 text-right">成本 我/他</th>
              <th className="px-2 py-1 text-right">中碰 我/他</th>
              <th className="px-2 py-1 text-right">得到 我/他</th>
            </tr>
          </thead>
          <tbody>
            {report.rows.map(r => (
              <tr key={r.bucket} className="border-t border-black/[0.05] dark:border-white/[0.05]">
                <td className="px-2 py-1 font-sans font-semibold">
                  {r.bucket}<span className="text-neutral-400 font-normal">({r.n})</span>
                </td>
                <td className="px-2 py-1 text-right">
                  {r.units.ours}/{r.units.theirs} <span className={diffCls(r.units.diff)}>{r.units.diff ? sign(r.units.diff) + r.units.diff : ''}</span>
                </td>
                <td className="px-2 py-1 text-right">
                  {money(r.cost.ours)}/{money(r.cost.theirs)} <span className="text-neutral-400">{r.cost.diff ? sign(r.cost.diff) + r.cost.diff : ''}</span>
                </td>
                <td className="px-2 py-1 text-right">
                  {r.carry.ours}/{r.carry.theirs} <span className={diffCls(r.carry.diff)}>{r.carry.diff ? sign(r.carry.diff) + r.carry.diff : ''}</span>
                </td>
                <td className="px-2 py-1 text-right">
                  {money(r.payout.ours)}/{money(r.payout.theirs)} <span className={diffCls(r.payout.diff)}>{r.payout.diff ? sign(r.payout.diff) + money(r.payout.diff) : ''}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* 該日期結算:中獎金額 + 最終需付(誰付誰)*/}
      <div className="rounded-lg border border-black/10 dark:border-white/10 p-2.5 text-[11px] font-mono space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-neutral-500">總成本 我/他</span>
          <span>{money(report.total_cost_ours)} / {money(report.total_cost_theirs)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-neutral-500">中獎金額 我/他</span>
          <span className="text-emerald-600 dark:text-emerald-400">{money(report.payout_ours)} / {money(report.payout_theirs)}</span>
        </div>
        <div className="flex items-center justify-between border-t border-black/10 dark:border-white/10 pt-1">
          <span className="font-sans font-semibold text-neutral-700 dark:text-neutral-200">最終{report.net_theirs >= 0 ? '(收/我方付)' : '(付/對方付)'}</span>
          <span className="font-bold">
            我 {money(report.net_ours)} / 帳單 {money(report.net_theirs)}
            {report.net_ours !== report.net_theirs && (
              <span className="ml-1.5 text-rose-600 dark:text-rose-400">差 {money(report.net_ours - report.net_theirs)}</span>
            )}
          </span>
        </div>
      </div>
      <div className="text-[10px] text-neutral-500 leading-relaxed">
        「最終」= 總成本 − 中獎金額(正 = 我方要付組頭,負 = 組頭付我方)。紅字 = 和對接人不一致(<strong>中碰 / 得到 / 最終</strong>最要注意);成本差多為盤口率不同,把這版盤口設成對接人的率即可歸零。
      </div>
    </div>
  );
};

// 快速上傳歷史(獨立彈窗):查看每批上傳的原始文本、下注明細/成本、總下注成本。
// 資料存在 localStorage(見 uploadHistory.ts),重開瀏覽器仍在。
export const UploadHistoryModal: React.FC<Props> = ({ isOpen, onClose, onRefill }) => {
  const [history, setHistory] = useState<UploadHistoryEntry[]>([]);
  const [filterEdition, setFilterEdition] = useState<string>('all');
  const [expanded, setExpanded] = useState<Set<number>>(new Set()); // 預設全收疊
  const toggle = (ts: number) => setExpanded(prev => {
    const n = new Set(prev); n.has(ts) ? n.delete(ts) : n.add(ts); return n;
  });
  // 對帳:哪一批正在對、貼上的帳單文字、比對結果
  const [reconTs, setReconTs] = useState<number | null>(null);
  const [billText, setBillText] = useState('');
  const [recon, setRecon] = useState<ReconcileDTO | null>(null);
  const [reconBusy, setReconBusy] = useState(false);
  const [reconErr, setReconErr] = useState<string | null>(null);
  const [reconDate, setReconDate] = useState('');   // 帳單沒日期時,手動補的日期

  const openRecon = (ts: number) => {
    const h = history.find(x => x.ts === ts);
    setReconTs(ts);
    setBillText(h?.bill ?? '');       // 帶回已保存的帳單原文
    setRecon(h?.recon ?? null);       // 帶回已保存的對帳結果
    setReconErr(null);
  };
  const saveRecon = async (ts: number) => {
    if (!recon) return;
    setHistory(await updateEntry(ts, { bill: billText, recon, reconAt: Date.now() }));
  };
  const runRecon = async (eid: number) => {
    setReconBusy(true); setReconErr(null); setRecon(null);
    try {
      const res = await api.ledgerReconcile(billText, eid, reconDate);
      setRecon(res);
      // 帳單沒日期、又沒手動補 → 提示補日期(第二種帳單格式常見)
      const noDate = (res?.bill?.errors ?? []).some(e => e.includes('日期'));
      if (noDate && !reconDate) {
        setReconErr('這張帳單沒有日期,請在上方填「對帳日期」後再比對。');
      }
    } catch (e) {
      setReconErr((e as Error).message);
    } finally {
      setReconBusy(false);
    }
  };

  const [winMap, setWinMap] = useState<Record<number, number>>({}); // ts → 已結算派彩(獲利)
  const [voidTs, setVoidTs] = useState<number | null>(null);   // 哪一批按了作廢(等二次確認)
  const [voidBusy, setVoidBusy] = useState(false);
  const [voidErr, setVoidErr] = useState<string | null>(null);
  const doVoid = async (ts: number) => {
    setVoidBusy(true); setVoidErr(null);
    try {
      setHistory(await voidEntry(ts));   // 後端連同 ledger 下注一起刪,回傳更新後清單
      setVoidTs(null);
    } catch (e) {
      setVoidErr((e as Error).message);
    } finally {
      setVoidBusy(false);
    }
  };

  // 每次開啟重讀一次(可能剛在快速上傳新增了一批);後端讀取,用 alive 防 race
  useEffect(() => {
    if (!isOpen) return;
    setFilterEdition('all'); setExpanded(new Set());
    let alive = true;
    loadHistory().then(list => { if (alive) setHistory(list); });
    return () => { alive = false; };
  }, [isOpen]);

  // 開啟後抓每批「該期×版×遊戲」已結算派彩 → 父列直接顯示獲利(不必先對帳)
  useEffect(() => {
    if (!isOpen || history.length === 0) return;
    let alive = true;
    (async () => {
      const pairs = await Promise.all(history.map(async h => {
        if (!h.issue) return [h.ts, 0] as const;
        try {
          const s = await api.ledgerDateSummary(h.issue, h.eid ?? 1, h.gameName);
          return [h.ts, s.payout] as const;
        } catch { return [h.ts, 0] as const; }
      }));
      if (alive) setWinMap(Object.fromEntries(pairs));
    })();
    return () => { alive = false; };
  }, [isOpen, history]);

  if (!isOpen) return null;

  // 版篩選:歷史裡出現過的版別
  const editions = Array.from(new Set(history.map(h => h.editionName).filter(Boolean)));
  const shown = filterEdition === 'all'
    ? history
    : history.filter(h => h.editionName === filterEdition);
  const historyTotal = shown.reduce((s, h) => s + h.totalCost, 0);

  // 重複批次偵測:同 遊戲 + 同 版(eid)+ 同 期(issue)出現 ≥2 次 → 都標紅提示。
  // 只有帶期號的才判(沒期號會把不同批綁在同一個空 key,誤判)。真實案例:同一期被上傳兩批一樣的。
  const dupKey = (h: UploadHistoryEntry) =>
    h.issue ? `${h.gameName}|${h.eid ?? 1}|${h.issue}` : null;
  const dupCounts: Record<string, number> = {};
  for (const h of shown) {
    const k = dupKey(h);
    if (k) dupCounts[k] = (dupCounts[k] ?? 0) + 1;
  }
  const isDupEntry = (h: UploadHistoryEntry) => {
    const k = dupKey(h);
    return k != null && (dupCounts[k] ?? 0) >= 2;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-stretch sm:items-center justify-center p-0 sm:p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full h-full sm:h-auto max-w-full sm:max-w-2xl sm:max-h-[90vh] bg-white dark:bg-[#121212] border-0 sm:border border-black/10 dark:border-white/10 rounded-none sm:rounded-2xl shadow-2xl flex flex-col text-neutral-800 dark:text-neutral-200">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.08] dark:border-white/[0.08] shrink-0">
          <div className="flex items-center gap-2 font-display font-bold text-base text-neutral-900 dark:text-white uppercase tracking-wide">
            <History className="w-4 h-4 text-neutral-500" />
            <span>快速上傳歷史</span>
            {shown.length > 0 && (
              <span className="font-mono text-xs font-normal text-neutral-400">
                {shown.length} 批・累計 {money(historyTotal)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-full text-neutral-400 hover:text-neutral-700 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0 p-4 sm:p-6 space-y-4 overflow-y-auto">
          {history.length === 0 && (
            <div className="text-[11px] text-neutral-400 dark:text-neutral-500 leading-relaxed p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03]">
              目前沒有上傳紀錄。到「快速上傳」貼下注文字、按<strong>「確認上傳」</strong>後,
              這裡會保留該批的<strong>原始文本</strong>、每筆<strong>下注明細與成本</strong>,
              以及<strong>總下注成本</strong>(存在本機瀏覽器,重開仍在)。
            </div>
          )}

          {/* 版篩選:只看某一版的上傳歷史 */}
          {editions.length > 1 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">版</span>
              {['all', ...editions].map(ed => (
                <button
                  key={ed}
                  type="button"
                  onClick={() => setFilterEdition(ed)}
                  className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                    filterEdition === ed
                      ? 'bg-black text-white dark:bg-white dark:text-black'
                      : 'border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
                  }`}
                >
                  {ed === 'all' ? '全部版' : ed}
                </button>
              ))}
            </div>
          )}

          {shown.map(h => {
            const isOpen = expanded.has(h.ts);
            // 獲利:優先用已結算派彩(自動),沒有再用對帳的我方中獎金額
            const win = winMap[h.ts] ?? h.recon?.report?.payout_ours;
            const pnl = win != null ? win - h.totalCost : undefined; // 盈虧 = 獲利 − 成本
            const isDup = isDupEntry(h);
            return (
            <div
              key={h.ts}
              className={`rounded-xl border overflow-hidden shadow-sm ${
                isDup
                  ? 'border-rose-400/70 dark:border-rose-500/50 border-l-4 border-l-rose-500 bg-rose-500/[0.05]'
                  : 'border-black/15 dark:border-white/15 bg-black/[0.02] dark:bg-white/[0.03]'
              }`}
            >
              <div className="flex items-center justify-between px-3 py-2 border-b border-black/[0.06] dark:border-white/[0.06] gap-2">
                <button
                  type="button"
                  onClick={() => toggle(h.ts)}
                  className="min-w-0 flex-1 text-left"
                >
                  <div className={`text-[11px] font-semibold truncate ${isDup ? 'text-rose-600 dark:text-rose-400' : 'text-neutral-700 dark:text-neutral-300'}`}>
                    <span className="text-neutral-400 mr-0.5">{isOpen ? '▾' : '▸'}</span>
                    {h.gameName}・{h.editionName}
                    {h.issue ? `・第 ${h.issue} 期` : ''}
                    <span className="ml-1.5 font-normal text-neutral-400">{h.count} 筆</span>
                    {h.reconAt && (
                      <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[9px] font-semibold">已對帳</span>
                    )}
                  </div>
                  {isDup && (
                    <div className="mt-1 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 text-[9px] font-bold">
                      <AlertTriangle className="w-2.5 h-2.5 shrink-0" />
                      可能重複上傳
                    </div>
                  )}
                  <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] font-mono">
                    <span className="text-neutral-500">成本 <span className="text-neutral-800 dark:text-neutral-200 font-bold">{money(h.totalCost)}</span></span>
                    <span className="text-neutral-500">獲利 <span className="text-emerald-600 dark:text-emerald-400 font-bold">{win != null ? money(win) : '—'}</span></span>
                    <span className="text-neutral-500">盈虧 <span className={`font-bold ${pnl == null ? 'text-neutral-400' : pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>{pnl != null ? (pnl >= 0 ? '+' : '') + money(pnl) : '—'}</span></span>
                  </div>
                </button>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-neutral-400 font-mono">{fmtTime(h.ts)}</span>
                  <button
                    type="button"
                    onClick={() => (reconTs === h.ts ? setReconTs(null) : openRecon(h.ts))}
                    title="貼對接人帳單,和這一版該日期的流水對帳"
                    className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold transition-colors ${
                      reconTs === h.ts
                        ? 'bg-black text-white dark:bg-white dark:text-black'
                        : 'text-neutral-500 hover:text-black dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5'
                    }`}
                  >
                    <ClipboardCheck className="w-3 h-3" />
                    對帳
                  </button>
                  {onRefill && (
                    <button
                      type="button"
                      onClick={() => onRefill(h.text)}
                      title="把這批文本帶回快速上傳文字框"
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold text-neutral-500 hover:text-black dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                    >
                      <CornerDownLeft className="w-3 h-3" />
                      填回
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => { setVoidErr(null); setVoidTs(voidTs === h.ts ? null : h.ts); }}
                    title="作廢這批上傳:連同它建立的下注紀錄一起刪除"
                    className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold transition-colors ${
                      voidTs === h.ts
                        ? 'bg-rose-600 text-white'
                        : 'text-neutral-500 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-black/5 dark:hover:bg-white/5'
                    }`}
                  >
                    <Ban className="w-3 h-3" />
                    作廢
                  </button>
                </div>
              </div>

              {/* 作廢二次確認:連同這批建立的 ledger 下注一起刪 */}
              {voidTs === h.ts && (
                <div className="px-3 py-2.5 border-b border-black/[0.06] dark:border-white/[0.06] bg-rose-500/[0.06] flex flex-wrap items-center gap-2">
                  <span className="text-[11px] text-rose-700 dark:text-rose-300 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                    作廢後,這批 <strong>{h.count}</strong> 筆下注(成本 {money(h.totalCost)})會從流水中移除,無法從這裡復原。確定?
                  </span>
                  <button
                    type="button"
                    disabled={voidBusy}
                    onClick={() => doVoid(h.ts)}
                    className="px-3 py-1 rounded-lg text-[11px] font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-40 transition-colors"
                  >
                    {voidBusy ? '作廢中…' : '確定作廢'}
                  </button>
                  <button
                    type="button"
                    disabled={voidBusy}
                    onClick={() => setVoidTs(null)}
                    className="px-3 py-1 rounded-lg text-[11px] font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                  >
                    取消
                  </button>
                  {voidErr && <span className="text-[11px] text-rose-600 dark:text-rose-400">{voidErr}</span>}
                </div>
              )}

              {/* 對帳面板:貼帳單 → 比對這一版該日期的流水 */}
              {reconTs === h.ts && (
                <div className="px-3 py-2.5 border-b border-black/[0.06] dark:border-white/[0.06] bg-amber-500/[0.04] space-y-2">
                  <div className="text-[10px] text-neutral-500 dark:text-neutral-400">
                    貼上對接人帳單(含日期/獎號/二三四各支與成本/中碰),比對「{h.editionName}」這一版該日期的流水。
                  </div>
                  <textarea
                    value={billText}
                    rows={7}
                    spellCheck={false}
                    placeholder={`8/24\n539獎號\n09、10、19、23、26\n539牌支\n二2090支 150062\n三 2640支 165000\n四 1050支 51765\n牌支共收366827\n三中4碰 228000\n合計 收 138827`}
                    onChange={e => setBillText(e.target.value)}
                    className="w-full px-2 py-1.5 rounded-lg border border-black/10 dark:border-white/10 bg-white dark:bg-[#121212] text-[11px] font-mono leading-relaxed text-neutral-900 dark:text-white outline-hidden resize-y"
                  />
                  <div className="flex items-center gap-2 flex-wrap">
                    <label className="text-[10px] text-neutral-500 dark:text-neutral-400 flex items-center gap-1">
                      對帳日期
                      <input
                        type="date"
                        value={reconDate}
                        onChange={e => setReconDate(e.target.value)}
                        title="帳單沒寫日期時填這裡(第二種帳單格式)"
                        className="px-1.5 py-1 rounded-md border border-black/10 dark:border-white/10 bg-white dark:bg-[#121212] text-[11px] font-mono text-neutral-900 dark:text-white outline-hidden"
                      />
                    </label>
                    <button
                      type="button"
                      disabled={reconBusy || !billText.trim()}
                      onClick={() => runRecon(h.eid ?? 1)}
                      className="px-3 py-1.5 rounded-lg text-[11px] font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 transition-opacity flex items-center gap-1.5"
                    >
                      <ClipboardCheck className="w-3.5 h-3.5" />
                      {reconBusy ? '比對中…' : '比對'}
                    </button>
                    {recon && (
                      <button
                        type="button"
                        onClick={() => saveRecon(h.ts)}
                        className="px-3 py-1.5 rounded-lg text-[11px] font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                      >
                        {h.reconAt ? '更新保存' : '保存對帳'}
                      </button>
                    )}
                    {h.reconAt && <span className="text-[10px] text-emerald-600 dark:text-emerald-400">已保存 {fmtTime(h.reconAt)}</span>}
                    {reconErr && <span className="text-[11px] text-rose-600 dark:text-rose-400">{reconErr}</span>}
                  </div>
                  {recon && <ReconReport data={recon} />}
                </div>
              )}

              {/* 原始文本(展開才顯示)*/}
              {isOpen && h.text && (
                <pre className="px-3 py-2 text-[10px] font-mono whitespace-pre-wrap break-all text-neutral-500 dark:text-neutral-400 border-b border-black/[0.06] dark:border-white/[0.06] max-h-28 overflow-y-auto">
                  {h.text}
                </pre>
              )}

              {/* 下注明細 + 成本(展開才顯示)*/}
              {isOpen && (
              <table className="w-full text-[11px]">
                <tbody className="font-mono">
                  {h.items.map((it, i) => (
                    <React.Fragment key={i}>
                      <tr className="border-t border-black/[0.05] dark:border-white/[0.05] first:border-t-0">
                        <td className="px-3 pt-1.5 pb-0 align-top">
                          <span className="px-1.5 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-[10px] mr-1.5 font-sans">
                            {MODE_LABEL[it.mode]}
                          </span>
                          <span className="font-sans text-neutral-600 dark:text-neutral-400">{it.playType}</span>
                        </td>
                        <td className="px-3 pt-1.5 pb-0 align-top text-neutral-700 dark:text-neutral-300">
                          {it.balls.length > 0
                            ? it.balls.map(n => String(n).padStart(2, '0')).join(' ')
                            : '—'}
                        </td>
                        <td className="px-3 pt-1.5 pb-0 align-top text-right whitespace-nowrap font-bold text-neutral-900 dark:text-white">
                          {money(it.cost)}
                        </td>
                      </tr>
                      {it.costExpr && (
                        <tr>
                          <td colSpan={3} className="px-3 pt-0 pb-1.5 text-[10px] text-neutral-400 dark:text-neutral-500">
                            {it.costExpr}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-black/10 dark:border-white/10 bg-black/[0.03] dark:bg-white/[0.05]">
                    <td className="px-3 py-1.5 font-sans font-semibold text-neutral-600 dark:text-neutral-300" colSpan={2}>
                      總下注成本
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono font-bold text-neutral-900 dark:text-white">
                      {money(h.totalCost)}
                    </td>
                  </tr>
                </tfoot>
              </table>
              )}
            </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
