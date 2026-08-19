import React from 'react';
import { Menu, Sun, Moon, HelpCircle } from 'lucide-react';
import { ThemeMode } from '../types';

interface Props {
  theme: ThemeMode;
  onToggleTheme: () => void;
  onOpenMobileMenu: () => void;
  onOpenFormula: () => void;
  title: string;
}

export const Header: React.FC<Props> = ({
  theme,
  onToggleTheme,
  onOpenMobileMenu,
  onOpenFormula,
  title
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
