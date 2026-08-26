import React, { useState, useEffect } from 'react';
import {
  ChevronRight,
  ChevronDown,
  ShieldAlert,
  Info,
  ClipboardPaste,
  History
} from 'lucide-react';
import { NavItem, DuoBetTab, ThemeMode } from './types';
import { Sidebar } from './components/Sidebar';
import { Header, GameSwitcher } from './components/Header';
import { FormulaModal } from './components/FormulaModal';
import { LoginModal } from './components/LoginModal';
import { QuickImportModal } from './components/QuickImportModal';
import { UploadHistoryModal } from './components/UploadHistoryModal';
import { useAuth } from './api/useAuth';
import { useGroups } from './api/useGroups';
import { useEditions } from './api/useEditions';
import { GroupBetTab } from './components/tabs/GroupBetTab';
import { ThreePillarTab } from './components/tabs/ThreePillarTab';
import { Combo9000Tab } from './components/tabs/Combo9000Tab';
import { ComboBetTab } from './components/tabs/ComboBetTab';
import { TotalPnLTab } from './components/tabs/TotalPnLTab';
import { CalculatorView } from './components/views/CalculatorView';
import { AnalysisView } from './components/views/AnalysisView';
import { PredictionView } from './components/views/PredictionView';
import { ExportView } from './components/views/ExportView';
import { LeaderboardView } from './components/views/LeaderboardView';
import { AuditView } from './components/views/AuditView';
import { SettingsView } from './components/views/SettingsView';

export default function App() {
  // Theme state
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('lottery_theme');
    return (saved as ThemeMode) || 'dark';
  });

  // 登入閘:未登入就擋住整個 App
  const { loggedIn } = useAuth();
  // 二合下注「組」設定(全站共用):決定有幾個組分頁、各組固定幾顆
  const { enabled: enabledGroups } = useGroups();
  // 下注「版」:記錄下注 / 快速上傳都記到選中的版
  const { editions, eid, setEid } = useEditions();

  // Navigation state
  const [activeNav, setActiveNav] = useState<NavItem>('duo_bet');
  const [duoTab, setDuoTab] = useState<DuoBetTab>('pillar1800');

  // UI expanders
  const [isHowToUseOpen, setIsHowToUseOpen] = useState(false);
  const [isDisclaimerOpen, setIsDisclaimerOpen] = useState(false);
  const [isFormulaModalOpen, setIsFormulaModalOpen] = useState(false);
  const [formulaModalType, setFormulaModalType] = useState<'formula' | 'disclaimer'>('formula');
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isQuickImportOpen, setIsQuickImportOpen] = useState(false);
  const [isUploadHistoryOpen, setIsUploadHistoryOpen] = useState(false);
  // 從上傳歷史「填回」帶回快速上傳的文本
  const [importInitialText, setImportInitialText] = useState<string>('');
  // 快速上傳寫進去的紀錄要讓各分頁重抓 —— useLedger 只在 loggedIn / mode 變才撈,
  // 所以拿這個計數器當分頁容器的 key,一變就重掛,流水自然重新載入。
  const [ledgerVersion, setLedgerVersion] = useState(0);

  // WebSocket:開獎 / 自動對獎後後端會推一則,收到就 bump ledgerVersion →
  // 各下注分頁重抓流水與開獎,不必手動刷新。斷線 3 秒自動重連。
  useEffect(() => {
    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const base = import.meta.env.BASE_URL.replace(/\/$/, '');
    const url = `${wsProto}//${window.location.host}${base}/api/ws`;
    let sock: WebSocket | null = null;
    let alive = true;
    let retry: number | undefined;
    const connect = () => {
      if (!alive) return;
      try {
        sock = new WebSocket(url);
        sock.onmessage = () => setLedgerVersion(v => v + 1);
        sock.onclose = () => { if (alive) retry = window.setTimeout(connect, 3000); };
        sock.onerror = () => { try { sock?.close(); } catch { /* ignore */ } };
      } catch {
        if (alive) retry = window.setTimeout(connect, 3000);
      }
    };
    connect();
    return () => {
      alive = false;
      if (retry) window.clearTimeout(retry);
      try { sock?.close(); } catch { /* ignore */ }
    };
  }, []);

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

  // 組分頁依設定動態產生(只列啟用中的組),id 就是該組的 ledger mode(single/multi)
  const duoTabList: { id: DuoBetTab; label: string; count?: number }[] = [
    ...enabledGroups.map(g => ({ id: g.mode as DuoBetTab, label: g.name, count: 0 })),
    { id: 'pillar1800', label: '三柱1800碰', count: 2 },
    { id: 'combo9000', label: '9000碰', count: 2 },
    { id: 'combo', label: '連碰', count: 2 },
    { id: 'totals', label: '總損益' },
  ];

  const getNavTitle = () => {
    switch (activeNav) {
      case 'duo_bet': return '紀錄下注';
      case 'calculator': return '連碰計算機';
      case 'analysis': return '統計分析';
      case 'prediction': return '五策略預測';
      case 'export': return '匯出中心';
      case 'leaderboard': return '績效榜單';
      case 'audit': return '操作歷史';
      case 'settings': return '系統設定';
      default: return '彩券統計分析';
    }
  };

  // 未登入 → 只給登入畫面(擋住頁面)
  if (!loggedIn) {
    return (
      <div className="min-h-screen bg-[#F9F9F7] dark:bg-[#0A0A0A]">
        <LoginModal isOpen gate onClose={() => {}} />
      </div>
    );
  }

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
          // 下注頁把遊戲選擇搬進下注流程,右上角就不再顯示;分析頁保留全站切換。
          showGameSwitcher={activeNav !== 'duo_bet'}
        />

        {/* Content View Container */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 w-full space-y-6">
          {activeNav === 'duo_bet' && (
            <div className="space-y-6">
              {/* Page Title & How to use Expander */}
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-xl sm:text-2xl font-display font-bold text-[#141414] dark:text-white tracking-wide uppercase">
                    紀錄下注矩陣
                  </h2>
                  {/* 貼一段下注文字 → 一次記多筆(解析規則見 backend/routers/importer.py) */}
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsUploadHistoryOpen(true)}
                      className="py-2 px-3.5 rounded-full text-xs font-semibold uppercase tracking-wider bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors flex items-center gap-1.5"
                    >
                      <History className="w-3.5 h-3.5" />
                      <span>上傳歷史</span>
                    </button>
                    <button
                      type="button"
                      id="open-quick-import-btn"
                      onClick={() => setIsQuickImportOpen(true)}
                      className="py-2 px-3.5 rounded-full text-xs font-semibold uppercase tracking-wider bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors flex items-center gap-1.5"
                    >
                      <ClipboardPaste className="w-3.5 h-3.5" />
                      <span>快速上傳</span>
                    </button>
                  </div>
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
                        <li>分頁：<strong>1組</strong>、<strong>2組</strong>(可在設定頁改固定顆數 / 停用)、<strong>三柱1800碰</strong>、<strong>連碰</strong>、<strong>總損益</strong>。各頁右上角即時顯示獨立累積損益。</li>
                        <li>下注、回填、紀錄、清除、建議車數<strong>均依各分頁獨立維護</strong>，互相隔離。</li>
                        <li><strong>每組獨立計算追平車數</strong>：各組只追自己的虧損,綜合彙整請切換至「總損益」分頁。</li>
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

              {/* 選遊戲 + 選版本(移到分頁列下方):下注遊戲設全域遊戲、下注版本是記帳目標版 */}
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] font-semibold text-neutral-500 dark:text-neutral-400">下注遊戲</span>
                  <GameSwitcher />
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[11px] font-semibold text-neutral-500 dark:text-neutral-400">下注版本</span>
                  <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1 flex-wrap">
                    {editions.map(e => (
                      <button
                        key={e.eid}
                        type="button"
                        onClick={() => setEid(e.eid)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                          eid === e.eid
                            ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                            : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                        }`}
                      >
                        {e.name}
                      </button>
                    ))}
                  </div>
                  <span className="text-[10px] text-neutral-400">(在「設定」可新增版、改名、設各版盤口)</span>
                </div>
              </div>

              {/* Tab Contents */}
              <div key={ledgerVersion}>
                {enabledGroups
                  .filter(g => g.mode === duoTab)
                  .map(g => <GroupBetTab key={g.gid} group={g} />)}
                {duoTab === 'pillar1800' && <ThreePillarTab />}
                {duoTab === 'combo9000' && <Combo9000Tab />}
                {duoTab === 'combo' && <ComboBetTab />}
                {duoTab === 'totals' && <TotalPnLTab />}
              </div>
            </div>
          )}

          {activeNav === 'calculator' && <CalculatorView />}
          {activeNav === 'analysis' && <AnalysisView />}
          {activeNav === 'prediction' && <PredictionView />}
          {activeNav === 'export' && <ExportView />}
          {activeNav === 'leaderboard' && <LeaderboardView />}
          {/* 作廢會改到記帳流水,沿用快速上傳那套 ledgerVersion 讓各分頁重抓 */}
          {activeNav === 'audit' && (
            <AuditView onReverted={() => setLedgerVersion(v => v + 1)} />
          )}
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

      {/* 快速上傳下注紀錄 */}
      <QuickImportModal
        isOpen={isQuickImportOpen}
        onClose={() => { setIsQuickImportOpen(false); setImportInitialText(''); }}
        onImported={() => setLedgerVersion(v => v + 1)}
        initialText={importInitialText}
      />

      {/* 上傳歷史(獨立彈窗):查看文本 + 明細 + 總成本;「填回」帶回快速上傳 */}
      <UploadHistoryModal
        isOpen={isUploadHistoryOpen}
        onClose={() => setIsUploadHistoryOpen(false)}
        onRefill={(t) => {
          setImportInitialText(t);
          setIsUploadHistoryOpen(false);
          setIsQuickImportOpen(true);
        }}
      />
    </div>
  );
}
