export type ThemeMode = 'light' | 'dark';

export type NavItem = 
  | 'duo_bet'      // 二合買牌
  | 'calculator'   // 連碰計算機
  | 'analysis'     // 統計分析
  | 'prediction'   // 五策略預測
  | 'export'       // 匯出
  | 'leaderboard'  // 排行榜
  | 'audit'        // 操作歷史(可作廢=反轉)
  | 'upload_history' // 快速上傳歷史(每筆明細/派彩/盈虧)
  | 'settings';    // 設定

// 紀錄下注分頁。現在 UI 只用 'cycle'(週期帳)與 'totals'(總損益);記帳一律走快速上傳,
// 下注策略頁已從導覽移除。single/multi/pillar1800/combo9000/combo 仍保留為型別值,
// 因為它們同時是流水紀錄的 mode key(見 lotteryData 的示範紀錄與各策略元件)。
export type DuoBetTab =
  | 'cycle'        // 週期帳(每週總帳,可展開 + 週期切換)
  | 'totals'       // 總損益
  | 'single'       // 1組(ledger mode key)
  | 'multi'        // 2組
  | 'pillar1800'   // 三柱1800碰
  | 'combo9000'    // 9000碰
  | 'combo';       // 連碰

export type LotteryGame = '今彩539' | '天天樂(加州 Fantasy 5)' | '六合彩';

export interface GameInfo {
  id: string;
  name: LotteryGame;
  totalBalls: number;
  drawCount: number;
  totalPeriods: number;
  latestPeriod: string;
  latestDate: string;
  latestBalls: number[];
  latestPillarDist?: string;
  latestHitsSummary?: string;
}

export interface BetRecord {
  id: string;
  index: number;
  date: string;
  issue: string;
  game: LotteryGame;
  mode: DuoBetTab;
  edition?: number; // 屬於哪個版(eid);舊紀錄沒有就當第一版
  cycle_id?: number | null; // 屬於哪個週期(後端自動補目前 open 的週期);沒有就未分週期
  playType?: string;
  stars?: number; // 連碰星數(2/3/4);非連碰為 0。舊 combo 紀錄可能沒有,從 playType 退回解析
  units: number; // 支數 or 車數
  cars?: number;
  betsCount: number; // 注數
  selectedBalls: number[];
  drawBalls: number[];
  pillars?: number[][]; // 自訂柱部分包牌:各柱號碼(對獎用各柱∩開獎相乘)
  pillarDist?: string; // e.g. "4 + 0 + 1"
  result: string; // e.g. "中 4 碰", "待開獎", "槓龜"
  cost: number;
  payout: number;
  pnl: number;
  cumPnl: number;
}
