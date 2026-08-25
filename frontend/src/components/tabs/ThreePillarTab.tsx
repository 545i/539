import React, { useState } from 'react';
import {
  ChevronRight,
  ChevronDown,
  AlertTriangle,
  FileText,
  CheckCircle2,
  XCircle,
  Layers,
  RotateCcw,
  RefreshCw,
  Minus,
  Plus
} from 'lucide-react';
import { INITIAL_PILLAR_RECORDS, PILLAR_THEORY_ROWS } from '../../data/lotteryData';
import { LotteryGame } from '../../types';
import { api, PillarInfoDTO, TensPairDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';
import { useLedger } from '../../api/useLedger';
import { useEditions } from '../../api/useEditions';
import { LotteryBallPad } from '../LotteryBallPad';
import { IssuePicker } from '../IssuePicker';

const pad = (n: number) => n.toString().padStart(2, '0');

// 柱位標題:連號就寫成「10 ~ 18」,像第三柱那種 01~09 + 19 + 30~39 就別假裝是一段
const pillarRange = (nums: number[]): string => {
  if (nums.length === 0) return '—';
  const lo = nums[0];
  const hi = nums[nums.length - 1];
  return hi - lo + 1 === nums.length ? `${pad(lo)} ~ ${pad(hi)}` : '不連續區段';
};

export const ThreePillarTab: React.FC = () => {
  // 遊戲由 Header 的全域切換器決定;三柱只有 39 選 5 的款玩得起來(supports_pillar)
  const { game: gameCfg, gameKey, loading: gameLoading } = useGame();
  const { eid, combineEditions } = useEditions();
  // 這個版 × 這款遊戲的盤口(1800碰每注成本 / 中一注可得)
  const oddsReq = useAsync(() => api.getEditionOdds(eid, gameKey), [eid, gameKey]);
  const odds = oddsReq.data?.fields;
  // 登入時流水存後端;未登入沿用 v2 的前端 state。依版篩選
  const ledger = useLedger('pillar1800', INITIAL_PILLAR_RECORDS, {edition: eid, combine: combineEditions, game: gameCfg?.name});
  const records = ledger.records;
  const [units, setUnits] = useState<number>(1);
  // 期號 / 日期:預設帶最新一期,使用者可用下拉選單改記到別期(補記 / 修期)
  const histReq = useAsync(() => api.history(gameKey, 30), [gameKey]);
  const latest = histReq.data?.latest ?? null;
  const draws = histReq.data?.draws ?? [];
  // 下一期(還沒開):給核對列的期號選擇器當常駐選項,讓「最新未開一期」永遠選得到
  const nextOpt = histReq.data?.next ?? undefined;
  const [issue, setIssue] = useState<string>('');
  const [issueTouched, setIssueTouched] = useState(false);
  const [betDate, setBetDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
  React.useEffect(() => {
    if (issueTouched) return;
    if (latest?.issue) setIssue(latest.issue);
    if (latest?.date) setBetDate(latest.date);
  }, [latest?.issue, latest?.date, issueTouched]);
  const pickIssue = (iss: string, d: string) => {
    setIssue(iss);
    setBetDate(d);
    setIssueTouched(true);
  };
  const [isTheoryOpen, setIsTheoryOpen] = useState(false);
  const [selectedBalls, setSelectedBalls] = useState<number[]>([]);
  // 自選手動組柱:已保存的各柱號碼(不再自動依範圍歸柱)
  const [savedPillars, setSavedPillars] = useState<number[][]>([]);
  // 備援「一鍵對獎」狀態
  const [settleBusy, setSettleBusy] = useState(false);
  const [settleMsg, setSettleMsg] = useState<string | null>(null);

  const supported = !!gameCfg?.supports_pillar;

  // 三柱基本盤(注數 / 過關率)—— 不適用的遊戲就不打後端
  const infoReq = useAsync<PillarInfoDTO | null>(
    () => (supported ? api.pillarInfo(gameKey) : Promise.resolve(null)),
    [gameKey, supported],
  );
  const totalBets = infoReq.data ? infoReq.data.total_bets : 0;
  const passProb = infoReq.data ? infoReq.data.pass_prob : null;
  // 柱位切法也讀後端,不在前端寫死 9/10/20
  const pillars: number[][] = infoReq.data ? infoReq.data.pillars : [[], [], []];
  const sizes: number[] = infoReq.data ? infoReq.data.sizes : [0, 0, 0];

  // 區間組合斷檔提醒
  const pairsReq = useAsync<TensPairDTO[] | null>(
    () => (supported ? api.tensPairs(gameKey, 3) : Promise.resolve(null)),
    [gameKey, supported],
  );

  const totalSpent = records.reduce((acc, r) => acc + r.cost, 0);
  const totalReturn = records.reduce((acc, r) => acc + r.payout, 0);
  const cumPnl = records.length > 0 ? records[records.length - 1].cumPnl : 0;
  const winCount = records.filter(r => r.payout > 0).length;

  if (!gameCfg) {
    return (
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
        {gameLoading ? '載入遊戲設定中…' : '讀不到遊戲設定,請重新整理頁面。'}
      </div>
    );
  }

  // 三柱 1800 碰是把 39 顆切成 9 / 10 / 20 三柱,49 選 6 的六合彩沒有這種盤 ——
  // 與其拿 39 選 5 的數字硬算給別款看,不如明講不適用。
  if (!supported) {
    return (
      <div className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-2.5 animate-in fade-in duration-200">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-amber-600 dark:text-amber-400" />
          <span className="text-sm font-display font-bold text-neutral-900 dark:text-white">
            {gameCfg.short_name}不適用三柱 1800 碰
          </span>
        </div>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed">
          三柱 1800 碰是把 39 顆號碼切成 9 × 10 × 20 三柱包牌的玩法,只有
          今彩539 與天天樂(都是 39 選 5)適用;{gameCfg.short_name}是
          {gameCfg.num_max} 選 {gameCfg.pick},柱位切法與注數都對不起來。
        </p>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          請用上方的彩券切換器改成今彩539 或天天樂。
        </p>
      </div>
    );
  }

  const game = gameCfg.name as LotteryGame;
  // 每注成本 / 中一注可得取「這個版」的盤口;讀不到先用 GameConfig 預設
  const betCost = odds?.bet_cost?.value ?? gameCfg.default_bet_cost;
  const betPrize = odds?.bet_prize?.value ?? gameCfg.default_bet_prize;
  const prize4 = 4 * betPrize;
  const prize3 = 3 * betPrize;

  // ── 三柱組牌(自選逐柱 / 一鍵全包)+ 支數倍投 ─────────────────────
  const PILLAR_NAMES = ['第一柱', '第二柱', '第三柱', '第四柱', '第五柱'];
  // 已被保存到某柱的號碼(同一顆不重複進兩柱)
  const usedInPillars = new Set(savedPillars.flat());
  const NUM_SLOTS = sizes.length || 3;   // 三柱固定 3 個柱位
  const allNumbers = Array.from({ length: gameCfg.num_max }, (_, i) => i + 1);
  // 你沒放進任何柱的號碼(自動補第三柱用;用「剩餘」而非固定範圍 → 不會重疊)
  const remainingNums = allNumbers.filter(n => !usedInPillars.has(n));
  // 三柱一律湊滿:自訂 2 柱 → 第三柱 = 剩下的號碼全包;自訂 3 柱 → 全照你的;不足 2 柱不成立
  const effectivePillars: number[][] =
    savedPillars.length >= NUM_SLOTS ? savedPillars.slice(0, NUM_SLOTS)
      : savedPillars.length === NUM_SLOTS - 1 ? [...savedPillars, remainingNums]
        : [];
  const effSizes = effectivePillars.map(p => p.length);
  const customCount = savedPillars.filter(p => p.length > 0).length;
  // 過關注數 = 三柱各顆數相乘;支數再倍投
  const comboBets = (effectivePillars.length === NUM_SLOTS && effSizes.every(s => s > 0))
    ? effSizes.reduce((a, b) => a * b, 1) : 0;
  const betsWithUnits = comboBets * units;
  const submitCost = betsWithUnits * betCost;
  const canSubmit = comboBets > 0;
  // 全包 = 三柱剛好 1800 注,此時額外顯示過關機率/彩金
  const isFullWheel = comboBets === totalBets;

  // 保存目前選取為下一柱(排除已在其他柱的號碼);最多 3 柱
  const savePillar = () => {
    if (savedPillars.length >= NUM_SLOTS) return;
    const fresh = selectedBalls.filter(n => !usedInPillars.has(n));
    if (fresh.length === 0) return;
    setSavedPillars(prev => [...prev, [...fresh].sort((a, b) => a - b)]);
    setSelectedBalls([]);
  };
  const removePillar = (i: number) =>
    setSavedPillars(prev => prev.filter((_, j) => j !== i));
  // 一鍵帶入固定柱範圍當作目前選取(方便快速組牌)
  const presetFromFixed = (i: number) =>
    setSelectedBalls((pillars[i] || []).filter(n => !usedInPillars.has(n)));
  // 一鍵全包:三柱各自全選(固定 9/10/20)→ 1800 注
  const loadFullWheel = () => {
    setSavedPillars(pillars.map(p => [...p]));
    setSelectedBalls([]);
  };

  const handleSubmit = () => {
    if (!canSubmit) return;
    ledger.add({
      date: betDate,
      issue,
      game,
      mode: 'pillar1800',
      edition: eid,
      units,
      cars: units,
      betsCount: betsWithUnits,
      selectedBalls: effectivePillars.flat(),
      drawBalls: [],
      pillars: effectivePillars,          // 三柱(含自動全包的柱)→ 對獎依各柱∩開獎相乘
      pillarDist: effSizes.join(' × '),
      result: '待開獎',
      cost: submitCost,
      payout: 0,
      pnl: 0,
    });
    setSavedPillars([]);
    setSelectedBalls([]);
  };

  // 備援:一鍵把所有「待開獎」且該期已開的紀錄自動對獎,再重抓流水
  const handleSettlePending = async () => {
    setSettleBusy(true);
    setSettleMsg(null);
    try {
      const res = await api.ledgerSettlePending();
      ledger.reload();
      setSettleMsg(res.settled > 0 ? `已自動對獎 ${res.settled} 筆` : '沒有待對獎的紀錄(都對過了)');
    } catch (e) {
      setSettleMsg((e as Error).message);
    } finally {
      setSettleBusy(false);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-5 animate-in fade-in duration-200 w-full overflow-hidden">
      {/* Top Banner Bar */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.25em] text-neutral-400 dark:text-neutral-500 font-semibold">
              Three Pillars Matrix (1800 Bets)
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              {gameCfg.short_name}
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              過關率 {passProb !== null ? `${(passProb * 100).toFixed(2)}%` : '—'}
            </span>
          </div>
          <div className="text-base sm:text-xl font-display font-bold text-neutral-900 dark:text-white mt-0.5">
            三柱 1800 碰包牌控制台
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            包下 {sizes.join('×')} = {totalBets.toLocaleString()} 注全組合，三柱各開出 1 顆即保證過關獲利。
          </div>
        </div>

        <div className="flex items-center justify-between md:justify-end gap-4 border-t md:border-t-0 pt-2.5 md:pt-0 border-black/[0.06] dark:border-white/[0.06]">
          <div className="text-left md:text-right">
            <span className="text-[10px] uppercase tracking-wider text-neutral-400 block">三柱累積損益</span>
            <div className={`text-xl sm:text-2xl font-mono font-bold ${cumPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {cumPnl >= 0 ? `+${cumPnl.toLocaleString()}` : cumPnl.toLocaleString()}
            </div>
          </div>
          <div className="text-right text-[11px] font-mono text-neutral-400">
            {records.length} 局・過關 {winCount} 局
          </div>
        </div>
      </div>

      {/* Main Dual-Column Workbench Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-5">
        
        {/* Left Column (5/12) - Configuration & Execution Panel */}
        <div className="lg:col-span-5 flex flex-col gap-4">

          {/* 三柱 1800 碰下注:逐柱組牌 / 一鍵全包(同一功能) */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                01 / 三柱 1800 碰下注
              </span>
              <span className="text-[11px] font-mono text-neutral-400">
                各柱相乘 = 注數
              </span>
            </div>

            <div className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-relaxed">
              自訂 <strong>2 柱</strong> → 第三柱自動全包「剩下的號碼」;或自訂滿 3 柱。
              注數 = 三柱顆數相乘。要整組全包就按<strong>「一鍵全包」</strong>({totalBets.toLocaleString()} 注)。
            </div>

            {/* 快速:一鍵全包(三柱各自全選)或帶入某柱範圍當作目前選取 */}
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={loadFullWheel}
                className="px-2.5 py-1 rounded-lg text-[10px] font-bold border border-black/80 dark:border-white/80 bg-black text-white dark:bg-white dark:text-black hover:opacity-90 active:scale-95 transition-all"
              >
                一鍵全包 ({totalBets.toLocaleString()} 注)
              </button>
              <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold ml-1">預設柱</span>
              {pillars.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => presetFromFixed(i)}
                  className="px-2.5 py-1 rounded-lg text-[10px] font-mono font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  {pillarRange(p)}
                </button>
              ))}
            </div>

            <LotteryBallPad
              selectedBalls={selectedBalls}
              onToggleBall={(ball) =>
                setSelectedBalls(prev =>
                  prev.includes(ball)
                    ? prev.filter(n => n !== ball)
                    : [...prev, ball].sort((a, b) => a - b)
                )
              }
              onClear={() => setSelectedBalls([])}
              totalBalls={gameCfg.num_max}
              maxBalls={gameCfg.num_max}
              label={savedPillars.length >= NUM_SLOTS
                ? '三柱已自訂完(可移除某柱再改)'
                : `選取號碼 → 保存為${PILLAR_NAMES[savedPillars.length] ?? `第${savedPillars.length + 1}柱`}`}
              layout="grid"
            />

            {/* 保存為下一柱(最多 3 柱) */}
            {savedPillars.length < NUM_SLOTS && (() => {
              const fresh = selectedBalls.filter(n => !usedInPillars.has(n)).length;
              const nextName = PILLAR_NAMES[savedPillars.length] ?? `第${savedPillars.length + 1}柱`;
              return (
                <button
                  type="button"
                  onClick={savePillar}
                  disabled={fresh === 0}
                  className="w-full py-2.5 rounded-xl text-xs font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 transition-colors flex items-center justify-center gap-2 active:scale-98"
                >
                  <Plus className="w-4 h-4" />
                  保存為 {nextName}{fresh > 0 ? `(${fresh} 顆)` : ''}
                </button>
              );
            })()}

            {/* 已保存的柱(在保存動作下方,順著由上往下的操作流程) */}
            {savedPillars.length > 0 && (
              <div className="space-y-1.5">
                {savedPillars.map((p, i) => {
                  const theme = [
                    'border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white',
                    'border-amber-500/20 bg-amber-500/5 text-amber-700 dark:text-amber-300',
                    'border-emerald-500/20 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300',
                  ][i % 3];
                  return (
                    <div key={i} className={`p-2.5 rounded-xl border flex items-center justify-between gap-2 ${theme}`}>
                      <div className="min-w-0">
                        <div className="text-[10px] uppercase tracking-wider font-semibold opacity-70">
                          {PILLAR_NAMES[i] ?? `第${i + 1}柱`}({p.length}顆)
                        </div>
                        <div className="text-xs font-mono font-bold mt-0.5 break-all">
                          {p.map(pad).join(' ')}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removePillar(i)}
                        className="shrink-0 p-1 rounded-lg text-neutral-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {/* 下注支數(倍投) */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">下注支數 (Units)</label>
                <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">{units} 支</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setUnits(Math.max(1, units - 1))}
                  className="w-9 h-9 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  <Minus className="w-4 h-4" />
                </button>
                <div className="flex-1 h-9 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] flex items-center justify-center font-mono font-bold text-sm text-neutral-900 dark:text-white">
                  {units} 支
                </div>
                <button
                  type="button"
                  onClick={() => setUnits(units + 1)}
                  className="w-9 h-9 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* 試算(全包時多顯示過關機率 / 彩金) */}
            <div className="p-3.5 sm:p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-2">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                {isFullWheel ? '全包試算 (1800 碰)' : '部分包牌試算'}
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-neutral-500 block text-[10px]">三柱顆數 × 支:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    {effSizes.length ? effSizes.join(' × ') : '—'} × {units}
                  </span>
                  <span className="block text-[10px] text-neutral-400">
                    {customCount >= NUM_SLOTS
                      ? `自訂滿 ${NUM_SLOTS} 柱`
                      : customCount === NUM_SLOTS - 1
                        ? `自訂 ${customCount} 柱,第${NUM_SLOTS}柱全包剩 ${remainingNums.length} 顆`
                        : `尚需自訂 ${NUM_SLOTS - 1 - customCount} 柱(或一鍵全包)`}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">可組出注數:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    {betsWithUnits.toLocaleString()} 注
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">投注成本:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    NT$ {submitCost.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">目前選取:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    {selectedBalls.length} 顆
                  </span>
                </div>
                {isFullWheel && (
                  <>
                    <div>
                      <span className="text-neutral-500 block text-[10px]">過關機率:</span>
                      <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                        {passProb !== null ? `${(passProb * 100).toFixed(2)}%` : '—'}
                      </span>
                    </div>
                    <div>
                      <span className="text-neutral-500 block text-[10px]">開 4/3 碰彩金:</span>
                      <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                        {(units * prize4).toLocaleString()} / {(units * prize3).toLocaleString()}
                      </span>
                    </div>
                  </>
                )}
              </div>
            </div>

            <button
              type="button"
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="w-full py-3 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 transition-opacity flex items-center justify-center gap-2 shadow-xs active:scale-98"
            >
              <FileText className="w-4 h-4" />
              送出記帳 {betsWithUnits.toLocaleString()} 注(待開獎)
            </button>
          </div>

          {/* 區間組合斷檔提醒 */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                02 / 1800碰斷檔提醒
              </span>
              <span className="text-[11px] font-mono text-neutral-400">
                連續 3 期未開
              </span>
            </div>

            <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
              任兩個十位區段連續 3 期都沒開出號碼，就列為警示。
            </div>

            {pairsReq.loading && (
              <div className="text-xs text-neutral-400">載入區間統計中…</div>
            )}
            {pairsReq.error && (
              <div className="text-xs text-rose-500">{pairsReq.error}</div>
            )}

            <div className="space-y-2">
              {(() => {
                const shown = (pairsReq.data || []).filter(p => p.streak >= 1);
                if (!pairsReq.loading && !pairsReq.error && shown.length === 0) {
                  return (
                    <div className="text-xs text-neutral-400">
                      目前沒有連續未開的區段組合 —— 各十位區段近期都有開出。
                    </div>
                  );
                }
                return shown.map(p => (
                <div
                  key={`${p.bands[0]}-${p.bands[1]}`}
                  className={`p-2.5 rounded-xl border flex items-center justify-between gap-2 ${
                    p.alert
                      ? 'bg-amber-500/10 border-amber-500/20'
                      : 'border-black/[0.06] dark:border-white/[0.06] bg-black/[0.02] dark:bg-white/[0.03]'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      {p.alert && (
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                      )}
                      <span className={`text-xs font-mono font-bold ${
                        p.alert ? 'text-amber-900 dark:text-amber-300' : 'text-neutral-900 dark:text-white'
                      }`}>
                        {p.labels[0]} × {p.labels[1]}
                      </span>
                    </div>
                    <div className="text-[10px] font-mono text-neutral-400 mt-0.5">
                      {p.range[0]} × {p.range[1]}
                    </div>
                  </div>

                  <div className={`text-[11px] font-mono shrink-0 text-right ${
                    p.alert ? 'text-amber-900 dark:text-amber-300 font-bold' : 'text-neutral-400'
                  }`}>
                    {p.alert ? `連續 ${p.streak} 期兩區段都未開` : `${p.streak} 期未開`}
                  </div>
                </div>
                ));
              })()}
            </div>
          </div>

        </div>

        {/* Right Column (7/12) - Metrics & Live Ledger */}
        <div className="lg:col-span-7 space-y-4">
          
          {/* Top 4 Metric Tiles */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3">
            <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">總投入成本</div>
              <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
                {totalSpent.toLocaleString()}
              </div>
            </div>

            <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">總回收彩金</div>
              <div className="text-base sm:text-lg font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
                {totalReturn.toLocaleString()}
              </div>
            </div>

            <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">累積淨損益</div>
              <div className={`text-base sm:text-lg font-bold font-mono mt-0.5 ${cumPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                {cumPnl >= 0 ? `+${cumPnl.toLocaleString()}` : cumPnl.toLocaleString()}
              </div>
            </div>

            <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">過關率 / 局數</div>
              <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
                {records.length > 0 ? `${((winCount / records.length) * 100).toFixed(0)}%` : '0%'}
              </div>
              <div className="text-[10px] text-neutral-400 font-mono">共 {records.length} 局</div>
            </div>
          </div>

          {/* Records Ledger Section */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                02 / 三柱流水帳與過關核對
              </h3>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleSettlePending}
                  disabled={settleBusy || !ledger.loggedIn}
                  title="備援:一鍵把所有待開獎且已開的紀錄自動對獎"
                  className="text-[11px] font-semibold text-neutral-500 hover:text-neutral-900 dark:hover:text-white disabled:opacity-30 transition-colors flex items-center gap-1 active:scale-95"
                >
                  <RefreshCw className={`w-3 h-3 ${settleBusy ? 'animate-spin' : ''}`} />
                  {settleBusy ? '對獎中…' : '一鍵對獎'}
                </button>
                <button
                  type="button"
                  onClick={ledger.undo}
                  disabled={records.length === 0}
                  className="text-[11px] font-semibold text-neutral-500 hover:text-neutral-900 dark:hover:text-white disabled:opacity-30 transition-colors flex items-center gap-1 active:scale-95"
                >
                  <RotateCcw className="w-3 h-3" />
                  撤銷上一筆
                </button>
              </div>
            </div>
            {settleMsg && (
              <div className="text-[11px] text-emerald-600 dark:text-emerald-400">{settleMsg}</div>
            )}

            {ledger.loading && <div className="text-xs text-neutral-400">載入流水帳中…</div>}
            {ledger.error && <div className="text-xs text-rose-500">{ledger.error}</div>}
            {!ledger.loggedIn && (
              <div className="text-[11px] text-neutral-400">
                未登入:紀錄只留在這個瀏覽器分頁,重整就會消失。
              </div>
            )}

            {/* Mobile View: Vertical Clean Cards (No Horizontal Scrolling) */}
            <div className="space-y-2.5 sm:hidden">
              {records.map((rec) => (
                <div 
                  key={rec.id}
                  className="p-3.5 rounded-xl border border-black/[0.08] dark:border-white/[0.08] bg-black/[0.01] dark:bg-white/[0.02] space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span className="w-5 h-5 rounded-full bg-black/5 dark:bg-white/10 text-[10px] font-mono font-bold flex items-center justify-center">
                        {rec.index}
                      </span>
                      <IssuePicker
                        issue={rec.issue}
                        date={rec.date}
                        draws={draws}
                        onSelect={(iss) => ledger.resettle(rec.id, iss)}
                        extraOption={nextOpt}
                        showNums={false}
                        onRefresh={() => ledger.resettle(rec.id, rec.issue)}
                        onManualHit={(k) => ledger.resettle(rec.id, rec.issue, k)}
                        manualPillars={rec.pillars?.length || 3}
                        gameLabel={gameCfg.short_name}
                      />
                    </div>

                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                      rec.pnl > 0 
                        ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 font-bold' 
                        : rec.result === '待開獎' 
                        ? 'bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-400' 
                        : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                    }`}>
                      {rec.result}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 pt-1 border-t border-black/[0.04] dark:border-white/[0.04] text-[11px]">
                    <div>
                      <span className="text-neutral-400 block text-[10px]">柱位分佈</span>
                      <span className="font-mono font-bold text-neutral-800 dark:text-neutral-200">{rec.pillarDist || '2+2+1'}</span>
                    </div>
                    <div>
                      <span className="text-neutral-400 block text-[10px]">投入成本</span>
                      <span className="font-mono text-neutral-800 dark:text-neutral-200">{rec.cost.toLocaleString()}</span>
                    </div>
                    <div>
                      <span className="text-neutral-400 block text-[10px]">本局損益</span>
                      <span className={`font-mono font-bold ${rec.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {rec.pnl >= 0 ? `+${rec.pnl.toLocaleString()}` : rec.pnl.toLocaleString()}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[11px] pt-1 border-t border-black/[0.04] dark:border-white/[0.04]">
                    <div className="text-neutral-400 text-[10px]">
                      開獎號: <span className="font-mono text-neutral-600 dark:text-neutral-400">{rec.drawBalls.map(b => b.toString().padStart(2, '0')).join(' ')}</span>
                    </div>
                    <div className="text-[10px] font-mono text-neutral-400">
                      {rec.betsCount.toLocaleString()} 注
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Desktop Table View */}
            <div className="lt-wrap border border-black/[0.08] dark:border-white/[0.08] rounded-xl hidden sm:block">
              <table className="lt">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>期號</th>
                    <th>遊戲</th>
                    <th>支數</th>
                    <th>柱位分佈</th>
                    <th>狀態</th>
                    <th>成本</th>
                    <th>回收</th>
                    <th>本局損益</th>
                    <th>累積損益</th>
                    <th>開獎號碼</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec) => (
                    <tr key={rec.id}>
                      <td>{rec.index}</td>
                      <td>
                        <IssuePicker
                          issue={rec.issue}
                          date={rec.date}
                          draws={draws}
                          onSelect={(iss) => ledger.resettle(rec.id, iss)}
                          extraOption={nextOpt}
                          showNums={false}
                          onRefresh={() => ledger.resettle(rec.id, rec.issue)}
                        onManualHit={(k) => ledger.resettle(rec.id, rec.issue, k)}
                        manualPillars={rec.pillars?.length || 3}
                        gameLabel={gameCfg.short_name}
                        />
                      </td>
                      <td className="text-xs font-semibold">{rec.game.split('(')[0]}</td>
                      <td className="font-mono text-xs font-bold">{rec.units} 支</td>
                      <td className="font-mono text-xs font-semibold">{rec.pillarDist || '2 + 2 + 1'}</td>
                      <td>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                          rec.pnl > 0 
                            ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 font-bold' 
                            : rec.result === '待開獎' 
                            ? 'bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-400' 
                            : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                        }`}>
                          {rec.result}
                        </span>
                      </td>
                      <td className="font-mono text-xs">{rec.cost.toLocaleString()}</td>
                      <td className="font-mono text-xs text-emerald-600 dark:text-emerald-400 font-bold">{rec.payout.toLocaleString()}</td>
                      <td className={`font-mono text-xs font-bold ${rec.pnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {rec.pnl >= 0 ? `+${rec.pnl.toLocaleString()}` : rec.pnl.toLocaleString()}
                      </td>
                      <td className={`font-mono text-xs font-bold ${rec.cumPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                        {rec.cumPnl >= 0 ? `+${rec.cumPnl.toLocaleString()}` : rec.cumPnl.toLocaleString()}
                      </td>
                      <td className="font-mono text-xs">
                        {rec.drawBalls.map(b => b.toString().padStart(2, '0')).join(' ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};
