// 快速上傳歷史:型別 + localStorage 工具(QuickImportModal 寫入、UploadHistoryModal 讀取)。
import { LedgerMode, ReconcileDTO } from '../api/client';

export const MODE_LABEL: Record<LedgerMode, string> = {
  single: '1組',
  multi: '2組',
  pillar1800: '1800碰',
  combo: '連碰',
};

export interface UploadHistoryItem {
  mode: LedgerMode;
  playType: string;   // 玩法(含碰/注數)
  balls: number[];    // 號碼
  units: number;      // 支 / 車
  cost: number;       // 這筆成本(後端重算)
  costExpr: string;   // 成本計算式(怎麼算的)
}

export interface UploadHistoryEntry {
  ts: number;
  gameName: string;
  editionName: string;
  eid?: number;       // 上傳到哪個版(對帳要用)
  issue: string;
  text: string;                 // 原始文本(可填回文字框重用)
  count: number;                // 實際寫入筆數
  totalCost: number;            // 這批的總下注成本(每筆 cost 加總)
  items: UploadHistoryItem[];   // 下注明細(每筆玩法/號碼/成本)
  bill?: string;                // 已保存的對帳帳單原文
  recon?: ReconcileDTO;         // 已保存的對帳結果(重開就看得到)
  reconAt?: number;             // 保存對帳的時間
}

const HISTORY_KEY = 'lotto539_quick_import_history';
export const HISTORY_CAP = 30;

export function loadHistory(): UploadHistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const arr = raw ? (JSON.parse(raw) as UploadHistoryEntry[]) : [];
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

export function saveHistory(list: UploadHistoryEntry[]): void {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, HISTORY_CAP)));
  } catch {
    // localStorage 滿了 / 隱私模式 —— 歷史是加分功能,存不了就算了
  }
}

/** 更新某一批歷史(以 ts 為鍵),回傳更新後清單。 */
export function updateHistory(ts: number, patch: Partial<UploadHistoryEntry>): UploadHistoryEntry[] {
  const list = loadHistory().map(h => (h.ts === ts ? { ...h, ...patch } : h));
  saveHistory(list);
  return list;
}

export function fmtTime(ts: number): string {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export const money = (n: number) => `$${Math.round(n).toLocaleString()}`;
