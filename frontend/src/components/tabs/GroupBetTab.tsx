import React, { useState } from 'react';
import {
  FileText,
  CheckCircle2,
  XCircle,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import { LotteryBallPad } from '../LotteryBallPad';
import { IssuePicker } from '../IssuePicker';
import { OverwriteConfirm } from '../OverwriteConfirm';
import { BetTargetSelector } from '../BetTargetSelector';
import { BetRecord, LotteryGame } from '../../types';
import { api, ErhePlanDTO, GroupDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';
import { useLedger } from '../../api/useLedger';
import { useWeekNav, WeekNav, WeekSubtotal } from '../WeekNav';
import { useHistoriesByGame } from '../../api/useHistories';
import { useEditions } from '../../api/useEditions';

// 二合買牌的「組」下注控制台。取代原本寫死的 SingleBetTab / MultiBetTab ——
// 兩者其實只差「鎖幾顆」與標籤,現在統一成一個吃 group 參數的元件:
//   - 球盤鎖成 group.ball_count(固定顆數,選滿即止)。
//   - 成本 = 顆數 × 車數 × default_cost_per_car(2755);中一顆每車 = default_win_payout
//     (21200,不除以 4),與 backend.settle 一致。
//   - 流水存在 group.mode(1組=single、2組=multi;不搬舊資料)。

interface Props {
  group: GroupDTO;
}

export const GroupBetTab: React.FC<Props> = ({ group }) => {
  const { game, gameKey, loading: gameLoading } = useGame();
  const { eid, edition, combineEditions, setCombineEditions } = useEditions();
  const [selectedBalls, setSelectedBalls] = useState<number[]>([]);
  const [cars, setCars] = useState<number>(5);
  // 這個版 × 這款遊戲的盤口(每車成本 / 中一顆可得);讀不到先用 GameConfig 預設
  const oddsReq = useAsync(() => api.getEditionOdds(eid, gameKey), [eid, gameKey]);
  const odds = oddsReq.data?.fields;

  // 期號 / 日期:預設帶最新一期,可用下拉改記到別期(補記 / 修期)
  const histReq = useAsync(() => api.history(gameKey, 30), [gameKey]);
  const latest = histReq.data?.latest ?? null;
  const draws = histReq.data?.draws ?? [];
  // 核對列的期號選擇器用「那列記錄自己的遊戲」的期別(混合顯示各遊戲,不能用全域遊戲)
  const histByGame = useHistoriesByGame();
  const [curIssue, setCurIssue] = useState<string>('');
  const [issueTouched, setIssueTouched] = useState(false);
  const [betDate, setBetDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
  React.useEffect(() => {
    if (issueTouched) return;
    if (latest?.issue) setCurIssue(latest.issue);
    if (latest?.date) setBetDate(latest.date);
  }, [latest?.issue, latest?.date, issueTouched]);
  const pickIssue = (iss: string, d: string) => {
    setCurIssue(iss);
    setBetDate(d);
    setIssueTouched(true);
  };

  // 登入時流水存後端;未登入沿用前端 state。依「版」篩選(本版 / 全部版合併由滑塊決定)
  const ledger = useLedger(group.mode, [], {edition: eid, combine: combineEditions});
  const allRecords = ledger.records;
  // 遊戲篩選:全部 / 各款;篩選後重算累積損益(從舊到新),上方儀表板與核對列表都跟著變。
  const [gameFilter, setGameFilter] = React.useState<'all' | 'lotto539' | 'fantasy5' | 'marksix'>('all');
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const gameKeyOf = (g: string) =>
    g.startsWith('今彩539') ? 'lotto539'
      : g.startsWith('天天樂') ? 'fantasy5'
        : g.startsWith('六合彩') ? 'marksix' : 'other';
  const records = React.useMemo(() => {
    const f = gameFilter === 'all' ? allRecords : allRecords.filter(r => gameKeyOf(r.game) === gameFilter);
    let running = 0;
    return f.map((r, i) => ({ ...r, index: i + 1, cumPnl: (running += r.pnl) }));
  }, [allRecords, gameFilter]);
  // 流水週導覽(共用):‹ › 依日曆前後移,中間切「全部週」
  const wk = useWeekNav(records);
  const flowRecords = wk.flowRecords;

  // 重新整理:補了最新一期開獎後,後端會自動把「待開獎」結算掉(見 backend/autosettle.py),
  // 但這頁的流水是掛載時抓一次就不動,不會反映後端已結算的 pnl。這裡重抓流水 + 開獎歷史,
  // 讓核對明細立刻跟上最新期。純前端重抓,不碰後端結算。
  const ledgerReload = ledger.reload;
  const histReload = histReq.reload;
  const refreshLedger = React.useCallback(() => {
    ledgerReload();
    histReload();
  }, [ledgerReload, histReload]);
  // 視窗重新取得焦點 / 分頁切回可見時自動重抓(常見情境:去「設定」抓完最新開獎再切回來)
  React.useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') refreshLedger();
    };
    window.addEventListener('focus', refreshLedger);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.removeEventListener('focus', refreshLedger);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [refreshLedger]);

  // 不固定顆數:依「這一組最新一筆下注紀錄」建議顆數 / 車數。沒有紀錄就退回設定的預設顆數。
  // 建議顆數/車數依「最近開獎日期」那筆,而非最後寫入的一筆 —— 重新上傳時
  // 寫入順序 ≠ 日期順序,取日期最新的才是真正「上次」。日期相同取較後寫入者。
  const lastRecord = records.length > 0
    ? records.reduce((best, r) =>
        (String(r.date ?? '') >= String(best.date ?? '') ? r : best))
    : null;
  const lastCount = lastRecord?.selectedBalls?.length ?? 0;
  const lastCars = lastRecord?.cars ?? lastRecord?.units ?? 0;
  const suggestBalls = lastCount || group.ball_count; // 建議顆數:上次幾顆,沒紀錄用預設
  // 成本 / 派彩試算用「實際選取顆數」,沒選就先用建議顆數,數字才不會是 0
  const activeCount = selectedBalls.length || suggestBalls;

  // 二合盤口取「這個版」的值(每車成本 / 中一顆可得,不除以 4);讀不到先用 GameConfig 預設
  const costPerCarPerBall = odds?.cost_per_car?.value ?? (game ? game.default_cost_per_car : 0);
  const prizePerHitPerCar = odds?.win_payout?.value ?? (game ? game.default_win_payout : 0);
  const { data: plan } = useAsync<ErhePlanDTO | null>(
    () =>
      game
        ? api.erhePlan(gameKey, activeCount, cars, {
            cost_per_car: costPerCarPerBall,
            win_payout: prizePerHitPerCar,
          })
        : Promise.resolve(null),
    [gameKey, activeCount, cars, costPerCarPerBall, prizePerHitPerCar],
  );

  const cumPnl = records.length > 0 ? records[records.length - 1].cumPnl : 0;
  const totalSpent = records.reduce((acc, r) => acc + r.cost, 0);
  const totalReturn = records.reduce((acc, r) => acc + r.payout, 0);
  const winCount = records.filter(r => r.payout > 0).length;
  // 累計總車數:這一版所有下注的車數(1組/2組;cars 缺就取 units)
  const totalCars = records.reduce((acc, r) => acc + (Number(r.cars ?? r.units) || 0), 0);

  if (!game) {
    return (
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
        {gameLoading ? '載入遊戲設定中…' : '讀不到遊戲設定,請重新整理頁面。'}
      </div>
    );
  }

  const gameName = game.name as LotteryGame;
  const numMax = game.num_max;
  const payoutOf = (hits: number) =>
    Math.round(plan?.hits.find(h => h.hits === hits)?.payout ?? cars * prizePerHitPerCar * hits);
  const currentCost = Math.round(plan?.total_cost ?? cars * activeCount * costPerCarPerBall);
  const prize1Hit = payoutOf(1);
  const prize2Hits = payoutOf(2);
  const prizeAllHits = payoutOf(activeCount);
  const canRecord = selectedBalls.length >= 1; // 不固定顆數:至少選 1 顆就能下

  // 建議車數(中1顆回本,照舊版):以「這一組自己的累積損益」算,不跟另一組混。
  // 顆數用建議顆數(最新紀錄的顆數):中1顆每車淨利 = 每車中獎(21200) − 顆數×每車成本(2755)。
  // 車數 = ⌈該組虧損 ÷ 每車淨利⌉;<=0 中1顆追不回、回本後用起始車數。
  const per1HitNet = Math.round(prizePerHitPerCar - suggestBalls * costPerCarPerBall);
  const inLoss = cumPnl < 0;
  const canRecover1Hit = per1HitNet > 0;
  const suggestCars = !inLoss
    ? null
    : !canRecover1Hit
    ? Infinity
    : Math.max(1, Math.ceil(-cumPnl / per1HitNet));
  // 舊版那幾個對照數字(建議車數旁一起放大顯示)
  const okSuggest = suggestCars != null && Number.isFinite(suggestCars);
  const suggestN = okSuggest ? (suggestCars as number) : 0;
  const suggestCost = okSuggest ? suggestBalls * suggestN * costPerCarPerBall : 0; // 本局成本
  const suggestGain = okSuggest ? suggestN * prizePerHitPerCar : 0;               // 中1顆可得
  const afterCum = okSuggest ? cumPnl + suggestGain - suggestCost : 0;            // 中1顆後累積

  const handleToggleBall = (num: number) => {
    if (selectedBalls.includes(num)) {
      setSelectedBalls(selectedBalls.filter(n => n !== num));
    } else if (selectedBalls.length < numMax) {
      setSelectedBalls([...selectedBalls, num]);
    }
  };

  const handleRecord = (status: string = '待開獎', hits: number = 0) => {
    const payout = hits > 0 ? payoutOf(hits) : 0;
    const pnl = status === '待開獎' ? 0 : payout - currentCost;
    ledger.add({
      date: betDate,
      issue: curIssue || '',
      game: gameName,
      mode: group.mode,
      edition: eid,
      units: cars,
      cars,
      betsCount: selectedBalls.length,
      selectedBalls: [...selectedBalls],
      drawBalls: [],
      result: status,
      cost: currentCost,
      payout,
      pnl,
    });
  };

  return (
    <div className="space-y-4 sm:space-y-5 animate-in fade-in duration-200 w-full overflow-hidden">
      {ledger.pendingConflict && (
        <OverwriteConfirm
          conflicts={ledger.pendingConflict.conflicts}
          onConfirm={ledger.confirmOverwrite}
          onCancel={ledger.cancelOverwrite}
        />
      )}
      {/* Top Banner Bar */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3 sm:space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-[0.25em] text-neutral-400 dark:text-neutral-500 font-semibold">
                Group Betting
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
                {game.short_name}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                {edition?.name ?? '第一版'}
              </span>
            </div>
            <div className="text-base sm:text-xl font-display font-bold text-neutral-900 dark:text-white mt-0.5">
              {group.name}下注控制台
            </div>
            <div className="text-[11px] font-mono text-neutral-500 dark:text-neutral-400 mt-0.5">
              建議顆數 <strong className="text-neutral-800 dark:text-neutral-100">{suggestBalls}</strong> 顆
              {lastRecord && <span> ・上次 {lastCount} 顆 {lastCars} 車</span>}
            </div>
          </div>

          <div className="flex items-center justify-between md:justify-end gap-4 border-t md:border-t-0 pt-2.5 md:pt-0 border-black/[0.06] dark:border-white/[0.06]">
            <div className="text-left md:text-right">
              <div className="flex items-center gap-1.5 md:justify-end">
                <span className="text-[10px] uppercase tracking-wider text-neutral-400">
                  {group.name}累積損益
                </span>
                {/* 滑塊:累積損益 / 建議車數 看「本版」還是「全部版合併」 */}
                <button
                  type="button"
                  onClick={() => setCombineEditions(!combineEditions)}
                  title="切換:本版 / 全部版合併"
                  className={`px-1.5 py-0.5 rounded-full text-[9px] font-semibold border transition-colors ${
                    combineEditions
                      ? 'bg-black text-white dark:bg-white dark:text-black border-black dark:border-white'
                      : 'border-black/15 dark:border-white/20 text-neutral-500'
                  }`}
                >
                  {combineEditions ? '全部版' : '本版'}
                </button>
              </div>
              <div className={`text-xl sm:text-2xl font-mono font-bold ${cumPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                {cumPnl >= 0 ? `+${cumPnl.toLocaleString()}` : cumPnl.toLocaleString()}
              </div>
            </div>
            <div className="text-right text-[11px] font-mono text-neutral-400">
              {records.length} 局・中 {winCount} 局
            </div>
          </div>
        </div>

        {/* 建議車數 —— 放大顯示(參考舊版「回本要下幾車」:回本車數 + 本局成本 + 中1顆可得 + 中後累積) */}
        <div className="p-4 sm:p-5 rounded-xl bg-gradient-to-br from-black/[0.04] to-black/[0.01] dark:from-white/[0.07] dark:to-white/[0.02] border border-black/[0.08] dark:border-white/[0.10]">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div>
              <div className="text-[10px] uppercase tracking-[0.25em] text-neutral-400 font-semibold">
                建議車數 · 中 1 顆回本(依建議 {suggestBalls} 顆)
              </div>
              {!inLoss ? (
                <div className="text-2xl sm:text-3xl font-display font-black text-emerald-600 dark:text-emerald-400 mt-0.5">
                  已回本 · 用起始車數
                </div>
              ) : !canRecover1Hit ? (
                <div className="text-2xl sm:text-3xl font-display font-black text-amber-600 dark:text-amber-400 mt-0.5">
                  無解 <span className="text-sm font-mono font-normal text-neutral-500">中1顆每車淨利 {per1HitNet.toLocaleString()} ≤ 0</span>
                </div>
              ) : (
                <div className="flex items-baseline gap-2 mt-0.5">
                  <span className="text-5xl sm:text-6xl font-display font-black text-neutral-900 dark:text-white leading-none tabular-nums">
                    {suggestN.toLocaleString()}
                  </span>
                  <span className="text-xl sm:text-2xl font-display font-bold text-neutral-500">車</span>
                </div>
              )}
            </div>
            {inLoss && canRecover1Hit && (
              <button
                type="button"
                onClick={() => setCars(suggestN)}
                className="px-5 py-3 rounded-xl text-sm font-bold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 active:scale-95 transition-all shadow-xs"
              >
                套用車數
              </button>
            )}
          </div>

          {inLoss && canRecover1Hit && (
            <div className="grid grid-cols-3 gap-2 sm:gap-3 mt-3 pt-3 border-t border-black/[0.06] dark:border-white/[0.08]">
              <div>
                <div className="text-[10px] text-neutral-400 uppercase tracking-wider">本局成本</div>
                <div className="text-sm sm:text-base font-mono font-bold text-neutral-900 dark:text-white">{suggestCost.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-[10px] text-neutral-400 uppercase tracking-wider">中 1 顆可得</div>
                <div className="text-sm sm:text-base font-mono font-bold text-emerald-600 dark:text-emerald-400">{suggestGain.toLocaleString()}</div>
              </div>
              <div>
                <div className="text-[10px] text-neutral-400 uppercase tracking-wider">中後累積</div>
                <div className={`text-sm sm:text-base font-mono font-bold ${afterCum >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
                  {afterCum >= 0 ? `+${afterCum.toLocaleString()}` : afterCum.toLocaleString()}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Dual-Column Workbench Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-5">
        {/* Left Column - Configuration */}
        <div className="lg:col-span-5 space-y-4">
          <BetTargetSelector />
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                01 / {group.name}參數配置
              </span>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-mono text-neutral-400">期號</span>
                <IssuePicker issue={curIssue} date={betDate} draws={draws} extraOption={histReq.data?.next ?? undefined} onSelect={pickIssue} />
              </div>
            </div>

            <div>
              <LotteryBallPad
                selectedBalls={selectedBalls}
                onToggleBall={handleToggleBall}
                onClear={() => setSelectedBalls([])}
                onQuickSelect={(balls) => setSelectedBalls(balls)}
                maxBalls={numMax}
                totalBalls={numMax}
                label={`選取下注號碼 (不固定顆數・建議 ${suggestBalls} 顆・已選 ${selectedBalls.length})`}
                layout="grid"
              />
            </div>

            {/* Car Stepper */}
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <label className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
                  下注車數 (Cars)
                </label>
                <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">
                  {cars} 車 ({activeCount} 顆)
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setCars(Math.max(1, cars - 1))}
                  className="w-10 h-10 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  −
                </button>
                <input
                  type="number" inputMode="numeric" min="1" step="1" value={cars}
                  onChange={e => { const v = parseInt(e.target.value, 10); setCars(Number.isFinite(v) ? v : 1); }}
                  onBlur={() => setCars(c => Math.max(1, Math.round(c) || 1))}
                  aria-label="下注車數"
                  className="flex-1 h-10 w-full rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-center font-mono font-bold text-sm text-neutral-900 dark:text-white outline-none focus:border-black/30 dark:focus:border-white/30"
                />
                <button
                  type="button"
                  onClick={() => setCars(cars + 1)}
                  className="w-10 h-10 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  +
                </button>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[1, 2, 3, 5, 8, 10, 15].map(c => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setCars(c)}
                    className={`flex-1 min-w-[42px] py-1 text-xs font-mono font-semibold rounded-lg border transition-all active:scale-95 ${
                      cars === c
                        ? 'bg-black text-white dark:bg-white dark:text-black border-black dark:border-white'
                        : 'border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {/* Live HUD */}
            <div className="p-3.5 sm:p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-2">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                損益階梯試算 (Live HUD)
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-neutral-500 block text-[10px]">總投入成本:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    NT$ {currentCost.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">中 1 顆拿回:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    NT$ {prize1Hit.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">中 2 顆拿回:</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    NT$ {prize2Hits.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">中 {activeCount} 顆全中:</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    NT$ {prizeAllHits.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="pt-2 flex flex-col sm:flex-row gap-2">
              <button
                type="button"
                disabled={!canRecord}
                onClick={() => handleRecord('待開獎', 0)}
                className="w-full py-3 px-4 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 transition-opacity flex items-center justify-center gap-2 shadow-xs active:scale-98"
              >
                <FileText className="w-4 h-4" />
                {canRecord ? '送出記帳 (待開獎)' : '請至少選 1 顆'}
              </button>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  disabled={!canRecord}
                  onClick={() => handleRecord(`中 ${selectedBalls.length} 顆`, selectedBalls.length)}
                  className="py-2.5 px-3 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold border border-emerald-600/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 disabled:opacity-30 transition-colors flex items-center justify-center gap-1 active:scale-95"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  模擬全中
                </button>
                <button
                  type="button"
                  disabled={!canRecord}
                  onClick={() => handleRecord('槓龜 (0顆)', 0)}
                  className="py-2.5 px-3 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold border border-rose-600/30 text-rose-700 dark:text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 disabled:opacity-30 transition-colors flex items-center justify-center gap-1 active:scale-95"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  模擬沒中
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Metrics & Ledger */}
        <div className="lg:col-span-7 space-y-4">
          {/* 遊戲篩選:全部 / 各款 —— 上方儀表板與下方核對列表都依此變動 */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">遊戲</span>
            {([['all', '全部'], ['lotto539', '今彩539'], ['fantasy5', '天天樂'], ['marksix', '六合彩']] as const).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setGameFilter(k)}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                  gameFilter === k
                    ? 'bg-black text-white dark:bg-white dark:text-black'
                    : 'border border-black/10 dark:border-white/10 text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 sm:gap-3">
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
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">中獎率 / 局數</div>
              <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
                {records.length > 0 ? `${((winCount / records.length) * 100).toFixed(0)}%` : '0%'}
              </div>
              <div className="text-[10px] text-neutral-400 font-mono">共 {records.length} 局</div>
            </div>
            <div className="p-3.5 sm:p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">累計總車數</div>
              <div className="text-base sm:text-lg font-bold font-mono text-neutral-900 dark:text-white mt-0.5">
                {totalCars.toLocaleString()} <span className="text-[10px] font-normal text-neutral-400">車</span>
              </div>
              <div className="text-[10px] text-neutral-400 font-mono">共 {records.length} 局</div>
            </div>
          </div>

          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
                  02 / {group.name}流水帳與開獎核對
                </h3>
                <WeekNav
                  focusWeek={wk.focusWeek}
                  allWeeks={wk.allWeeks}
                  canNext={wk.canNext}
                  onPrev={() => wk.goWeek(-1)}
                  onNext={() => wk.goWeek(1)}
                  onToggleAll={() => wk.setAllWeeks(v => !v)}
                />
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={refreshLedger}
                  disabled={ledger.loading}
                  title="補了最新開獎後,重抓流水讓核對明細跟上(後端已自動結算)"
                  className="text-[11px] font-semibold text-neutral-500 hover:text-neutral-900 dark:hover:text-white disabled:opacity-30 transition-colors flex items-center gap-1 active:scale-95"
                >
                  <RefreshCw className={`w-3 h-3 ${ledger.loading ? 'animate-spin' : ''}`} />
                  重新整理
                </button>
              </div>
            </div>

            <WeekSubtotal records={flowRecords} label={wk.label} />
            {!wk.allWeeks && flowRecords.length === 0 && (
              <div className="text-[11px] text-neutral-400">{wk.label} 沒有紀錄。用 ‹ › 切到其他週。</div>
            )}

            {ledger.loading && <div className="text-xs text-neutral-400">載入流水帳中…</div>}
            {ledger.error && <div className="text-xs text-rose-500">{ledger.error}</div>}
            {!ledger.loggedIn && (
              <div className="text-[11px] text-neutral-400">
                未登入:紀錄只留在這個瀏覽器分頁,重整就會消失。
              </div>
            )}

            {/* Desktop Table View */}
            <div className="lt-wrap border border-black/[0.08] dark:border-white/[0.08] rounded-xl overflow-x-auto">
              <table className="lt">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>期號 / 核對</th>
                    <th>遊戲</th>
                    <th>車數</th>
                    <th>狀態</th>
                    <th>成本</th>
                    <th>回收</th>
                    <th>本局損益</th>
                    <th>累積損益</th>
                    <th>下注號碼</th>
                    <th>開獎號碼</th>
                    <th>撤銷</th>
                  </tr>
                </thead>
                <tbody>
                  {flowRecords.map((rec) => (
                    <tr key={rec.id}>
                      <td>{rec.index}</td>
                      <td>
                        <IssuePicker
                          issue={rec.issue}
                          date={rec.date}
                          draws={histByGame[rec.game]?.draws ?? []}
                          onSelect={(iss) => ledger.resettle(rec.id, iss)}
                          extraOption={histByGame[rec.game]?.next ?? undefined}
                          showNums={false}
                          onRefresh={() => ledger.resettle(rec.id, rec.issue)}
                          onManualHit={(k) => ledger.resettle(rec.id, rec.issue, k)}
                        />
                      </td>
                      <td className="text-xs font-semibold">{rec.game.split('(')[0]}</td>
                      <td className="font-mono text-xs font-bold">{rec.cars || rec.units} 車</td>
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
                        <div className="flex flex-wrap gap-1">
                          {rec.selectedBalls.map(b => (
                            <span key={b} className={`px-1 py-0.5 rounded ${rec.drawBalls.includes(b) ? 'bg-black text-white dark:bg-white dark:text-black font-bold' : ''}`}>
                              {b.toString().padStart(2, '0')}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="font-mono text-xs">
                        {rec.drawBalls.map(b => b.toString().padStart(2, '0')).join(' ')}
                      </td>
                      <td>
                        {confirmDeleteId === rec.id ? (
                          <button
                            type="button"
                            onClick={() => { ledger.deleteById(rec.id); setConfirmDeleteId(null); }}
                            className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-rose-600 text-white hover:bg-rose-700 transition-colors"
                          >
                            確認?
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setConfirmDeleteId(rec.id)}
                            title="撤銷這一筆"
                            className="inline-flex items-center p-1 rounded-md text-neutral-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-black/5 dark:hover:bg-white/5 transition-colors active:scale-95"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
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
