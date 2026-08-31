// 週期工具:週一~週日為一週,全由日期推導(以 UTC 計算避開時區把日期挪錯天)。
// 供各分頁的「週導覽」共用:第幾週(MMDD~MMDD)、上一週/下一週。

/** YYYY-MM-DD 加 n 天,回傳 YYYY-MM-DD。 */
export const weekAddDays = (ymd: string, n: number): string => {
  const [y, m, d] = ymd.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + n);
  return dt.toISOString().slice(0, 10);
};

/** 某日期所在週的「週一」(YYYY-MM-DD);沒有合法日期回空字串(未分週)。週日歸前一個週一。 */
export const weekMonday = (raw: string): string => {
  const s = String(raw ?? '');
  if (!/^\d{4}-\d{2}-\d{2}/.test(s)) return '';
  const ymd = s.slice(0, 10);
  const [y, m, d] = ymd.split('-').map(Number);
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();  // 0=日 … 6=六
  return weekAddDays(ymd, dow === 0 ? -6 : 1 - dow);
};

/** ISO 週次(1–53):以該週週一推算。 */
export const isoWeekNo = (monday: string): number => {
  if (!monday) return 0;
  const [y, m, d] = monday.split('-').map(Number);
  const th = new Date(Date.UTC(y, m - 1, d));
  th.setUTCDate(th.getUTCDate() + 3);                       // 該週的星期四
  const firstTh = new Date(Date.UTC(th.getUTCFullYear(), 0, 4));
  const fDow = (firstTh.getUTCDay() + 6) % 7;               // 週一=0
  firstTh.setUTCDate(firstTh.getUTCDate() - fDow + 3);      // 首週的星期四
  return 1 + Math.round((th.getTime() - firstTh.getTime()) / (7 * 86400000));
};

/** MMDD(去掉年份與分隔號),例:2026-08-24 → 0824。 */
const mmdd = (ymd: string): string => ymd.slice(5).replace('-', '');

/** 「第 N 週(0824~0830)」;無日期回「未分週」。 */
export const weekRangeLabel = (monday: string): string =>
  monday
    ? `第 ${isoWeekNo(monday)} 週(${mmdd(monday)}~${mmdd(weekAddDays(monday, 6))})`
    : '未分週';

/** 從一堆紀錄(帶 date)取出出現過的週一清單,新→舊排序(未分週的空字串排最後)。 */
export const distinctWeeks = (dates: string[]): string[] => {
  const set = new Set<string>();
  for (const d of dates) set.add(weekMonday(d));
  return Array.from(set).sort((a, b) => (a && b ? b.localeCompare(a) : a ? -1 : 1));
};
