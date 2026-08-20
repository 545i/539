import React from 'react';
import { Trophy } from 'lucide-react';
import { api, LeaderboardDTO, LeaderRowDTO } from '../../api/client';
import { useAsync } from '../../api/useAsync';
import { useAuth } from '../../api/useAuth';

// 排行榜的數字全部來自後端 /leaderboard —— 也就是大家實際記過的帳,
// 不是回測、不是模擬。沒人記帳就是空榜(不補示範資料,免得看起來像真的)。

const pnlText = (v: number) => `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString()}`;
const pct = (v: number | null) => (v === null ? '—' : `${(v * 100).toFixed(1)}%`);

const pnlColor = (v: number) =>
  v > 0
    ? 'text-emerald-600 dark:text-emerald-400'
    : v < 0
      ? 'text-rose-600 dark:text-rose-400'
      : 'text-neutral-900 dark:text-white';

/** 一列排行(使用者榜與下法榜共用同一種卡片)。 */
const Row: React.FC<{
  rank: number;
  title: string;
  badge?: string;
  highlight?: boolean;
  row: LeaderRowDTO;
}> = ({ rank, title, badge, highlight, row }) => (
  <div
    className={`p-5 rounded-2xl bg-white dark:bg-[#121212] border flex items-center justify-between gap-4 ${
      highlight
        ? 'border-black/30 dark:border-white/30'
        : 'border-black/[0.08] dark:border-white/[0.08]'
    }`}
  >
    <div className="flex items-center gap-4">
      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-display font-bold text-xs ${
        rank === 1 ? 'bg-black text-white dark:bg-white dark:text-black' :
        'border border-black/15 dark:border-white/15 text-neutral-700 dark:text-neutral-300'
      }`}>
        {String(rank).padStart(2, '0')}
      </div>
      <div>
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

    <div className="text-right">
      <div className="text-[10px] uppercase tracking-wider text-neutral-400">累積損益</div>
      <div className={`text-xl font-bold font-mono ${pnlColor(row.total_pnl)}`}>
        {pnlText(row.total_pnl)}
      </div>
    </div>
  </div>
);

export const LeaderboardView: React.FC = () => {
  const { loggedIn } = useAuth();
  const { data, loading, error } = useAsync<LeaderboardDTO | null>(
    () => (loggedIn ? api.leaderboard() : Promise.resolve(null)),
    [loggedIn],
  );

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
              依各帳號實際記錄的下注流水彙總累積損益、勝率與報酬率
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
          />
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
