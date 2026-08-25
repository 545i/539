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
const put = <T>(path: string, body: unknown) =>
  request<T>(path, {method: 'PUT', body: JSON.stringify(body)});
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

// 區間組合斷檔的公共設定(全站共用):每組多帶 threshold(連幾期沒一起開就提醒)
export interface ComboWatchItem {
  label: string;
  groups: number[][];
  threshold: number;
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

// 快速上傳下注紀錄(需登入):貼一段文字 → 後端解析成多筆流水。
// dry_run = true 只解析回傳預覽,不寫入;確認後再打一次 dry_run = false。
// 認不出來的行進 errors,不影響其他筆 —— 所以 items 與 errors 可能同時有東西。
// 對帳:對接人帳單解析 + 與我們流水並排比對
export interface ReconcileCellDTO { ours: number; theirs: number; diff: number; }
export interface ReconcileRowDTO {
  bucket: string;     // 二 / 三 / 四
  star: number;
  n: number;          // 我們這桶有幾筆
  units: ReconcileCellDTO;
  cost: ReconcileCellDTO;
  carry: ReconcileCellDTO;   // 中碰
  payout: ReconcileCellDTO;  // 得到的錢
}
export interface ReconcileDTO {
  bill: {
    date: string;
    game: GameKey | null;
    draw: number[];
    slips: Record<string, {units: number; cost: number}>;
    total_cost: number;
    wins: Array<{star: number; carry: number; amount: number}>;
    net: number;
    errors: string[];
  };
  report: {
    rows: ReconcileRowDTO[];
    total_cost_ours: number;
    total_cost_theirs: number;
    cost_gap: number;
    payout_ours: number;
    payout_theirs: number;
    net_ours: number;      // 正=我方付,負=對方付
    net_theirs: number;
    have_records: boolean;
    maybe_wrong_date: boolean;
  } | null;
  records_used: number;
}

export interface QuickImportItemDTO {
  id: number | null; // dry_run 時為 null(還沒進資料庫)
  line: string; // 產生這一筆的原文
  mode: LedgerMode;
  record: Record<string, unknown>; // 就是 BetRecord(缺 id / index / cumPnl)
}

export interface QuickImportErrorDTO {
  line_no: number;
  line: string;
  message: string;
}

export interface QuickImportDTO {
  game: GameKey;
  game_name: string;
  dry_run: boolean;
  parsed: number;
  saved: number;
  items: QuickImportItemDTO[];
  errors: QuickImportErrorDTO[];
}

// 快速上傳確認提交(需登入):把預覽裡(可能被編輯過的)結構化 items 送回後端,
// 後端重算成本後寫入。與 quickImport(dryRun=false)不同 —— 這裡收的是解析結果
// 不是原始文字,所以使用者在預覽裡改的號碼 / 支車才算數。
export interface QuickImportCommitItem {
  mode: LedgerMode;
  selectedBalls: number[];
  units: number;
  stars?: number; // 連碰重算成本要用
  hit_count?: number | null; // 忘記期數但記得中幾顆:直接手填結算
}

// 二合下注「組」設定(全站共用):固定顆數 + 是否啟用。
// gid ↔ mode 由後端決定(1組=single、2組=multi);前端只認 mode 去存取流水。
export interface GroupDTO {
  gid: number;
  mode: LedgerMode;
  name: string; // 「1組」「2組」
  ball_count: number; // 固定顆數(現在當「預設建議顆數」)
  enabled: boolean;
}

// 下注「版」(edition):一套組頭盤口。每版可自訂名稱,盤口依版×遊戲各自設定。
export interface EditionDTO {
  eid: number;
  name: string;
}

// 版×遊戲的整套盤口(每欄位 value + custom=是否有自訂,否則吃預設)
export interface EditionOddsField {
  value: number;
  custom: boolean;
}
export interface EditionOddsDTO {
  eid: number;
  game: GameKey;
  fields: Record<string, EditionOddsField>; // cost_per_car / win_payout / bet_cost / bet_prize / combo_cost{2,3,4} / combo_prize{2,3,4}
}

// 操作歷史(需登入):下注 / 撤銷 / 上傳 / 清空各留一筆痕跡,每筆都可以「作廢」。
// 作廢 = 反轉那個動作(作廢撤銷就是把紀錄救回來),而且作廢自己也是一筆歷史。
// action_label 與 reversible 由後端算好 —— 前端不要自己維護一份對照與規則。
export type AuditAction =
  | 'bet_add' // 單筆下注
  | 'bet_delete' // 撤銷一筆
  | 'bet_clear' // 清空某下法
  | 'quick_import' // 快速上傳一批
  | 'void'; // 作廢(反轉)某個操作

export interface AuditLogDTO {
  id: number;
  action: AuditAction;
  action_label: string;
  target_id: number | null;
  summary: string;
  voided: boolean; // 已被作廢
  void_of: number | null; // 這筆是「作廢誰」的紀錄
  reversible: boolean; // 還能不能按作廢(void 本身與已作廢的都不行)
  created: string;
}

export interface AuditVoidDTO {
  ok: boolean;
  voided: number; // 被作廢的操作 id
  reverted: number; // 實際反轉了幾筆 ledger 紀錄(目標早就不在時會是 0)
  log: AuditLogDTO | null; // 作廢動作本身不再另記一筆,固定為 null
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

// 排行榜展開一列時看到的「該帳號下注明細」(新→舊)。登入後看得到任一帳號,
// 跟排行榜本身同一批資料 —— 榜上已經公開累積損益,明細只是把它攤開。
// 數字欄位可能是 null:舊紀錄沒有那個欄位,跟「這局 0 元」要分得開,顯示成「—」。
export interface UserLedgerEntryDTO {
  id: number;
  mode: LedgerMode;
  mode_name: string; // 下法的中文名(後端算好,前端不要再維護一份對照)
  created: string;
  date: string;
  issue: string;
  game: string;
  playType: string;
  result: string;
  selectedBalls: number[];
  units: number | null; // 支數 or 車數
  cars: number | null;
  betsCount: number | null;
  cost: number | null;
  payout: number | null;
  pnl: number | null;
}

export interface UserLedgerDTO {
  username: string;
  count: number;
  entries: UserLedgerEntryDTO[];
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

// 連碰星數盤口(全域設定,不是個人偏好 —— 改了全站的試算與記帳成本都跟著動)
export interface StarCostRowDTO {
  cost: number; // 每碰成本
  prize: number; // 中一碰可得
  custom: boolean; // true = 後台改過,false = 還是程式的出廠預設
  updated: string;
  updated_by: string;
}

export interface StarCostDTO {
  stars: number[]; // [2, 3, 4]
  star_names: Record<string, string>; // {"2":"二星", ...}
  costs: Record<string, StarCostRowDTO>; // 鍵是星數(JSON 的鍵一律字串)
  defaults: Record<string, {cost: number; prize: number}>;
}

/** PUT 的內容:只送要改的星數也可以。 */
export type StarCostInput = Record<string, {cost: number; prize: number}>;

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
  // 改期數重新對獎:登入時存後端(回傳更新後那筆);未登入用 preview 不寫 DB。
  // hitCount 有值 = 手填中獎顆數(忘記期數但記得中幾顆),不查開獎號直接依組公式算。
  ledgerResettle: (id: number, issue: string, hitCount?: number | null) =>
    put<LedgerEntryDTO>(`ledger/${id}`, {issue, hit_count: hitCount ?? null}),
  ledgerSettlePreview: (
    record: Record<string, unknown>,
    issue: string,
    hitCount?: number | null,
  ) =>
    post<Record<string, unknown>>('ledger/settle-preview', {
      record,
      issue,
      hit_count: hitCount ?? null,
    }),
  ledgerClear: (mode?: LedgerMode) =>
    del<{ok: boolean; deleted: number}>(`ledger${mode ? `?mode=${mode}` : ''}`),

  // 備援:一鍵把自己所有「待開獎」且該期已開的紀錄自動對獎
  ledgerSettlePending: () =>
    post<{settled: number}>('ledger/settle-pending', {}),

  // 對帳:貼對接人帳單 → 解析 + 抓同版同日期同遊戲流水並排比對
  ledgerReconcile: (bill: string, edition: number) =>
    post<ReconcileDTO>('ledger/reconcile', {bill, edition}),

  // 快速上傳:貼一段下注文字,dryRun 先預覽、再確認寫入(需登入)
  quickImport: (
    game: GameKey,
    text: string,
    dryRun = false,
    opts: {date?: string; issue?: string; edition?: number} = {},
  ) =>
    post<QuickImportDTO>('ledger/quick-import', {
      game,
      text,
      dry_run: dryRun,
      date: opts.date ?? null,
      issue: opts.issue ?? '',
      edition: opts.edition ?? 1,
    }),
  // 確認上傳(編輯過的解析結果 → 後端重算成本後寫入)
  quickImportCommit: (
    game: GameKey,
    items: QuickImportCommitItem[],
    opts: {date?: string; issue?: string; edition?: number; dryRun?: boolean} = {},
  ) =>
    post<QuickImportDTO>('ledger/quick-import/commit', {
      game,
      items,
      date: opts.date ?? null,
      issue: opts.issue ?? '',
      edition: opts.edition ?? 1,
      dry_run: opts.dryRun ?? false,
    }),

  // 二合下注組設定(讀不用登入,改要登入;全站共用)
  getGroups: () => get<GroupDTO[]>('groups'),
  setGroups: (groups: Array<Partial<GroupDTO> & {gid: number}>) =>
    put<GroupDTO[]>('groups', {groups}),

  // 下注「版」(讀公開,改要登入;全站共用)
  getEditions: () => get<EditionDTO[]>('editions'),
  addEdition: (name: string) => post<EditionDTO>('editions', {name}),
  renameEdition: (eid: number, name: string) =>
    put<{ok: boolean}>(`editions/${eid}`, {name}),
  deleteEdition: (eid: number) => del<{ok: boolean}>(`editions/${eid}`),
  getEditionOdds: (eid: number, game: GameKey) =>
    get<EditionOddsDTO>(`editions/${eid}/odds?game=${game}`),
  setEditionOdds: (eid: number, game: GameKey, values: Record<string, number>) =>
    put<Record<string, number>>(`editions/${eid}/odds`, {game, values}),
  resetEditionOdds: (eid: number, game: GameKey) =>
    del<Record<string, number>>(`editions/${eid}/odds?game=${game}`),

  // audit 操作歷史(需登入):列自己的操作、作廢(反轉)某一筆
  auditList: (limit = 200) => get<AuditLogDTO[]>(`audit?limit=${limit}`),
  auditVoid: (id: number) => post<AuditVoidDTO>(`audit/${id}/void`, {}),

  // leaderboard 排行榜(需登入;資料來自全站記帳流水)
  leaderboard: (limit = 50) => get<LeaderboardDTO>(`leaderboard?limit=${limit}`),
  // 某帳號的下注明細(排行榜展開那一列才抓,不要一次抓全榜)
  userLedger: (username: string) =>
    get<UserLedgerDTO>(`leaderboard/${encodeURIComponent(username)}/ledger`),

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

  // 連碰星數盤口(讀不用登入,改要登入;改的是全站共用的成本)
  getStarCosts: () => get<StarCostDTO>('star-cost'),
  setStarCosts: (costs: StarCostInput) => put<StarCostDTO>('star-cost', {costs}),
  resetStarCosts: () => del<StarCostDTO>('star-cost'),

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
  // 區間組合斷檔的公共設定(讀公開、寫要登入;全站共用,提醒機器人也讀這份)
  getComboWatch: (game: GameKey) =>
    get<ComboWatchItem[]>(`stats/combo-watch?game=${game}`),
  setComboWatch: (game: GameKey, combos: ComboWatchItem[]) =>
    put<ComboWatchItem[]>('stats/combo-watch', {game, combos}),
  testComboWatch: (game: GameKey) =>
    post<{alerts: unknown[]; sent: boolean; notify_enabled: boolean}>(
      `stats/combo-watch/test?game=${game}`, {}),
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
