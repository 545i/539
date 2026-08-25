import React from 'react';
import { Menu, Sun, Moon, HelpCircle } from 'lucide-react';
import { ThemeMode } from '../types';
import { useGame } from '../api/useGame';

// 全域遊戲切換器:一處切、全站跟著換。下注頁把它搬進下注流程(當「選遊戲」第一步),
// 其他分析頁仍由 Header 右上角顯示。
export const GameSwitcher: React.FC = () => {
  const { games, gameKey, setGameKey } = useGame();
  if (games.length === 0) return null;
  return (
    <div className="inline-flex p-0.5 rounded-xl bg-black/[0.04] dark:bg-white/[0.06] border border-black/[0.06] dark:border-white/[0.08] gap-0.5">
      {games.map(g => (
        <button
          key={g.key}
          type="button"
          onClick={() => setGameKey(g.key)}
          title={g.name}
          className={`px-2.5 sm:px-3 py-1 rounded-lg text-[11px] sm:text-xs font-semibold transition-all whitespace-nowrap ${
            gameKey === g.key
              ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
              : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
          }`}
        >
          {g.short_name}
        </button>
      ))}
    </div>
  );
};

interface Props {
  theme: ThemeMode;
  onToggleTheme: () => void;
  onOpenMobileMenu: () => void;
  onOpenFormula: () => void;
  title: string;
  // 下注頁把遊戲選擇搬進下注流程,右上角這顆就隱藏;其他(分析)頁保留全站切換。
  showGameSwitcher?: boolean;
}

export const Header: React.FC<Props> = ({
  theme,
  onToggleTheme,
  onOpenMobileMenu,
  onOpenFormula,
  title,
  showGameSwitcher = true
}) => {
  return (
    <header className="sticky top-0 z-30 h-16 bg-[#FFFFFF]/90 dark:bg-[#0A0A0A]/90 backdrop-blur-md border-b border-black/[0.08] dark:border-white/[0.08] px-4 sm:px-8 flex items-center justify-between transition-colors duration-200">
      <div className="flex items-center gap-3">
        <button
          type="button"
          id="mobile-menu-btn"
          onClick={onOpenMobileMenu}
          className="p-2 -ml-1 rounded-xl lg:hidden text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 border border-black/10 dark:border-white/10"
          aria-label="打開選單"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div>
          <div className="text-[9px] uppercase tracking-[0.25em] text-neutral-400 dark:text-neutral-500 font-semibold">
            Dualis Analytics
          </div>
          <h2 className="text-base sm:text-lg font-display font-bold text-[#141414] dark:text-white tracking-wide">
            {title}
          </h2>
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {showGameSwitcher && <GameSwitcher />}
        <button
          type="button"
          id="header-formula-btn"
          onClick={onOpenFormula}
          className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider rounded-full border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
        >
          <HelpCircle className="w-3.5 h-3.5 text-neutral-500" />
          <span>算式說明</span>
        </button>

        <button
          type="button"
          id="header-theme-toggle-btn"
          onClick={onToggleTheme}
          aria-label="切換主題模式"
          className="w-9 h-9 rounded-full border border-black/10 dark:border-white/10 flex items-center justify-center bg-black/[0.02] dark:bg-white/[0.04] text-neutral-800 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 transition-transform active:scale-95"
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-neutral-200" />
          ) : (
            <Moon className="w-4 h-4 text-neutral-800" />
          )}
        </button>
      </div>
    </header>
  );
};
