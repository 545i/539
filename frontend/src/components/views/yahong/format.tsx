import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { YahongFmt, YahongGrade, YahongVerdictColor, YahongPillarBadge } from '../../../api/client';

// 統一格式化:與後端 fmt 標記一一對應(見 docs/yahong/API.md)。
export const fmtValue = (value: number, fmt: YahongFmt): string => {
  switch (fmt) {
    case 'pct': return `${(value * 100).toFixed(1)}%`;
    case 'pct100': return `${value.toFixed(1)}%`;
    case 'money': return Math.round(value).toLocaleString();
    case 'num1': return value.toFixed(1);
    case 'num2': return value.toFixed(2);
    case 'period': return `${Math.round(value)} 期`;
    default: return String(value);
  }
};

export const pad2 = (n: number) => n.toString().padStart(2, '0');
export const money = (n: number) => Math.round(n).toLocaleString();

// 五裁決橫幅底色(依 color 欄位)
export const VERDICT_BANNER: Record<YahongVerdictColor, string> = {
  red: 'bg-rose-500/10 border-rose-500/30 text-rose-700 dark:text-rose-300',
  amber: 'bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-300',
  gold: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-700 dark:text-yellow-300',
  green: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300',
  slate: 'bg-black/[0.03] dark:bg-white/[0.05] border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300',
};

// 名次分級 S/A/B/C 的球色與說明
export const GRADE_META: Record<YahongGrade, { label: string; slogan: string; dot: string; text: string; ring: string }> = {
  S: { label: 'S 級', slogan: '絕對主將', dot: 'bg-yellow-500 text-white', text: 'text-yellow-700 dark:text-yellow-300', ring: 'border-yellow-500/40 bg-yellow-500/10' },
  A: { label: 'A 級', slogan: '優質副牌', dot: 'bg-emerald-600 text-white', text: 'text-emerald-700 dark:text-emerald-300', ring: 'border-emerald-500/40 bg-emerald-500/10' },
  B: { label: 'B 級', slogan: '中性觀望', dot: 'bg-neutral-400 text-white', text: 'text-neutral-600 dark:text-neutral-300', ring: 'border-black/[0.08] dark:border-white/[0.08] bg-black/[0.02] dark:bg-white/[0.03]' },
  C: { label: 'C 級', slogan: '強制冷卻', dot: 'bg-rose-500 text-white', text: 'text-rose-700 dark:text-rose-300', ring: 'border-rose-500/40 bg-rose-500/10' },
};

// 柱碰徽章配色(綜合分析看板)
export const BADGE_META: Record<YahongPillarBadge, string> = {
  alert: 'bg-rose-500/15 text-rose-700 dark:text-rose-300',
  ready: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
  ok: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300',
};

// 四推薦模式配色
export const RECOMMEND_META: Record<string, { ball: string; text: string }> = {
  gold: { ball: 'bg-yellow-500 text-white', text: 'text-yellow-700 dark:text-yellow-300' },
  rose: { ball: 'bg-rose-500 text-white', text: 'text-rose-700 dark:text-rose-300' },
  cyan: { ball: 'bg-cyan-500 text-white', text: 'text-cyan-700 dark:text-cyan-300' },
  purple: { ball: 'bg-purple-500 text-white', text: 'text-purple-700 dark:text-purple-300' },
};

// 每個子分頁頂端的中性說明(統計包裝提醒)
export const Disclaimer: React.FC = () => (
  <p className="text-[11px] leading-relaxed text-neutral-400 dark:text-neutral-500 flex items-start gap-1.5">
    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
    <span>本策略為統計包裝,樂透為獨立事件,連槓 / Z / 馬可夫等訊號不具預測力,僅供參考。</span>
  </p>
);

// 載入 / 錯誤的共用小塊
export const Loading: React.FC<{ text?: string }> = ({ text = '載入中…' }) => (
  <div className="text-xs text-neutral-400">{text}</div>
);
export const ErrorBox: React.FC<{ msg: string }> = ({ msg }) => (
  <div className="text-xs text-rose-500">{msg}</div>
);

// 卡片外框(沿用專案風格)
export const cardClass =
  'p-4 sm:p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]';
