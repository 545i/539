import React, {useEffect, useState} from 'react';
import {X, ClipboardPaste, ListChecks, Upload, AlertTriangle, CheckCircle2} from 'lucide-react';
import {api, QuickImportDTO, QuickImportWarningDTO, LedgerMode, TensPairDTO, GameKey} from '../api/client';
import {useAsync} from '../api/useAsync';
import {useAuth} from '../api/useAuth';
import {useGame} from '../api/useGame';
import {useEditions} from '../api/useEditions';
import {
  UploadHistoryEntry, UploadHistoryItem, MODE_LABEL, saveEntry, loadHistory, money,
} from './uploadHistory';

// 快速上傳下注紀錄:貼一段下注文字 → 預覽 → 確認寫進自己的記帳流水。
//
// 解析規則全在後端(backend/routers/importer.py),前端不重算成本 —— 預覽顯示的
// 就是等一下真的會存進去的那份 record,兩邊不會對不起來。
//
// 先「解析預覽」(dry_run)再「確認上傳」是刻意的兩步:文字認錯行的機率不低,
// 直接寫進去要一筆一筆撤銷很麻煩。
//
// 上傳歷史(文本 + 明細 + 逐筆派彩/盈虧)在獨立頁 views/UploadHistoryView;這裡只負責
// 在「確認上傳」成功後把該批寫進後端上傳歷史(見 uploadHistory.ts)。

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onImported?: () => void; // 上傳成功後通知外面重抓流水
  refill?: UploadHistoryEntry | null;  // 從上傳歷史「填回」:帶回整批預填,上傳時作廢原批次(編輯取代)
}

// 預覽裡一列可編輯的解析結果(號碼與支/車可改;連碰另記 stars 供後端重算成本)
interface DraftItem {
  mode: LedgerMode;
  playType: string;
  balls: string; // 使用者可編輯的號碼字串(空白 / 底線 / 逗號分隔)
  units: number;
  stars: number;
  incomplete: boolean;
  hit: string; // 中獎顆數(忘記期數時直接填);空 = 待開獎
  base: number; // 每單位基礎成本(二合每注/連碰每碰…);預設帶版盤口,可逐筆改
}

function parseBalls(s: string): number[] {
  return (s.match(/\d{1,2}/g) ?? []).map(Number).filter(n => n > 0);
}

const SAMPLE = `02x50車
09_15_19_20x20車
02_09_15_19_20_25_28_33
八顆三星1200
八顆四星1200
10_18
20_29
其他400`;


export const QuickImportModal: React.FC<Props> = ({isOpen, onClose, onImported, refill}) => {
  const {loggedIn} = useAuth();
  const {games} = useGame();
  const {editions} = useEditions();
  const [text, setText] = useState('');
  const [issue, setIssue] = useState('');
  const [preview, setPreview] = useState<QuickImportDTO | null>(null);
  const [draftItems, setDraftItems] = useState<DraftItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<number | null>(null);
  // 每筆試算成本 + 計算式(對齊 draftItems;算不出來的 null)
  const [costs, setCosts] = useState<({cost: number; expr: string} | null)[]>([]);
  const [costBusy, setCostBusy] = useState(false);
  // 🟡 防呆提醒(期號格式 / 大車支 / 舊日期 / 重複):黃色列出、不阻斷上傳
  const [warnings, setWarnings] = useState<QuickImportWarningDTO[]>([]);

  // 上傳目標的三要件:全部改成 modal 內部狀態,不再沿用全域 gameKey / 預設 eid。
  // 每次開啟、每次上傳成功後都回到「尚未選擇」,強迫重新確認,避免連續上傳傳錯地方。
  const [selDate, setSelDate] = useState('');            // 日期(YYYY-MM-DD)
  const [selGame, setSelGame] = useState<GameKey | null>(null); // 遊戲
  const [selEid, setSelEid] = useState<number | null>(null);    // 版
  // 期號由「日期 + 遊戲」自動反查,反查不到時的提示訊息
  const [issueHint, setIssueHint] = useState('');
  // 期號狀態:''=尚未查 / 'drawn'=已開有真期號 / 'pending'=合法開獎日未開(可預先記錄,
  // 期號留空、開獎後依日期校正)/ 'closed'=非開獎日(擋)。predictedIssue 為 pending
  // 時純數字款的預估期號,僅顯示提示、不寫進紀錄。
  const [drawStatus, setDrawStatus] = useState<'' | 'drawn' | 'pending' | 'closed'>('');
  const [predictedIssue, setPredictedIssue] = useState('');
  // 填回=編輯取代:記住要取代的原批次 ts,上傳成功後作廢它(刪舊 ledger + 上傳紀錄)
  const [replaceTs, setReplaceTs] = useState<number | null>(null);
  // 去重:偵測到「這個 遊戲+版+日期 已上傳過」時,存那張既有卡片 → 跳覆蓋確認
  const [overwriteTarget, setOverwriteTarget] = useState<UploadHistoryEntry | null>(null);
  // 未來日期防呆:選到今天以後的日期,按上傳時先跳確認(避免手滑選錯日期)
  const [futurePrompt, setFuturePrompt] = useState(false);

  // 每次開啟:三要件回到「尚未選擇」,並清掉上次殘留的預覽 / 橫幅
  useEffect(() => {
    if (!isOpen) return;
    setSelDate('');
    setSelGame(null);
    setSelEid(null);
    setIssue('');
    setIssueHint('');
    setDrawStatus('');
    setPredictedIssue('');
    setPreview(null);
    setDraftItems([]);
    setText('');
    setDone(null);
    setError(null);
    setReplaceTs(null);
    setOverwriteTarget(null);
    setFuturePrompt(false);
    setWarnings([]);
  }, [isOpen]);
  // 從上傳歷史「填回」:預填整批(日期/遊戲/版/文本)並記住原批次 ts。在重置 effect
  // 之後跑,覆蓋「尚未選擇」;上傳成功時作廢原批次 = 編輯取代,不會留下舊的重複批。
  useEffect(() => {
    if (!isOpen || !refill) return;
    setText(refill.text ?? '');
    setSelDate(refill.date ?? '');
    setSelGame(games.find(g => g.name === refill.gameName)?.key ?? null);
    setSelEid(refill.eid ?? null);
    setReplaceTs(refill.ts);
  }, [isOpen, refill, games]);

  // 反查期號:日期 + 遊戲都選好時,用日期去該遊戲的開獎紀錄反查那一天的期號並帶入。
  // 這樣一次上傳流程只需選一次日期,切換遊戲會用同一天自動重新反查(依賴含 selGame)。
  useEffect(() => {
    if (!isOpen) return;
    if (!selDate || !selGame) {
      setIssue(''); setIssueHint(''); setDrawStatus(''); setPredictedIssue('');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const h = await api.history(selGame, 60);
        if (cancelled) return;
        const hit = h.draws.find(d => d.date === selDate);
        if (hit?.issue) {
          setIssue(hit.issue); setIssueHint(''); setDrawStatus('drawn'); setPredictedIssue('');
          return;
        }
        // 已開的裡面找不到,再看看是不是「下一期」(還沒開但期號已定)
        if (h.next?.date === selDate && h.next?.issue) {
          setIssue(h.next.issue); setIssueHint(''); setDrawStatus('drawn'); setPredictedIssue('');
          return;
        }
        // 反查不到期號 → 問後端這天是不是合法開獎日:是的話可預先記錄(期號留空,
        // 開獎後依日期校正回填),不是才擋。
        const r = await api.resolveIssue(selGame, selDate);
        if (cancelled) return;
        if (r.status === 'drawn' && r.issue) {
          setIssue(r.issue); setIssueHint(''); setDrawStatus('drawn'); setPredictedIssue('');
        } else if (r.status === 'pending') {
          setIssue(''); setDrawStatus('pending'); setPredictedIssue(r.predicted || '');
          setIssueHint(r.predicted
            ? `期號未定,開獎後自動校正(預估第 ${r.predicted} 期)`
            : '期號未定,開獎後自動校正');
        } else {
          setIssue(''); setDrawStatus('closed'); setPredictedIssue('');
          setIssueHint('這一天不是這個遊戲的開獎日,請確認日期');
        }
      } catch {
        if (!cancelled) {
          setIssue(''); setDrawStatus(''); setPredictedIssue('');
          setIssueHint('查詢期號失敗,請稍後再試');
        }
      }
    })();
    return () => { cancelled = true; };
  }, [isOpen, selDate, selGame]);

  // 上傳目標就緒:有真期號,或這天是合法開獎日但還沒開(pending,期號留空、
  // 開獎後依日期校正)。pending 也能預覽 / 上傳,期號欄送空字串。
  const canTarget = !!issue || drawStatus === 'pending';

  // 預覽即時試算成本:把目前(可能改過的)draft 丟後端 dry_run commit 只重算不寫入,
  // 拿回每筆 record.cost / costExpr。debounce 350ms,避免打字時一直打 API。
  // ⚠ 必須在任何 early return 之前(Hooks 規則);開啟且有 preview 才真的算。
  useEffect(() => {
    if (!isOpen || !preview || draftItems.length === 0 || !loggedIn
        || selGame == null || selEid == null || !canTarget) {
      setCosts([]);
      return;
    }
    let cancelled = false;
    setCostBusy(true);
    const t = window.setTimeout(async () => {
      try {
        const items = draftItems.map(d => ({
          mode: d.mode,
          selectedBalls: parseBalls(d.balls),
          units: d.units,
          stars: d.stars,
          hit_count: d.hit.trim() === '' ? null : Math.max(0, Math.floor(Number(d.hit) || 0)),
          base_cost: d.base > 0 ? d.base : null,
        }));
        const res = await api.quickImportCommit(selGame, items, {issue, edition: selEid, date: selDate, dryRun: true});
        if (cancelled) return;
        // 🟡 提醒依「編輯後」的 draft 重算(重複 / 大車支會隨改動即時更新)
        setWarnings(res.warnings ?? []);
        // 後端把算不出來的收進 errors(line_no = 1-based draft 序),其餘依序在 items
        const errLines = new Set(res.errors.map(e => e.line_no));
        const arr: ({cost: number; expr: string} | null)[] = [];
        let k = 0;
        for (let i = 1; i <= items.length; i++) {
          if (errLines.has(i)) {
            arr.push(null);
          } else {
            const rec = res.items[k]?.record ?? {};
            arr.push({cost: typeof rec.cost === 'number' ? rec.cost : 0, expr: String(rec.costExpr ?? '')});
            k++;
          }
        }
        setCosts(arr);
      } catch {
        if (!cancelled) setCosts([]);
      } finally {
        if (!cancelled) setCostBusy(false);
      }
    }, 350);
    return () => { cancelled = true; window.clearTimeout(t); };
  }, [isOpen, draftItems, issue, canTarget, selEid, selGame, selDate, preview, loggedIn]);

  // 區間斷檔提醒(參考用):依目前選的遊戲,只顯示未開(streak>=1)的配對。
  // 門檻用 1(每期+1):只要一期沒開就算斷檔並高亮,不等到 3 期。
  const pairs = useAsync<TensPairDTO[]>(
    () => (isOpen && selGame ? api.tensPairs(selGame, 1) : Promise.resolve([])),
    [selGame, isOpen],
  );
  const brokenPairs = (pairs.data ?? []).filter(p => p.streak >= 1);

  if (!isOpen) return null;

  const reset = () => {
    setPreview(null);
    setDraftItems([]);
    setError(null);
    setDone(null);
    setWarnings([]);
  };

  const num = (v: unknown) => (typeof v === 'number' ? v : 0);

  // 解析預覽:把文字丟後端 dry_run,回來的每筆變成一列可編輯的 draft
  const runPreview = async () => {
    if (!selGame || selEid == null || !selDate || !canTarget) return; // 三要件 + 期號就緒(或合法開獎日待開)才給預覽
    setBusy(true);
    setError(null);
    try {
      const res = await api.quickImport(selGame, text, true, {issue, edition: selEid, date: selDate});
      setPreview(res);
      setWarnings(res.warnings ?? []);
      setDraftItems(
        res.items.map(it => ({
          mode: it.mode,
          playType: String(it.record.playType ?? ''),
          balls: ((it.record.selectedBalls as number[]) ?? [])
            .map(n => String(n).padStart(2, '0'))
            .join(' '),
          units: num(it.record.units),
          stars: num(it.record.stars),
          incomplete: Boolean(it.record.incomplete),
          hit: '',
          base: num(it.record.baseCost),
        })),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // 實際送出:可帶 replaceOverride(要覆蓋的舊批 ts)。**先刪舊、再寫新**——
  // 覆蓋失敗就中止、不寫新,避免新舊並存造成重複(見去重設計)。
  const doCommit = async (replaceOverride?: number) => {
    if (!selGame || selEid == null || !selDate || !canTarget) return;
    const toReplace = replaceOverride ?? replaceTs ?? undefined;
    setBusy(true);
    setError(null);
    try {
      // 覆蓋:先作廢舊批(連同它的 ledger 下注一起刪);刪不掉就中止,不寫新的
      if (toReplace != null) {
        await api.uploadHistoryDelete(toReplace);
      }
      const res = await api.quickImportCommit(
        selGame,
        draftItems.map(d => ({
          mode: d.mode,
          selectedBalls: parseBalls(d.balls),
          units: d.units,
          stars: d.stars,
          hit_count: d.hit.trim() === '' ? null : Math.max(0, Math.floor(Number(d.hit) || 0)),
          base_cost: d.base > 0 ? d.base : null,
        })),
        {issue, edition: selEid, date: selDate},
      );
      // 下注明細 + 總成本:全用後端重算後的 record(前端不重算金額)
      const detail: UploadHistoryItem[] = res.items.map(it => ({
        mode: it.mode,
        playType: String(it.record.playType ?? ''),
        balls: (it.record.selectedBalls as number[]) ?? [],
        units: num(it.record.units),
        cost: num(it.record.cost),
        costExpr: String(it.record.costExpr ?? ''),
      }));
      const totalCost = detail.reduce((s, d) => s + d.cost, 0);
      const entry: UploadHistoryEntry = {
        ts: Date.now(),
        gameName: games.find(x => x.key === selGame)?.name ?? selGame,
        editionName: editions.find(e => e.eid === selEid)?.name ?? String(selEid),
        eid: selEid,
        issue,
        date: selDate,     // 存這一期日期,上傳歷史列表顯示「第 X 期(日期)」對帳好認
        text,
        count: res.saved,
        totalCost,
        items: detail,
        // 記下這批建立的 ledger id → 作廢時精準刪這些,也讓上傳歷史頁逐筆接回派彩
        // (與 items 同序,UploadHistoryView 靠 index 對齊)
        entryIds: res.items.map(it => it.id).filter((x): x is number => x != null),
      };
      // 寫進後端上傳歷史(獨立頁 UploadHistoryView 讀取);未登入靜默略過
      await saveEntry(entry);
      setReplaceTs(null);
      setOverwriteTarget(null);
      onImported?.();
      // 不自動關閉:讓使用者看到成功訊息;歷史到「上傳歷史」彈窗查看
      setDone(res.saved);
      setText('');
      setPreview(null);
      setDraftItems([]);
      // 三要件回到「尚未選擇」,強迫下一批重新確認日期 / 遊戲 / 版,避免沿用傳錯地方
      setSelDate('');
      setSelGame(null);
      setSelEid(null);
      setIssue('');
      setIssueHint('');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // 今天(台灣本機日期,YYYY-MM-DD);選到今天以後就是「未來日期」
  const todayStr = new Date().toLocaleDateString('en-CA');
  const isFutureDate = !!selDate && selDate > todayStr;

  // 確認上傳(閘門):先擋未來日期,再查是否已上傳過 —— 兩關都過才真的送。
  // skipFutureCheck:未來日期確認過後再進來時跳過那一關。
  const confirm = async (skipFutureCheck = false) => {
    if (!selGame || selEid == null || !selDate || !canTarget) return;
    // 未來日期防呆:選到今天以後的日期 → 先跳確認(避免手滑把日期選錯)
    if (!skipFutureCheck && isFutureDate) { setFuturePrompt(true); return; }
    const selGameName = games.find(x => x.key === selGame)?.name ?? selGame;
    try {
      const hist = await loadHistory();
      const conflict = hist.find(h =>
        h.gameName === selGameName && h.eid === selEid && h.date === selDate
        && h.ts !== replaceTs);
      if (conflict) { setOverwriteTarget(conflict); return; }  // 跳確認,先不送
    } catch { /* 讀不到歷史就當沒衝突,照常送 */ }
    await doCommit();
  };

  const costTotal = costs.reduce((s, c) => s + (c ? c.cost : 0), 0);

  const setDraft = (i: number, patch: Partial<DraftItem>) =>
    setDraftItems(prev => prev.map((d, j) => (j === i ? {...d, ...patch} : d)));

  const errors = preview?.errors ?? [];
  const anyIncomplete = draftItems.some(d => d.incomplete);

  // 三要件就緒判斷:日期 / 遊戲 / 版 任一未選,或期號未就緒(反查不到又非合法開獎日),
  // 就不給預覽 / 上傳。pending(合法開獎日待開,期號留空、開獎後校正)也算就緒。
  const missingSel: string[] = [];
  if (!selDate) missingSel.push('日期');
  if (!selGame) missingSel.push('遊戲');
  if (selEid == null) missingSel.push('版');
  const targetReady = missingSel.length === 0 && canTarget;
  const selGameName = games.find(x => x.key === selGame)?.name ?? '';
  const selGameShort = games.find(x => x.key === selGame)?.short_name ?? '';
  const selEditionName = selEid == null ? '' : (editions.find(e => e.eid === selEid)?.name ?? String(selEid));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        id="quick-import-modal-content"
        className="w-full max-w-3xl max-h-[90vh] bg-white dark:bg-[#121212] border border-black/10 dark:border-white/10 rounded-2xl shadow-2xl flex flex-col text-neutral-800 dark:text-neutral-200"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.08] dark:border-white/[0.08] shrink-0">
          <div className="flex items-center gap-2 font-display font-bold text-base text-neutral-900 dark:text-white uppercase tracking-wide">
            <ClipboardPaste className="w-4 h-4 text-neutral-500" />
            <span>快速上傳下注紀錄</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            id="close-quick-import-btn"
            className="p-1.5 rounded-full text-neutral-400 hover:text-neutral-700 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-4 overflow-y-auto">
          {!loggedIn && (
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-800 dark:text-amber-300 flex items-start gap-2">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>快速上傳要先登入 —— 紀錄是記在你的帳號底下的。</span>
            </div>
          )}

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                上傳到哪款
              </label>
              <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
                {games.map(g => (
                  <button
                    key={g.key}
                    type="button"
                    onClick={() => { setSelGame(g.key); reset(); }} // modal 內自己選,不再全域切換
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      selGame === g.key
                        ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                    }`}
                  >
                    {g.short_name}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                上傳到哪版
              </label>
              <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1 flex-wrap">
                {editions.map(e => (
                  <button
                    key={e.eid}
                    type="button"
                    onClick={() => { setSelEid(e.eid); reset(); }} // 本地選版,初始無任何版高亮
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      selEid === e.eid
                        ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                    }`}
                  >
                    {e.name}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                下注日期(整批只選一次)
              </label>
              <div className="flex items-center gap-2 flex-wrap">
                <input
                  id="quick-import-date"
                  type="date"
                  value={selDate}
                  onChange={e => { setSelDate(e.target.value); reset(); }}
                  title="先選日期,切換遊戲時會用這一天自動反查期號"
                  className="h-8 px-2.5 rounded-lg border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-xs font-mono text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40"
                />
                {/* 反查到的期號(唯讀顯示);由日期 + 遊戲決定 */}
                <span
                  id="quick-import-issue"
                  className="h-8 min-w-24 inline-flex items-center px-2.5 rounded-lg border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-xs font-mono text-neutral-900 dark:text-white"
                >
                  {issue
                    ? `第 ${issue} 期`
                    : drawStatus === 'pending'
                      ? (predictedIssue ? `第 ${predictedIssue} 期(預估)` : '期號未定')
                      : (selDate && selGame ? '查無期號' : '待選日期/遊戲')}
                </span>
              </div>
              {issueHint && (
                <div className={`mt-1 text-[10px] ${
                  drawStatus === 'pending'
                    ? 'text-sky-700 dark:text-sky-400'
                    : 'text-amber-700 dark:text-amber-400'
                }`}>{issueHint}</div>
              )}
            </div>
            <div className="text-[11px] text-neutral-500 dark:text-neutral-400 pb-2.5">
              {targetReady ? (
                <>記到 <strong>{selGameName}・{selEditionName}・{
                  issue ? `第 ${issue} 期` : (predictedIssue ? `第 ${predictedIssue} 期(預估)` : '期號未定')
                }{selDate ? `(${selDate})` : ''}</strong>,結果一律先記「待開獎」,{
                  issue ? '開獎後再結算' : '開獎後依日期自動校正期號並結算'}。</>
              ) : (
                <>尚未選好上傳目標:請先選擇 <strong>{missingSel.length ? missingSel.join(' / ') : '期號(依日期反查)'}</strong>。</>
              )}
            </div>
          </div>

          {/* 區間斷檔提醒(參考用):依目前遊戲,只顯示未開的區段配對 */}
          <div className="rounded-xl border border-black/[0.08] dark:border-white/[0.08] bg-black/[0.02] dark:bg-white/[0.03] p-3 space-y-2">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>1800碰斷檔提醒（{selGameShort || '尚未選遊戲'}・參考）</span>
            </div>
            {!selGame && (
              <div className="text-[11px] text-neutral-400">先在上方選一款遊戲才顯示斷檔提醒。</div>
            )}
            {selGame && pairs.loading && <div className="text-[11px] text-neutral-400">載入中…</div>}
            {selGame && !pairs.loading && brokenPairs.length === 0 && (
              <div className="text-[11px] text-neutral-400">
                各十位區段近期都有開出，目前沒有連續未開的組合。
              </div>
            )}
            <div className="flex flex-wrap gap-1.5">
              {brokenPairs.map(p => (
                <span
                  key={`${p.bands[0]}-${p.bands[1]}`}
                  className={`px-2 py-1 rounded-lg text-[11px] font-mono ${
                    p.alert
                      ? 'bg-amber-500/15 text-amber-800 dark:text-amber-300 border border-amber-500/30 font-bold'
                      : 'bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300'
                  }`}
                  title={`${p.range[0]} × ${p.range[1]}`}
                >
                  {p.labels[0]}×{p.labels[1]} {p.streak}期未開
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
              下注文字
            </label>
            <textarea
              id="quick-import-text"
              value={text}
              rows={9}
              spellCheck={false}
              placeholder={SAMPLE}
              onChange={e => {
                setText(e.target.value);
                reset();
              }}
              className="w-full px-3 py-2.5 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-sm font-mono leading-relaxed text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40 transition-colors resize-y"
            />
            <div className="mt-2 text-[10px] text-neutral-400 leading-relaxed space-y-0.5">
              <div>下注行<strong>依出現順序</strong>歸組:第 1 行 → 1組、第 2 行 → 2組。<code>21_24x20車</code> = 20 車(<strong>車字可省略</strong>,<code>21_24x20</code> 也認)</div>
              <div>一行選號 + <code>八顆三星1200</code> = 星碰三星(不足八顆會自動往上補足,可在預覽手改)</div>
              <div><code>10_18</code> / <code>20_29</code> / <code>其他400</code> 三行 = 1800碰 4 支</div>
            </div>
          </div>

          {error && (
            <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-700 dark:text-rose-400">
              {error}
            </div>
          )}

          {done !== null && (
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-800 dark:text-emerald-300 flex items-start gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>已寫入 {done} 筆,各記帳分頁重新整理後就看得到。</span>
            </div>
          )}

          {preview && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
                <ListChecks className="w-3.5 h-3.5" />
                <span>解析出 {draftItems.length} 筆(號碼與支/車可直接改,成本上傳時後端重算)</span>
              </div>

              {draftItems.length > 0 && (
                <div className="rounded-xl border border-black/[0.08] dark:border-white/[0.08] overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead className="bg-black/[0.03] dark:bg-white/[0.04] text-neutral-500">
                      <tr>
                        <th className="px-3 py-2 text-left font-semibold">玩法</th>
                        <th className="px-3 py-2 text-left font-semibold">號碼(可編輯)</th>
                        <th className="px-3 py-2 text-right font-semibold">支 / 車</th>
                        <th className="px-3 py-2 text-right font-semibold">基礎成本<br/><span className="font-normal text-[9px]">每注/每碰·可改</span></th>
                        <th className="px-3 py-2 text-right font-semibold">中獎顆數<br/><span className="font-normal text-[9px]">忘記期數可填</span></th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      {draftItems.map((d, i) => (
                        <React.Fragment key={i}>
                        <tr
                          className={`border-t border-black/[0.06] dark:border-white/[0.06] ${
                            d.incomplete ? 'bg-amber-500/10' : ''
                          }`}
                        >
                          <td className="px-3 py-2 font-sans align-top">
                            <span className="px-1.5 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-[10px] mr-1.5">
                              {MODE_LABEL[d.mode]}
                            </span>
                            {d.playType}
                            {d.incomplete && (
                              <div className="text-[10px] text-amber-700 dark:text-amber-400 mt-0.5">
                                ⚠ 顆數不足,請手動補齊號碼
                              </div>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <input
                              value={d.balls}
                              onChange={e => setDraft(i, {balls: e.target.value})}
                              spellCheck={false}
                              className="w-full px-2 py-1 rounded-lg border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-[11px] font-mono text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40"
                            />
                            <span className="text-[10px] text-neutral-400">
                              {parseBalls(d.balls).length} 顆
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right align-top">
                            <input
                              type="number"
                              min={1}
                              value={d.units}
                              onChange={e => setDraft(i, {units: Number(e.target.value)})}
                              className="w-16 px-2 py-1 rounded-lg border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-[11px] font-mono text-right text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40"
                            />
                          </td>
                          <td className="px-3 py-2 text-right align-top">
                            <input
                              type="number"
                              min={0}
                              step="0.1"
                              value={d.base}
                              onChange={e => setDraft(i, {base: Number(e.target.value)})}
                              title="這筆的每單位基礎成本(二合每注 / 連碰每碰…);預設帶版盤口,改了只影響這一筆"
                              className="w-20 px-2 py-1 rounded-lg border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-[11px] font-mono text-right text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40"
                            />
                          </td>
                          <td className="px-3 py-2 text-right align-top">
                            <input
                              type="number"
                              min={0}
                              value={d.hit}
                              placeholder="待開獎"
                              onChange={e => setDraft(i, {hit: e.target.value})}
                              title="填了就直接依這個中獎數結算(不必期數);留空 = 待開獎"
                              className="w-16 px-2 py-1 rounded-lg border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-[11px] font-mono text-right text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40"
                            />
                          </td>
                        </tr>
                        {/* 成本解析:這一筆成本是怎麼算出來的 */}
                        <tr
                          key={`cost-${i}`}
                          className={`border-t-0 ${d.incomplete ? 'bg-amber-500/10' : ''}`}
                        >
                          <td colSpan={5} className="px-3 pb-2 pt-0">
                            <div className="flex items-baseline justify-between gap-2 text-[10px] text-neutral-500 dark:text-neutral-400">
                              <span className="font-mono">
                                {costs[i]
                                  ? (costs[i]!.expr || '—')
                                  : (costBusy ? '試算中…' : '—')}
                              </span>
                              <span className="font-mono font-bold text-neutral-800 dark:text-neutral-200 whitespace-nowrap">
                                {costs[i] ? money(costs[i]!.cost) : ''}
                              </span>
                            </div>
                          </td>
                        </tr>
                      </React.Fragment>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="border-t-2 border-black/10 dark:border-white/15 bg-black/[0.03] dark:bg-white/[0.05]">
                        <td colSpan={3} className="px-3 py-2 text-right font-sans font-semibold text-neutral-700 dark:text-neutral-200">
                          總下注成本{costBusy && ' (試算中…)'}
                        </td>
                        <td className="px-3 py-2 text-right font-mono font-bold text-neutral-900 dark:text-white whitespace-nowrap">
                          {money(costTotal)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}

              {errors.length > 0 && (
                <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-700 dark:text-rose-400 space-y-1">
                  <div className="flex items-center gap-2 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>{errors.length} 行不會被記進去(看不懂 / 遊戲不支援的下法)</span>
                  </div>
                  {errors.map((e, i) => (
                    <div key={i} className="font-mono">
                      第 {e.line_no} 行{e.line ? `「${e.line}」` : ''}—— {e.message}
                    </div>
                  ))}
                </div>
              )}

              {/* 🟡 防呆提醒:黃色列出、不阻斷上傳(期號格式 / 大車支 / 舊日期 / 重複) */}
              {warnings.length > 0 && (
                <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-800 dark:text-amber-300 space-y-1">
                  <div className="flex items-center gap-2 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>{warnings.length} 項提醒(可照樣上傳,但請先確認)</span>
                  </div>
                  {warnings.map((w, i) => (
                    <div key={i} className="font-mono">
                      {w.line_no ? `第 ${w.line_no} 筆:` : ''}{w.message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 上傳歷史已抽成獨立頁 UploadHistoryView(見側欄「上傳歷史」或下注頁的「上傳歷史」鈕) */}
        </div>

        {/* 未來日期確認:選到今天以後的日期 → 先確認是不是真的要記到那天 */}
        {futurePrompt && (
          <div className="px-6 py-3 border-t border-sky-500/30 bg-sky-500/[0.07] space-y-2 shrink-0">
            <div className="flex items-start gap-1.5 text-[12px] text-sky-800 dark:text-sky-300">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>
                你選的下注日期是 <strong>{selDate}(第 {Number(selDate.slice(8, 10))} 天)</strong>,
                比今天 <strong>{todayStr}(第 {Number(todayStr.slice(8, 10))} 天)</strong> 還晚 ——
                這是<strong>未來、還沒開獎</strong>的日期。<br />
                確定要把這批下注記到 <strong>{selDate}</strong> 嗎?(通常是記今天或補記過去的期別)
              </span>
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => setFuturePrompt(false)}
                className="py-1.5 px-3 rounded-lg text-[11px] font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-40 transition-colors"
              >
                取消,我要改日期
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => { setFuturePrompt(false); confirm(true); }}
                className="py-1.5 px-3 rounded-lg text-[11px] font-semibold bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-40 transition-colors"
              >
                確定,記到 {selDate}
              </button>
            </div>
          </div>
        )}

        {/* 覆蓋確認:偵測到同 遊戲+版+日期 已上傳過 → 列出將被覆蓋的紀錄,確認才送 */}
        {overwriteTarget && (
          <div className="px-6 py-3 border-t border-amber-500/30 bg-amber-500/[0.06] space-y-2 shrink-0">
            <div className="flex items-start gap-1.5 text-[11px] text-amber-800 dark:text-amber-300">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>
                <strong>{overwriteTarget.gameName}・{overwriteTarget.editionName}・{overwriteTarget.date}</strong> 已經上傳過
                (<strong>{overwriteTarget.count} 筆・{money(overwriteTarget.totalCost)}</strong>)。
                送出會<strong>覆蓋</strong>以下紀錄:
              </span>
            </div>
            <div className="rounded-lg border border-amber-500/20 bg-white/60 dark:bg-black/20 divide-y divide-black/[0.04] dark:divide-white/[0.04] max-h-32 overflow-y-auto">
              {overwriteTarget.items.map((it, i) => (
                <div key={i} className="flex items-center justify-between gap-2 px-2.5 py-1 text-[10px]">
                  <span className="font-sans text-neutral-600 dark:text-neutral-300 shrink-0">{MODE_LABEL[it.mode]} {it.playType}</span>
                  <span className="font-mono text-neutral-500 truncate">{it.balls.map(b => String(b).padStart(2, '0')).join(' ') || '—'}</span>
                  <span className="font-mono font-bold text-neutral-800 dark:text-neutral-200 shrink-0">{money(it.cost)}</span>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => setOverwriteTarget(null)}
                className="py-1.5 px-3 rounded-lg text-[11px] font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-40 transition-colors"
              >
                取消
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => doCommit(overwriteTarget.ts)}
                className="py-1.5 px-3 rounded-lg text-[11px] font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-40 transition-colors flex items-center gap-1.5"
              >
                <Upload className="w-3.5 h-3.5" />
                {busy ? '覆蓋中…' : '確認覆蓋並送出'}
              </button>
            </div>
          </div>
        )}

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-black/[0.08] dark:border-white/[0.08] shrink-0">
          {!targetReady && (
            <span className="mr-auto text-[11px] text-amber-700 dark:text-amber-400">
              請先選擇 {missingSel.length ? missingSel.join(' / ') : '期號(依日期反查)'}
            </span>
          )}
          <button
            type="button"
            id="quick-import-preview-btn"
            disabled={busy || !text.trim() || !loggedIn || !targetReady}
            onClick={runPreview}
            className="py-2.5 px-4 rounded-xl text-xs uppercase tracking-wider font-semibold bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 transition-colors flex items-center gap-2"
          >
            <ListChecks className="w-4 h-4" />
            {busy ? '處理中…' : '解析預覽'}
          </button>
          <button
            type="button"
            id="quick-import-submit-btn"
            // 一定要先預覽過、而且真的有解析出東西才給上傳;三要件未齊也不給
            disabled={busy || !loggedIn || draftItems.length === 0 || done !== null || !targetReady || overwriteTarget != null || futurePrompt}
            onClick={() => confirm()}
            title={anyIncomplete ? '仍有顆數不足的列,建議先補齊再上傳' : ''}
            className="py-2.5 px-4 rounded-xl text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 transition-opacity flex items-center gap-2 shadow-xs active:scale-98"
          >
            <Upload className="w-4 h-4" />
            確認上傳{draftItems.length > 0 ? ` ${draftItems.length} 筆` : ''}
          </button>
        </div>
      </div>
    </div>
  );
};
