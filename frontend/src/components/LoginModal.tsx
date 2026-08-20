import React, {useState} from 'react';
import {X, LogIn, UserPlus, KeyRound, CheckCircle2} from 'lucide-react';
import {useAuth} from '../api/useAuth';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  gate?: boolean; // 登入閘模式:不給關(隱藏關閉鈕),登入才放行
}

// 登入 / 註冊(註冊需邀請碼,沿用後端 core.auth 的規則)。
// 登入成功就關掉,各分頁的流水帳會自己去後端撈。
export const LoginModal: React.FC<Props> = ({isOpen, onClose, gate = false}) => {
  const {login, register} = useAuth();
  const [tab, setTab] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (!isOpen) return null;

  const switchTab = (next: 'login' | 'register') => {
    setTab(next);
    setError(null);
    setNotice(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (tab === 'login') {
        await login(username.trim(), password);
        setPassword('');
        onClose();
      } else {
        const res = await register(username.trim(), password, inviteCode.trim());
        setNotice(res.message);
        setTab('login');
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        id="login-modal-content"
        className="w-full max-w-sm bg-white dark:bg-[#121212] border border-black/10 dark:border-white/10 rounded-2xl shadow-2xl flex flex-col text-neutral-800 dark:text-neutral-200"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.08] dark:border-white/[0.08]">
          <div className="flex items-center gap-2 font-display font-bold text-base text-neutral-900 dark:text-white uppercase tracking-wide">
            <KeyRound className="w-4 h-4 text-neutral-500" />
            <span>{gate ? '請先登入' : '帳號登入'}</span>
          </div>
          {!gate && (
            <button
              type="button"
              onClick={onClose}
              id="close-login-modal-btn"
              className="p-1.5 rounded-full text-neutral-400 hover:text-neutral-700 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* 登入 / 註冊切換 */}
          <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06]">
            {([
              {id: 'login' as const, label: '登入'},
              {id: 'register' as const, label: '註冊'},
            ]).map(t => (
              <button
                key={t.id}
                type="button"
                id={`login-tab-${t.id}`}
                onClick={() => switchTab(t.id)}
                className={`py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                  tab === t.id
                    ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                    : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                帳號
              </label>
              <input
                id="login-username"
                type="text"
                value={username}
                autoComplete="username"
                onChange={e => setUsername(e.target.value)}
                className="w-full h-10 px-3 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-sm font-mono text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40 transition-colors"
              />
            </div>

            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                密碼
              </label>
              <input
                id="login-password"
                type="password"
                value={password}
                autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                onChange={e => setPassword(e.target.value)}
                className="w-full h-10 px-3 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-sm font-mono text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40 transition-colors"
              />
            </div>

            {tab === 'register' && (
              <div>
                <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                  邀請碼
                </label>
                <input
                  id="login-invite-code"
                  type="text"
                  value={inviteCode}
                  onChange={e => setInviteCode(e.target.value)}
                  className="w-full h-10 px-3 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-sm font-mono text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40 transition-colors"
                />
                <p className="text-[10px] text-neutral-400 mt-1.5">
                  沒有邀請碼無法註冊新帳號。
                </p>
              </div>
            )}
          </div>

          {error && (
            <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-700 dark:text-rose-400">
              {error}
            </div>
          )}

          {notice && (
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-800 dark:text-emerald-300 flex items-start gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>{notice}</span>
            </div>
          )}

          <button
            type="submit"
            id="login-submit-btn"
            disabled={busy || !username.trim() || !password}
            className="w-full py-3 px-4 rounded-xl text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 transition-opacity flex items-center justify-center gap-2 shadow-xs active:scale-98"
          >
            {tab === 'login' ? <LogIn className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
            {busy ? '處理中…' : tab === 'login' ? '登入' : '註冊帳號'}
          </button>

          <p className="text-[10px] text-neutral-400 leading-relaxed">
            登入後記帳流水存在伺服器,重整或換裝置都還在;未登入時紀錄只留在這個瀏覽器分頁。
          </p>
        </form>
      </div>
    </div>
  );
};
