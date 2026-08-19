// 前後端唯一契約:所有 API 呼叫都走這裡。各頁面元件請 import 這裡的函式,
// 不要自己拼 fetch 網址,也不要再用 data/lotteryData.ts 的假資料。
//
// 網址前綴:import.meta.env.BASE_URL 由 vite base 決定(正式環境為 "/539/"),
// 所以 apiUrl("games") → "/539/api/games";dev 由 vite proxy 轉給 8540 埠後端。

const BASE = import.meta.env.BASE_URL.replace(/\/$/, ''); // "/539"

function apiUrl(path: string): string {
  return `${BASE}/api/${path.replace(/^\//, '')}`;
}

// ── 登入 token(localStorage)──────────────────────────────
const TOKEN_KEY = 'lotto539_token';
export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> | undefined),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(apiUrl(path), {...opts, headers});
  if (res.status === 401) {
    clearToken();
    throw new ApiError(401, '請重新登入');
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      msg = body.detail || body.message || msg;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body: unknown) =>
  request<T>(path, {method: 'POST', body: JSON.stringify(body)});

// ── 型別(對應後端回傳)────────────────────────────────────
export type GameKey = 'lotto539' | 'fantasy5' | 'marksix';

export interface GameDTO {
  key: GameKey;
  name: string;
  short_name: string;
  num_max: number;
  pick: number;
  ticket_price: number;
  currency: string;
  prize: Record<string, number>;
  total_comb: number;
  supports_pillar: boolean;
  default_bet_cost: number;
  default_bet_prize: number;
  default_cost_per_car: number;
  default_win_payout: number;
}

export interface DrawDTO {
  date: string;
  issue?: string;
  nums: number[];
}

export interface HistoryDTO {
  game: GameKey;
  count: number;
  draws: DrawDTO[];
  latest: (DrawDTO & {pillar_dist?: string; hits_summary?: string}) | null;
}

export interface MissingDTO {
  num: number;
  current: number;
  max_gap: number;
}

export interface NumCount {
  num: number;
  count: number;
}
export interface HotColdDTO {
  hot: NumCount[];
  cold: NumCount[];
}

// 星數 / 十位區段統計
export interface TensBandsDTO {
  bands: string[]; // ["01~09","10~19","20~29","30~39"]
  band_totals: Record<string, number>;
  star_dist: Record<string, number>;
  patterns: {pattern: string; count: number; ratio: number}[];
}

// 奇偶 / 大小 / 和值
export interface ParityDTO {
  odd_dist: Record<string, number>;
  big_dist: Record<string, number>;
  size_split: number;
  sum_min: number;
  sum_max: number;
  sum_avg: number;
}

// 區間組合提醒(新功能 A)
export interface TensPairDTO {
  bands: [number, number];
  labels: [string, string];
  range: [string, string];
  streak: number;
  alert: boolean;
}

// 三柱 1800碰
export interface PillarInfoDTO {
  pillars: [number[], number[], number[]];
  sizes: [number, number, number];
  total_bets: number;
  pass_prob: number;
  expected_hits: number;
  theory_rows: {
    dist: string;
    hits: number;
    prob: number;
    return_amount: number;
    pnl: number;
  }[];
}

// 部分包牌(新功能 B)
export interface PartialBetsDTO {
  pillars: [number[], number[], number[]];
  counts: [number, number, number];
  bets: number;
  total: number;
  coverage: number;
  buyable: boolean;
}

export interface PillarRecoveryDTO {
  feasible: boolean;
  multiplier: number | null;
  cost: number | null;
  gain_per_multiple: number;
}

export interface PillarHistoryDTO {
  periods: number;
  actual_pass_rate: number;
  theory_pass_rate: number;
  passed: number;
  current_streak: number;
  max_streak: number;
}

// ── API 函式 ──────────────────────────────────────────────
export const api = {
  // auth
  login: (username: string, password: string) =>
    post<{token: string; username: string}>('auth/login', {username, password}),
  register: (username: string, password: string, invite_code: string) =>
    post<{ok: boolean; message: string}>('auth/register', {
      username,
      password,
      invite_code,
    }),
  me: () => get<{username: string}>('auth/me'),

  // games
  games: () => get<GameDTO[]>('games'),

  // history
  history: (game: GameKey, limit = 0) =>
    get<HistoryDTO>(`history?game=${game}${limit ? `&limit=${limit}` : ''}`),

  // stats
  missing: (game: GameKey) => get<MissingDTO[]>(`stats/missing?game=${game}`),
  hotCold: (game: GameKey, window = 30, top = 5) =>
    get<HotColdDTO>(`stats/hotcold?game=${game}&window=${window}&top=${top}`),
  frequency: (game: GameKey) => get<NumCount[]>(`stats/frequency?game=${game}`),
  tensPairs: (game: GameKey, threshold = 3) =>
    get<TensPairDTO[]>(`stats/tens-pairs?game=${game}&threshold=${threshold}`),
  tensBands: (game: GameKey) => get<TensBandsDTO>(`stats/tens-bands?game=${game}`),
  parity: (game: GameKey) => get<ParityDTO>(`stats/parity?game=${game}`),

  // pillar 1800碰
  pillarInfo: (game: GameKey) => get<PillarInfoDTO>(`pillar/info?game=${game}`),
  pillarPartial: (game: GameKey, picks: number[]) =>
    post<PartialBetsDTO>('pillar/partial', {game, picks}),
  pillarRecovery: (game: GameKey, loss: number, cost: number, prize: number) =>
    get<PillarRecoveryDTO>(
      `pillar/recovery?game=${game}&loss=${loss}&cost=${cost}&prize=${prize}`,
    ),
  pillarHistory: (game: GameKey, periods = 200) =>
    get<PillarHistoryDTO>(`pillar/history?game=${game}&periods=${periods}`),
};
