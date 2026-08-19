import React, { useEffect, useState } from 'react';
import { Settings, Sliders, Moon, Sun, Save } from 'lucide-react';
import { ThemeMode } from '../../types';
import { api } from '../../api/client';
import { useAsync } from '../../api/useAsync';

interface Props {
  theme: ThemeMode;
  onToggleTheme: () => void;
}

export const SettingsView: React.FC<Props> = ({ theme, onToggleTheme }) => {
  // 盤口欄位的預設值改由後端 GameDTO 的 default_* 帶入(今彩539);
  // 下面的字面值只是後端還沒回來前的初值,與 core/games.py 相同。
  const { data: games } = useAsync(() => api.games(), []);
  const [pillarCost, setPillarCost] = useState<number>(63);
  const [pillarPrize, setPillarPrize] = useState<number>(57000);
  const [singleCarCost, setSingleCarCost] = useState<number>(2755);
  const [singleCarPrize, setSingleCarPrize] = useState<number>(21200);
  const [seeded, setSeeded] = useState(false);

  useEffect(() => {
    if (seeded || !games) return;
    const g = games.find(x => x.key === 'lotto539') ?? games[0];
    if (!g) return;
    setPillarCost(g.default_bet_cost);
    setPillarPrize(g.default_bet_prize);
    setSingleCarCost(g.default_cost_per_car);
    setSingleCarPrize(g.default_win_payout);
    setSeeded(true); // 只帶一次,之後不覆蓋使用者輸入
  }, [games, seeded]);

  // TODO(api): 設定儲存端點 —— 後端沒有寫入盤口參數的端點,維持 v2 的模擬儲存。
  // TODO(api): autoupdate 狀態端點 —— 本頁目前沒有「開獎資料更新狀態」區塊,
  // 後端補上 /api/autoupdate/status 後才在此新增(不自行加沒有資料來源的 UI)。
  const handleSave = () => {
    alert('已成功儲存盤口與偏好設定！');
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <Settings className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              系統與盤口設定
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              自訂下注成本、派彩金額、外觀佈景與三柱1800碰參數
            </p>
          </div>
        </div>
      </div>

      {/* Theme Settings */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
          {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
          <span>介面外觀主題 (深色 / 亮色)</span>
        </h3>

        <div className="flex items-center justify-between p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
          <div>
            <div className="font-semibold text-xs text-neutral-900 dark:text-white">
              目前模式: {theme === 'dark' ? '極致沉浸黑 (Sophisticated Dark)' : '典雅明亮白 (Editorial Light)'}
            </div>
            <div className="text-[11px] text-neutral-500 mt-0.5">高對比極簡視覺語彙，支援隨系統或手動切換</div>
          </div>
          <button
            type="button"
            onClick={onToggleTheme}
            className="px-4 py-2 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity"
          >
            切換為 {theme === 'dark' ? '亮色模式' : '深色模式'}
          </button>
        </div>
      </div>

      {/* Odds Parameters */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
          <Sliders className="w-4 h-4" />
          <span>盤口設定 — 三柱 1800 碰</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
              每注成本 (元)
            </label>
            <input
              type="number"
              value={pillarCost}
              onChange={e => setPillarCost(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
              中一注可得 (元)
            </label>
            <input
              type="number"
              value={pillarPrize}
              onChange={e => setPillarPrize(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
            />
          </div>
        </div>

        <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2 pt-3 border-t border-black/[0.06] dark:border-white/[0.06]">
          <Sliders className="w-4 h-4" />
          <span>盤口設定 — 單顆下注 (今彩539)</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
              每車成本 (元)
            </label>
            <input
              type="number"
              value={singleCarCost}
              onChange={e => setSingleCarCost(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500 mb-1.5">
              中獎可得 (元)
            </label>
            <input
              type="number"
              value={singleCarPrize}
              onChange={e => setSingleCarPrize(Number(e.target.value) || 0)}
              className="w-full px-3 py-2 text-xs sm:text-sm rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-900 dark:text-white font-mono focus:outline-hidden"
            />
          </div>
        </div>

        <div className="pt-3">
          <button
            type="button"
            onClick={handleSave}
            className="px-6 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity flex items-center gap-2 shadow-xs"
          >
            <Save className="w-3.5 h-3.5" />
            儲存所有設定
          </button>
        </div>
      </div>
    </div>
  );
};
