import React, { useState } from 'react';
import { 
  FileText,
  CheckCircle2,
  TrendingUp,
  Trash2,
  Minus,
  Plus
} from 'lucide-react';
import { INITIAL_COMBO_RECORDS } from '../../data/lotteryData';
import { LotteryBallPad } from '../LotteryBallPad';
import { IssuePicker } from '../IssuePicker';
import { BetTargetSelector } from '../BetTargetSelector';
import { LotteryGame } from '../../types';
import { api } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';
import { useLedger } from '../../api/useLedger';
import { useHistoriesByGame } from '../../api/useHistories';
import { useEditions } from '../../api/useEditions';

// UI 的中文玩法名 → core.combo 的 play key(注數規則由後端依這個決定)
type PlayMethod = '星碰' | '連碰(全碰)' | '立柱' | '拖膽';
const PLAY_KEYS: Record<PlayMethod, 'star' | 'combo' | 'pillar' | 'dan'> = {
  '星碰': 'star',
  '連碰(全碰)': 'combo',
  '立柱': 'pillar',
  '拖膽': 'dan',
};

export const ComboBetTab: React.FC = () => {
  // 遊戲由 Header 的全域切換器決定,這裡不再自己記一份
  const { game, gameKey, loading: gameLoading } = useGame();
  const { eid, combineEditions } = useEditions();
  // 這個版 × 這款遊戲的盤口(連碰各星數每碰成本 / 派彩)
  const oddsReq = useAsync(() => api.getEditionOdds(eid, gameKey), [eid, gameKey]);
  const odds = oddsReq.data?.fields;
  // 登入時流水存後端;未登入沿用 v2 的前端 state。依版篩選
  const ledger = useLedger('combo', INITIAL_COMBO_RECORDS, {edition: eid, combine: combineEditions});
  const records = ledger.records;
  const [playMethod, setPlayMethod] = useState<PlayMethod>('星碰');
  const [starCount, setStarCount] = useState<'二星' | '三星' | '四星'>('三星');
  const [selectedBalls, setSelectedBalls] = useState<number[]>([3, 6, 12, 15, 22, 25, 32, 35]);
  const [units, setUnits] = useState<number>(12);
  // 期號 / 日期:預設帶最新一期,使用者可用下拉選單改記到別期(補記 / 修期)
  const histReq = useAsync(() => api.history(gameKey, 30), [gameKey]);
  const latest = histReq.data?.latest ?? null;
  const draws = histReq.data?.draws ?? [];
  // 核對列的期號選擇器用「那列記錄自己的遊戲」的期別(混合顯示各遊戲,不能用全域遊戲)
  const histByGame = useHistoriesByGame();
  const [curIssue, setCurIssue] = useState<string>('');
  const [issueTouched, setIssueTouched] = useState(false);
  const [betDate, setBetDate] = useState<string>(() => new Date().toISOString().slice(0, 10));
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
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

  const n = selectedBalls.length;
  const k = starCount === '二星' ? 2 : (starCount === '三星' ? 3 : 4);

  // 星碰只適用 39 選 5 的款(今彩539 / 天天樂)。六合彩選到星碰就當成連碰算 ——
  // 這裡不去動 playMethod state,切回今彩539 時使用者原本選的星碰會自己回來。
  const starAllowed = game ? game.supports_pillar : true;
  const activePlay: PlayMethod =
    !starAllowed && playMethod === '星碰' ? '連碰(全碰)' : playMethod;

  // 碰數 / 每碰成本 / 每碰彩金全部走後端 core.combo —— 四種玩法的碰數規則不同
  // (星碰 C(選幾顆,星數)、立柱多一顆膽),前端自己算 C(n,k) 會把它們算成同一個。
  // 每碰成本 / 派彩帶入「這個版」的盤口(讀不到就讓後端用預設市場價)
  const perBet = odds?.[`combo_cost${k}`]?.value;
  const prizeOdds = odds?.[`combo_prize${k}`]?.value;
  const { data: calc } = useAsync(
    () => api.comboCalc({
      game: gameKey, play: PLAY_KEYS[activePlay], stars: k, picked: n,
      per_bet: perBet, prize: prizeOdds,
    }),
    [gameKey, activePlay, k, n, perBet, prizeOdds],
  );

  const totalSpent = records.reduce((acc, r) => acc + r.cost, 0);
  const totalReturn = records.reduce((acc, r) => acc + r.payout, 0);
  const cumPnl = records.length > 0 ? records[records.length - 1].cumPnl : 0;
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
  const totalComb = calc?.bets ?? 0;
  const prizePerHitComb = calc?.prize_per_hit ?? 0;
  // 一支 = 買滿這張的全部碰數;總成本 = 單支成本(碰數×每碰) × 支數
  const currentCost = Math.round((calc?.total_cost ?? 0) * units);

  const handleToggleBall = (num: number) => {
    if (selectedBalls.includes(num)) {
      setSelectedBalls(selectedBalls.filter(n2 => n2 !== num));
    } else {
      // 不限顆數:選到號碼上限為止(碰數由後端依實際顆數 C(n,k) 動態算)
      if (selectedBalls.length < numMax) {
        setSelectedBalls([...selectedBalls, num]);
      }
    }
  };

  const handleRecord = (status: string = '待開獎') => {
    const isWin = status === '中三星 (1碰)';
    const payout = isWin ? Math.round(prizePerHitComb * units) : 0;
    const pnl = status === '待開獎' ? 0 : payout - currentCost;

    ledger.add({
      date: betDate,
      issue: curIssue || '',
      game: gameName,
      mode: 'combo',
      edition: eid,
      playType: `${activePlay} ${starCount} (${units} 支)`,
      units,
      cars: units,
      betsCount: totalComb,
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
              Combination Matrix Engine
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-mono bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300">
              {game.short_name}
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

          <BetTargetSelector />

          <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-display font-bold uppercase tracking-wider text-neutral-900 dark:text-white">
                01 / 連碰組合參數
              </span>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-mono text-neutral-400">期號</span>
                <IssuePicker issue={curIssue} date={betDate} draws={draws} extraOption={histReq.data?.next ?? undefined} onSelect={pickIssue} />
              </div>
            </div>

            {/* Method & Stars Grid */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                  玩法方式
                </label>
                <select
                  value={activePlay}
                  onChange={e => setPlayMethod(e.target.value as PlayMethod)}
                  className="w-full px-3 py-1.5 text-xs rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-800 dark:text-neutral-200"
                >
                  {starAllowed && <option value="星碰">星碰</option>}
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

            {!starAllowed && (
              <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-800 dark:text-amber-300">
                {game.short_name}不適用星碰(星碰是 39 選 5 的玩法),已改用連碰計算。
                要用星碰請在上方切換成今彩539 / 天天樂。
              </div>
            )}

            {/* Ball Selector Matrix */}
            <div>
              <LotteryBallPad
                selectedBalls={selectedBalls}
                onToggleBall={handleToggleBall}
                onClear={() => setSelectedBalls([])}
                onQuickSelect={(balls) => setSelectedBalls(balls)}
                maxBalls={numMax}
                totalBalls={numMax}
                label={`選取號碼 (已選 ${n} 顆・${k} 星 = ${totalComb} 碰)`}
                layout="grid"
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
                    NT$ {Math.round(prizePerHitComb * units).toLocaleString()}
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
                        draws={histByGame[rec.game]?.draws ?? []}
                        onSelect={(iss) => ledger.resettle(rec.id, iss)}
                        extraOption={histByGame[rec.game]?.next ?? undefined}
                        showNums={false}
                        onRefresh={() => ledger.resettle(rec.id, rec.issue)}
                        onManualHit={(k) => ledger.resettle(rec.id, rec.issue, k)}
                      />
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
                    <div className="flex items-center justify-between gap-1">
                      <div className="flex items-center gap-1 flex-wrap">
                        <span className="text-neutral-400 text-[10px]">下注:</span>
                        {rec.selectedBalls.map(b => (
                          <span key={b} className={`px-1 py-0.2 rounded font-mono text-[10px] ${rec.drawBalls.includes(b) ? 'bg-emerald-600 text-white font-bold' : 'bg-black/5 dark:bg-white/10'}`}>
                            {b.toString().padStart(2, '0')}
                          </span>
                        ))}
                      </div>
                      {confirmDeleteId === rec.id ? (
                        <button
                          type="button"
                          onClick={() => { ledger.deleteById(rec.id); setConfirmDeleteId(null); }}
                          className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-semibold bg-rose-600 text-white hover:bg-rose-700 transition-colors"
                        >
                          確認?
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(rec.id)}
                          title="撤銷這一筆"
                          className="shrink-0 inline-flex items-center p-1 rounded-md text-neutral-400 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-black/5 dark:hover:bg-white/5 transition-colors active:scale-95"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
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
                    <th>撤銷</th>
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
                        />
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
