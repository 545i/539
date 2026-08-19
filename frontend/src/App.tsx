import React, { useState, useEffect } from 'react';
import { 
  ChevronRight, 
  ChevronDown, 
  ShieldAlert,
  Info
} from 'lucide-react';
import { NavItem, DuoBetTab, ThemeMode } from './types';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { FormulaModal } from './components/FormulaModal';
import { SingleBetTab } from './components/tabs/SingleBetTab';
import { MultiBetTab } from './components/tabs/MultiBetTab';
import { ThreePillarTab } from './components/tabs/ThreePillarTab';
import { ComboBetTab } from './components/tabs/ComboBetTab';
import { TotalPnLTab } from './components/tabs/TotalPnLTab';
import { CalculatorView } from './components/views/CalculatorView';
import { AnalysisView } from './components/views/AnalysisView';
import { ExportView } from './components/views/ExportView';
import { LeaderboardView } from './components/views/LeaderboardView';
import { SettingsView } from './components/views/SettingsView';

export default function App() {
  // Theme state
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('lottery_theme');
    return (saved as ThemeMode) || 'dark';
  });

  // Navigation state
  const [activeNav, setActiveNav] = useState<NavItem>('duo_bet');
  const [duoTab, setDuoTab] = useState<DuoBetTab>('pillar1800');

  // UI expanders
  const [isHowToUseOpen, setIsHowToUseOpen] = useState(false);
  const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);
  const [isFormulaModalOpen, setIsFormulaModalOpen] = useState(false);
  const [formulaModalType, setFormulaModalType] = useState<'formula' | 'disclaimer'>('formula');
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  // Sync theme class to documentElement
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('lottery_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  const openFormula = () => {
    setFormulaModalType('formula');
    setIsFormulaModalOpen(true);
  };

  const openDisclaimer = () => {
    setFormulaModalType('disclaimer');
    setIsFormulaModalOpen(true);
  };

  const duoTabList: { id: DuoBetTab; label: string; count?: number }[] = [
    { id: 'single', label: '單顆下注', count: 0 },
    { id: 'multi', label: '多顆下注', count: 0 },
    { id: 'pillar1800', label: '三柱1800碰', count: 2 },
    { id: 'combo', label: '連碰', count: 2 },
    { id: 'totals', label: '總損益' },
  ];

  const getNavTitle = () => {
    switch (activeNav) {
      case 'duo_bet': return '二合買牌';
      case 'calculator': return '連碰計算機';
      case 'analysis': return '統計分析';
      case 'export': return '匯出中心';
      case 'leaderboard': return '績效榜單';
      case 'settings': return '系統設定';
      default: return '彩券統計分析';
    }
  };

  return (
    <div className="min-h-screen bg-[#F9F9F7] dark:bg-[#0A0A0A] text-[#141414] dark:text-[#EAEAEA] flex flex-col font-sans transition-colors duration-200 antialiased selection:bg-black selection:text-white dark:selection:bg-white dark:selection:text-black">
      {/* Left Sidebar */}
      <Sidebar
        activeNav={activeNav}
        onSelectNav={setActiveNav}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenFormula={openFormula}
        onOpenDisclaimer={openDisclaimer}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Layout Area */}
      <div className="lg:pl-72 flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <Header
          theme={theme}
          onToggleTheme={toggleTheme}
          onOpenMobileMenu={() => setIsMobileSidebarOpen(true)}
          onOpenFormula={openFormula}
          title={getNavTitle()}
        />

        {/* Content View Container */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 w-full space-y-6">
          {activeNav === 'duo_bet' && (
            <div className="space-y-6">
              {/* Page Title & How to use Expander */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl sm:text-2xl font-display font-bold text-[#141414] dark:text-white tracking-wide uppercase">
                    二合買牌矩陣
                  </h2>
                </div>

                {/* "這頁怎麼用" Expander */}
                <div className="rounded-2xl border border-black/[0.08] dark:border-white/[0.08] overflow-hidden bg-white dark:bg-[#121212]">
                  <button
                    type="button"
                    id="how-to-use-expander-btn"
                    onClick={() => setIsHowToUseOpen(!isHowToUseOpen)}
                    className="w-full px-5 py-3 flex items-center justify-between text-xs sm:text-sm font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <Info className="w-4 h-4 text-neutral-500" />
                      <span className="tracking-wide">策略操作導引說明</span>
                    </div>
                    {isHowToUseOpen ? <ChevronDown className="w-4 h-4 text-neutral-400" /> : <ChevronRight className="w-4 h-4 text-neutral-400" />}
                  </button>

                  {isHowToUseOpen && (
                    <div className="p-5 border-t border-black/[0.08] dark:border-white/[0.08] text-xs sm:text-sm text-neutral-600 dark:text-neutral-300 space-y-2 leading-relaxed bg-black/[0.01] dark:bg-white/[0.01]">
                      <ul className="list-disc pl-5 space-y-1.5">
                        <li>五個分頁：<strong>單顆下注</strong>、<strong>多顆下注</strong>、<strong>三柱1800碰</strong>、<strong>連碰</strong>、<strong>總損益</strong>。各頁右上角即時顯示獨立累積損益。</li>
                        <li>下注、回填、紀錄、清除、建議車數<strong>均依各分頁獨立維護</strong>，互相隔離。</li>
                        <li><strong>每種下法獨立計算追平車數</strong>：單顆只追單顆虧損，四者綜合彙整請切換至「總損益」分頁。</li>
                        <li><strong>三柱1800碰</strong>：全覆蓋組合共 1800 注三合，各柱開出 1 顆即保證過關，過關率達 55.36%。</li>
                        <li><strong>連碰</strong>：星碰 / 全碰 / 立柱 / 拖膽，注數依照組合理論計算。</li>
                      </ul>
                    </div>
                  )}
                </div>
              </div>

              {/* Mode Tabs Bar */}
              <div className="border-b border-black/[0.08] dark:border-white/[0.08] pb-3">
                <div className="flex overflow-x-auto gap-2 no-scrollbar">
                  {duoTabList.map(tab => {
                    const isActive = duoTab === tab.id;
                    return (
                      <button
                        key={tab.id}
                        id={`tab-${tab.id}`}
                        type="button"
                        onClick={() => setDuoTab(tab.id)}
                        className={`whitespace-nowrap px-4 py-2 rounded-full text-xs font-semibold uppercase tracking-wider transition-all duration-150 flex items-center gap-1.5 ${
                          isActive
                            ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                            : 'bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
                        }`}
                      >
                        <span>{tab.label}</span>
                        {tab.count !== undefined && (
                          <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono font-normal ${
                            isActive 
                              ? 'bg-white/20 dark:bg-black/20 text-current' 
                              : 'bg-black/5 dark:bg-white/10 text-neutral-500'
                          }`}>
                            {tab.count}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Tab Contents */}
              <div>
                {duoTab === 'single' && <SingleBetTab />}
                {duoTab === 'multi' && <MultiBetTab />}
                {duoTab === 'pillar1800' && <ThreePillarTab />}
                {duoTab === 'combo' && <ComboBetTab />}
                {duoTab === 'totals' && <TotalPnLTab />}
              </div>
            </div>
          )}

          {activeNav === 'calculator' && <CalculatorView />}
          {activeNav === 'analysis' && <AnalysisView />}
          {activeNav === 'export' && <ExportView />}
          {activeNav === 'leaderboard' && <LeaderboardView />}
          {activeNav === 'settings' && <SettingsView theme={theme} onToggleTheme={toggleTheme} />}

          {/* Bottom Disclaimer Expander */}
          <div className="pt-6">
            <div className="rounded-2xl border border-black/[0.08] dark:border-white/[0.08] overflow-hidden bg-white dark:bg-[#121212]">
              <button
                type="button"
                id="bottom-disclaimer-btn"
                onClick={() => setIsDisclaimerOpen(!isDisclaimerOpen)}
                className="w-full px-5 py-3.5 flex items-center justify-between text-xs sm:text-sm font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-black/[0.02] dark:hover:bg-white/[0.02] transition-colors"
              >
                <div className="flex items-center gap-2 text-neutral-900 dark:text-neutral-100">
                  <ShieldAlert className="w-4 h-4 text-neutral-500" />
                  <span className="tracking-wide">風險與數學期望值提醒</span>
                </div>
                {isDisclaimerOpen ? <ChevronDown className="w-4 h-4 text-neutral-400" /> : <ChevronRight className="w-4 h-4 text-neutral-400" />}
              </button>

              {isDisclaimerOpen && (
                <div className="p-5 border-t border-black/[0.08] dark:border-white/[0.08] text-xs sm:text-sm text-neutral-600 dark:text-neutral-300 space-y-2 leading-relaxed bg-black/[0.01] dark:bg-white/[0.01]">
                  <p>回本車數純屬算術推算，無法改變每局之負期望值本質。</p>
                  <p>
                    連敗時虧損呈幾何級數成長：每敗一局虧損乘上 1/(1−k)。k 主要由「押選顆數」決定。選號越多、下注越多款，k 越趨近於 1，資金消耗急遽加速。
                  </p>
                  <p className="text-neutral-400">
                    長期統計仍為負期望值，請理性娛樂。詳細數學推導請點選左側「統計推導 / 算式」。
                  </p>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>

      {/* Formula & Disclaimer Modal */}
      <FormulaModal
        isOpen={isFormulaModalOpen}
        onClose={() => setIsFormulaModalOpen(false)}
        type={formulaModalType}
      />
    </div>
  );
}
