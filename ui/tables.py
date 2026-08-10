"""純 HTML 的展示表格 —— 用來取代 st.dataframe 在部分場合的模糊問題。

**為什麼不用 st.dataframe**

st.dataframe / st.data_editor 是用 canvas 畫的(內部是 glide-data-grid),
它把畫布倍率無條件進位成整數:

    實際 DPR   畫布倍率   結果
    1 / 2 / 3    1/2/3    剛好對齊,清晰
    1.25          2       被縮到 0.625 倍 → 糊
    1.5           2       縮到 0.75 倍   → 糊
    2.5           3       縮到 0.83 倍   → 糊

Windows 的顯示縮放常是 125%/150%、Android 的 DPR 多半不是整數、
瀏覽器按過 Ctrl+= 也會變成非整數 —— 這些情況表格就會糊。
深色模式還會再對表格套 filter: invert(),又多一層合成。

HTML 表格的文字由瀏覽器直接排版,任何縮放都清晰,也不需要 invert 反白。

**取捨**:沒有排序、捲動與右上角工具列,所以只適合「短的、唯讀的」表。
長表(逐期明細那種)還是留給 st.dataframe 比較好用。
"""
from __future__ import annotations

import html
import re

import pandas as pd
import streamlit as st

# 內文裡的【NN】會被換成綠色標籤 —— 比純文字的括號好認
_HIT_RE = re.compile(r"【(\d+)】")

_CSS = """
<style>
.lt-wrap { overflow: auto; margin: .25rem 0 .75rem; }
.lt { border-collapse: collapse; width: 100%; font-size: .92rem;
      font-variant-numeric: tabular-nums; }
.lt th, .lt td { padding: .42rem .6rem; text-align: left; white-space: nowrap;
                 border-bottom: 1px solid var(--lt-line); }
.lt th { background: var(--lt-head); color: var(--lt-head-fg); font-weight: 700;
         position: sticky; top: 0; }
.lt tbody tr:nth-child(even) { background: var(--lt-zebra); }
.lt td { color: var(--lt-fg); }
/* 深色模式的全域規則會用 !important 把 markdown 內的字色統一成淺灰,
   中獎標籤要壓過它才會是綠底白字。
   不限定在 .lt 之內 —— 用欄位排出來的列(例如下注頁的預測表)也要能用。 */
.lt-hit { background: #16a34a; color: #fff !important; font-weight: 700;
          padding: 1px 6px; border-radius: 4px; }
.lt-num { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
/* 用 st.columns 排出來的表格列:表頭與分隔線 */
.lt-hd { font-weight: 700; color: var(--lt-head-fg); font-size: .88rem;
         border-bottom: 2px solid var(--lt-line); padding-bottom: .25rem; }
.lt-cell { padding: .1rem 0; color: var(--lt-fg); }
/* 附註(例如「中 2 顆」)不准被拆開換行,否則「顆」會單獨掉到下一行 */
.lt-sub { color: #64748b; font-size: .8rem; white-space: nowrap; }
/* 關鍵:Streamlit 的 st.columns 在窄螢幕會自動堆疊成直的,
   表格會整個散掉(表頭變 4 行、每筆資料再變 4 行)。這裡強制它保持橫排,
   並讓各欄可以一起壓縮而不是把版面撐爆。 */
div[class*="lt-cols"] div[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: .4rem !important;
    align-items: center;
}
div[class*="lt-cols"] div[data-testid="stColumn"] {
    min-width: 0 !important;
}
div[class*="lt-cols"] div[data-testid="stColumn"] > div { min-width: 0 !important; }
/* 手機上號碼放不下時讓它換行,但欄位本身不准掉下去 */
div[class*="lt-cols"] .lt-cell { white-space: normal; word-break: break-word; }
/* 按鈕文字要壓在一行 —— 欄窄時「帶入」會被拆成兩個直排的字。
   Streamlit 把文字包在內層的 markdown 容器裡,所以連子元素一起指定。 */
div[class*="lt-cols"] .stButton > button,
div[class*="lt-cols"] .stButton > button * {
    white-space: nowrap !important;
    word-break: keep-all !important;
}
div[class*="lt-cols"] .stButton > button {
    padding: .2rem .3rem !important;
    min-height: 0 !important;
    font-size: .82rem !important;
}
/* 桌機上別把按鈕拉成整欄那麼寬;手機維持滿寬,手指比較好點 */
div[class*="lt-cols"] .stButton { max-width: 130px; }
@media (max-width: 640px) {
  div[class*="lt-cols"] .stButton { max-width: none; }
}
@media (max-width: 640px) {
  div[class*="lt-cols"] .lt-cell, div[class*="lt-cols"] .lt-hd { font-size: .8rem; }
  .lt-hit { padding: 1px 4px; }
}
</style>
"""

_LIGHT = """
<style>:root { --lt-head:#f1f5f9; --lt-head-fg:#334155; --lt-line:#e2e8f0;
  --lt-zebra:#f8fafc; --lt-fg:#1f2937; }</style>
"""
_DARK = """
<style>:root { --lt-head:#262730; --lt-head-fg:#e8e8e8; --lt-line:#3a3f4b;
  --lt-zebra:#161a23; --lt-fg:#e8e8e8; }</style>
"""


def _inject() -> None:
    """送出樣式(每次重跑都送,Streamlit 會自行去重)。"""
    st.markdown(_CSS, unsafe_allow_html=True)
    dark = bool(st.session_state.get("dark_mode", False))
    st.markdown(_DARK if dark else _LIGHT, unsafe_allow_html=True)


def _cell(value, mono_cols: set[str], col: str) -> str:
    """一格的內容:先 escape,再把【NN】換成綠色標籤。"""
    text = "" if value is None else str(value)
    out = html.escape(text)
    out = _HIT_RE.sub(r'<span class="lt-hit">\1</span>', out)
    if col in mono_cols:
        out = f'<span class="lt-num">{out}</span>'
    return out


def inline(text: str, mono: bool = False) -> str:
    """單格用的 HTML:把【NN】換成綠色標籤,其餘 escape。

    給「用 st.columns 排出來的表格」使用 —— 那種列裡要放真的按鈕,
    沒辦法整段塞進 <table>,但號碼還是要跟表格內長得一樣。
    呼叫端記得先叫一次 ensure_css()。
    """
    out = _HIT_RE.sub(r'<span class="lt-hit">\1</span>', html.escape(str(text or "")))
    cls = "lt-cell lt-num" if mono else "lt-cell"
    return f'<span class="{cls}">{out}</span>'


def ensure_css() -> None:
    """在表格外使用 inline() 時,先送出樣式。"""
    _inject()


def cols_container(key: str):
    """回傳一個容器 —— 在它裡面用 st.columns 排的列,手機上也不會被拆成直的。

    Streamlit 的欄在窄螢幕預設會堆疊,表格會整個散掉;
    容器的 key 會變成 DOM class,上面的 CSS 靠它把橫排鎖住。
    """
    ensure_css()
    return st.container(key=f"lt-cols-{key}")


def header_row(cols, labels: list[str]) -> None:
    """畫出用 st.columns 排的表頭列。"""
    ensure_css()
    for c, text in zip(cols, labels):
        c.markdown(f'<div class="lt-hd">{html.escape(text)}</div>',
                   unsafe_allow_html=True)


def html_table(df: pd.DataFrame, mono_cols: tuple[str, ...] = (),
               max_height: int | None = None) -> None:
    """把 DataFrame 畫成純 HTML 表格。

    df         要顯示的資料(內容一律當文字處理)
    mono_cols  這些欄位用等寬字型(號碼、金額對齊比較好看)
    max_height 給長表用:超過這個高度(px)就在表格內捲動,不把頁面撐長。
               表頭是 sticky 的,捲動時仍看得到欄名。
    """
    if df is None or df.empty:
        st.caption("(沒有資料)")
        return
    _inject()
    mono = set(mono_cols)
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = []
    for _, row in df.iterrows():
        tds = "".join(f"<td>{_cell(row[c], mono, str(c))}</td>" for c in df.columns)
        body.append(f"<tr>{tds}</tr>")
    style = f' style="max-height:{int(max_height)}px"' if max_height else ""
    st.markdown(
        f'<div class="lt-wrap"{style}><table class="lt">'
        f"<thead><tr>{head}</tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table></div>',
        unsafe_allow_html=True,
    )
