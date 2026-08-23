import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, BarChart3, Bell, Flame, Snowflake, LayoutGrid, SlidersHorizontal,
  Plus, Trash2, RotateCcw, Target,
} from 'lucide-react';
import {
  api, ComboTogetherDTO, ComboTogetherIn, IntervalGroupIn, IntervalPairDTO, PillarInfoDTO,
} from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useGame } from '../../api/useGame';

const WINDOW = 830; // 冷熱號取樣上限(資料不足時以實際期數為準)
const HIST_OPTIONS = [20, 30, 50, 100] as const;
const THRESHOLD_OPTIONS = [2, 3, 4, 5, 6] as const;

// 區間組合提醒的使用者設定(存 localStorage,重整後保留)
const INTERVALS_KEY = 'lotto539_intervals';             // { [gameKey]: [{label, nums}, ...] }
const WATCH_THRESHOLD_KEY = 'lotto539_watch_threshold'; // 連續幾期未開才算警示
// 存的是 {label, groups}(groups 保留各區間分開),跟舊的 lotto539_special_combos
// 結構不同,所以另開一個 key —— 免得讀到舊格式沒有 groups 直接炸掉
const COMBOS_KEY = 'lotto539_combo_together';           // { [gameKey]: [{label, groups}, ...] }

// localStorage 在無痕/被停用時會直接丟例外,包起來免得整頁掛掉
const readStore = <T,>(key: string, fallback: T): T => {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
};
const writeStore = (key: string, value: unknown) => {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* 存不進去就算了,不影響功能 */
  }
};

const pairKey = (groups: [number, number]) => `${groups[0]}-${groups[1]}`;

// 一列區間組合:alert=已達門檻(amber)、quiet=未開但還沒到門檻
const PairRow: React.FC<{ p: IntervalPairDTO; detail: string; tone: 'alert' | 'quiet' }> = ({
  p,
  detail,
  tone,
}) => (
  <div
    className={`p-2.5 rounded-xl border flex items-center justify-between gap-2 ${
      tone === 'alert'
        ? 'bg-amber-500/10 border-amber-500/20'
        : 'bg-black/[0.02] dark:bg-white/[0.03] border-black/[0.06] dark:border-white/[0.06]'
    }`}
  >
    <div className="min-w-0">
      <div className="flex items-center gap-1.5">
        {tone === 'alert' && (
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
        )}
        <span
          className={`text-xs font-mono font-bold ${
            tone === 'alert' ? 'text-amber-900 dark:text-amber-300' : 'text-neutral-900 dark:text-white'
          }`}
        >
          {p.labels[0]} × {p.labels[1]}
        </span>
      </div>
      <div className="text-[10px] font-mono text-neutral-400 mt-0.5 truncate">{detail}</div>
    </div>
    <div
      className={`text-[11px] font-mono shrink-0 text-right ${
        tone === 'alert' ? 'text-amber-900 dark:text-amber-300 font-bold' : 'text-neutral-400'
      }`}
    >
      {tone === 'alert' ? `連續 ${p.streak} 期兩區間都未開` : `${p.streak} 期未開`}
    </div>
  </div>
);

// 一組區間組合:streak = 距上次「所有區間同一期一起開出」幾期。達門檻走 amber,
// 未達門檻(含 0 期,代表上一期剛好全開)也一律列出 —— 是使用者自己挑的組合。
const ComboRow: React.FC<{
  label: string;
  detail: string;
  stat?: ComboTogetherDTO;
  onRemove: () => void;
}> = ({ label, detail, stat, onRemove }) => {
  const alert = stat?.alert ?? false;
  return (
    <div
      className={`p-2.5 rounded-xl border flex items-center justify-between gap-2 ${
        alert
          ? 'bg-amber-500/10 border-amber-500/20'
          : 'bg-black/[0.02] dark:bg-white/[0.03] border-black/[0.06] dark:border-white/[0.06]'
      }`}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          {alert && (
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
          )}
          <span
            className={`text-xs font-mono font-bold ${
              alert ? 'text-amber-900 dark:text-amber-300' : 'text-neutral-900 dark:text-white'
            }`}
          >
            {label}
          </span>
        </div>
        <div className="text-[10px] font-mono text-neutral-400 mt-0.5 truncate">
          {detail}
          {stat ? ` · 歷史最長 ${stat.max_gap} 期` : ''}
        </div>
        {alert && stat && (
          <div className="text-[10px] font-semibold text-amber-700 dark:text-amber-400 mt-0.5">
            {label} 已連續 {stat.streak} 期沒有全部同時出現
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <div className="text-right">
          <div className="text-[10px] text-neutral-400">距上次同時出現</div>
          <div
            className={`text-xl font-mono font-bold leading-none mt-0.5 ${
              alert ? 'text-amber-900 dark:text-amber-300' : 'text-neutral-900 dark:text-white'
            }`}
          >
            {stat ? `${stat.streak} 期` : '—'}
          </div>
        </div>
        <button
          type="button"
          onClick={onRemove}
          title="刪除這組組合"
          className="p-1 rounded-lg text-neutral-400 hover:text-rose-500 hover:bg-rose-500/10 transition-all"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};

// 依十位分段上色:01~09 / 10~19 / 20~29 / 30~39 / 40~49(六合彩才有最後一段)
const BAND_DOT = [
  'bg-neutral-900 text-white dark:bg-white dark:text-black',
  'bg-blue-600 text-white',
  'bg-amber-600 text-white',
  'bg-emerald-600 text-white',
  'bg-fuchsia-600 text-white',
];
const BAND_LEGEND = [
  'bg-neutral-900 dark:bg-white',
  'bg-blue-600',
  'bg-amber-600',
  'bg-emerald-600',
  'bg-fuchsia-600',
];

const bandIndex = (n: number) => (n <= 9 ? 0 : Math.floor(n / 10));
const bandDot = (n: number) => BAND_DOT[bandIndex(n)] ?? BAND_DOT[BAND_DOT.length - 1];
const pad2 = (n: number) => n.toString().padStart(2, '0');

// 預設區間 = 十位四段(539/天天樂 01~09…30~39;六合彩多一段 40~49)
const defaultIntervals = (numMax: number): IntervalGroupIn[] => {
  const out: IntervalGroupIn[] = [];
  for (let i = 0; i <= bandIndex(numMax); i++) {
    const lo = i === 0 ? 1 : i * 10;
    const hi = Math.min(i * 10 + 9, numMax);
    const nums: number[] = [];
    for (let n = lo; n <= hi; n++) nums.push(n);
    out.push({ label: `${pad2(lo)}~${pad2(hi)}`, nums });
  }
  return out;
};

// 預設範例:「全部十位區間同時出現」(539/天天樂 4 段、六合彩 5 段)。
// 各段各自一個 group —— 要的是「每一段當期都至少開一顆」,不是把號碼併起來。
const defaultCombos = (numMax: number): ComboTogetherIn[] => {
  const ivs = defaultIntervals(numMax);
  if (ivs.length < 2) return [];
  return [
    {
      label: `${ivs.length} 段同時出現`,
      groups: ivs.map(g => g.nums),
    },
  ];
};

// 號碼輸入 parser:支援「1-15」「2,4,6,20-25」「1~9 12」等寫法,
// 全形逗號/破折號也吃;超出號碼上限或重複的直接濾掉。
const parseNums = (raw: string, numMax: number): number[] => {
  const out = new Set<number>();
  // ，=全形逗號 、=、 ；=全形分號 / ～=～ ー=ー －=－ —=— –=–
  for (const part of raw.replace(/\s+/g, '').split(/[,;，、；]+/)) {
    if (!part) continue;
    const m = part.match(/^(\d+)(?:[-~～ー－—–](\d+))?$/);
    if (!m) continue;
    const a = Number(m[1]);
    const b = m[2] === undefined ? a : Number(m[2]);
    const lo = Math.min(a, b);
    const hi = Math.max(a, b);
    for (let n = lo; n <= hi; n++) if (n >= 1 && n <= numMax) out.add(n);
  }
  return [...out].sort((x, y) => x - y);
};

// 區間涵蓋號碼的摘要:連續就寫「01~15」,不連續就列號碼(太多只列前幾顆)
const numsSummary = (nums: number[]): string => {
  if (nums.length === 0) return '(無號碼)';
  if (nums.length === 1) return pad2(nums[0]);
  const contiguous = nums.length === nums[nums.length - 1] - nums[0] + 1;
  if (contiguous) return `${pad2(nums[0])}~${pad2(nums[nums.length - 1])}`;
  const shown = nums.slice(0, 8).map(pad2).join(',');
  return nums.length > 8 ? `${shown}…(共 ${nums.length} 顆)` : shown;
};

export const AnalysisView: React.FC = () => {
  const { gameKey, game } = useGame();
  const [activeTab, setActiveTab] = useState<'draw_history' | 'hot_cold' | 'pillar_dist' | 'odd_even'>('draw_history');
  const [histN, setHistN] = useState<number>(30);
  const [showWatchSetup, setShowWatchSetup] = useState(false);
  const [threshold, setThreshold] = useState<number>(() => {
    const v = readStore<number>(WATCH_THRESHOLD_KEY, 3);
    return (THRESHOLD_OPTIONS as readonly number[]).includes(v) ? v : 3;
  });
  // 每款彩券各自記一份自訂區間(號碼上限不同,不能共用);沒存過就用預設十位分段
  const [intervalMap, setIntervalMap] = useState<Record<string, IntervalGroupIn[]>>(() =>
    readStore<Record<string, IntervalGroupIn[]>>(INTERVALS_KEY, {}),
  );
  const [newLabel, setNewLabel] = useState('');
  const [newNums, setNewNums] = useState('');
  // 區間組合斷檔改為「全站公共設定」(存後端 stats/combo-watch,提醒機器人也讀這份)。
  // comboVer 變一下就重抓(存檔後刷新)。
  const [comboVer, setComboVer] = useState(0);
  const comboWatch = useAsync(() => api.getComboWatch(gameKey), [gameKey, comboVer]);
  const [newComboLabel, setNewComboLabel] = useState('');
  const [watchMsg, setWatchMsg] = useState<string | null>(null);
  // 勾選上方那份區間清單來組出一個組合(勾的是區間 index)
  const [pickedIvs, setPickedIvs] = useState<number[]>([]);

  useEffect(() => writeStore(WATCH_THRESHOLD_KEY, threshold), [threshold]);
  useEffect(() => writeStore(INTERVALS_KEY, intervalMap), [intervalMap]);

  // 號碼上限跟著遊戲走(今彩539/天天樂 39、六合彩 49);後端還沒回來前先用 39 撐版面
  const numMax = game?.num_max ?? 39;
  const pick = game?.pick ?? 5;
  const supportsPillar = game?.supports_pillar ?? true;
  const gameName = game?.short_name ?? '本遊戲';
  const allNums = useMemo(() => Array.from({ length: numMax }, (_, i) => i + 1), [numMax]);
  // 圖例段數:39 顆到 30~39、49 顆多一段 40~49
  const bands = useMemo(() => {
    const out: { c: string; t: string }[] = [];
    for (let i = 0; i <= bandIndex(numMax); i++) {
      const lo = i === 0 ? 1 : i * 10;
      const hi = Math.min(i * 10 + 9, numMax);
      out.push({ c: BAND_LEGEND[i] ?? BAND_LEGEND[BAND_LEGEND.length - 1], t: `${pad2(lo)}~${pad2(hi)}` });
    }
    return out;
  }, [numMax]);

  const hotCold = useAsync(() => api.hotCold(gameKey, WINDOW, 6), [gameKey]);
  const history = useAsync(() => api.history(gameKey), [gameKey]);
  // 六合彩沒有三柱玩法 —— 直接不打端點,免得拿 400 當錯誤顯示
  const pillarInfo = useAsync<PillarInfoDTO | null>(
    () => (supportsPillar ? api.pillarInfo(gameKey) : Promise.resolve(null)),
    [gameKey, supportsPillar],
  );
  const parity = useAsync(() => api.parity(gameKey), [gameKey]);
  const drawHist = useAsync(() => api.history(gameKey, histN), [gameKey, histN]);

  // 目前這款遊戲的區間清單:使用者存過就用他的,沒有就帶預設十位分段
  const intervals = useMemo(
    () => intervalMap[gameKey] ?? defaultIntervals(numMax),
    [intervalMap, gameKey, numMax],
  );
  const isCustom = intervalMap[gameKey] !== undefined;
  // 區間內容也是查詢條件,序列化後當 deps(陣列每次 render 都是新物件,不能直接當 dep)
  const intervalsKey = useMemo(() => JSON.stringify(intervals), [intervals]);
  // 區間組合斷檔:alert 由後端依 threshold 算,所以門檻/區間改了要重抓
  const intervalPairs = useAsync<IntervalPairDTO[]>(
    () =>
      intervals.length >= 2
        ? api.intervalPairs(gameKey, intervals, threshold)
        : Promise.resolve([]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [gameKey, threshold, intervalsKey],
  );

  // 端點已把「久的」排前面,這裡只依門檻分堆不重排
  const pairs = useMemo(() => intervalPairs.data ?? [], [intervalPairs.data]);
  // 只顯示「未開」的組合(streak >= 1);已開(0 期)的不列出
  const alertPairs = pairs.filter(p => p.alert);
  const quietPairs = pairs.filter(p => !p.alert && p.streak >= 1);

  // 區間管理:改動一律寫進 intervalMap[gameKey],之後就走使用者自己那份
  const updateIntervals = (fn: (cur: IntervalGroupIn[]) => IntervalGroupIn[]) =>
    setIntervalMap(prev => ({
      ...prev,
      [gameKey]: fn(prev[gameKey] ?? defaultIntervals(numMax)),
    }));
  const parsedNewNums = useMemo(() => parseNums(newNums, numMax), [newNums, numMax]);
  const addInterval = () => {
    if (parsedNewNums.length === 0) return;
    const label = newLabel.trim() || numsSummary(parsedNewNums);
    updateIntervals(cur => [...cur, { label, nums: parsedNewNums }]);
    setNewLabel('');
    setNewNums('');
  };
  const removeInterval = (idx: number) =>
    updateIntervals(cur => cur.filter((_, i) => i !== idx));
  const resetIntervals = () =>
    setIntervalMap(prev => {
      const next = { ...prev };
      delete next[gameKey];
      return next;
    });

  // 提醒列要秀的號碼摘要:用後端回的 group index 去對回自己送出去的區間
  const pairDetail = (p: IntervalPairDTO) =>
    [p.groups[0], p.groups[1]]
      .map(i => (intervals[i] ? numsSummary(intervals[i].nums) : '?'))
      .join(' × ');

  // ── 區間組合斷檔(全站公共)──────────────────────────────
  const watchCombos = useMemo(() => comboWatch.data ?? [], [comboWatch.data]);
  const combos = useMemo<ComboTogetherIn[]>(
    () => watchCombos.map(c => ({ label: c.label, groups: c.groups })),
    [watchCombos],
  );
  // 提醒門檻取第一組的(全部同一個);沒資料先用 5
  const watchThreshold = watchCombos[0]?.threshold ?? 5;
  const combosKey = useMemo(() => JSON.stringify(combos), [combos]);
  // 共現斷檔:alert 由後端依門檻算,門檻/組合改了都要重抓
  const comboTogether = useAsync<ComboTogetherDTO[]>(
    () =>
      combos.length > 0
        ? api.comboTogether(gameKey, combos, watchThreshold)
        : Promise.resolve([]),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [gameKey, watchThreshold, combosKey],
  );

  // 存回全站公共設定(每組帶同一個門檻),存完刷新
  const saveCombos = (list: ComboTogetherIn[], thr: number) => {
    setWatchMsg(null);
    api.setComboWatch(gameKey, list.map(c => ({ label: c.label, groups: c.groups, threshold: thr })))
      .then(() => { setComboVer(v => v + 1); setWatchMsg('已儲存(全站生效,提醒機器人也會用這份)。'); })
      .catch(e => setWatchMsg((e as Error).message));
  };

  // 後端把結果依 streak 重排過,對不回原本的順序 —— 用 label 配回本地清單拿 index
  // (同名組合按出現順序逐一取用,不會互相錯位)
  const comboRows = useMemo(() => {
    const byLabel = new Map<string, ComboTogetherDTO[]>();
    for (const r of comboTogether.data ?? []) {
      const bucket = byLabel.get(r.label);
      if (bucket) bucket.push(r);
      else byLabel.set(r.label, [r]);
    }
    const rows = combos.map((c, idx) => ({ combo: c, idx, stat: byLabel.get(c.label)?.shift() }));
    // 沒有統計(還沒回來/對不到)的排最後
    return rows.sort((a, b) => (b.stat?.streak ?? -1) - (a.stat?.streak ?? -1));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comboTogether.data, combosKey]);

  const comboAlertCount = comboRows.filter(r => r.stat?.alert).length;

  const updateCombos = (fn: (cur: ComboTogetherIn[]) => ComboTogetherIn[]) =>
    saveCombos(fn(combos), watchThreshold);
  const removeCombo = (idx: number) => updateCombos(cur => cur.filter((_, i) => i !== idx));

  // 換遊戲時區間清單整份換掉,舊的勾選 index 已無意義
  useEffect(() => setPickedIvs([]), [gameKey]);
  const toggleIv = (i: number) =>
    setPickedIvs(cur => (cur.includes(i) ? cur.filter(x => x !== i) : [...cur, i]));

  // 勾選的區間 → 一個組合:每個區間各自一個 group(不聯集,共現要看各段分開),
  // 名稱預設用區間名接起來
  const pickedSorted = useMemo(() => [...pickedIvs].sort((a, b) => a - b), [pickedIvs]);
  const pickedGroups = useMemo(
    () => pickedSorted.map(i => intervals[i]?.nums).filter(ns => ns && ns.length > 0) as number[][],
    [pickedSorted, intervals],
  );
  const pickedLabel = useMemo(
    () => pickedSorted.map(i => intervals[i]?.label).filter(Boolean).join(' + '),
    [pickedSorted, intervals],
  );
  // 至少兩個區間才有「同時出現」可言
  const canAddCombo = pickedGroups.length >= 2;
  const addComboFromIntervals = () => {
    if (!canAddCombo) return;
    const label = newComboLabel.trim() || pickedLabel;
    updateCombos(cur => [...cur, { label, groups: pickedGroups }]);
    setNewComboLabel('');
    setPickedIvs([]);
  };

  // 開獎歷史走勢:最新一期排最上面
  const histRows = useMemo(
    () => [...(drawHist.data?.draws ?? [])].reverse(),
    [drawHist.data],
  );
  // 各號在這段期數內的出現次數(欄位分佈統計)
  const histFreq = useMemo(() => {
    const f = new Map<number, number>();
    for (const d of drawHist.data?.draws ?? [])
      for (const n of d.nums) f.set(n, (f.get(n) ?? 0) + 1);
    return f;
  }, [drawHist.data]);

  // 出現率的分母:近 WINDOW 期,但資料不足時用實際總期數
  const periods = history.data ? Math.min(WINDOW, history.data.count) : WINDOW;
  const toRate = (count: number) =>
    periods > 0 ? `${((count / periods) * 100).toFixed(1)}%` : '—';

  const hotNumbers = (hotCold.data?.hot ?? []).map(item => ({
    num: item.num,
    count: item.count,
    rate: toRate(item.count),
  }));

  const coldNumbers = (hotCold.data?.cold ?? []).map(item => ({
    num: item.num,
    count: item.count,
    rate: toRate(item.count),
  }));

  const hotColdLoading = hotCold.loading || history.loading;
  const hotColdError = hotCold.error || history.error;

  // 三柱實際開出率:全歷史每期開出的號碼落在各柱的比例
  const pillarActual = useMemo(() => {
    const pillars = pillarInfo.data?.pillars;
    const draws = history.data?.draws;
    if (!pillars || !draws || draws.length === 0) return null;
    const which = new Map<number, number>();
    pillars.forEach((p, i) => p.forEach(n => which.set(n, i)));
    const counts = [0, 0, 0];
    let total = 0;
    for (const d of draws) {
      for (const n of d.nums) {
        const i = which.get(n);
        if (i !== undefined) {
          counts[i] += 1;
          total += 1;
        }
      }
    }
    return total > 0 ? counts.map(c => (c / total) * 100) : null;
  }, [pillarInfo.data, history.data]);

  const sizes = pillarInfo.data?.sizes;
  const pillarTotal = sizes ? sizes[0] + sizes[1] + sizes[2] : 0;
  const theoryRate = (i: number) =>
    sizes && pillarTotal > 0 ? `${((sizes[i] / pillarTotal) * 100).toFixed(2)}%` : '—';
  const actualRate = (i: number) =>
    pillarActual ? `${pillarActual[i].toFixed(1)}%` : '—';

  // 柱別標題直接從後端給的號碼組推:連號就寫區間,不連號(第三柱)就寫顆數
  const pillarLabel = (i: number) => {
    const p = pillarInfo.data?.pillars?.[i];
    if (!p || p.length === 0) return `第 ${i + 1} 柱`;
    const lo = Math.min(...p);
    const hi = Math.max(...p);
    return p.length === hi - lo + 1
      ? `第 ${i + 1} 柱 (${lo}-${hi})`
      : `第 ${i + 1} 柱 (其餘 ${p.length} 顆)`;
  };

  const pillarLoading = pillarInfo.loading || history.loading;
  const pillarError = pillarInfo.error || history.error;

  // 單號 / 大號比例:Σ(k × 期數) ÷ (每期 pick 顆 × 總期數)
  const parityPct = useMemo(() => {
    const d = parity.data;
    if (!d) return null;
    const draws = Object.values(d.odd_dist).reduce((a, b) => a + b, 0);
    if (draws === 0) return null;
    const weighted = (dist: Record<string, number>) =>
      Object.entries(dist).reduce((a, [k, v]) => a + Number(k) * v, 0);
    return {
      odd: (weighted(d.odd_dist) / (pick * draws)) * 100,
      big: (weighted(d.big_dist) / (pick * draws)) * 100,
    };
  }, [parity.data, pick]);

  // 大小的切點由後端給(539 是 19,六合彩是 24),不要自己假設
  const split = parity.data?.size_split;

  const ratioText = (pct: number | undefined) =>
    pct === undefined ? '—' : `${pct.toFixed(1)}% : ${(100 - pct).toFixed(1)}%`;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Title */}
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              歷史開獎數據與統計分析
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              目前分析 {gameName}(01~{pad2(numMax)},每期 {pick} 顆)
              {history.data ? ` — 共 ${history.data.count.toLocaleString()} 期` : ''}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-black/[0.08] dark:border-white/[0.08] pb-2">
        {[
          { id: 'draw_history', label: '開獎歷史' },
          { id: 'hot_cold', label: '冷熱號統計' },
          { id: 'pillar_dist', label: '三柱分佈統計' },
          { id: 'odd_even', label: '單雙/大小比' }
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id as any)}
            className={`px-4 py-2 text-xs uppercase tracking-wider font-semibold rounded-full transition-all ${
              activeTab === t.id
                ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                : 'text-neutral-600 dark:text-neutral-400 hover:bg-black/5 dark:hover:bg-white/5'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Draw History Distribution Matrix */}
      {activeTab === 'draw_history' && (
        <>
        {/* 區間組合斷檔提醒(區間由使用者自訂,預設帶十位分段) */}
        <div className="p-4 sm:p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Bell className="w-4 h-4 text-amber-500" />
              <span>區間組合斷檔提醒</span>
              {alertPairs.length > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-300 text-[10px] font-mono font-bold">
                  {alertPairs.length} 組警示
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
                {THRESHOLD_OPTIONS.map(n => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setThreshold(n)}
                    className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                      threshold === n
                        ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                    }`}
                  >
                    {n} 期
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setShowWatchSetup(v => !v)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-black/[0.08] dark:border-white/[0.08] text-xs font-semibold text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 transition-all"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                {showWatchSetup ? '收起設定' : '設定監看區間'}
              </button>
            </div>
          </div>

          <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
            自訂的兩個號碼區間連續 {threshold} 期都沒開出號碼就跳警示;
            目前 {gameName} 有 {intervals.length} 個區間、共 {pairs.length} 組配對
            {isCustom ? '(已套用自訂區間)' : '(預設十位分段)'}。
          </div>

          {/* 區間設定:自己定義要監看的號碼區間,存在瀏覽器本機 */}
          {showWatchSetup && (
            <div className="p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                  我的號碼區間({gameName} 01~{pad2(numMax)})
                </span>
                <button
                  type="button"
                  onClick={resetIntervals}
                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-neutral-600 dark:text-neutral-300 hover:text-black dark:hover:text-white"
                >
                  <RotateCcw className="w-3 h-3" />
                  還原預設
                </button>
              </div>

              {/* 目前區間清單 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {intervals.map((g, i) => (
                  <div
                    key={`${g.label}-${i}`}
                    className="flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg bg-white dark:bg-[#121212] border border-black/[0.12] dark:border-white/[0.12]"
                  >
                    <span className="min-w-0">
                      <span className="block text-xs font-mono font-bold text-neutral-900 dark:text-white truncate">
                        {g.label}
                      </span>
                      <span className="block text-[10px] font-mono text-neutral-400 truncate">
                        {numsSummary(g.nums)}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => removeInterval(i)}
                      title="刪除這個區間"
                      className="p-1 rounded-lg text-neutral-400 hover:text-rose-500 hover:bg-rose-500/10 transition-all shrink-0"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {intervals.length === 0 && (
                  <div className="text-[11px] text-neutral-400">
                    還沒有任何區間 —— 在下面新增,或按「還原預設」拿回十位分段。
                  </div>
                )}
              </div>

              {/* 新增區間 */}
              <div className="pt-1 border-t border-black/[0.06] dark:border-white/[0.06] space-y-2">
                <div className="flex flex-col sm:flex-row gap-2">
                  <input
                    type="text"
                    value={newLabel}
                    onChange={e => setNewLabel(e.target.value)}
                    placeholder="區間名稱(可留空)"
                    className="sm:w-40 px-2.5 py-1.5 rounded-lg bg-white dark:bg-[#121212] border border-black/[0.12] dark:border-white/[0.12] text-xs text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:outline-none focus:border-black/30 dark:focus:border-white/30"
                  />
                  <input
                    type="text"
                    value={newNums}
                    onChange={e => setNewNums(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') addInterval();
                    }}
                    placeholder="號碼,如 1-15 或 2,4,6,20-25"
                    className="flex-1 px-2.5 py-1.5 rounded-lg bg-white dark:bg-[#121212] border border-black/[0.12] dark:border-white/[0.12] text-xs font-mono text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:outline-none focus:border-black/30 dark:focus:border-white/30"
                  />
                  <button
                    type="button"
                    onClick={addInterval}
                    disabled={parsedNewNums.length === 0}
                    className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-black text-white dark:bg-white dark:text-black text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    新增
                  </button>
                </div>
                <p className="text-[10px] font-mono text-neutral-400">
                  {newNums.trim()
                    ? parsedNewNums.length > 0
                      ? `將加入 ${parsedNewNums.length} 顆:${numsSummary(parsedNewNums)}`
                      : `看不懂這組號碼,或都超出 01~${pad2(numMax)} 的範圍`
                    : `支援「起-迄」與逗號:1-15、2,4,6,20-25;超過 ${pad2(numMax)} 的號碼會自動忽略。`}
                </p>
              </div>

              <p className="text-[10px] text-neutral-400">
                區間設定存在這台瀏覽器({gameName}單獨一份),重整後保留。
              </p>
            </div>
          )}

          {intervalPairs.loading && <div className="text-xs text-neutral-400">載入區間統計中…</div>}
          {intervalPairs.error && <div className="text-xs text-rose-500">{intervalPairs.error}</div>}

          {!intervalPairs.loading && !intervalPairs.error && (
            <div className="space-y-2">
              {alertPairs.map(p => (
                <PairRow key={pairKey(p.groups)} p={p} detail={pairDetail(p)} tone="alert" />
              ))}
              {quietPairs.map(p => (
                <PairRow key={pairKey(p.groups)} p={p} detail={pairDetail(p)} tone="quiet" />
              ))}
              {alertPairs.length + quietPairs.length === 0 && (
                <div className="text-xs text-neutral-400">
                  {intervals.length < 2
                    ? '至少要有兩個區間才能算組合提醒 —— 按「設定監看區間」新增。'
                    : '目前沒有未開的組合 —— 監看中的區間近期都有開出。'}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 區間組合共現:勾幾個區間組成一組,追蹤距上次「全部同一期一起開」幾期 */}
        <div className="p-4 sm:p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Target className="w-4 h-4 text-amber-500" />
              <span>區間組合同時出現(多久沒一起開)</span>
              <span className="px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 text-[10px] font-semibold">
                全站公共・提醒機器人
              </span>
              {comboAlertCount > 0 && (
                <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-700 dark:text-amber-300 text-[10px] font-mono font-bold">
                  {comboAlertCount} 組警示
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] text-neutral-400">提醒門檻</span>
              <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
                {THRESHOLD_OPTIONS.map(n => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => saveCombos(combos, n)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                      watchThreshold === n
                        ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                    }`}
                  >
                    {n} 期
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => api.testComboWatch(gameKey).then(r =>
                  setWatchMsg(r.notify_enabled
                    ? (r.sent ? '已發測試提醒到群組(目前有斷檔)。' : '目前沒有達門檻的斷檔,未發送。')
                    : 'Telegram 尚未設定(遠端未設 chat_id/token)。'))
                  .catch(e => setWatchMsg((e as Error).message))}
                className="px-3 py-1.5 rounded-xl border border-black/[0.08] dark:border-white/[0.08] text-xs font-semibold text-neutral-600 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5"
              >
                測試提醒
              </button>
            </div>
          </div>

          <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
            勾選上方那份區間清單裡的幾個區間組成一組(例:01~09 + 10~19 + 20~29 + 30~39),
            追蹤距上次「每個區間在同一期都至少開出一顆」過了幾期;連續 <strong>{watchThreshold}</strong> 期
            沒有一起開就跳警示、並由<strong>提醒機器人推到群組</strong>。這份設定<strong>全站共用</strong>,
            目前 {gameName} 監看 {combos.length} 組。
          </div>
          {watchMsg && <div className="text-[11px] text-emerald-600 dark:text-emerald-400">{watchMsg}</div>}

          {comboTogether.loading && <div className="text-xs text-neutral-400">載入區間組合統計中…</div>}
          {comboTogether.error && <div className="text-xs text-rose-500">{comboTogether.error}</div>}

          <div className="space-y-2">
            {comboRows.map(r => (
              <ComboRow
                key={`${r.combo.label}-${r.idx}`}
                label={r.combo.label}
                detail={
                  `${r.combo.groups.length} 個區間:` + r.combo.groups.map(numsSummary).join(' + ')
                }
                stat={r.stat}
                onRemove={() => removeCombo(r.idx)}
              />
            ))}
            {combos.length === 0 && (
              <div className="text-xs text-neutral-400">
                還沒有監看中的組合 —— 在下面勾兩個以上的區間(例如 10~19 與 30~39)新增。
              </div>
            )}
          </div>

          {/* 新增組合:勾區間,每個區間各自是一個 group */}
          <div className="pt-3 border-t border-black/[0.06] dark:border-white/[0.06] space-y-3">
            <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
              勾選要納入的區間({intervals.length} 個可選)
            </div>

            {intervals.length === 0 ? (
              <div className="text-[11px] text-neutral-400">
                目前沒有任何區間 —— 先到上方「設定監看區間」新增,或按「還原預設」拿回十位分段。
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {intervals.map((g, i) => {
                  const on = pickedIvs.includes(i);
                  return (
                    <button
                      key={`${g.label}-${i}`}
                      type="button"
                      onClick={() => toggleIv(i)}
                      aria-pressed={on}
                      className={`px-3 py-1.5 rounded-xl border text-left transition-all ${
                        on
                          ? 'bg-black text-white dark:bg-white dark:text-black border-transparent'
                          : 'bg-white dark:bg-[#121212] border-black/[0.12] dark:border-white/[0.12] text-neutral-700 dark:text-neutral-300 hover:border-black/30 dark:hover:border-white/30'
                      }`}
                    >
                      <span className="block text-xs font-mono font-bold">{g.label}</span>
                      <span
                        className={`block text-[10px] font-mono ${
                          on ? 'opacity-70' : 'text-neutral-400'
                        }`}
                      >
                        {numsSummary(g.nums)}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={newComboLabel}
                onChange={e => setNewComboLabel(e.target.value)}
                placeholder={pickedLabel || '組合名稱(可留空,預設用區間名)'}
                className="flex-1 px-2.5 py-1.5 rounded-lg bg-white dark:bg-[#121212] border border-black/[0.12] dark:border-white/[0.12] text-xs text-neutral-900 dark:text-white placeholder:text-neutral-400 focus:outline-none focus:border-black/30 dark:focus:border-white/30"
              />
              <button
                type="button"
                onClick={addComboFromIntervals}
                disabled={!canAddCombo}
                className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-black text-white dark:bg-white dark:text-black text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                <Plus className="w-3.5 h-3.5" />
                加入這組
              </button>
            </div>

            <p className="text-[10px] font-mono text-neutral-400">
              {canAddCombo
                ? `${pickedLabel} — ${pickedGroups.length} 個區間都要在同一期各開出至少一顆才算「一起開」`
                : pickedGroups.length === 1
                  ? '只勾了一個區間 —— 至少要兩個才有「同時出現」可言。'
                  : '還沒勾任何區間 —— 勾 2 個以上(例如四段全勾)看它多久沒一起開。'}
            </p>

            <p className="text-[10px] text-neutral-400">
              組合存在這台瀏覽器({gameName}單獨一份),重整後保留;存的是當下各區間的號碼,
              之後改區間清單不會回頭動到已建立的組合。右側大字為距上次全部同時出現的期數。
            </p>
          </div>
        </div>

        <div className="p-4 sm:p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <LayoutGrid className="w-4 h-4 text-neutral-500" />
              <span>開獎歷史分佈走勢(01~{pad2(numMax)} × 開獎日期)</span>
            </div>
            <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
              {HIST_OPTIONS.map(n => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setHistN(n)}
                  className={`px-3 py-1 rounded-lg text-xs font-mono font-semibold transition-all ${
                    histN === n
                      ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                      : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                  }`}
                >
                  近 {n} 期
                </button>
              ))}
            </div>
          </div>

          {/* 分色圖例(依十位) */}
          <div className="flex flex-wrap gap-3 text-[10px] text-neutral-500 dark:text-neutral-400">
            {bands.map(l => (
              <span key={l.t} className="inline-flex items-center gap-1">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${l.c}`} />
                {l.t}
              </span>
            ))}
          </div>

          {drawHist.loading && <div className="text-xs text-neutral-400">載入開獎歷史…</div>}
          {drawHist.error && <div className="text-xs text-rose-500">{drawHist.error}</div>}

          {!drawHist.loading && !drawHist.error && (
            <div className="overflow-x-auto -mx-1 px-1">
              <table className="border-separate border-spacing-0 text-center">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 bg-white dark:bg-[#121212] px-2 py-1.5 text-left text-[10px] uppercase tracking-wider text-neutral-400 font-semibold">
                      開獎日期
                    </th>
                    {allNums.map(n => (
                      <th
                        key={n}
                        className="px-0.5 py-1.5 text-[9px] font-mono text-neutral-400 dark:text-neutral-500 min-w-[1.35rem]"
                      >
                        {n.toString().padStart(2, '0')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {histRows.map(d => {
                    const hit = new Set(d.nums);
                    return (
                      <tr key={d.date + (d.issue ?? '')} className="hover:bg-black/[0.02] dark:hover:bg-white/[0.02]">
                        <td className="sticky left-0 z-10 bg-white dark:bg-[#121212] px-2 py-1 text-left whitespace-nowrap border-t border-black/[0.05] dark:border-white/[0.05]">
                          <span className="font-mono text-[11px] text-neutral-700 dark:text-neutral-300">{d.date}</span>
                        </td>
                        {allNums.map(n => (
                          <td key={n} className="px-0.5 py-1 border-t border-black/[0.05] dark:border-white/[0.05]">
                            {hit.has(n) ? (
                              <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[9px] font-mono font-bold ${bandDot(n)}`}>
                                {n.toString().padStart(2, '0')}
                              </span>
                            ) : (
                              <span className="inline-block w-1 h-1 rounded-full bg-black/10 dark:bg-white/10" />
                            )}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr>
                    <td className="sticky left-0 z-10 bg-black/[0.02] dark:bg-white/[0.03] px-2 py-1.5 text-left text-[10px] uppercase tracking-wider text-neutral-400 font-semibold border-t border-black/[0.08] dark:border-white/[0.08]">
                      出現次數
                    </td>
                    {allNums.map(n => {
                      const c = histFreq.get(n) ?? 0;
                      return (
                        <td
                          key={n}
                          className={`px-0.5 py-1.5 text-[10px] font-mono border-t border-black/[0.08] dark:border-white/[0.08] ${
                            c === 0 ? 'text-neutral-300 dark:text-neutral-600' : 'text-neutral-900 dark:text-white font-bold'
                          }`}
                        >
                          {c}
                        </td>
                      );
                    })}
                  </tr>
                </tfoot>
              </table>
            </div>
          )}

          <p className="text-[11px] text-neutral-400 dark:text-neutral-500">
            每一列為一期開獎,圓點標出當期開出的號碼(依十位分色);最下方為該號在近 {histN} 期的出現次數分佈。
          </p>
        </div>
        </>
      )}

      {/* Hot & Cold View */}
      {activeTab === 'hot_cold' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {/* Hot numbers */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Flame className="w-4 h-4 text-amber-500" />
              <span>近 {periods} 期最熱門號碼 TOP 6</span>
            </div>
            <div className="space-y-2">
              {hotColdLoading && <div className="text-xs text-neutral-400">載入中…</div>}
              {hotColdError && <div className="text-xs text-rose-500">{hotColdError}</div>}
              {hotNumbers.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-full bg-black text-white dark:bg-white dark:text-black font-mono font-bold text-xs flex items-center justify-center">
                      {item.num.toString().padStart(2, '0')}
                    </span>
                    <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">開出 {item.count} 次</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-neutral-900 dark:text-white">{item.rate}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Cold numbers */}
          <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
            <div className="flex items-center gap-2 text-neutral-900 dark:text-white font-display font-bold text-sm uppercase tracking-wide">
              <Snowflake className="w-4 h-4 text-neutral-400" />
              <span>近 {periods} 期最冷門號碼 TOP 6</span>
            </div>
            <div className="space-y-2">
              {hotColdLoading && <div className="text-xs text-neutral-400">載入中…</div>}
              {hotColdError && <div className="text-xs text-rose-500">{hotColdError}</div>}
              {coldNumbers.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-full border border-black/20 dark:border-white/20 text-neutral-700 dark:text-neutral-300 font-mono font-bold text-xs flex items-center justify-center">
                      {item.num.toString().padStart(2, '0')}
                    </span>
                    <span className="text-xs font-semibold text-neutral-800 dark:text-neutral-200">開出 {item.count} 次</span>
                  </div>
                  <span className="text-xs font-mono font-bold text-neutral-500">{item.rate}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Pillar Distribution View */}
      {activeTab === 'pillar_dist' && (
        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">三柱開出頻率與過關比率</h3>
          {!supportsPillar ? (
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06] text-xs text-neutral-500 dark:text-neutral-400">
              {gameName}不適用三柱 —— 三柱 1800 碰是為 39 選 5 的盤設計的,
              換回今彩539 或天天樂才會有這頁的統計。
            </div>
          ) : (
            <>
              {pillarLoading && <div className="text-xs text-neutral-400">載入中…</div>}
              {pillarError && <div className="text-xs text-rose-500">{pillarError}</div>}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[0, 1, 2].map(i => (
                  <div key={i} className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
                    <div className="text-[10px] uppercase tracking-wider text-neutral-400">{pillarLabel(i)}</div>
                    <div className="text-2xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{actualRate(i)}</div>
                    <div className="text-[10px] text-neutral-400 mt-1">理論開出率 {theoryRate(i)}</div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Odd Even View */}
      {activeTab === 'odd_even' && (
        <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
          <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">單雙比與大小比分析</h3>
          {parity.loading && <div className="text-xs text-neutral-400">載入中…</div>}
          {parity.error && <div className="text-xs text-rose-500">{parity.error}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">單號 vs 雙號</div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{ratioText(parityPct?.odd)}</div>
            </div>
            <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
              <div className="text-[10px] uppercase tracking-wider text-neutral-400">
                {split
                  ? `大號 (${pad2(split + 1)}-${pad2(numMax)}) vs 小號 (01-${pad2(split)})`
                  : '大號 vs 小號'}
              </div>
              <div className="text-xl font-bold font-mono text-neutral-900 dark:text-white mt-1">{ratioText(parityPct?.big)}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
