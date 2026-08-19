import React, { useMemo, useState } from 'react';
import { 
  ChevronRight, 
  ChevronDown, 
  AlertTriangle, 
  FileText, 
  Info,
  CheckCircle2,
  XCircle,
  Layers,
  RotateCcw,
  Minus,
  Plus
} from 'lucide-react';
import { INITIAL_PILLAR_RECORDS, PILLAR_THEORY_ROWS } from '../../data/lotteryData';
import { LotteryGame } from '../../types';
import { api, GameKey, PartialBetsDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useLedger } from '../../api/useLedger';
import { LotteryBallPad } from '../LotteryBallPad';

export const ThreePillarTab: React.FC = () => {
  // 登入時流水存後端;未登入沿用 v2 的前端 state(含示範資料)
  const ledger = useLedger('pillar1800', INITIAL_PILLAR_RECORDS);
  const records = ledger.records;
  const [gameKey, setGameKey] = useState<GameKey>('lotto539');
  const [units, setUnits] = useState<number>(1);
  const [issue, setIssue] = useState<string>('115000201');
  const [betDate, setBetDate] = useState<string>('2026-08-19');
  const [isTheoryOpen, setIsTheoryOpen] = useState(false);
  const [selectedBalls, setSelectedBalls] = useState<number[]>([]);

  // 遊戲清單:只留支援三柱包牌的
  const gamesReq = useAsync(() => api.games(), []);
  const pillarGames = useMemo(
    () => (gamesReq.data || []).filter(g => g.supports_pillar),
    [gamesReq.data],
  );
  const currentGame =
    pillarGames.find(g => g.key === gameKey) || pillarGames[0] || null;
  const activeKey: GameKey = currentGame ? currentGame.key : gameKey;
  const game = (currentGame ? currentGame.name : '今彩539') as LotteryGame;

  // 三柱基本盤(注數 / 過關率)
  const infoReq = useAsync(() => api.pillarInfo(activeKey), [activeKey]);
  const totalBets = infoReq.data ? infoReq.data.total_bets : 1800;
  const passProb = infoReq.data ? infoReq.data.pass_prob : null;

  // 部分包牌(選號變動就重算)
  const partialReq = useAsync<PartialBetsDTO | null>(
    () =>
      selectedBalls.length === 0
        ? Promise.resolve(null)
        : api.pillarPartial(activeKey, selectedBalls),
    [activeKey, selectedBalls.join(',')],
  );

  // 區間組合斷檔提醒
  const pairsReq = useAsync(() => api.tensPairs(activeKey, 3), [activeKey]);

  const betCost = currentGame ? currentGame.default_bet_cost : 63;
  const betPrize = currentGame ? currentGame.default_bet_prize : 57000;
  const unitCost = totalBets * betCost; // 1800 x 63
  const prize4 = 4 * betPrize;
  const prize3 = 3 * betPrize;
  const currentCost = units * unitCost;

  const handleRecord = (resultType: '待開獎' | '中 4 碰' | '中 3 碰' | '槓龜(斷柱)') => {
    let payout = 0;
    if (resultType === '中 4 碰') payout = units * prize4;
    if (resultType === '中 3 碰') payout = units * prize3;
    const pnl = resultType === '待開獎' ? 0 : payout - currentCost;

    ledger.add({
      date: betDate,
      issue,
      game,
      mode: 'pillar1800',
      units,
      cars: units,
      betsCount: units * totalBets,
      selectedBalls: [],
      drawBalls: [5, 10, 16, 28, 39],
      pillarDist: resultType === '中 4 碰' ? '2 + 2 + 1' : (resultType === '中 3 碰' ? '2 + 1 + 2' : '3 + 2 + 0'),
      result: resultType,
      cost: currentCost,
      payout,
      pnl
    });
  };

  const totalSpent = records.reduce((acc, r) => acc + r.cost, 0);
  const totalReturn = records.reduce((acc, r) => acc + r.payout, 0);
  const cumPnl = records.length > 0 ? records[records.length - 1].cumPnl : 0;
  const winCount = records.filter(r => r.payout > 0).length;

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
              過關率 {passProb !== null ? `${(passProb * 100).toFixed(2)}%` : '—'}
            </span>
          </div>
          <div className="text-base sm:text-xl font-display font-bold text-neutral-900 dark:text-white mt-0.5">
            三柱 1800 碰包牌控制台
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            包下 9×10×20 = 1,800 注全組合，三柱各開出 1 顆即保證過關獲利。
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
        <div className="lg:col-span-5 space-y-4">
          
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                01 / 三柱下注配置
              </span>
              <span className="text-[11px] font-mono text-neutral-400">
                1 支 = {totalBets.toLocaleString()} 注
              </span>
            </div>

            {/* Game Selector */}
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                彩券種類
              </label>
              <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
                {pillarGames.map(g => (
                  <button
                    key={g.key}
                    type="button"
                    onClick={() => {
                      setGameKey(g.key);
                      setSelectedBalls([]);
                    }}
                    className={`py-1.5 px-2 rounded-lg text-xs font-semibold truncate transition-all ${
                      activeKey === g.key
                        ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                    }`}
                  >
                    {g.name.split('(')[0]}
                  </button>
                ))}
              </div>
              {gamesReq.loading && (
                <div className="text-xs text-neutral-400 mt-1.5">載入彩券清單中…</div>
              )}
              {gamesReq.error && (
                <div className="text-xs text-rose-500 mt-1.5">{gamesReq.error}</div>
              )}
            </div>

            {/* Pillar Structure Visualizer Cards */}
            <div className="space-y-2">
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
                固定包牌柱位矩陣 (39 顆全包)
              </label>
              
              <div className="grid grid-cols-3 gap-2">
                <div className="p-2.5 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]">
                  <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">第一柱 (9顆)</div>
                  <div className="text-xs font-mono font-bold text-neutral-900 dark:text-white mt-0.5">10 ~ 18</div>
                  <div className="text-[9px] text-neutral-400">10 11 12 13 14...</div>
                </div>

                <div className="p-2.5 rounded-xl border border-amber-500/20 bg-amber-500/5">
                  <div className="text-[10px] uppercase tracking-wider text-amber-600 dark:text-amber-400 font-semibold">第二柱 (10顆)</div>
                  <div className="text-xs font-mono font-bold text-amber-700 dark:text-amber-300 mt-0.5">20 ~ 29</div>
                  <div className="text-[9px] text-amber-600/70">20 21 22 23 24...</div>
                </div>

                <div className="p-2.5 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
                  <div className="text-[10px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold">第三柱 (20顆)</div>
                  <div className="text-xs font-mono font-bold text-emerald-700 dark:text-emerald-300 mt-0.5">01-09+30s</div>
                  <div className="text-[9px] text-emerald-600/70">01~09, 19, 30~39</div>
                </div>
              </div>
            </div>

            {/* Units Multiplier Stepper */}
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <label className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
                  包牌支數 (Units)
                </label>
                <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">
                  {units} 支 ({units * totalBets} 注)
                </span>
              </div>

              {/* Stepper with Large Buttons */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setUnits(Math.max(1, units - 1))}
                  className="w-10 h-10 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  <Minus className="w-4 h-4" />
                </button>
                
                <div className="flex-1 h-10 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] flex items-center justify-center font-mono font-bold text-sm text-neutral-900 dark:text-white">
                  {units} 支
                </div>

                <button
                  type="button"
                  onClick={() => setUnits(units + 1)}
                  className="w-10 h-10 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>

              {/* Quick Preset Pills */}
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[1, 2, 3, 5].map(u => (
                  <button
                    key={u}
                    type="button"
                    onClick={() => setUnits(u)}
                    className={`flex-1 py-1 text-xs font-mono font-semibold rounded-lg border transition-all active:scale-95 ${
                      units === u
                        ? 'bg-black text-white dark:bg-white dark:text-black border-black dark:border-white'
                        : 'border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
                    }`}
                  >
                    {u} 支
                  </button>
                ))}
              </div>
            </div>

            {/* Live Financial Preview Card */}
            <div className="p-3.5 sm:p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-2">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                成本與過關彩金試算 (Live HUD)
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-neutral-500 block text-[10px]">本局投入成本:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    NT$ {currentCost.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">過關機率:</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    {passProb !== null
                      ? `${(passProb * 100).toFixed(2)}% (1/${(1 / passProb).toFixed(1)}局)`
                      : '—'}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">開 3 碰彩金 (2+2+1):</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    NT$ {(units * prize3).toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">開 4 碰彩金 (2+1+2):</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    NT$ {(units * prize4).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Action Buttons Panel */}
            <div className="pt-2 space-y-2">
              <button
                type="button"
                onClick={() => handleRecord('待開獎')}
                className="w-full py-3 px-4 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity flex items-center justify-center gap-2 shadow-xs active:scale-98"
              >
                <FileText className="w-4 h-4" />
                送出記帳 (待開獎)
              </button>

              <div className="grid grid-cols-3 gap-1.5">
                <button
                  type="button"
                  onClick={() => handleRecord('中 4 碰')}
                  className="py-2.5 px-2 rounded-xl text-[11px] font-semibold border border-emerald-600/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 transition-colors flex items-center justify-center gap-1 active:scale-95"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  模擬中4碰
                </button>

                <button
                  type="button"
                  onClick={() => handleRecord('中 3 碰')}
                  className="py-2.5 px-2 rounded-xl text-[11px] font-semibold border border-emerald-600/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 transition-colors flex items-center justify-center gap-1 active:scale-95"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  模擬中3碰
                </button>

                <button
                  type="button"
                  onClick={() => handleRecord('槓龜(斷柱)')}
                  className="py-2.5 px-2 rounded-xl text-[11px] font-semibold border border-rose-600/30 text-rose-700 dark:text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 transition-colors flex items-center justify-center gap-1 active:scale-95"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  模擬斷柱
                </button>
              </div>
            </div>
          </div>

          {/* 自選號碼・部分包牌 */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                02 / 自選號碼・部分包牌
              </span>
              <span className="text-[11px] font-mono text-neutral-400">
                全包 {totalBets.toLocaleString()} 注
              </span>
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
              totalBalls={currentGame ? currentGame.num_max : 39}
              maxBalls={currentGame ? currentGame.num_max : 39}
              label="自選包牌號碼"
            />

            {partialReq.loading && (
              <div className="text-xs text-neutral-400">計算注數中…</div>
            )}
            {partialReq.error && (
              <div className="text-xs text-rose-500">{partialReq.error}</div>
            )}

            {!partialReq.loading && !partialReq.error && !partialReq.data && (
              <div className="text-xs text-neutral-400">
                尚未選號。三柱各選幾顆，就組出幾注。
              </div>
            )}

            {partialReq.data && (
              <div className="space-y-2.5">
                <div className="grid grid-cols-3 gap-2">
                  <div className="p-2.5 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03]">
                    <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">第一柱</div>
                    <div className="text-xs font-mono font-bold text-neutral-900 dark:text-white mt-0.5">
                      {partialReq.data.counts[0]} 顆
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl border border-amber-500/20 bg-amber-500/5">
                    <div className="text-[10px] uppercase tracking-wider text-amber-600 dark:text-amber-400 font-semibold">第二柱</div>
                    <div className="text-xs font-mono font-bold text-amber-700 dark:text-amber-300 mt-0.5">
                      {partialReq.data.counts[1]} 顆
                    </div>
                  </div>
                  <div className="p-2.5 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
                    <div className="text-[10px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold">第三柱</div>
                    <div className="text-xs font-mono font-bold text-emerald-700 dark:text-emerald-300 mt-0.5">
                      {partialReq.data.counts[2]} 顆
                    </div>
                  </div>
                </div>

                <div className="p-3.5 sm:p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-2">
                  <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                    部分包牌試算
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-neutral-500 block text-[10px]">可組出注數:</span>
                      <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                        {partialReq.data.bets.toLocaleString()} / {partialReq.data.total.toLocaleString()} 注
                      </span>
                    </div>
                    <div>
                      <span className="text-neutral-500 block text-[10px]">涵蓋率:</span>
                      <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                        {(partialReq.data.coverage * 100).toFixed(2)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-neutral-500 block text-[10px]">投注成本:</span>
                      <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                        NT$ {(partialReq.data.bets * betCost).toLocaleString()}
                      </span>
                    </div>
                    <div>
                      <span className="text-neutral-500 block text-[10px]">已選號碼:</span>
                      <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                        {selectedBalls.length} 顆
                      </span>
                    </div>
                  </div>
                </div>

                {partialReq.data.buyable ? (
                  <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-800 dark:text-emerald-300 flex items-start gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    <span>三柱都有號碼，這組選號可以下注。</span>
                  </div>
                ) : (
                  <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-700 dark:text-rose-400 flex items-start gap-2">
                    <XCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    <span>某柱未選，組不出任何一注。</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 區間組合斷檔提醒 */}
          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                03 / 區間組合斷檔提醒
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
              {(pairsReq.data || []).map(p => (
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
              ))}
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
                      <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">
                        {rec.issue}
                      </span>
                      <span className="text-[10px] text-neutral-400">
                        {rec.date}
                      </span>
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
                      1,800 注全包
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
                        <div className="text-xs font-mono font-bold">{rec.issue}</div>
                        <div className="text-[10px] text-neutral-400">{rec.date}</div>
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
