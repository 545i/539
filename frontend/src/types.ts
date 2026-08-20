export type ThemeMode = 'light' | 'dark';

export type NavItem = 
  | 'duo_bet'      // 二合買牌
  | 'calculator'   // 連碰計算機
  | 'analysis'     // 統計分析
  | 'prediction'   // 五策略預測
  | 'export'       // 匯出
  | 'leaderboard'  // 排行榜
  | 'settings';    // 設定

export type DuoBetTab = 
  | 'single'       // 單顆下注
  | 'multi'        // 多顆下注
  | 'pillar1800'   // 三柱1800碰
  | 'combo'        // 連碰
  | 'totals';      // 總損益

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
  playType?: string;
  units: number; // 支數 or 車數
  cars?: number;
  betsCount: number; // 注數
  selectedBalls: number[];
  drawBalls: number[];
  pillarDist?: string; // e.g. "4 + 0 + 1"
  result: string; // e.g. "中 4 碰", "待開獎", "槓龜"
  cost: number;
  payout: number;
  pnl: number;
  cumPnl: number;
}
