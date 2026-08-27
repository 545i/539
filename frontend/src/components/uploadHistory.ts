// 快速上傳歷史:型別 + 後端 SQL 存取(登入帳號綁定、跨裝置)。
// 原本走 localStorage;現改呼叫 /upload-history(見 backend/routers/upload_history.py)。
import { api, LedgerMode, ReconcileDTO } from '../api/client';

export const MODE_LABEL: Record<LedgerMode, string> = {
  single: '1組',
  multi: '2組',
  pillar1800: '1800碰',
  combo9000: '9000碰',
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
  date?: string;      // 這一期的開獎日期(YYYY-MM-DD);列表顯示「第 X 期(日期)」,對帳好認
  text: string;                 // 原始文本(可填回文字框重用)
  count: number;                // 實際寫入筆數
  totalCost: number;            // 這批的總下注成本(每筆 cost 加總)
  items: UploadHistoryItem[];   // 下注明細(每筆玩法/號碼/成本)
  entryIds?: number[];          // 這批建立的 ledger 下注 id(作廢時精準刪這些)
  bill?: string;                // 已保存的對帳帳單原文
  recon?: ReconcileDTO;         // 已保存的對帳結果(重開就看得到)
  reconAt?: number;             // 保存對帳的時間
}

export const HISTORY_CAP = 30;

/** 讀全部上傳歷史(新→舊);未登入 / 出錯回空陣列。 */
export async function loadHistory(): Promise<UploadHistoryEntry[]> {
  try {
    const list = await api.uploadHistoryList<UploadHistoryEntry>();
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

/** 新增一批;上限由後端維持。未登入 / 出錯吞掉(不影響上傳流程)。 */
export async function saveEntry(entry: UploadHistoryEntry): Promise<void> {
  try {
    await api.uploadHistoryAdd<UploadHistoryEntry>(entry);
  } catch {
    // 未登入沒有跨裝置歷史;存不了就算了
  }
}

/** 更新某一批(以 ts 為鍵);回傳更新後清單(重讀)。 */
export async function updateEntry(
  ts: number, patch: Partial<UploadHistoryEntry>,
): Promise<UploadHistoryEntry[]> {
  try {
    await api.uploadHistoryUpdate<UploadHistoryEntry>(ts, patch as Record<string, unknown>);
  } catch {
    // 略過
  }
  return loadHistory();
}

/** 作廢某一批上傳(以 ts 為鍵):後端連同這批建立的 ledger 下注一起刪。回傳更新後清單。 */
export async function voidEntry(ts: number): Promise<UploadHistoryEntry[]> {
  await api.uploadHistoryDelete(ts);   // 失敗往上拋,讓 UI 顯示錯誤
  return loadHistory();
}

export function fmtTime(ts: number): string {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getMonth() + 1)}/${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

export const money = (n: number) => `$${Math.round(n).toLocaleString()}`;
