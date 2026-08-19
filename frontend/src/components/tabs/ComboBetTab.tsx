import React, { useState } from 'react';
import { 
  FileText,
  CheckCircle2,
  TrendingUp,
  RotateCcw,
  Minus,
  Plus
} from 'lucide-react';
import { INITIAL_COMBO_RECORDS } from '../../data/lotteryData';
import { LotteryBallPad } from '../LotteryBallPad';
import { BetRecord, LotteryGame } from '../../types';
import { api, GameKey } from '../../api/client';
import { useAsync } from '../../api/useAsync';

export const ComboBetTab: React.FC = () => {
  const { data: games, loading: gamesLoading, error: gamesError } = useAsync(() => api.games(), []);
  const [records, setRecords] = useState<BetRecord[]>(INITIAL_COMBO_RECORDS);
  const [gameKey, setGameKey] = useState<GameKey>('lotto539');
  const gameCfg = games?.find(g => g.key === gameKey) ?? null;
  // 清單還沒回來前沿用今彩539 的規格,避免首屏數字跳動
  const gameName = (gameCfg?.name ?? '今彩539') as LotteryGame;
  const numMax = gameCfg?.num_max ?? 39;
  const [playMethod, setPlayMethod] = useState<'星碰' | '連碰(全碰)' | '立柱' | '拖膽'>('星碰');
  const [starCount, setStarCount] = useState<'二星' | '三星' | '四星'>('三星');
  const [selectedBalls, setSelectedBalls] = useState<number[]>([3, 6, 12, 15, 22, 25, 32, 35]);
  const [units, setUnits] = useState<number>(12);
  const [betDate, setBetDate] = useState<string>('2026-08-19');

  const handleToggleBall = (num: number) => {
    if (selectedBalls.includes(num)) {
      setSelectedBalls(selectedBalls.filter(n => n !== num));
    } else {
      if (selectedBalls.length < 10) {
        setSelectedBalls([...selectedBalls, num]);
      }
    }
  };

  // Combination formula C(n, k)
  const n = selectedBalls.length;
  const k = starCount === '二星' ? 2 : (starCount === '三星' ? 3 : 4);
  const getComb = (total: number, pick: number) => {
    if (total < pick) return 0;
    let res = 1;
    for (let i = 1; i <= pick; i++) {
      res = (res * (total - i + 1)) / i;
    }
    return res;
  };
  const totalComb = getComb(n, k);
  const costPerComb = 74; // standard base // TODO(api): 需要「每碰成本」欄位(GameDTO 只有三合的 default_bet_cost)
  const currentCost = Math.round(totalComb * costPerComb * (units / 6));
  // 三星每碰彩金 = 後端 default_bet_prize;二星 / 四星後端還沒有對應欄位,先留 v2 原值
  // TODO(api): 需要 default_star_prize(二星 / 四星每碰彩金)
  const prizePerHitComb = starCount === '二星'
    ? 5700
    : (starCount === '三星' ? (gameCfg?.default_bet_prize ?? 57000) : 800000);

  const handleRecord = (status: string = '待開獎') => {
    const isWin = status === '中三星 (1碰)';
    const payout = isWin ? Math.round(prizePerHitComb * (units / 6)) : 0;
    const pnl = status === '待開獎' ? 0 : payout - currentCost;
    const lastCum = records.length > 0 ? records[records.length - 1].cumPnl : 0;

    const newRec: BetRecord = {
      id: `c-${Date.now()}`,
      index: records.length + 1,
      date: betDate,
      issue: '115000201',
      game: gameName,
      mode: 'combo',
      playType: `${playMethod} ${starCount} (${units} 支)`,
      units,
      cars: units,
      betsCount: totalComb,
      selectedBalls: [...selectedBalls],
      drawBalls: [5, 11, 12, 17, 18],
      result: status,
      cost: currentCost,
      payout,
      pnl,
      cumPnl: lastCum + pnl
    };
    setRecords([...records, newRec]);
  };

  const handleUndo = () => {
    if (records.length > 0) {
      setRecords(records.slice(0, -1));
    }
  };

  const totalSpent = records.reduce((acc, r) => acc + r.cost, 0);
  const totalReturn = records.reduce((acc, r) => acc + r.payout, 0);
  const cumPnl = records.length > 0 ? records[records.length - 1].cumPnl : -84336;
  const winCount = records.filter(r => r.payout > 0).length;

  return (
    <div className="space-y-4 sm:space-y-5 animate-in fade-in duration-200 w-full overflow-hidden">
      {/* Top Banner Bar */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] flex flex-col md:flex-row md:items-center justify-between gap-3 sm:gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-[0.25em] text-neutral-400 dark:text-neutral-500 font-semibold">
              Combination Matrix Engine
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              C({n}, {k}) = {totalComb} 碰
            </span>
          </div>
          <div className="text-base sm:text-xl font-display font-bold text-neutral-900 dark:text-white mt-0.5">
            連碰 / 立柱 / 拖膽下注控制台
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            組合碰數演算法：自動試算全碰組數與倍率注數，支援開獎號碼智能對獎。
          </div>
        </div>

        <div className="flex items-center justify-between md:justify-end gap-4 border-t md:border-t-0 pt-2.5 md:pt-0 border-black/[0.06] dark:border-white/[0.06]">
          <div className="text-left md:text-right">
            <span className="text-[10px] uppercase tracking-wider text-neutral-400 block">連碰累積損益</span>
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
                01 / 連碰組合參數
              </span>
              <span className="text-[11px] font-mono text-neutral-400">
                期號: 115000201
              </span>
            </div>

            {/* Game Selector */}
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                彩券種類
              </label>
              <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
                {(games ?? []).map(g => (
                  <button
                    key={g.key}
                    type="button"
                    onClick={() => setGameKey(g.key)}
                    className={`py-1.5 px-1 sm:px-2 rounded-lg text-xs font-semibold truncate transition-all ${
                      gameKey === g.key
                        ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                    }`}
                  >
                    {g.short_name}
                  </button>
                ))}
              </div>
              {gamesLoading && <div className="text-xs text-neutral-400 mt-1">載入遊戲清單…</div>}
              {gamesError && <div className="text-xs text-rose-500 mt-1">{gamesError}</div>}
            </div>

            {/* Method & Stars Grid */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                  玩法方式
                </label>
                <select
                  value={playMethod}
                  onChange={e => setPlayMethod(e.target.value as any)}
                  className="w-full px-3 py-1.5 text-xs rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-800 dark:text-neutral-200"
                >
                  <option value="星碰">星碰</option>
                  <option value="連碰(全碰)">連碰 (全碰)</option>
                  <option value="立柱">立柱</option>
                  <option value="拖膽">拖膽</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                  星數規格
                </label>
                <div className="grid grid-cols-3 gap-1 p-0.5 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
                  {(['二星', '三星', '四星'] as const).map(s => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setStarCount(s)}
                      className={`py-1 text-[11px] font-semibold rounded-lg transition-all ${
                        starCount === s
                          ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                          : 'text-neutral-600 dark:text-neutral-400'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Ball Selector Matrix */}
            <div>
              <LotteryBallPad
                selectedBalls={selectedBalls}
                onToggleBall={handleToggleBall}
                onClear={() => setSelectedBalls([])}
                onQuickSelect={(balls) => setSelectedBalls(balls.slice(0, 8))}
                maxBalls={10}
                totalBalls={numMax}
                label="選取號碼 (目前已選組數)"
              />
            </div>

            {/* Units Multiplier Stepper & Pills */}
            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <label className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
                  下注支數 (Units)
                </label>
                <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">
                  {units} 支 (合計 {totalComb} 碰)
                </span>
              </div>

              {/* Stepper with Large Buttons */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setUnits(Math.max(1, units - 2))}
                  className="w-10 h-10 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  <Minus className="w-4 h-4" />
                </button>
                
                <div className="flex-1 h-10 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] flex items-center justify-center font-mono font-bold text-sm text-neutral-900 dark:text-white">
                  {units} 支
                </div>

                <button
                  type="button"
                  onClick={() => setUnits(units + 2)}
                  className="w-10 h-10 rounded-xl border border-black/10 dark:border-white/10 flex items-center justify-center text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95 transition-all"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>

              <div className="flex flex-wrap gap-1.5 pt-1">
                {[6, 12, 18, 24, 30].map(u => (
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
                組合注數與成本試算 (Live Preview)
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-neutral-500 block text-[10px]">總組合碰數:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    {totalComb} 碰
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">本期總成本:</span>
                  <span className="font-mono font-bold text-sm text-neutral-900 dark:text-white">
                    NT$ {currentCost.toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">命中 1 碰彩金:</span>
                  <span className="font-mono font-bold text-sm text-emerald-600 dark:text-emerald-400">
                    NT$ {Math.round(prizePerHitComb * (units / 6)).toLocaleString()}
                  </span>
                </div>
                <div>
                  <span className="text-neutral-500 block text-[10px]">玩法規格:</span>
                  <span className="font-mono font-bold text-sm text-neutral-800 dark:text-neutral-200">
                    {starCount} 賠率
                  </span>
                </div>
              </div>
            </div>

            {/* Action Buttons Panel */}
            <div className="pt-2 flex flex-col sm:flex-row gap-2">
              <button
                type="button"
                onClick={() => handleRecord('待開獎')}
                className="w-full py-3 px-4 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity flex items-center justify-center gap-2 shadow-xs active:scale-98"
              >
                <FileText className="w-4 h-4" />
                送出記帳 (待開獎)
              </button>

              <button
                type="button"
                onClick={() => handleRecord('中三星 (1碰)')}
                className="py-2.5 px-4 rounded-xl sm:rounded-full text-xs uppercase tracking-wider font-semibold border border-emerald-600/30 text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 transition-colors flex items-center justify-center gap-1.5 active:scale-95"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                模擬中 1 碰
              </button>
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
                02 / 連碰流水帳與開獎核對
              </h3>
              <button
                type="button"
                onClick={handleUndo}
                disabled={records.length === 0}
                className="text-[11px] font-semibold text-neutral-500 hover:text-neutral-900 dark:hover:text-white disabled:opacity-30 transition-colors flex items-center gap-1 active:scale-95"
              >
                <RotateCcw className="w-3 h-3" />
                撤銷上一筆
              </button>
            </div>

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
                      rec.payout > 0 
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
                      <span className="text-neutral-400 block text-[10px]">玩法碰數</span>
                      <span className="font-mono font-bold text-neutral-800 dark:text-neutral-200">{rec.betsCount || 70} 碰</span>
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
                    <th>玩法</th>
                    <th>碰數</th>
                    <th>狀態</th>
                    <th>成本</th>
                    <th>回收</th>
                    <th>損益</th>
                    <th>開獎對號</th>
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
                      <td className="text-xs font-semibold">{rec.playType}</td>
                      <td className="font-mono text-xs">{rec.betsCount || 70} 碰</td>
                      <td>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                          rec.payout > 0 
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
                      <td className="font-mono text-xs">
                        <div className="flex flex-wrap gap-1">
                          {rec.selectedBalls.map(b => (
                            <span key={b} className={`px-1 rounded text-[10px] ${rec.drawBalls.includes(b) ? 'bg-black text-white dark:bg-white dark:text-black font-bold' : 'text-neutral-400'}`}>
                              {b.toString().padStart(2, '0')}
                            </span>
                          ))}
                        </div>
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
