import React, { useState, useEffect } from 'react';
import {
  ChevronRight,
  ChevronDown,
  Info,
  ClipboardPaste,
  History
} from 'lucide-react';
import { NavItem, DuoBetTab, ThemeMode } from './types';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { FormulaModal } from './components/FormulaModal';
import { LoginModal } from './components/LoginModal';
import { QuickImportModal } from './components/QuickImportModal';
import { UploadHistoryView } from './components/views/UploadHistoryView';
import { UploadHistoryEntry } from './components/uploadHistory';
import { useAuth } from './api/useAuth';
import { useAllLedger } from './api/useLedger';
import { WeeklyLedger } from './components/views/WeeklyLedger';
import { TotalPnLTab } from './components/tabs/TotalPnLTab';
import { CalculatorView } from './components/views/CalculatorView';
import { AnalysisView } from './components/views/AnalysisView';
import { PredictionView } from './components/views/PredictionView';
import { YahongView } from './components/views/YahongView';
import { ExportView } from './components/views/ExportView';
import { RiskView } from './components/views/RiskView';
import { AuditView } from './components/views/AuditView';
import { SettingsView } from './components/views/SettingsView';
import { SharedBillsView } from './components/views/SharedBillsView';

export default function App() {
  // Theme state
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem('lottery_theme');
    return (saved as ThemeMode) || 'dark';
  });

  // 登入閘:未登入就擋住整個 App
  const { loggedIn } = useAuth();

  // Navigation state
  const [activeNav, setActiveNav] = useState<NavItem>('duo_bet');
  const [duoTab, setDuoTab] = useState<DuoBetTab>('pillar1800');

  // UI expanders
  const [isHowToUseOpen, setIsHowToUseOpen] = useState(false);
  const [isFormulaModalOpen, setIsFormulaModalOpen] = useState(false);
  const [formulaModalType, setFormulaModalType] = useState<'formula' | 'disclaimer'>('formula');
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isQuickImportOpen, setIsQuickImportOpen] = useState(false);
  // 從上傳歷史「填回」帶回快速上傳的文本
  const [importRefill, setImportRefill] = useState<UploadHistoryEntry | null>(null);
  // 流水 cache 現由 LedgerProvider 全站共用,重抓靠 reload();
  // ledgerVersion 仍當下注分頁容器的 key —— 一變就重掛,連帶重抓分頁內的開獎/期號資料。
  const { reload: reloadLedger } = useAllLedger();
  const [ledgerVersion, setLedgerVersion] = useState(0);
  // 開獎 / 作廢 / 上傳後:重抓共用流水 cache + 重掛分頁(刷新開獎)。
  const refreshLedger = React.useCallback(() => {
    reloadLedger();
    setLedgerVersion(v => v + 1);
  }, [reloadLedger]);

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
        sock.onmessage = () => refreshLedger();
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
  // 紀錄下注只剩:週期帳(逐筆流水依週期展開/切換)+ 總損益。記帳走快速上傳。
  const duoTabList: { id: DuoBetTab; label: string; count?: number }[] = [
    { id: 'cycle', label: '週期帳' },
    { id: 'totals', label: '總損益' },
  ];

  const getNavTitle = () => {
    switch (activeNav) {
      case 'duo_bet': return '紀錄下注';
      case 'calculator': return '連碰計算機';
      case 'analysis': return '統計分析';
      case 'prediction': return '五策略預測';
      case 'yahong': return '雅宏策略';
      case 'export': return '匯出中心';
      case 'risk': return '風險與數學期望值';
      case 'audit': return '操作歷史';
      case 'upload_history': return '快速上傳歷史';
      case 'shared_bills': return '佔比帳單';
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
            <div className="space-y-4">
              {/* 頂部壓成一列:分頁(左,可橫捲)+ 導引說明 / 上傳歷史 / 快速上傳(右)。
                  頁名已在 Header,不再重複大標;導引說明展開才佔高度。 */}
              <div className="border-b border-black/[0.08] dark:border-white/[0.08] pb-2 space-y-2">
                <div className="flex items-center gap-2">
                  <div className="flex-1 min-w-0 flex overflow-x-auto gap-1.5 no-scrollbar">
                    {duoTabList.map(tab => {
                      const isActive = duoTab === tab.id;
                      return (
                        <button
                          key={tab.id}
                          id={`tab-${tab.id}`}
                          type="button"
                          onClick={() => setDuoTab(tab.id)}
                          className={`whitespace-nowrap px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider transition-all duration-150 flex items-center gap-1.5 ${
                            isActive
                              ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                              : 'bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5'
                          }`}
                        >
                          <span>{tab.label}</span>
                          {tab.count !== undefined && (
                            <span className={`text-[calc(10px*var(--fs))] px-1.5 py-0.2 rounded-full font-mono font-normal ${
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
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      id="how-to-use-expander-btn"
                      onClick={() => setIsHowToUseOpen(!isHowToUseOpen)}
                      title="策略操作導引說明"
                      className={`w-8 h-8 rounded-full flex items-center justify-center border transition-colors ${
                        isHowToUseOpen
                          ? 'bg-black text-white dark:bg-white dark:text-black border-transparent'
                          : 'bg-white dark:bg-[#161616] border-black/[0.08] dark:border-white/[0.08] text-neutral-500 hover:bg-black/5 dark:hover:bg-white/5'
                      }`}
                    >
                      <Info className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveNav('upload_history')}
                      title="上傳歷史"
                      className="py-1.5 px-3 rounded-full text-xs font-semibold uppercase tracking-wider bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors flex items-center gap-1.5 whitespace-nowrap"
                    >
                      <History className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">上傳歷史</span>
                    </button>
                    {/* 貼一段下注文字 → 一次記多筆(解析規則見 backend/routers/importer.py) */}
                    <button
                      type="button"
                      id="open-quick-import-btn"
                      onClick={() => setIsQuickImportOpen(true)}
                      title="快速上傳"
                      className="py-1.5 px-3 rounded-full text-xs font-semibold uppercase tracking-wider bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors flex items-center gap-1.5 whitespace-nowrap"
                    >
                      <ClipboardPaste className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">快速上傳</span>
                    </button>
                  </div>
                </div>

                {isHowToUseOpen && (
                  <ul className="list-disc pl-5 py-1 space-y-1 text-xs sm:text-sm text-neutral-600 dark:text-neutral-300 leading-relaxed">
                    <li>分頁：<strong>1組</strong>、<strong>2組</strong>(可在設定頁改固定顆數 / 停用)、<strong>三柱1800碰</strong>、<strong>連碰</strong>、<strong>總損益</strong>。各頁右上角即時顯示獨立累積損益。</li>
                    <li>下注、回填、紀錄、清除、建議車數<strong>均依各分頁獨立維護</strong>，互相隔離。</li>
                    <li><strong>每組獨立計算追平車數</strong>：各組只追自己的虧損,綜合彙整請切換至「總損益」分頁。</li>
                    <li><strong>三柱1800碰</strong>：全覆蓋組合共 1800 注三合，各柱開出 1 顆即保證過關，過關率達 55.36%。</li>
                    <li><strong>連碰</strong>：星碰 / 全碰 / 立柱 / 拖膽，注數依照組合理論計算。</li>
                  </ul>
                )}
              </div>

              {/* Tab Contents */}
              <div key={ledgerVersion}>
                {duoTab === 'cycle' && <WeeklyLedger />}
                {duoTab === 'totals' && <TotalPnLTab />}
              </div>
            </div>
          )}

          {activeNav === 'calculator' && <CalculatorView />}
          {activeNav === 'analysis' && <AnalysisView />}
          {activeNav === 'prediction' && <PredictionView />}
          {activeNav === 'yahong' && <YahongView />}
          {activeNav === 'export' && <ExportView />}
          {activeNav === 'risk' && <RiskView />}
          {/* 作廢會改到記帳流水,沿用快速上傳那套 ledgerVersion 讓各分頁重抓 */}
          {activeNav === 'audit' && (
            <AuditView onReverted={refreshLedger} />
          )}
          {/* 快速上傳歷史(獨立頁):每筆明細 + 逐筆派彩/盈虧;填回→切到下注頁開快速上傳;
              作廢會動到 ledger 流水,bump ledgerVersion 讓各分頁重抓 */}
          {activeNav === 'upload_history' && (
            <UploadHistoryView
              onRefill={(entry) => {
                setImportRefill(entry);
                setActiveNav('duo_bet');
                setIsQuickImportOpen(true);
              }}
              onChanged={refreshLedger}
            />
          )}
          {activeNav === 'shared_bills' && <SharedBillsView />}
          {activeNav === 'settings' && <SettingsView theme={theme} onToggleTheme={toggleTheme} />}
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
        onClose={() => { setIsQuickImportOpen(false); setImportRefill(null); }}
        onImported={refreshLedger}
        refill={importRefill}
      />
    </div>
  );
}
