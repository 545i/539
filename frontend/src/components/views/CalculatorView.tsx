import React, { useState } from 'react';
import { Calculator, Dices, RotateCcw, Info, Hash } from 'lucide-react';
import { LotteryBallPad } from '../LotteryBallPad';
import { api, type GameKey } from '../../api/client';
import { useAsync } from '../../api/useAsync';

// 後端 /api/games 還沒回來(或抓失敗)時用的墊底清單,值與 core/games.py 一致,
// 這樣切換鈕永遠是三顆、版面不會閃動。
type GameOption = { key: GameKey; short_name: string; num_max: number };
const FALLBACK_GAMES: GameOption[] = [
  { key: 'lotto539', short_name: '今彩539', num_max: 39 },
  { key: 'fantasy5', short_name: '天天樂', num_max: 39 },
  { key: 'marksix', short_name: '六合彩', num_max: 49 },
];

export const CalculatorView: React.FC = () => {
  const { data: gamesData } = useAsync(() => api.games(), []);
  const games: GameOption[] = gamesData ?? FALLBACK_GAMES;

  const [gameKey, setGameKey] = useState<GameKey>('lotto539');
  const currentGame = games.find(g => g.key === gameKey) ?? games[0];
  const [star, setStar] = useState<number>(2);
  const [selectedBalls, setSelectedBalls] = useState<number[]>([1, 8, 12, 17, 23, 31]);
  const [costPerBet, setCostPerBet] = useState<number>(80);

  const handleToggleBall = (num: number) => {
    if (selectedBalls.includes(num)) {
      setSelectedBalls(selectedBalls.filter(b => b !== num));
    } else {
      setSelectedBalls([...selectedBalls, num]);
    }
  };

  // Combinations formula C(n, k)
  // TODO(api): 連碰計算端點 —— 目前碰數/成本/組合展開都在前端算,
  // 後端若補上「連碰注數計算」就改成打端點(含拖膽、星碰、立柱的注數規則)。
  const combination = (n: number, k: number): number => {
    if (k < 0 || k > n) return 0;
    if (k === 0 || k === n) return 1;
    let c = 1;
    for (let i = 1; i <= k; i++) {
      c = (c * (n - (k - i))) / i;
    }
    return Math.round(c);
  };

  const n = selectedBalls.length;
  const comboCount = combination(n, star);
  const totalCost = comboCount * costPerBet;

  // Generate sample combinations
  const generateSampleCombos = () => {
    if (selectedBalls.length < star) return [];
    const sorted = [...selectedBalls].sort((a, b) => a - b);
    const results: number[][] = [];
    const recurse = (startIdx: number, current: number[]) => {
      if (current.length === star) {
        results.push([...current]);
        return;
      }
      for (let i = startIdx; i < sorted.length; i++) {
        if (results.length >= 10) return; // limit to 10 previews
        current.push(sorted[i]);
        recurse(i + 1, current);
        current.pop();
      }
    };
    recurse(0, []);
    return results;
  };

  const sampleCombos = generateSampleCombos();

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Header Banner */}
      <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <Calculator className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base sm:text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              連碰矩陣與組合計算機
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              即時精確試算 C(n, k) 組合碰數、總成本階梯與注單展開預覽
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setSelectedBalls([3, 7, 12, 18, 25, 33])}
          className="px-3 py-1.5 rounded-full text-xs font-semibold border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 transition-colors hidden sm:flex items-center gap-1.5"
        >
          <RotateCcw className="w-3 h-3" />
          重設示範號碼
        </button>
      </div>

      {/* Dual Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        
        {/* Left Column (6/12) - Configuration & Ball Pad */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            
            {/* Game & Star Selection */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                  彩券類型
                </label>
                <div className="grid grid-cols-3 gap-1 p-0.5 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
                  {games.map(g => (
                    <button
                      key={g.key}
                      type="button"
                      onClick={() => setGameKey(g.key)}
                      className={`py-1.5 text-xs font-semibold rounded-lg truncate transition-all ${
                        gameKey === g.key
                          ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                          : 'text-neutral-600 dark:text-neutral-400'
                      }`}
                    >
                      {g.short_name}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                  下注星數 (k)
                </label>
                <div className="grid grid-cols-4 gap-1 p-0.5 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
                  {[2, 3, 4, 5].map(s => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setStar(s)}
                      className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                        star === s
                          ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                          : 'text-neutral-600 dark:text-neutral-400'
                      }`}
                    >
                      {s}星
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
                onQuickSelect={(balls) => setSelectedBalls(balls)}
                maxBalls={39}
                totalBalls={currentGame?.num_max ?? 39}
                label={`選取連碰號碼 (${selectedBalls.length} 顆)`}
              />
            </div>

            {/* Cost Per Bet Config */}
            {/* TODO(api): 連碰盤口端點 —— 單碰價格目前是寫死的四段預設,
                後端 GameDTO 只有單顆/三柱的 default_*,沒有連碰單碰價。 */}
            <div className="flex items-center justify-between pt-1">
              <label className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
                單碰基準成本 (元)
              </label>
              <div className="flex items-center gap-1.5">
                {[60, 74, 80, 100].map(c => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setCostPerBet(c)}
                    className={`px-2.5 py-1 text-xs font-mono rounded-full border transition-all ${
                      costPerBet === c
                        ? 'bg-black text-white dark:bg-white dark:text-black border-black dark:border-white'
                        : 'border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-300'
                    }`}
                  >
                    ${c}
                  </button>
                ))}
              </div>
            </div>

          </div>
        </div>

        {/* Right Column (6/12) - Calculation Results & Combinations Deck */}
        <div className="lg:col-span-6 space-y-4">
          
          {/* 4 Summary Tiles */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">選取總顆數 (n)</div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white mt-0.5">{n} 顆</div>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">總碰數 C({n},{star})</div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white mt-0.5">{comboCount.toLocaleString()} 碰</div>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">單碰價格</div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white mt-0.5">NT$ {costPerBet}</div>
            </div>

            <div className="p-4 rounded-xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">總下注成本</div>
              <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-0.5">
                NT$ {totalCost.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Sample Combinations Preview Card */}
          <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs sm:text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-1.5">
                <Hash className="w-4 h-4 text-neutral-500" />
                <span>注單組合展開預覽 (前 {sampleCombos.length} 組)</span>
              </h3>
              <span className="text-[10px] font-mono text-neutral-400">共 {comboCount} 碰</span>
            </div>

            {sampleCombos.length === 0 ? (
              <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.02] border border-black/[0.06] dark:border-white/[0.06] text-xs text-neutral-500">
                請在左方至少選取 {star} 顆號碼以產生組合。
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
                {sampleCombos.map((combo, idx) => (
                  <div key={idx} className="p-2 rounded-lg bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] flex items-center justify-between">
                    <span className="text-[10px] font-mono text-neutral-400">#{idx + 1}</span>
                    <div className="flex gap-1 font-mono font-bold text-xs text-neutral-900 dark:text-white">
                      {combo.map(b => (
                        <span key={b} className="px-1.5 py-0.5 rounded bg-black/5 dark:bg-white/10">
                          {b.toString().padStart(2, '0')}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Combinations Ladder Formula Table */}
          <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-2 text-xs">
            <div className="flex items-center gap-1.5 font-bold text-neutral-900 dark:text-white">
              <Info className="w-3.5 h-3.5 text-neutral-500" />
              <span>C(n, k) 快速碰數對照表 (2星 ~ 4星)</span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-center pt-1 font-mono text-[11px]">
              <div className="p-2 rounded bg-white dark:bg-[#161616] border border-black/[0.06] dark:border-white/[0.06]">
                <div className="text-neutral-400">5 顆 (2星)</div>
                <div className="font-bold text-neutral-900 dark:text-white">10 碰</div>
              </div>
              <div className="p-2 rounded bg-white dark:bg-[#161616] border border-black/[0.06] dark:border-white/[0.06]">
                <div className="text-neutral-400">8 顆 (3星)</div>
                <div className="font-bold text-neutral-900 dark:text-white">56 碰</div>
              </div>
              <div className="p-2 rounded bg-white dark:bg-[#161616] border border-black/[0.06] dark:border-white/[0.06]">
                <div className="text-neutral-400">10 顆 (3星)</div>
                <div className="font-bold text-neutral-900 dark:text-white">120 碰</div>
              </div>
              <div className="p-2 rounded bg-white dark:bg-[#161616] border border-black/[0.06] dark:border-white/[0.06]">
                <div className="text-neutral-400">12 顆 (4星)</div>
                <div className="font-bold text-neutral-900 dark:text-white">495 碰</div>
              </div>
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};
