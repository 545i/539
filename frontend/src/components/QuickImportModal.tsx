import React, {useEffect, useMemo, useState} from 'react';
import {X, ClipboardPaste, ListChecks, Upload, AlertTriangle, CheckCircle2} from 'lucide-react';
import {api, QuickImportDTO, LedgerMode, TensPairDTO} from '../api/client';
import {useAsync} from '../api/useAsync';
import {useAuth} from '../api/useAuth';
import {useGame} from '../api/useGame';

// 快速上傳下注紀錄:貼一段下注文字 → 預覽 → 確認寫進自己的記帳流水。
//
// 解析規則全在後端(backend/routers/importer.py),前端不重算成本 —— 預覽顯示的
// 就是等一下真的會存進去的那份 record,兩邊不會對不起來。
//
// 先「解析預覽」(dry_run)再「確認上傳」是刻意的兩步:文字認錯行的機率不低,
// 直接寫進去要一筆一筆撤銷很麻煩。

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onImported?: () => void; // 上傳成功後通知外面重抓流水
}

const MODE_LABEL: Record<LedgerMode, string> = {
  single: '單顆',
  multi: '多顆',
  pillar1800: '1800碰',
  combo: '連碰',
};

const SAMPLE = `02x50車
09_15_19_20x20車
02_09_15_19_20_25_28_33
八顆三星1200
八顆四星1200
10_18
20_29
其他400`;


export const QuickImportModal: React.FC<Props> = ({isOpen, onClose, onImported}) => {
  const {loggedIn} = useAuth();
  const {gameKey, game, games, setGameKey} = useGame();
  const [text, setText] = useState('');
  const [issue, setIssue] = useState('');
  const [preview, setPreview] = useState<QuickImportDTO | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<number | null>(null);

  // 下注期數:預設帶入「最新一期 +1」(下一期);使用者可自行改
  const hist = useAsync(() => (isOpen ? api.history(gameKey, 1) : Promise.resolve(null)), [gameKey, isOpen]);
  const nextIssue = useMemo(() => {
    const last = hist.data?.latest?.issue;
    if (!last) return '';
    const m = last.match(/^(\d+)$/);
    return m ? String(Number(m[1]) + 1) : last;
  }, [hist.data]);
  useEffect(() => { setIssue(nextIssue); }, [nextIssue]);

  // 區間斷檔提醒(參考用):依目前選的遊戲,只顯示未開(streak>=1)的配對
  const pairs = useAsync<TensPairDTO[]>(
    () => (isOpen ? api.tensPairs(gameKey, 3) : Promise.resolve([])),
    [gameKey, isOpen],
  );
  const brokenPairs = (pairs.data ?? []).filter(p => p.streak >= 1);

  if (!isOpen) return null;

  const reset = () => {
    setPreview(null);
    setError(null);
    setDone(null);
  };

  const run = async (dryRun: boolean) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.quickImport(gameKey, text, dryRun, {issue});
      setPreview(res);
      if (!dryRun) {
        setDone(res.saved);
        onImported?.();
        // 上傳成功後關閉彈窗(留一下讓成功訊息閃一下)
        window.setTimeout(() => {
          setText('');
          reset();
          onClose();
        }, 900);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const num = (v: unknown) => (typeof v === 'number' ? v : 0);
  const items = preview?.items ?? [];
  const errors = preview?.errors ?? [];
  const totalCost = items.reduce((acc, it) => acc + num(it.record.cost), 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        id="quick-import-modal-content"
        className="w-full max-w-3xl max-h-[90vh] bg-white dark:bg-[#121212] border border-black/10 dark:border-white/10 rounded-2xl shadow-2xl flex flex-col text-neutral-800 dark:text-neutral-200"
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-black/[0.08] dark:border-white/[0.08] shrink-0">
          <div className="flex items-center gap-2 font-display font-bold text-base text-neutral-900 dark:text-white uppercase tracking-wide">
            <ClipboardPaste className="w-4 h-4 text-neutral-500" />
            <span>快速上傳下注紀錄</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            id="close-quick-import-btn"
            className="p-1.5 rounded-full text-neutral-400 hover:text-neutral-700 dark:hover:text-white hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-4 overflow-y-auto">
          {!loggedIn && (
            <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-800 dark:text-amber-300 flex items-start gap-2">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>快速上傳要先登入 —— 紀錄是記在你的帳號底下的。</span>
            </div>
          )}

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                上傳到哪款
              </label>
              <div className="inline-flex p-1 rounded-xl bg-black/[0.03] dark:bg-white/[0.04] border border-black/[0.06] dark:border-white/[0.06] gap-1">
                {games.map(g => (
                  <button
                    key={g.key}
                    type="button"
                    onClick={() => {
                      setGameKey(g.key); // 全域切換:上傳目標 + 區間紀錄等全站一起換
                      reset();
                    }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      gameKey === g.key
                        ? 'bg-black text-white dark:bg-white dark:text-black shadow-xs'
                        : 'text-neutral-600 dark:text-neutral-400 hover:text-black dark:hover:text-white'
                    }`}
                  >
                    {g.short_name}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
                下注期數
              </label>
              <input
                id="quick-import-issue"
                type="text"
                inputMode="numeric"
                value={issue}
                placeholder={nextIssue || '期別'}
                onChange={e => setIssue(e.target.value)}
                className="h-10 w-40 px-3 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-sm font-mono text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40 transition-colors"
              />
            </div>
            <div className="text-[11px] text-neutral-500 dark:text-neutral-400 pb-2.5">
              記到 <strong>{game?.name ?? gameKey}</strong>(由上方遊戲切換器決定),
              結果一律先記「待開獎」,開獎後再結算。
            </div>
          </div>

          {/* 區間斷檔提醒(參考用):依目前遊戲,只顯示未開的區段配對 */}
          <div className="rounded-xl border border-black/[0.08] dark:border-white/[0.08] bg-black/[0.02] dark:bg-white/[0.03] p-3 space-y-2">
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>區間斷檔提醒（{game?.short_name ?? gameKey}・參考）</span>
            </div>
            {pairs.loading && <div className="text-[11px] text-neutral-400">載入中…</div>}
            {!pairs.loading && brokenPairs.length === 0 && (
              <div className="text-[11px] text-neutral-400">
                各十位區段近期都有開出，目前沒有連續未開的組合。
              </div>
            )}
            <div className="flex flex-wrap gap-1.5">
              {brokenPairs.map(p => (
                <span
                  key={`${p.bands[0]}-${p.bands[1]}`}
                  className={`px-2 py-1 rounded-lg text-[11px] font-mono ${
                    p.alert
                      ? 'bg-amber-500/15 text-amber-800 dark:text-amber-300 border border-amber-500/30 font-bold'
                      : 'bg-black/5 dark:bg-white/10 text-neutral-600 dark:text-neutral-300'
                  }`}
                  title={`${p.range[0]} × ${p.range[1]}`}
                >
                  {p.labels[0]}×{p.labels[1]} {p.streak}期未開
                </span>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400 mb-1.5">
              下注文字
            </label>
            <textarea
              id="quick-import-text"
              value={text}
              rows={9}
              spellCheck={false}
              placeholder={SAMPLE}
              onChange={e => {
                setText(e.target.value);
                reset();
              }}
              className="w-full px-3 py-2.5 rounded-xl border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] text-sm font-mono leading-relaxed text-neutral-900 dark:text-white outline-hidden focus:border-black/40 dark:focus:border-white/40 transition-colors resize-y"
            />
            <div className="mt-2 text-[10px] text-neutral-400 leading-relaxed space-y-0.5">
              <div><code>02x50車</code> = 單顆、50 車　|　<code>09_15_19_20x20車</code> = 多顆、20 車</div>
              <div>一行選號 + <code>八顆三星1200</code> = 星碰三星 12 支(支數 = 金額 ÷ 100)</div>
              <div><code>10_18</code> / <code>20_29</code> / <code>其他400</code> 三行 = 1800碰 4 支</div>
            </div>
          </div>

          {error && (
            <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-700 dark:text-rose-400">
              {error}
            </div>
          )}

          {done !== null && (
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-800 dark:text-emerald-300 flex items-start gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>已寫入 {done} 筆,各記帳分頁重新整理後就看得到。</span>
            </div>
          )}

          {preview && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] font-semibold text-neutral-400">
                <ListChecks className="w-3.5 h-3.5" />
                <span>
                  解析出 {preview.parsed} 筆　總成本 {totalCost.toLocaleString()}
                </span>
              </div>

              {items.length > 0 && (
                <div className="rounded-xl border border-black/[0.08] dark:border-white/[0.08] overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead className="bg-black/[0.03] dark:bg-white/[0.04] text-neutral-500">
                      <tr>
                        <th className="px-3 py-2 text-left font-semibold">玩法</th>
                        <th className="px-3 py-2 text-left font-semibold">號碼</th>
                        <th className="px-3 py-2 text-right font-semibold">支 / 車</th>
                        <th className="px-3 py-2 text-right font-semibold">注 / 碰</th>
                        <th className="px-3 py-2 text-right font-semibold">成本</th>
                      </tr>
                    </thead>
                    <tbody className="font-mono">
                      {items.map((it, i) => (
                        <tr
                          key={i}
                          className="border-t border-black/[0.06] dark:border-white/[0.06]"
                        >
                          <td className="px-3 py-2 font-sans">
                            <span className="px-1.5 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-[10px] mr-1.5">
                              {MODE_LABEL[it.mode]}
                            </span>
                            {String(it.record.playType ?? '')}
                          </td>
                          <td className="px-3 py-2 text-neutral-500">
                            {((it.record.selectedBalls as number[]) ?? [])
                              .map(n => String(n).padStart(2, '0'))
                              .join(' ') || '—'}
                          </td>
                          <td className="px-3 py-2 text-right">{num(it.record.units)}</td>
                          <td className="px-3 py-2 text-right">
                            {num(it.record.betsCount).toLocaleString()}
                          </td>
                          <td className="px-3 py-2 text-right">
                            {num(it.record.cost).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {errors.length > 0 && (
                <div className="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-800 dark:text-amber-300 space-y-1">
                  <div className="flex items-center gap-2 font-semibold">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>{errors.length} 行看不懂,這些行不會被記進去</span>
                  </div>
                  {errors.map((e, i) => (
                    <div key={i} className="font-mono">
                      第 {e.line_no} 行「{e.line}」—— {e.message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-black/[0.08] dark:border-white/[0.08] shrink-0">
          <button
            type="button"
            id="quick-import-preview-btn"
            disabled={busy || !text.trim() || !loggedIn}
            onClick={() => run(true)}
            className="py-2.5 px-4 rounded-xl text-xs uppercase tracking-wider font-semibold bg-white dark:bg-[#161616] border border-black/[0.08] dark:border-white/[0.08] text-neutral-700 dark:text-neutral-300 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-30 transition-colors flex items-center gap-2"
          >
            <ListChecks className="w-4 h-4" />
            {busy ? '處理中…' : '解析預覽'}
          </button>
          <button
            type="button"
            id="quick-import-submit-btn"
            // 一定要先預覽過、而且真的有解析出東西才給上傳
            disabled={busy || !loggedIn || items.length === 0 || done !== null}
            onClick={() => run(false)}
            className="py-2.5 px-4 rounded-xl text-xs uppercase tracking-wider font-semibold bg-black text-white dark:bg-white dark:text-black hover:opacity-90 disabled:opacity-30 transition-opacity flex items-center gap-2 shadow-xs active:scale-98"
          >
            <Upload className="w-4 h-4" />
            確認上傳{items.length > 0 ? ` ${items.length} 筆` : ''}
          </button>
        </div>
      </div>
    </div>
  );
};
