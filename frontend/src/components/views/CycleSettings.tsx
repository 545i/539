import React, {useCallback, useEffect, useState} from 'react';
import {CalendarClock, Plus, CheckCircle2} from 'lucide-react';
import {api, CycleDTO} from '../../api/client';
import {useAuth} from '../../api/useAuth';

// 週期性紀錄設定:管理記帳「週期」。同時只有一個進行中(open)週期,
// 新下注會自動綁到它;按「結算」把它收掉後,可再開新週期。歷史週期列在下方。

// ISO 時間 → 好讀的本地字串(拿不到就顯示「—」)
const fmt = (s?: string): string => {
  if (!s) return '—';
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString();
};

export const CycleSettings: React.FC = () => {
  const {loggedIn} = useAuth();
  const [cycles, setCycles] = useState<CycleDTO[]>([]);
  const [current, setCurrent] = useState<CycleDTO | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // 重新載入週期清單 + 目前進行中週期
  const reload = useCallback(() => {
    if (!loggedIn) {
      setCycles([]);
      setCurrent(null);
      return;
    }
    Promise.all([api.getCycles(), api.getCurrentCycle()])
      .then(([list, cur]) => {
        setCycles(list);
        setCurrent(cur);
      })
      .catch(e => setErr((e as Error).message));
  }, [loggedIn]);

  useEffect(() => {
    reload();
  }, [reload]);

  // 開新週期
  const createCycle = async () => {
    const n = name.trim();
    if (!n) {
      setErr('請先輸入週期名稱。');
      return;
    }
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      await api.createCycle(n);
      setName('');
      reload();
      setMsg(`已開新週期「${n}」。`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // 結算目前週期
  const closeCurrent = async () => {
    if (!current) return;
    if (!window.confirm(`確定結算週期「${current.name}」?結算後新下注要開新週期才會被歸類。`)) return;
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      await api.closeCycle(current.id);
      reload();
      setMsg(`已結算週期「${current.name}」。`);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-6 rounded-2xl bg-white dark:bg-[#121212] border border-black/[0.08] dark:border-white/[0.08] space-y-4">
      <h3 className="text-sm font-display font-bold text-neutral-900 dark:text-white uppercase tracking-wide flex items-center gap-2">
        <CalendarClock className="w-4 h-4" />
        <span>週期性紀錄</span>
      </h3>
      <div className="text-[11px] text-neutral-500 dark:text-neutral-400">
        每個「週期」是一段記帳區間(例如「9月上半」)。同時只有一個
        <strong className="text-neutral-700 dark:text-neutral-200">進行中</strong>週期,
        新下注會自動歸到它。結算後想繼續記帳就開新週期。
      </div>

      {/* 目前進行中週期 */}
      <div className="p-4 rounded-xl bg-black/[0.02] dark:bg-white/[0.03] border border-black/[0.06] dark:border-white/[0.06]">
        {current ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-emerald-600 dark:text-emerald-400">
                進行中
              </div>
              <div className="font-display font-bold text-sm text-neutral-900 dark:text-white mt-0.5">
                {current.name}
              </div>
              <div className="text-[11px] text-neutral-500 mt-0.5 font-mono">
                開始 {fmt(current.started_at)}
              </div>
            </div>
            <button
              type="button"
              onClick={closeCurrent}
              disabled={busy || !loggedIn}
              className="px-4 py-2 rounded-full text-xs uppercase tracking-wider font-semibold border border-black/10 dark:border-white/10 text-neutral-700 dark:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 flex items-center gap-2"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              結算目前週期
            </button>
          </div>
        ) : (
          <div className="text-xs text-neutral-500 dark:text-neutral-400">
            {loggedIn ? '目前沒有進行中的週期。' : '登入後才能管理週期。'}
          </div>
        )}
      </div>

      {/* 開新週期 */}
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[12rem]">
          <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
            新週期名稱
          </label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') createCycle();
            }}
            placeholder="例如:9月上半"
            className="w-full px-3 py-2 text-sm rounded-xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#161616] text-neutral-900 dark:text-white focus:outline-hidden"
          />
        </div>
        <button
          type="button"
          onClick={createCycle}
          disabled={busy || !loggedIn}
          className="px-6 py-2.5 rounded-full text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 flex items-center gap-2 shadow-xs"
        >
          <Plus className="w-3.5 h-3.5" />
          {busy ? '處理中…' : loggedIn ? '開新週期' : '登入後才能開'}
        </button>
      </div>

      {msg && <div className="text-[11px] text-emerald-600 dark:text-emerald-400">{msg}</div>}
      {err && <div className="text-[11px] text-rose-500">{err}</div>}

      {/* 歷史週期 */}
      {cycles.length > 0 && (
        <div className="space-y-2">
          <div className="text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
            歷史週期
          </div>
          <div className="lt-wrap border border-black/[0.08] dark:border-white/[0.08] rounded-xl overflow-x-auto">
            <table className="lt w-full">
              <thead>
                <tr>
                  <th>名稱</th>
                  <th>狀態</th>
                  <th>開始</th>
                  <th>結算</th>
                </tr>
              </thead>
              <tbody>
                {cycles.map(c => (
                  <tr key={c.id}>
                    <td className="font-semibold text-xs text-neutral-900 dark:text-white">{c.name}</td>
                    <td className="text-xs">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold whitespace-nowrap ${
                          c.status === 'open'
                            ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                            : 'bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300'
                        }`}
                      >
                        {c.status === 'open' ? '進行中' : '已結算'}
                      </span>
                    </td>
                    <td className="font-mono text-xs">{fmt(c.started_at)}</td>
                    <td className="font-mono text-xs">{fmt(c.closed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
