import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  Calculator, 
  Download, 
  Trophy, 
  Settings, 
  Moon, 
  Sun, 
  LogOut, 
  ChevronRight, 
  ChevronDown, 
  HelpCircle, 
  ShieldAlert,
  Dices,
  History,
  ClipboardList,
  Layers,
  LogIn,
  Sparkles
} from 'lucide-react';
import { NavItem, ThemeMode } from '../types';
import { api } from '../api/client';
import { useAsync } from '../api/useAsync';
import { useAuth } from '../api/useAuth';
import { LoginModal } from './LoginModal';

// 每 30 分鐘重抓一次開獎資料:跨日/跨期/夏令時後 next.at 會變,定時重抓自動校正跟上。
const LIVE_REFRESH_MS = 30 * 60 * 1000;

// 從 ISO(含 +08:00 台灣偏移)取台灣牆鐘 MM/DD HH:MM —— 直接切字串,不經瀏覽器時區換算。
const fmtDrawAt = (iso: string): string =>
  `${iso.slice(5, 7)}/${iso.slice(8, 10)} ${iso.slice(11, 13)}:${iso.slice(14, 16)}`;

// 距離開獎剩餘;>=1 小時顯示「Xh Ym」,否則「Ym Zs」。已過(<=0)回 null → 顯示「開獎中」。
// iso 帶時區偏移,new Date 解析後與 now(epoch ms)相減不受瀏覽器時區影響。
const fmtCountdown = (iso: string, now: number): string | null => {
  const diff = new Date(iso).getTime() - now;
  if (diff <= 0) return null;
  const totalMin = Math.floor(diff / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h > 0) return `${h}h ${m}m`;
  const s = Math.floor((diff % 60000) / 1000);
  return `${m}m ${s}s`;
};

// 側欄「Live Draw Database」:三款遊戲的即時最新開獎 + 下一期開獎時刻/倒數(接真 API)
const LiveDrawList: React.FC = () => {
  const { data, reload } = useAsync(async () => {
    const gs = await api.games();
    return Promise.all(
      gs.map(async g => {
        const h = await api.history(g.key, 1);
        return { key: g.key, name: g.name, count: h.count, latest: h.latest, next: h.next };
      }),
    );
  }, []);

  // 每秒更新 now 讓倒數走動
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  // 每 30 分鐘重抓(校正)
  useEffect(() => {
    const t = window.setInterval(() => reload(), LIVE_REFRESH_MS);
    return () => window.clearInterval(t);
  }, [reload]);

  if (!data) {
    return <div className="px-2 text-[10px] text-neutral-400">載入開獎資料…</div>;
  }

  return (
    <div className="space-y-2.5 text-xs">
      {data.map(row => {
        const countdown = row.next?.at ? fmtCountdown(row.next.at, now) : null;
        return (
          <div
            key={row.key}
            className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]"
          >
            <div className="font-semibold text-neutral-900 dark:text-neutral-100 flex items-center justify-between">
              <span className="tracking-tight">{row.name}</span>
              <span className="text-[10px] font-mono text-neutral-500 dark:text-neutral-400">
                {row.count} 期
              </span>
            </div>
            <div className="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1 flex items-center justify-between">
              <span className="text-[10px] font-mono">{row.latest?.date ?? '—'}</span>
              {row.latest?.issue && (
                <span className="font-mono text-[10px]">#{row.latest.issue}</span>
              )}
            </div>
            <div className="mt-2 flex items-center gap-1 font-mono text-[11px] flex-wrap">
              {(row.latest?.nums ?? []).map((b, i) => (
                <span
                  key={i}
                  className="px-1.5 py-0.5 rounded bg-black/5 dark:bg-white/10 text-neutral-900 dark:text-neutral-100 font-bold"
                >
                  {b.toString().padStart(2, '0')}
                </span>
              ))}
            </div>
            {row.next?.at && (
              <div className="mt-2 pt-2 border-t border-black/[0.05] dark:border-white/[0.05] flex items-center justify-between gap-2 font-mono text-[10px] text-neutral-500 dark:text-neutral-400">
                <span className="truncate">
                  下一期{row.next.issue ? ` #${row.next.issue}` : ''} · {fmtDrawAt(row.next.at)} 開獎
                </span>
                <span className="shrink-0 tabular-nums font-semibold text-neutral-700 dark:text-neutral-300">
                  {countdown ? `剩 ${countdown}` : '開獎中'}
                </span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

interface Props {
  activeNav: NavItem;
  onSelectNav: (nav: NavItem) => void;
  theme: ThemeMode;
  onToggleTheme: () => void;
  onOpenFormula: () => void;
  onOpenDisclaimer: () => void;
  isMobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<Props> = ({
  activeNav,
  onSelectNav,
  theme,
  onToggleTheme,
  onOpenFormula,
  onOpenDisclaimer,
  isMobileOpen = false,
  onCloseMobile
}) => {
  const [isDisclaimerExpanded, setIsDisclaimerExpanded] = useState(false);
  const [isLoginOpen, setIsLoginOpen] = useState(false);
  const { loggedIn, username, logout } = useAuth();

  const navItems: { id: NavItem; label: string; icon: React.ReactNode; tag?: string }[] = [
    { id: 'duo_bet', label: '紀錄下注', icon: <Dices className="w-4 h-4" />, tag: 'Core' },
    { id: 'calculator', label: '連碰計算機', icon: <Calculator className="w-4 h-4" /> },
    { id: 'analysis', label: '統計分析', icon: <BarChart3 className="w-4 h-4" /> },
    { id: 'prediction', label: '五策略預測', icon: <Sparkles className="w-4 h-4" /> },
    { id: 'export', label: '匯出', icon: <Download className="w-4 h-4" /> },
    { id: 'leaderboard', label: '排行榜', icon: <Trophy className="w-4 h-4" /> },
    { id: 'audit', label: '操作歷史', icon: <History className="w-4 h-4" /> },
    { id: 'upload_history', label: '上傳歷史', icon: <ClipboardList className="w-4 h-4" /> },
    { id: 'settings', label: '設定', icon: <Settings className="w-4 h-4" /> },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isMobileOpen && (
        <div 
          onClick={onCloseMobile}
          className="fixed inset-0 bg-black/70 z-40 lg:hidden backdrop-blur-xs transition-opacity"
        />
      )}

      <aside
        id="app-sidebar"
        className={`fixed top-0 left-0 bottom-0 z-40 w-72 lg:w-72 bg-[#FFFFFF] dark:bg-[#0A0A0A] border-r border-black/[0.08] dark:border-white/[0.08] flex flex-col transition-transform duration-200 ease-in-out ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        {/* Sidebar Header / Brand */}
        <div className="p-6 border-b border-black/[0.08] dark:border-white/[0.08]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full border border-black/20 dark:border-white/20 flex items-center justify-center bg-black dark:bg-white text-white dark:text-black font-display font-bold text-xs tracking-wider">
                D
              </div>
              <div>
                <h1 className="font-display font-bold text-base text-[#141414] dark:text-white tracking-[0.05em] uppercase">
                  Dualis <span className="font-sans text-xs font-normal text-black/50 dark:text-white/50 lowercase italic">lottery</span>
                </h1>
                <p className="text-[10px] uppercase tracking-[0.2em] text-black/40 dark:text-white/40">
                  Precision Analytics
                </p>
              </div>
            </div>
          </div>

          {/* User Account Strip:登入後記帳存後端,未登入只留在這個瀏覽器分頁 */}
          <div className="mt-5 pt-3 border-t border-black/[0.06] dark:border-white/[0.06] flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-400 font-medium min-w-0">
              <div className={`w-2 h-2 rounded-full shrink-0 ${
                loggedIn
                  ? 'bg-emerald-500 ring-2 ring-emerald-500/20'
                  : 'bg-neutral-400 ring-2 ring-neutral-400/20'
              }`}></div>
              <span className="font-mono text-[11px] tracking-wide truncate">
                {loggedIn ? username || '已登入' : '未登入 (紀錄不會保存)'}
              </span>
            </div>
            {loggedIn ? (
              <button
                type="button"
                id="logout-btn"
                onClick={logout}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold rounded-full border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 text-neutral-700 dark:text-neutral-300 transition-colors shrink-0"
              >
                <LogOut className="w-3 h-3" />
                登出
              </button>
            ) : (
              <button
                type="button"
                id="login-btn"
                onClick={() => setIsLoginOpen(true)}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold rounded-full bg-black text-white dark:bg-white dark:text-black hover:opacity-90 transition-opacity shrink-0"
              >
                <LogIn className="w-3 h-3" />
                登入
              </button>
            )}
          </div>

          {/* Theme Toggle Pill */}
          <div className="mt-3.5 flex items-center justify-between p-2.5 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
            <div className="flex items-center gap-2 text-xs font-medium text-neutral-800 dark:text-neutral-200">
              {theme === 'dark' ? (
                <Moon className="w-3.5 h-3.5 text-neutral-300" />
              ) : (
                <Sun className="w-3.5 h-3.5 text-neutral-700" />
              )}
              <span className="text-[11px] uppercase tracking-wider">
                {theme === 'dark' ? 'Midnight Dark' : 'Canvas Light'}
              </span>
            </div>
            <button
              type="button"
              id="theme-pill-toggle"
              onClick={onToggleTheme}
              className="px-2.5 py-0.5 text-[10px] uppercase font-bold tracking-widest rounded-full bg-black text-white dark:bg-white dark:text-black transition-transform active:scale-95"
            >
              {theme === 'dark' ? 'Light' : 'Dark'}
            </button>
          </div>
        </div>

        {/* Scrollable Navigation & Info Area */}
        <div className="flex-1 overflow-y-auto px-4 py-5 space-y-6 text-sm">
          {/* Navigation Section */}
          <div>
            <div className="px-2 mb-2.5 text-[10px] uppercase tracking-[0.25em] text-neutral-400 dark:text-neutral-500 font-semibold">
              Navigation
            </div>
            <nav className="space-y-1">
              {navItems.map(item => {
                const isActive = activeNav === item.id;
                return (
                  <button
                    key={item.id}
                    id={`nav-${item.id}`}
                    type="button"
                    onClick={() => {
                      onSelectNav(item.id);
                      if (onCloseMobile) onCloseMobile();
                    }}
                    className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl font-medium text-xs transition-all duration-150 ${
                      isActive
                        ? 'bg-black text-white dark:bg-white dark:text-black font-semibold shadow-xs'
                        : 'text-neutral-700 dark:text-neutral-300 hover:bg-black/[0.04] dark:hover:bg-white/[0.05]'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={isActive ? 'text-white dark:text-black' : 'text-neutral-500 dark:text-neutral-400'}>
                        {item.icon}
                      </span>
                      <span className="tracking-wide">{item.label}</span>
                    </div>
                    {item.tag && !isActive && (
                      <span className="text-[9px] px-1.5 py-0.5 uppercase tracking-wider rounded border border-black/10 dark:border-white/10 text-neutral-400">
                        {item.tag}
                      </span>
                    )}
                    {isActive && (
                      <div className="w-1.5 h-1.5 rounded-full bg-white dark:bg-black"></div>
                    )}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* Lottery Draw Status Area */}
          <div className="pt-2 border-t border-black/[0.06] dark:border-white/[0.06]">
            <div className="px-2 mb-2.5 text-[10px] uppercase tracking-[0.25em] text-neutral-400 dark:text-neutral-500 font-semibold">
              Live Draw Database
            </div>
            <LiveDrawList />
          </div>

          {/* Disclaimer Expander */}
          <div className="pt-2 border-t border-black/[0.06] dark:border-white/[0.06]">
            <div className="rounded-xl border border-black/[0.06] dark:border-white/[0.06] overflow-hidden bg-black/[0.01] dark:bg-white/[0.02]">
              <button
                type="button"
                id="sidebar-disclaimer-btn"
                onClick={() => setIsDisclaimerExpanded(!isDisclaimerExpanded)}
                className="w-full px-3.5 py-2.5 flex items-center justify-between text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-2 text-neutral-600 dark:text-neutral-400">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span className="text-[11px] uppercase tracking-wider">免責聲明 (必讀)</span>
                </div>
                {isDisclaimerExpanded ? (
                  <ChevronDown className="w-3.5 h-3.5 text-neutral-400" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-neutral-400" />
                )}
              </button>

              {isDisclaimerExpanded && (
                <div className="p-3.5 pt-1 text-[11px] text-neutral-600 dark:text-neutral-400 space-y-2 border-t border-black/[0.06] dark:border-white/[0.06] leading-relaxed bg-white dark:bg-[#101010]">
                  <p>
                    今彩539 每期開獎為獨立隨機事件，長期期望報酬率約 <strong>-44.16%</strong>。
                  </p>
                  <button
                    onClick={onOpenDisclaimer}
                    className="text-neutral-900 dark:text-white underline font-semibold block mt-1"
                  >
                    查看完整精算法則
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar Footer Action */}
        <div className="p-4 border-t border-black/[0.08] dark:border-white/[0.08] bg-black/[0.02] dark:bg-black/40">
          <button
            type="button"
            id="formula-trigger-btn"
            onClick={onOpenFormula}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold uppercase tracking-wider rounded-xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-800 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 shadow-xs transition-all active:scale-98"
          >
            <HelpCircle className="w-3.5 h-3.5 text-neutral-500" />
            <span>說明 / 算式 (供驗算)</span>
          </button>
        </div>
      </aside>

      <LoginModal isOpen={isLoginOpen} onClose={() => setIsLoginOpen(false)} />
    </>
  );
};

