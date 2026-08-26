import React, { useState } from 'react';
import {
  FileText,
  Layers,
  RotateCcw,
  RefreshCw,
  Minus,
  Plus
} from 'lucide-react';
import { INITIAL_COMBO9000_RECORDS } from '../../data/lotteryData';
import { LotteryGame } from '../../types';
import { api } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';
import { useLedger } from '../../api/useLedger';
import { useHistoriesByGame } from '../../api/useHistories';
import { useEditions } from '../../api/useEditions';
import { IssuePicker } from '../IssuePicker';

// 四段的十位頭切法(與後端 core.combo9000 一致):0頭 9 顆、其餘各 10 顆。
const SEGMENTS: { name: string; range: string; size: number }[] = [
  { name: '0頭', range: '01 ~ 09', size: 9 },
  { name: '1頭', range: '10 ~ 19', size: 10 },
  { name: '2頭', range: '20 ~ 29', size: 10 },
  { name: '3頭', range: '30 ~ 39', size: 10 },
];
const TOTAL_BETS = 9000; // 9 × 10 × 10 × 10

export const Combo9000Tab: React.FC = () => {
  // 遊戲由 Header 的全域切換器決定;9000碰只有 39 選 5 的款玩得起來(supports_combo9000)
  const { game: gameCfg, gameKey, loading: gameLoading } = useGame();
  const { eid, combineEditions } = useEditions();
  // 這個版 × 這款遊戲的盤口:成本用四星每碰單價 combo_cost4、派彩用四星中一碰 combo_prize4
  const oddsReq = useAsync(() => api.getEditionOdds(eid, gameKey), [eid, gameKey]);
  const odds = oddsReq.data?.fields;
  // 登入時流水存後端;未登入沿用前端 state。依版篩選
  const ledger = useLedger('combo9000', INITIAL_COMBO9000_RECORDS, {edition: eid, combine: combineEditions});
  const records = ledger.records;
  const [units, setUnits] = useState<number>(1);

  // 期號 / 日期:預設帶最新一期,使用者可用下拉選單改記到別期(補記 / 修期)
  const histReq = useAsync(() => api.history(gameKey, 30), [gameKey]);
  const latest = histReq.data?.latest ?? null;
  const histByGame = useHistoriesByGame();
  const [issue, setIssue] = useState<string>('');
  const [issueTouched, setIssueTouched] = useState(false);
  const [betDate, setBetDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
  React.useEffect(() => {
    if (issueTouched) return;
    if (latest?.issue) setIssue(latest.issue);
    if (latest?.date) setBetDate(latest.date);
  }, [latest?.issue, latest?.date, issueTouched]);

  // 備援「一鍵對獎」狀態
  const [settleBusy, setSettleBusy] = useState(false);
  const [settleMsg, setSettleMsg] = useState<string | null>(null);

  const supported = !!gameCfg?.supports_combo9000;

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

  // 9000碰 是把 39 顆切成 0/1/2/3 頭四段,49 選 6 的六合彩沒有這種盤。
  if (!supported) {
    return (
      <div className="p-5 sm:p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-2.5 animate-in fade-in duration-200">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-amber-600 dark:text-amber-400" />
          <span className="text-sm font-display font-bold text-neutral-900 dark:text-white">
            {gameCfg.short_name}不適用 9000碰
          </span>
        </div>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 leading-relaxed">
          9000碰 是把 39 顆號碼依十位頭切成 0/1/2/3 頭四段(9 × 10 × 10 × 10)包牌的玩法,
          只有今彩539 與天天樂(都是 39 選 5)適用;{gameCfg.short_name}是
          {gameCfg.num_max} 選 {gameCfg.pick},四段切法與碰數都對不起來。
        </p>
        <p className="text-xs text-neutral-500 dark:text-neutral-400">
          請用上方的彩券切換器改成今彩539 或天天樂。
        </p>
      </div>
    );
  }

  const game = gameCfg.name as LotteryGame;
  // 每碰成本 / 中一碰可得取「這個版」的四星盤口;讀不到先給常見預設
  const betCost = odds?.combo_cost4?.value ?? 50;
  const betPrize = odds?.combo_prize4?.value ?? 750000;

  // 全包固定 9000 碰;支數倍投;過關固定中 2 碰
  const betsWithUnits = TOTAL_BETS * units;
  const submitCost = betsWithUnits * betCost;
  const passPayout = 2 * betPrize * units;

  const handleSubmit = () => {
    ledger.add({
      date: betDate,
      issue,
      game,
      mode: 'combo9000',
      edition: eid,
      units,
      cars: units,
      betsCount: betsWithUnits,
      selectedBalls: [],
      drawBalls: [],
      pillarDist: '',
      result: '待開獎',
      cost: submitCost,
      payout: 0,
      pnl: 0,
    });
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
              Four Heads Matrix (9000 Bets)
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              {gameCfg.short_name}
            </span>
          </div>
          <div className="text-base sm:text-xl font-display font-bold text-neutral-900 dark:text-white mt-0.5">
            9000碰 四段全包控制台
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            包下 9×10×10×10 = {TOTAL_BETS.toLocaleString()} 碰,四段(0/1/2/3 頭)各開出 1 顆即過關固定中 2 碰。
          </div>
        </div>

        <div className="flex items-center justify-between md:justify-end gap-4 border-t md:border-t-0 pt-2.5 md:pt-0 border-black/[0.06] dark:border-white/[0.06]">
          <div className="text-left md:text-right">
            <span className="text-[10px] uppercase tracking-wider text-neutral-400 block">9000碰累積損益</span>
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

          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                01 / 9000碰 全包下注
              </span>
              <span className="text-[11px] font-mono text-neutral-400">
                四段全包 = {TOTAL_BETS.toLocaleString()} 碰
              </span>
            </div>

            <div className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-relaxed">
              9000碰 是固定全包:四段(十位頭)各取一顆組成一碰,共 9×10×10×10 =
              <strong> {TOTAL_BETS.toLocaleString()} 碰</strong>。開獎 5 顆若四段都有落點即過關,
              固定中 2 碰;任一段缺(缺頭)則槓龜。
            </div>

            {/* 四段一覽 */}
            <div className="grid grid-cols-2 gap-1.5">
              {SEGMENTS.map((s, i) => (
                <div
                  key={i}
                  className="p-2.5 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]"
                >
                  <div className="text-[10px] uppercase tracking-wider font-semibold text-neutral-400">
                    {s.name}({s.size} 顆)
                  </div>
                  <div className="text-xs font-mono font-bold mt-0.5 text-neutral-900 dark:text-white">
                    {s.range}
                  </div>
                </div>
              ))}
            </div>

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

            {/* 試算 */}
            <div className="p-3.5 sm:p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-2">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                全包試算 (9000 碰)
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-neutral-500 block text-[10px]">總碰數 × 支:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    {TOTAL_BETS.toLocaleString()} × {units}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">投注碰數:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    {betsWithUnits.toLocaleString()} 碰
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">投注成本:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    NT$ {submitCost.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">過關彩金(中 2 碰):</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    {passPayout.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={handleSubmit}
              className="w-full py-3 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 transition-opacity flex items-center justify-center gap-2 shadow-xs active:scale-98"
            >
              <FileText className="w-4 h-4" />
              送出記帳 {betsWithUnits.toLocaleString()} 碰(待開獎)
            </button>
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
                02 / 9000碰 流水帳與過關核對
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

            {/* Mobile View */}
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
                        draws={histByGame[rec.game]?.draws ?? []}
                        onSelect={(iss) => ledger.resettle(rec.id, iss)}
                        extraOption={histByGame[rec.game]?.next ?? undefined}
                        showNums={false}
                        onRefresh={() => ledger.resettle(rec.id, rec.issue)}
                        onManualHit={(k) => ledger.resettle(rec.id, rec.issue, k)}
                        manualPillars={2}
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
                      <span className="text-neutral-400 block text-[10px]">四段落點</span>
                      <span className="font-mono font-bold text-neutral-800 dark:text-neutral-200">{rec.pillarDist || '—'}</span>
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
                      {rec.betsCount.toLocaleString()} 碰
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
                    <th>四段落點</th>
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
                          draws={histByGame[rec.game]?.draws ?? []}
                          onSelect={(iss) => ledger.resettle(rec.id, iss)}
                          extraOption={histByGame[rec.game]?.next ?? undefined}
                          showNums={false}
                          onRefresh={() => ledger.resettle(rec.id, rec.issue)}
                          onManualHit={(k) => ledger.resettle(rec.id, rec.issue, k)}
                          manualPillars={2}
                          gameLabel={gameCfg.short_name}
                        />
                      </td>
                      <td className="text-xs font-semibold">{rec.game.split('(')[0]}</td>
                      <td className="font-mono text-xs font-bold">{rec.units} 支</td>
                      <td className="font-mono text-xs font-semibold">{rec.pillarDist || '—'}</td>
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
