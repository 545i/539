// 複製文字到剪貼簿。navigator.clipboard 只在安全連線(HTTPS / localhost)可用 ——
// 現在網站走 http://IP:8540,瀏覽器不給用,所以退回舊式 execCommand('copy')
// (暫時建一個看不見的 textarea、選取後複製)。回傳是否成功。
export async function copyText(text: string): Promise<boolean> {
  if (window.isSecureContext && navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch { /* 往下走舊式 */ }
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.position = 'fixed';
  ta.style.top = '0';
  ta.style.left = '0';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  ta.setSelectionRange(0, text.length);   // iOS Safari 要這行才選得到
  let ok = false;
  try {
    ok = document.execCommand('copy');
  } catch {
    ok = false;
  }
  document.body.removeChild(ta);
  return ok;
}
