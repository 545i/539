import React, { useState } from 'react';
import { 
  FileText, 
  CheckCircle2, 
  XCircle,
  TrendingUp,
  RotateCcw,
  Sparkles,
  Minus,
  Plus
} from 'lucide-react';
import { LotteryBallPad } from '../LotteryBallPad';
import { IssuePicker } from '../IssuePicker';
import { BetRecord, LotteryGame } from '../../types';
import { api, ErhePlanDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';
import { useLedger } from '../../api/useLedger';

// 未登入時的示範流水(登入後改用後端自己的紀錄)
const DEMO_RECORDS: BetRecord[] = [
  {
    id: 'mb-demo-1',
    index: 1,
    date: '2026-08-18',
    issue: '115000200',
    game: '今彩539',
    mode: 'multi',
    units: 5,
    cars: 5,
    betsCount: 10,
    selectedBalls: [3, 5, 8, 12, 17, 21, 24, 28, 33, 37],
    drawBalls: [5, 11, 12, 17, 18],
    result: '中了 3 顆',
    cost: 6887,
    payout: 79500,
    pnl: 72613,
    cumPnl: 72613
  }
];

export const MultiBetTab: React.FC = () => {
  // 遊戲由 Header 的全域切換器決定,這裡不再自己記一份
  const { game, gameKey, loading: gameLoading } = useGame();
  const [selectedBalls, setSelectedBalls] = useState<number[]>([3, 5, 8, 12, 17, 21, 24, 28, 33, 37]);
  const [cars, setCars] = useState<number>(5);
  // 期號 / 日期:預設帶最新一期,使用者可用下拉選單改記到別期(補記 / 修期)
  const histReq = useAsync(() => api.history(gameKey, 30), [gameKey]);
  const latest = histReq.data?.latest ?? null;
  const draws = histReq.data?.draws ?? [];
  const [nextIssue, setNextIssue] = useState<string>('');
  const [issueTouched, setIssueTouched] = useState(false);
  const [betDate, setBetDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
  React.useEffect(() => {
    if (issueTouched) return;
    if (latest?.issue) setNextIssue(latest.issue);
    if (latest?.date) setBetDate(latest.date);
  }, [latest?.issue, latest?.date, issueTouched]);
  const pickIssue = (iss: string, d: string) => {
    setNextIssue(iss);
    setBetDate(d);
    setIssueTouched(true);
  };
  // 登入時流水存後端;未登入沿用 v2 的前端 state(含示範資料)
  const ledger = useLedger('multi', DEMO_RECORDS);
  const records = ledger.records;

  const ballCount = selectedBalls.length || 10;
  // 多顆盤口沿用 v2 的換算比例:每顆每車成本 = 每車成本 ÷ 20、每顆每車彩金 = 每車中獎可得 ÷ 4
  // 每顆每車成本 = 二合單顆成本 72.5 × 38 = 2755(與單顆下注一致,不再除 20)
  const costPerCarPerBall = game ? game.default_cost_per_car : 0;
  const prizePerHitPerCar = game ? game.default_win_payout / 4 : 0;
  // 成本與各段中獎回收由後端 core.erhe 算(押 ballCount 顆),盤口帶上面換算後的值。
  // 遊戲清單還沒回來就先不打(盤口會是 0),等 game 進來 deps 一變就自動補算。
  const { data: plan } = useAsync<ErhePlanDTO | null>(
    () =>
      game
        ? api.erhePlan(gameKey, ballCount, cars, {
            cost_per_car: costPerCarPerBall,
            win_payout: prizePerHitPerCar,
          })
        : Promise.resolve(null),
    [gameKey, ballCount, cars, costPerCarPerBall, prizePerHitPerCar],
  );

  const cumPnl = records.length > 0 ? records[records.length - 1].cumPnl : 0;
  const totalSpent = records.reduce((acc, r) => acc + r.cost, 0);
  const totalReturn = records.reduce((acc, r) => acc + r.payout, 0);
  const winCount = records.filter(r => r.payout > 0).length;

  // 規格全部讀 game;還沒載到就先不畫,免得閃一次別款遊戲的數字
  if (!game) {
    return (
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
        {gameLoading ? '載入遊戲設定中…' : '讀不到遊戲設定,請重新整理頁面。'}
      </div>
    );
  }

  const gameName = game.name as LotteryGame;
  const numMax = game.num_max;
  // plan 還沒回來前先用換算比例自估,避免首屏數字跳動
  const payoutOf = (hits: number) =>
    Math.round(plan?.hits.find(h => h.hits === hits)?.payout ?? cars * prizePerHitPerCar * hits);
  const currentCost = Math.round(plan?.total_cost ?? cars * ballCount * costPerCarPerBall);
  const prize1Hit = payoutOf(1);
  const prize2Hits = payoutOf(2);
  const prize3Hits = payoutOf(3);

  const handleToggleBall = (num: number) => {
    if (selectedBalls.includes(num)) {
      setSelectedBalls(selectedBalls.filter(n => n !== num));
    } else {
      if (selectedBalls.length < 20) {
        setSelectedBalls([...selectedBalls, num]);
      }
    }
  };

  const handleRecord = (status: string = '待開獎', hits: number = 0) => {
    const payout = hits > 0 ? hits * prize1Hit : 0;
    const pnl = status === '待開獎' ? 0 : payout - currentCost;

    ledger.add({
      date: betDate,
      issue: nextIssue || '',
      game: gameName,
      mode: 'multi',
      units: cars,
      cars,
      betsCount: selectedBalls.length,
      selectedBalls: [...selectedBalls],
      drawBalls: [],
      result: status,
      cost: currentCost,
      payout,
      pnl
    });
  };

  return (
    <div className="space-y-4 sm:space-y-5 animate-in fade-in duration-200 w-full overflow-hidden">
      {/* Top Banner Bar */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.25em] text-neutral-400 dark:text-neutral-500 font-semibold">
              Multi-Ball Portfolio Strategy
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              {game.short_name}
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              {ballCount} 顆分佈
            </span>
          </div>
          <div className="text-base sm:text-xl font-display font-bold text-neutral-900 dark:text-white mt-0.5">
            多顆下注控制台
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            挑選 8~15 顆潛力號碼矩陣，命中 1 顆即按比例回收彩金。
          </div>
        </div>

        <div className="flex items-center justify-between md:justify-end gap-4 border-t md:border-t-0 pt-2.5 md:pt-0 border-black/[0.06] dark:border-white/[0.06]">
          <div className="text-left md:text-right">
            <span className="text-[10px] uppercase tracking-wider text-neutral-400 block">多顆累積損益</span>
            <div className={`text-xl sm:text-2xl font-mono font-bold ${cumPnl >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}`}>
              {cumPnl >= 0 ? `+${cumPnl.toLocaleString()}` : cumPnl.toLocaleString()}
            </div>
          </div>
          <div className="text-right text-[11px] font-mono text-neutral-400">
            {records.length} 局・中 {winCount} 局
          </div>
        </div>
      </div>

      {/* Main Dual-Column Workbench Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-5">
        
        {/* Left Column (5/12) - Configuration & Execution Panel */}
        <div className="lg:col-span-5 space-y-4">
          
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                01 / 多顆組合參數
              </span>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-mono text-neutral-400">期號</span>
                <IssuePicker issue={nextIssue} date={betDate} draws={draws} onSelect={pickIssue} />
              </div>
            </div>

            {/* Ball Selector Matrix */}
            <div>
              <LotteryBallPad
                selectedBalls={selectedBalls}
                onToggleBall={handleToggleBall}
                onClear={() => setSelectedBalls([])}
                onQuickSelect={(balls) => setSelectedBalls(balls)}
                maxBalls={15}
                totalBalls={numMax}
                label={`選取組合號碼 (建議 8~15 顆)`}
              />
            </div>

            {/* Car Stepper for Mobile */}
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <label className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
                  下注車數 (Cars)
                </label>
                <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">
                  {cars} 車 ({selectedBalls.length} 顆矩陣)
                </span>
              </div>

              {/* Stepper with Large Buttons */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setCars(Math.max(1, cars - 1))}
                  className="w-10 h-10 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  <Minus className="w-4 h-4" />
                </button>
                
                <div className="flex-1 h-10 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] flex items-center justify-center font-mono font-bold text-sm text-neutral-900 dark:text-white">
                  {cars} 車
                </div>

                <button
                  type="button"
                  onClick={() => setCars(cars + 1)}
                  className="w-10 h-10 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>

              {/* Quick Car Selection Pills */}
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

            {/* Live Financial Preview Card */}
            <div className="p-3.5 sm:p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-2">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                多顆損益階梯試算 (Live HUD)
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
                  <span className="text-neutral-500 block text-[10px]">中 3 顆大賺:</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    NT$ {prize3Hits.toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Action Buttons Panel */}
            <div className="pt-2 flex flex-col sm:flex-row gap-2">
              <button
                type="button"
                onClick={() => handleRecord('待開獎', 0)}
                className="w-full py-3 px-4 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity flex items-center justify-center gap-2 shadow-xs active:scale-98"
              >
                <FileText className="w-4 h-4" />
                送出記帳 (待開獎)
              </button>

              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => handleRecord('中了 2 顆', 2)}
                  className="py-2.5 px-3 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold border border-emerald-600/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 transition-colors flex items-center justify-center gap-1 active:scale-95"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  模擬中2顆
                </button>

                <button
                  type="button"
                  onClick={() => handleRecord('槓龜 (0顆)', 0)}
                  className="py-2.5 px-3 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold border border-rose-600/30 text-rose-700 dark:text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 transition-colors flex items-center justify-center gap-1 active:scale-95"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  模擬沒中
                </button>
              </div>
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
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">中獎率 / 局數</div>
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
                02 / 多顆流水帳與開獎核對
              </h3>
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
                        onRefresh={() => ledger.resettle(rec.id, rec.issue)}
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
                      <span className="text-neutral-400 block text-[10px]">下注車數</span>
                      <span className="font-mono font-bold text-neutral-800 dark:text-neutral-200">{rec.cars || rec.units} 車</span>
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

                  <div className="space-y-1 text-[11px] pt-1 border-t border-black/[0.04] dark:border-white/[0.04]">
                    <div className="flex items-center gap-1 flex-wrap">
                      <span className="text-neutral-400 text-[10px]">下注:</span>
                      {rec.selectedBalls.map(b => (
                        <span key={b} className={`px-1 py-0.2 rounded font-mono text-[10px] ${rec.drawBalls.includes(b) ? 'bg-emerald-600 text-white font-bold' : 'bg-black/5 dark:bg-white/10'}`}>
                          {b.toString().padStart(2, '0')}
                        </span>
                      ))}
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
                    <th>車數</th>
                    <th>狀態</th>
                    <th>成本</th>
                    <th>回收</th>
                    <th>本局損益</th>
                    <th>累積損益</th>
                    <th>下注號碼</th>
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
                          onRefresh={() => ledger.resettle(rec.id, rec.issue)}
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
