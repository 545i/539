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
// token 一變(登入 / 登出 / 過期被踢)就通知訂閱者,useAuth 靠這個讓全站
// 同步切換登入狀態 —— 不然要嘛整頁 reload,要嘛各元件各自記一份會不同步。
const TOKEN_KEY = 'lotto539_token';
const USER_KEY = 'lotto539_user';
const authListeners = new Set<() => void>();

function notifyAuth() {
  authListeners.forEach(fn => fn());
}

export function subscribeAuth(fn: () => void): () => void {
  authListeners.add(fn);
  return () => authListeners.delete(fn);
}

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const getUsername = (): string | null => localStorage.getItem(USER_KEY);

export const setToken = (t: string, username?: string) => {
  localStorage.setItem(TOKEN_KEY, t);
  if (username) localStorage.setItem(USER_KEY, username);
  notifyAuth();
};

export const clearToken = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  notifyAuth();
};

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
  // 401 分兩種:登入表單被打槍(要顯示「帳號或密碼錯誤」)vs. 帶著的 token
  // 過期被踢(要清掉 token 讓全站切回未登入)。後者才動 token。
  const isLoginAttempt = path.startsWith('auth/login') || path.startsWith('auth/register');
  if (res.status === 401 && token && !isLoginAttempt) {
    clearToken();
    throw new ApiError(401, '登入已過期,請重新登入');
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
const del = <T>(path: string) => request<T>(path, {method: 'DELETE'});

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

// 自訂區間(使用者自己定義的號碼區間)
export interface IntervalGroupIn {
  label: string;
  nums: number[];
}
export interface IntervalPairDTO {
  groups: [number, number];
  labels: [string, string];
  streak: number;
  alert: boolean;
}

// 特殊組合(一組號碼整組連續幾期都沒開)
export interface ComboAbsenceDTO {
  label: string;
  size: number;
  streak: number;
  max_gap: number;
  alert: boolean;
}

// 區間組合同時出現(數個區間連續幾期沒有全部一起開出)
export interface ComboTogetherIn {
  label: string;
  groups: number[][]; // 每個區間的號碼
}
export interface ComboTogetherDTO {
  label: string;
  groups: number;
  streak: number;
  max_gap: number;
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

// 二合(二星)買牌試算
export interface ErheHitDTO {
  hits: number; // 中幾顆
  prob: number;
  payout: number; // 回收 = 中幾顆 × 車數 × 中獎可得
  pnl: number; // 本局損益 = 回收 − 成本
}

export interface ErhePlanDTO {
  game: GameKey;
  n_numbers: number;
  cars: number;
  cost_per_car: number;
  win_payout: number;
  notes_per_car: number; // 1 車的注數(碰數)
  dan_prob: number; // 單顆命中率 = pick / num_max
  any_hit_prob: number; // 押 n 顆至少中 1 顆
  total_cost: number;
  payout_per_hit: number;
  ev_rate: number;
  kelly_fraction: number;
  per_car_1hit_net: number;
  breakeven_hits: number | null;
  hits: ErheHitDTO[];
}

// 盤口覆寫:不給就用後端 GameConfig 的預設值
export interface ErheOdds {
  cost_per_car?: number;
  win_payout?: number;
}

export interface ErheRecoveryDTO {
  next_cars: number | null; // null = 中 1 顆再多車也追不回來
  per_car_1hit: number;
  recovered: boolean;
  can_recover_1hit: boolean;
  next_cost: number | null;
}

export interface ErheProgressionDTO {
  per_round_ev: number;
  rows: {
    round: number;
    cars: number;
    round_cost: number;
    cumulative_cost: number;
    payout_per_hit: number;
    break_even_hits: number | null;
    busted: boolean;
  }[];
}

export interface ErheMartingaleDTO {
  multiplier: number;
  bust_round: number | null;
  steps: {
    round: number;
    cars: number;
    round_cost: number;
    cumulative_cost: number;
    cars_to_break_even: number | null;
  }[];
}

export interface ErheSimultaneousDTO {
  k: number;
  share: number;
  feasible: boolean;
  cars: Record<string, number>;
  total_cost: number | null;
  worst_after: number | null;
  all_hit_after: number | null;
  recovered: boolean;
  short: string[];
}

// 連碰 / 星碰 / 立柱 / 拖膽 試算
export interface ComboCalcIn {
  game: GameKey;
  play: string; // 'star' | 'combo' | 'pillar' | 'dan'
  stars: number;
  picked: number;
  dans?: number;
  per_bet?: number;
  prize?: number;
  sheets?: number;
}

export interface ComboCalcDTO {
  game: string;
  play: {key: string; name: string; dans: number | null; desc: string};
  stars: number;
  star_name: string;
  picked: number;
  dans: number;
  drag: number;
  bets: number;
  per_bet: number;
  prize_per_hit: number;
  odds: number | null;
  sheets: number;
  total_cost: number;
  round_cost: number;
  breakeven_bets: number | null;
  fair_odds: number | null;
  win_prob: number;
  expected_hits: number;
  expected_net: number;
  return_rate: number;
  possible_hits: number[];
  hit_probs: {hits: number; prob: number}[];
}

export interface ComboBetsDTO {
  bets: number;
  stars: number;
  dans: number;
  drag: number;
  limit: number;
  truncated: boolean;
  list: number[][];
}

// 五策略參考選號 / 預測分析
// 五種策略的期望中獎率完全相同(見 core/picker.py),排名只是把運氣視覺化。
export interface PredictStrategyDTO {
  key: string; // random | hot | cold | frequency | balanced
  label: string;
  desc: string;
  sets: number[][]; // 每組推薦號碼(依該款 pick 顆)
  top_numbers: {num: number; weight: number}[]; // 該策略偏好的號碼
  uniform: boolean; // true = 權重均勻(random / balanced),偏好清單沒有意義
  error: string | null;
}

export interface PredictDTO {
  game: GameKey;
  game_name: string;
  num_max: number;
  pick: number;
  sets: number;
  seed: number;
  periods: number;
  target: {issue: string; date: string | null; label: string};
  strategies: PredictStrategyDTO[];
  notice: string;
}

export interface PredictReviewRowDTO {
  issue: string | null;
  date: string | null;
  label: string;
  drawn: number[];
  picks: Record<string, {numbers: number[]; matched: number[]; hits: number}>;
}

export interface PredictRankDTO {
  strategy: string;
  label: string;
  periods: number;
  total_hits: number;
  best: number;
  avg: number;
  hit_rate: number;
}

export interface PredictReviewDTO {
  game: GameKey;
  pick: number;
  num_max: number;
  expected_avg: number; // 純隨機的期望命中 = pick² / num_max
  periods: number;
  strategies: {key: string; label: string; desc: string}[];
  rows: PredictReviewRowDTO[];
  ranking: PredictRankDTO[];
  notice: string;
}

// 記帳流水帳(需登入)
// mode 對應各下注分頁;record 就是前端的 BetRecord,後端原封不動存成 JSON,
// 所以這裡刻意用寬鬆型別 —— 後端不解讀內容,欄位增減不必兩邊同步改。
export type LedgerMode = 'single' | 'multi' | 'pillar1800' | 'combo';

export interface LedgerEntryDTO {
  id: number;
  mode: LedgerMode;
  record: Record<string, unknown>;
  created: string;
}

// 排行榜(需登入):後端把 ledger 流水彙總成使用者排名與各下法表現。
// roi 可能是 null —— 「總成本 0」和「打平」是兩回事,前端要顯示成「—」。
export interface LeaderRowDTO {
  name: string;
  rounds: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  total_cost: number;
  total_payout: number;
  roi: number | null;
  last_at: string;
}

export interface LeaderUserDTO extends LeaderRowDTO {
  rank: number;
  username: string;
  is_me: boolean;
}

export interface LeaderModeDTO extends LeaderRowDTO {
  mode: LedgerMode;
}

export interface LeaderboardDTO {
  me: string;
  users: LeaderUserDTO[];
  modes: LeaderModeDTO[];
}

// 開獎資料更新狀態(設定頁)
export interface AutoupdateGameDTO {
  key: GameKey;
  name: string;
  short_name: string;
  data_file: string;
  scheduled: boolean; // 有登記開獎時刻表才會自動更新
  note: string;
  latest: string | null; // CSV 目前最新一期(台灣日期)
  target: string | null; // 現在應該已經有的最新一期
  stale: boolean; // latest < target = 該去抓了
  next_draw: string | null;
  status: {
    running: boolean;
    msg: string;
    error: string;
    attempts: number;
    added: number;
    done_at: string | null;
  };
}

export interface AutoupdateDTO {
  scheduler_running: boolean;
  tick_seconds: number;
  max_attempts: number;
  checked_at: string;
  games: AutoupdateGameDTO[];
}

export interface FetchNowRowDTO {
  key: GameKey;
  name: string;
  ok: boolean;
  fetched: number;
  added: number;
  latest: string | null;
  error: string;
}

export interface FetchNowDTO {
  results: FetchNowRowDTO[];
  games: AutoupdateGameDTO[];
}

function qs(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) sp.set(k, String(v));
  }
  return sp.toString();
}

// ── 檔案下載 ──────────────────────────────────────────────
// 匯出端點回的是 xlsx / json 檔案,不是 JSON 物件,所以不能走 request()。
// 流水帳匯出要帶 Authorization,直接開新分頁 / <a href> 帶不了標頭 ——
// 只能 fetch 成 blob 再用臨時 <a download> 觸發下載。
export const exportUrl = (path: string): string => apiUrl(path);

/** 從 Content-Disposition 取檔名(優先 RFC 5987 的 filename*)。 */
function filenameFrom(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1]);
    } catch {
      /* 壞掉就退回 fallback */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1] : fallback;
}

async function download(path: string, fallbackName: string): Promise<string> {
  const token = getToken();
  const res = await fetch(apiUrl(path), {
    headers: token ? {Authorization: `Bearer ${token}`} : {},
  });
  if (res.status === 401 && token) {
    clearToken();
    throw new ApiError(401, '登入已過期,請重新登入');
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      msg = body.detail || body.message || msg;
    } catch {
      /* 非 JSON 錯誤就用狀態碼 */
    }
    throw new ApiError(res.status, msg);
  }

  const name = filenameFrom(res.headers.get('Content-Disposition'), fallbackName);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return name;
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

  // ledger 記帳流水帳(需登入;未登入時前端自己用 state 撐著)
  ledgerList: (mode?: LedgerMode) =>
    get<LedgerEntryDTO[]>(`ledger${mode ? `?mode=${mode}` : ''}`),
  ledgerAdd: (mode: LedgerMode, record: Record<string, unknown>) =>
    post<LedgerEntryDTO>('ledger', {mode, record}),
  ledgerDelete: (id: number) =>
    del<{ok: boolean; deleted: number}>(`ledger/${id}`),
  ledgerClear: (mode?: LedgerMode) =>
    del<{ok: boolean; deleted: number}>(`ledger${mode ? `?mode=${mode}` : ''}`),

  // leaderboard 排行榜(需登入;資料來自全站記帳流水)
  leaderboard: (limit = 50) => get<LeaderboardDTO>(`leaderboard?limit=${limit}`),

  // export 匯出(回檔案,呼叫後瀏覽器直接下載;回傳實際檔名)
  exportReport: (game: GameKey, limit = 0) =>
    download(
      `export/report.xlsx?${qs({game, limit: limit || undefined})}`,
      `${game}_report.xlsx`,
    ),
  exportLedgerXlsx: () => download('export/ledger.xlsx', 'ledger.xlsx'),
  exportLedgerJson: () => download('export/ledger.json', 'ledger.json'),

  // settings 開獎資料更新狀態 / 手動抓取(抓取需登入)
  autoupdateStatus: () => get<AutoupdateDTO>('settings/autoupdate'),
  fetchNow: (game?: GameKey) =>
    post<FetchNowDTO>('settings/fetch-now', {game: game ?? null}),

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
  intervalPairs: (
    game: GameKey,
    groups: IntervalGroupIn[],
    threshold = 3,
  ) =>
    post<IntervalPairDTO[]>('stats/interval-pairs', {game, threshold, groups}),
  comboAbsence: (
    game: GameKey,
    combos: IntervalGroupIn[],
    threshold = 3,
  ) =>
    post<ComboAbsenceDTO[]>('stats/combo-absence', {game, threshold, combos}),
  comboTogether: (
    game: GameKey,
    combos: ComboTogetherIn[],
    threshold = 3,
  ) =>
    post<ComboTogetherDTO[]>('stats/combo-together', {game, threshold, combos}),
  tensBands: (game: GameKey) => get<TensBandsDTO>(`stats/tens-bands?game=${game}`),
  parity: (game: GameKey) => get<ParityDTO>(`stats/parity?game=${game}`),

  // predict 五策略參考選號(純計算,不需登入)
  // seed 不給時後端依「下一期期號」推導 —— 同一期重整拿到同一組號碼;
  // 要重抽就帶一個新的 seed(例如 Date.now())。
  predict: (game: GameKey, sets = 1, seed?: number) =>
    get<PredictDTO>(`predict?${qs({game, sets, seed})}`),
  predictReview: (game: GameKey, periods = 20) =>
    get<PredictReviewDTO>(`predict/review?${qs({game, periods})}`),

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

  // erhe 二合買牌(單顆 / 多顆下注試算)
  erhePlan: (game: GameKey, nNumbers: number, cars: number, odds: ErheOdds = {}) =>
    get<ErhePlanDTO>(
      `erhe/plan?${qs({game, n_numbers: nNumbers, cars, ...odds})}`,
    ),
  erheRecovery: (
    game: GameKey,
    cumulativeNet: number,
    nNumbers: number,
    odds: ErheOdds = {},
    baseCars = 3,
  ) =>
    get<ErheRecoveryDTO>(
      `erhe/recovery?${qs({
        game,
        cumulative_net: cumulativeNet,
        n_numbers: nNumbers,
        base_cars: baseCars,
        ...odds,
      })}`,
    ),
  erheProgression: (
    game: GameKey,
    progression: number[],
    nNumbers: number,
    odds: ErheOdds = {},
    capital = 500000,
  ) =>
    get<ErheProgressionDTO>(
      `erhe/progression?${qs({
        game,
        progression: progression.join(','),
        n_numbers: nNumbers,
        capital,
        ...odds,
      })}`,
    ),
  erheMartingale: (
    game: GameKey,
    baseCars = 3,
    multiplier = 2,
    rounds = 12,
    odds: ErheOdds = {},
    capital?: number,
  ) =>
    get<ErheMartingaleDTO>(
      `erhe/martingale?${qs({
        game,
        base_cars: baseCars,
        multiplier,
        rounds,
        capital,
        ...odds,
      })}`,
    ),
  // plans: {遊戲代號: [押幾顆, 每車成本, 中獎可得]}
  erheSimultaneous: (
    cumulativeNet: number,
    plans: Record<string, [number, number, number]>,
    opts: {fixed?: Record<string, number>; base_cars?: number; share?: number} = {},
  ) =>
    post<ErheSimultaneousDTO>('erhe/simultaneous', {
      cumulative_net: cumulativeNet,
      plans,
      ...opts,
    }),

  // combo 連碰家族試算(連碰 / 星碰 / 立柱 / 拖膽)
  comboCalc: (body: ComboCalcIn) => post<ComboCalcDTO>('combo/calc', body),
  comboBets: (
    game: GameKey,
    stars: number,
    nums: number[],
    danNums: number[] = [],
    limit = 10,
  ) =>
    post<ComboBetsDTO>('combo/bets', {game, stars, nums, dan_nums: danNums, limit}),
};
