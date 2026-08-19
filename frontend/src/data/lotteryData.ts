import { BetRecord, GameInfo } from '../types';

export const GAME_LIST: GameInfo[] = [
  {
    id: '539',
    name: '今彩539',
    totalBalls: 39,
    drawCount: 5,
    totalPeriods: 830,
    latestPeriod: '115000200',
    latestDate: '2026-08-18',
    latestBalls: [5, 6, 10, 28, 39],
    latestPillarDist: '1 + 1 + 3',
    latestHitsSummary: '中 3 碰'
  },
  {
    id: 'cal',
    name: '天天樂(加州 Fantasy 5)',
    totalBalls: 39,
    drawCount: 5,
    totalPeriods: 3058,
    latestPeriod: '3058',
    latestDate: '2026-08-19',
    latestBalls: [3, 14, 22, 29, 36],
    latestPillarDist: '1 + 2 + 2',
    latestHitsSummary: '中 4 碰'
  },
  {
    id: 'mark6',
    name: '六合彩',
    totalBalls: 49,
    drawCount: 6,
    totalPeriods: 2081,
    latestPeriod: '2081',
    latestDate: '2026-08-18',
    latestBalls: [7, 12, 25, 33, 41, 48],
    latestPillarDist: '1 + 1 + 4',
    latestHitsSummary: '中 2 碰'
  }
];

export const INITIAL_PILLAR_RECORDS: BetRecord[] = [
  {
    id: 'p-1',
    index: 1,
    date: '2026-08-12',
    issue: '115000196',
    game: '今彩539',
    mode: 'pillar1800',
    units: 1,
    betsCount: 1800,
    selectedBalls: [],
    drawBalls: [5, 11, 12, 17, 18],
    pillarDist: '4 + 0 + 1',
    result: '中 4 碰',
    cost: 113400,
    payout: 45000,
    pnl: -68400,
    cumPnl: -68400
  },
  {
    id: 'p-2',
    index: 2,
    date: '2026-08-12',
    issue: '115000197',
    game: '今彩539',
    mode: 'pillar1800',
    units: 1,
    betsCount: 1800,
    selectedBalls: [],
    drawBalls: [7, 19, 21, 25, 34],
    pillarDist: '0 + 2 + 3',
    result: '中 3 碰',
    cost: 113400,
    payout: 33750,
    pnl: -79650,
    cumPnl: -148050
  }
];

export const INITIAL_COMBO_RECORDS: BetRecord[] = [
  {
    id: 'c-1',
    index: 1,
    date: '2026-08-13',
    issue: '115000196',
    game: '今彩539',
    mode: 'combo',
    playType: '星碰 三星+四星 12 支',
    units: 12,
    betsCount: 70,
    selectedBalls: [3, 6, 12, 15, 22, 25, 32, 35],
    drawBalls: [5, 11, 12, 17, 18],
    result: '三星槓龜、四星槓龜',
    cost: 84336,
    payout: 0,
    pnl: -84336,
    cumPnl: -84336
  }
];

export const PILLAR_THEORY_ROWS = [
  { dist: '3 + 1 + 1', hits: '3 碰', prob: '16.71%', returnAmount: '171,000', pnl: '+57,600' },
  { dist: '2 + 2 + 1', hits: '4 碰', prob: '13.98%', returnAmount: '228,000', pnl: '+114,600' },
  { dist: '2 + 1 + 2', hits: '4 碰', prob: '15.65%', returnAmount: '228,000', pnl: '+114,600' },
  { dist: '1 + 2 + 2', hits: '4 碰', prob: '9.02%', returnAmount: '228,000', pnl: '+114,600' },
  { dist: '斷柱 (任一柱 0 顆)', hits: '0 碰 (槓龜)', prob: '44.64%', returnAmount: '0', pnl: '-113,400' },
];

export const COMPARISON_TABLE_DATA = [
  {
    game: '今彩539',
    mode: '單顆下注',
    balls: '1 顆',
    winProb: '12.82%',
    costPerCar: '2,755',
    prizePerWin: '21,200',
    kFactor: '0.130',
    recoverySpeed: '快 (1 局補平)'
  },
  {
    game: '今彩539',
    mode: '多顆下注',
    balls: '20 顆',
    winProb: '51.28%',
    costPerCar: '55,100',
    prizePerWin: '106,000',
    kFactor: '0.520',
    recoverySpeed: '慢 (複利膨脹)'
  },
  {
    game: '天天樂',
    mode: '單顆下注',
    balls: '1 顆',
    winProb: '12.82%',
    costPerCar: '2,755',
    prizePerWin: '21,200',
    kFactor: '0.130',
    recoverySpeed: '快'
  },
  {
    game: '六合彩',
    mode: '單顆下注',
    balls: '1 顆',
    winProb: '12.24%',
    costPerCar: '3,528',
    prizePerWin: '28,800',
    kFactor: '0.123',
    recoverySpeed: '最快'
  }
];

export const TOTAL_STRATEGY_PERFORMANCE = [
  { name: '單顆下注', rounds: 0, hits: 0, cost: 0, payout: 0, pnl: 0, roi: '0.0%' },
  { name: '多顆下注', rounds: 0, hits: 0, cost: 0, payout: 0, pnl: 0, roi: '0.0%' },
  { name: '三柱1800碰', rounds: 2, hits: 2, cost: 226800, payout: 78750, pnl: -148050, roi: '-65.3%' },
  { name: '連碰 (星碰/立柱)', rounds: 2, hits: 0, cost: 84336, payout: 0, pnl: -84336, roi: '-100.0%' },
];

export const RECOVERY_COMPARISON_TABLE = [
  { game: '今彩539 (單顆)', cars: 12, cost: '33,060', prize: '254,400', afterPnl: '+221,340' },
  { game: '今彩539 (多顆 20顆)', cars: 48, cost: '2,644,800', prize: '5,088,000', afterPnl: '+2,443,200' },
  { game: '天天樂 (單顆)', cars: 12, cost: '33,060', prize: '254,400', afterPnl: '+221,340' },
  { game: '六合彩 (單顆)', cars: 10, cost: '35,280', prize: '288,000', afterPnl: '+252,720' },
  { game: '六合彩 (多顆 20顆)', cars: 58, cost: '4,092,480', prize: '8,352,000', afterPnl: '+4,259,520' },
];
