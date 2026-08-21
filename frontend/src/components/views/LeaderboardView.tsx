import React from 'react';
import { ChevronDown, Trophy } from 'lucide-react';
import { api, LeaderboardDTO, LeaderRowDTO, UserLedgerDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useAuth } from '../../api/useAuth';

// 排行榜的數字全部來自後端 /leaderboard —— 也就是大家實際記過的帳,
// 不是回測、不是模擬。沒人記帳就是空榜(不補示範資料,免得看起來像真的)。
//
// 這頁刻意不吃全域遊戲:後端的流水彙總沒有遊戲維度(ledger 只分下法),
// 榜上是所有遊戲合計。等後端 /leaderboard 支援 game 參數再接上全域切換器。

const pnlText = (v: number) => `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString()}`;
const pct = (v: number | null) => (v === null ? '—' : `${(v * 100).toFixed(1)}%`);

const pnlColor = (v: number) =>
  v > 0
    ? 'text-emerald-600 dark:text-emerald-400'
    : v < 0
      ? 'text-rose-600 dark:text-rose-400'
      : 'text-neutral-900 dark:text-white';

const num = (v: number | null) => (v === null ? '—' : Math.round(v).toLocaleString());
const balls = (bs: number[]) => bs.map(b => b.toString().padStart(2, '0'));

/** 一列排行(使用者榜與下法榜共用同一種卡片)。 */
const Row: React.FC<{
  rank: number;
  title: string;
  badge?: string;
  highlight?: boolean;
  row: LeaderRowDTO;
  /** 有給就代表這列可以展開看明細(下法榜不給,就還是一張靜態卡片)。 */
  onToggle?: () => void;
  expanded?: boolean;
  children?: React.ReactNode;
}> = ({ rank, title, badge, highlight, row, onToggle, expanded, children }) => {
  const head = (
    <div className="flex items-center justify-between gap-4 w-full">
      <div className="flex items-center gap-4">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center font-display font-bold text-xs shrink-0 ${
          rank === 1 ? 'bg-black text-white dark:bg-white dark:text-black' :
          'border border-black/15 dark:border-white/15 text-neutral-700 dark:text-neutral-300'
        }`}>
          {String(rank).padStart(2, '0')}
        </div>
        <div className="text-left">
          <div className="font-bold text-sm text-neutral-900 dark:text-white flex items-center gap-2">
            <span>{title}</span>
            {badge && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300 font-mono">
                {badge}
              </span>
            )}
          </div>
          <div className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
            局數: <strong className="font-mono text-neutral-800 dark:text-neutral-200">{row.rounds}</strong>
            {' | '}勝率: <strong className="font-mono text-neutral-800 dark:text-neutral-200">{pct(row.win_rate)}</strong>
            {' | '}實際報酬率: <strong className="font-mono">{pct(row.roi)}</strong>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wider text-neutral-400">累積損益</div>
          <div className={`text-xl font-bold font-mono ${pnlColor(row.total_pnl)}`}>
            {pnlText(row.total_pnl)}
          </div>
        </div>
        {onToggle && (
          <ChevronDown
            className={`w-4 h-4 text-neutral-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          />
        )}
      </div>
    </div>
  );

  return (
    <div
      className={`rounded-2xl bg-white dark:bg-[#121212] border ${
        highlight
          ? 'border-black/30 dark:border-white/30'
          : 'border-black/[0.08] dark:border-white/[0.08]'
      }`}
    >
      {onToggle ? (
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="w-full p-5 flex items-center hover:bg-black/[0.02] dark:hover:bg-white/[0.03] rounded-2xl transition-colors"
        >
          {head}
        </button>
      ) : (
        <div className="p-5 flex items-center">{head}</div>
      )}
      {expanded && children && (
        <div className="px-5 pb-5 border-t border-black/[0.06] dark:border-white/[0.06] pt-4">
          {children}
        </div>
      )}
    </div>
  );
};

/** 展開後的下注明細。這個元件只在展開時才被掛上,所以收合狀態下不會發請求;
 *  再展開會重抓一次 —— 別人的流水隨時在變,拿新的比拿快取的合理。 */
const UserLedger: React.FC<{ username: string }> = ({ username }) => {
  const { data, loading, error } = useAsync<UserLedgerDTO>(
    () => api.userLedger(username),
    [username],
  );

  if (loading) {
    return <div className="text-xs text-neutral-500">載入 {username} 的下注歷史…</div>;
  }
  if (error) {
    return <div className="text-xs text-rose-600 dark:text-rose-400">載入失敗:{error}</div>;
  }
  const entries = data?.entries ?? [];
  if (entries.length === 0) {
    return <div className="text-xs text-neutral-500 dark:text-neutral-400">這個帳號還沒有下注紀錄。</div>;
  }

  return (
    <div className="space-y-2">
      <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500">
        下注歷史({entries.length} 筆,新→舊)
      </div>
      <div className="lt-wrap border border-black/[0.08] dark:border-white/[0.08] rounded-xl">
        <table className="lt">
          <thead>
            <tr>
              <th>期號</th>
              <th>遊戲</th>
              <th>玩法</th>
              <th>號碼</th>
              <th>支/車</th>
              <th>成本</th>
              <th>結果</th>
              <th>損益</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(e => (
              <tr key={e.id}>
                <td>
                  <div className="text-xs font-mono font-bold">{e.issue || '—'}</div>
                  <div className="text-[10px] text-neutral-400">{e.date || e.created.slice(0, 10)}</div>
                </td>
                <td className="text-xs font-semibold">{(e.game || '—').split('(')[0]}</td>
                <td className="text-xs">
                  <div className="font-semibold">{e.mode_name}</div>
                  {e.playType && <div className="text-[10px] text-neutral-400">{e.playType}</div>}
                </td>
                <td className="font-mono text-xs">
                  {e.selectedBalls.length ? balls(e.selectedBalls).join(' ') : '—'}
                </td>
                <td className="font-mono text-xs">{num(e.cars ?? e.units)}</td>
                <td className="font-mono text-xs">{num(e.cost)}</td>
                <td>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                    (e.pnl ?? 0) > 0
                      ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 font-bold'
                      : e.result === '待開獎'
                        ? 'bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-400'
                        : 'bg-rose-500/10 text-rose-600 dark:text-rose-400'
                  }`}>
                    {e.result || '—'}
                  </span>
                </td>
                <td className={`font-mono text-xs font-bold ${e.pnl === null ? '' : pnlColor(e.pnl)}`}>
                  {e.pnl === null ? '—' : pnlText(e.pnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export const LeaderboardView: React.FC = () => {
  const { loggedIn } = useAuth();
  const { data, loading, error } = useAsync<LeaderboardDTO | null>(
    () => (loggedIn ? api.leaderboard() : Promise.resolve(null)),
    [loggedIn],
  );

  // 手風琴:同時只展開一個帳號 —— 一次抓一份明細,也不會整頁變成長長的表格牆。
  const [open, setOpen] = React.useState<string | null>(null);

  const users = data?.users ?? [];
  const modes = data?.modes ?? [];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08]">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-full bg-black/5 dark:bg-white/5 text-neutral-900 dark:text-white">
            <Trophy className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide">
              記帳損益排行榜
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              依各帳號實際記錄的下注流水彙總累積損益、勝率與報酬率(所有遊戲合計);點任一列可展開看該帳號的下注歷史
            </p>
          </div>
        </div>
      </div>

      {!loggedIn && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
          排行榜含各帳號的損益,請先登入後檢視。
        </div>
      )}
      {loggedIn && loading && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500">
          載入中…
        </div>
      )}
      {loggedIn && error && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-rose-500/30 text-xs text-rose-600 dark:text-rose-400">
          載入失敗:{error}
        </div>
      )}
      {loggedIn && !loading && !error && users.length === 0 && (
        <div className="p-5 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] text-xs text-neutral-500 dark:text-neutral-400">
          還沒有任何記帳紀錄。到「二合買牌」各分頁記幾筆帳,這裡就會有排名。
        </div>
      )}

      <div className="space-y-3">
        {users.map(u => (
          <Row
            key={u.username}
            rank={u.rank}
            title={u.username}
            badge={u.is_me ? '我' : undefined}
            highlight={u.is_me}
            row={u}
            expanded={open === u.username}
            onToggle={() => setOpen(cur => (cur === u.username ? null : u.username))}
          >
            <UserLedger username={u.username} />
          </Row>
        ))}
      </div>

      {modes.length > 0 && (
        <>
          <div className="px-1 text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 dark:text-neutral-500">
            全站各下法表現(所有帳號合計)
          </div>
          <div className="space-y-3">
            {modes.map((m, i) => (
              <Row key={m.mode} rank={i + 1} title={m.name} row={m} />
            ))}
          </div>
        </>
      )}
    </div>
  );
};
