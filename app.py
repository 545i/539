"""彩券統計分析 Streamlit Web 應用(今彩539 / 天天樂 / 六合彩)。

沒有全域的「遊戲模式」:三款的開獎資料一律同時維護,
二合買牌(策略1)三款共用同一個損益池,統計分析則在頁內切換要看哪一款。

重要提醒(與 core 模組一致):每期開獎為獨立隨機事件,數學上無法預測,
長期期望報酬率為負。本工具僅供統計學習與娛樂用途。
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from core import (auth, backtest, binary_wide, constants, erhe, excel_report,
                  games, kelly, picker)
from core import autoupdate, scraper, scraper_fantasy5, scraper_marksix, stats, storage
from core import checker, predictor
from core.loader import DataError, load_history, merge, save
from ui import docs, numpad, tables


def _writable_base() -> Path:
    """可寫入資料的根目錄。

    PyInstaller 打包成單一 exe 後,__file__ 指向會被刪除的暫存解壓目錄;
    frozen 模式改用 exe 所在資料夾,讓 data/history.csv 持久保存在 exe 旁邊。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _bundle_base() -> Path:
    """唯讀資源(隨 exe 打包)的根目錄:frozen 時為 _MEIPASS,否則同專案目錄。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", _writable_base()))
    return Path(__file__).resolve().parent


# ── 導覽(不再有全域遊戲切換)──────────────────────────────
NAV_ITEMS = ["二合買牌", "統計分析", "匯出", "排行榜", "設定"]


# ── 資料路徑與載入(依遊戲分檔)────────────────────────────
DATA_DIR = _writable_base() / "data"
_BUNDLE_DIR = _bundle_base() / "data"


def game_data_path(game) -> Path:
    """某遊戲歷史資料的可寫入路徑(exe 旁邊)。"""
    return DATA_DIR / game.data_file


@st.cache_data(show_spinner=False)
def load_df(game_key: str) -> pd.DataFrame:
    """讀取指定遊戲的歷史開獎資料。

    順序:exe 旁邊的 data/<檔> → 打包內附的種子資料 → 產生範例資料。
    以 game_key(字串)當 cache key,讓各遊戲資料各自快取、互不干擾。
    """
    game = games.get(game_key)
    path = DATA_DIR / game.data_file
    bundled = _BUNDLE_DIR / game.data_file
    # 首次執行(exe 旁無資料)時,把打包內附的歷史資料複製出來(純位元組,避開 CopyFile2)。
    if not path.exists() and bundled.exists() and bundled != path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bundled.read_bytes())
    try:
        return load_history(path, game.pick, game.num_max)
    except DataError:
        df = generate_sample_safe(game)
        save(df, path)
        return df


def generate_sample_safe(game=None) -> pd.DataFrame:
    """產生固定 seed 的範例資料(避開系統時鐘),號碼規格依所選遊戲。"""
    from core.loader import generate_sample

    game = game or games.DEFAULT_GAME
    return generate_sample(500, pick=game.pick, num_max=game.num_max)


# ── 通用小工具 ────────────────────────────────────────────
def _date_str(ts) -> str:
    """把日期轉成 YYYY-MM-DD 字串。"""
    return pd.to_datetime(ts).strftime("%Y-%m-%d")


def _range_label(fdf: pd.DataFrame) -> str:
    """產生「目前 X 期(最早 ~ 最新)」說明文字。"""
    if fdf.empty:
        return "目前 0 期(無資料)"
    s = fdf.sort_values("date")
    return f"目前 {len(s)} 期({_date_str(s['date'].iloc[0])} ~ {_date_str(s['date'].iloc[-1])})"


# ── 側邊欄:遊戲選擇 + 全域範圍選擇 + 導覽 ────────────────
_DARK_CSS = """
<style>
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], section.main {
  background-color: #0e1117 !important; }
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
  background-color: #1b1f27 !important; }
/* 文字一律變白 */
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp p, .stApp li, .stApp label, .stApp span,
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] *,
[data-testid="stWidgetLabel"] *, [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
[data-testid="stCaptionContainer"], button[data-baseweb="tab"],
section[data-testid="stSidebar"] * { color: #e8e8e8 !important; }
/* 按鈕變深 */
.stButton button, [data-testid="stBaseButton-secondary"], [data-testid="baseButton-secondary"] {
  background-color: #262730 !important; color: #e8e8e8 !important; border: 1px solid #3a3f4b !important; }
/* 輸入框 / 下拉變深 */
input, textarea, [data-baseweb="input"], [data-baseweb="base-input"],
[data-baseweb="select"] > div, [data-testid="stNumberInputContainer"] {
  background-color: #262730 !important; color: #e8e8e8 !important; }
/* alert(info/warning/error/success)維持深字以保可讀 */
[data-testid="stAlert"], [data-testid="stAlert"] * { color: #11151c !important; }
/* 表格反白 */
[data-testid="stDataFrame"], [data-testid="stTable"] {
  filter: invert(0.92) hue-rotate(180deg); }
</style>
"""


_MOBILE_CSS = """
<style>
/* 手機:橫向欄位自動換行成兩欄,不要硬擠成一條而把數字折成好幾行 */
@media (max-width: 640px) {
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    gap: 0.35rem !important;
  }
  [data-testid="stColumn"] {
    flex: 1 1 calc(50% - 0.35rem) !important;
    min-width: calc(50% - 0.35rem) !important;
  }
  /* 指標:字縮小且不折行 */
  [data-testid="stMetric"] {
    padding: 0.35rem 0.5rem !important;
    border: 1px solid rgba(128,128,128,0.22);
    border-radius: 8px;
  }
  [data-testid="stMetricValue"] {
    font-size: 1.15rem !important; white-space: nowrap !important; }
  [data-testid="stMetricLabel"] p { font-size: 0.78rem !important; }
  [data-testid="stMetricDelta"] { font-size: 0.72rem !important; }
  [data-testid="stMetricDelta"] div { white-space: nowrap !important; }

  /* 指標列是要「一眼橫向比較」的,所以強迫並排:寧可縮字也不換行。
     字級用 vw 讓它跟著螢幕寬縮放,窄機也塞得下 4~5 欄。 */
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
    flex-wrap: nowrap !important;
    gap: 0.2rem !important;
  }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    width: auto !important;
  }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetric"] {
    padding: 0.3rem 0.25rem !important;
  }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricValue"] {
    font-size: clamp(0.6rem, 3.4vw, 1.15rem) !important;
    line-height: 1.25 !important;
    overflow: hidden !important;
  }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricLabel"] p {
    font-size: clamp(0.5rem, 2.3vw, 0.78rem) !important;
    line-height: 1.2 !important;
    white-space: normal !important;
  }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricDelta"] {
    font-size: clamp(0.45rem, 2vw, 0.72rem) !important;
    padding: 0 !important;
  }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricDelta"] svg {
    width: 0.9em !important; height: 0.9em !important;
  }
  /* delta 的字被 .stApp p 的 16px !important 蓋掉,而且自帶 nowrap + ellipsis,
     所以要直接指到 p 上,並解掉截字才不會出現「中獎 0(…」。 */
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricDelta"] div,
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) [data-testid="stMetricDelta"] p {
    font-size: clamp(0.45rem, 2vw, 0.72rem) !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    line-height: 1.2 !important;
  }

  html, body, .stApp, .stMarkdown, .stApp p, .stApp li { font-size: 16px !important; }
  .block-container { padding: 2.6rem 0.5rem 1rem 0.5rem !important; }
  [data-testid="stDataFrame"], [data-testid="stTable"] { font-size: 14px !important; }
  button[data-baseweb="tab"] { font-size: 0.9rem !important; padding: 0.3rem 0.5rem !important; }
  h1 { font-size: 1.5rem !important; } h2 { font-size: 1.25rem !important; }
  h3 { font-size: 1.08rem !important; }
  .stButton button { font-size: 1rem !important; padding: 0.5rem !important; }
  /* 說明類文字收小,別佔掉半個畫面 */
  [data-testid="stCaptionContainer"] p { font-size: 0.78rem !important; line-height: 1.45 !important; }
  [data-testid="stAlert"] p { font-size: 0.82rem !important; line-height: 1.5 !important; }
  /* 折疊標題壓扁一點 */
  [data-testid="stExpander"] summary { padding: 0.3rem 0.6rem !important; }
}
</style>
"""


def _note(text: str, title: str = "說明", expanded: bool = False):
    """把長段說明收進折疊區 —— 手機上不佔版面,想看再點開。"""
    with st.expander(title, expanded=expanded):
        st.markdown(text)


def _apply_theme():
    """套用主題:預設亮色(原生);深色模式開關;手機放大字級。"""
    import plotly.io as pio

    st.markdown(_MOBILE_CSS, unsafe_allow_html=True)  # 手機放大,永遠套用
    _numeric_keyboard()                               # 手機的數字欄位跳數字鍵盤
    dark = st.sidebar.toggle("深色模式", value=False, key="dark_mode")
    pio.templates.default = "plotly_dark" if dark else "plotly_white"
    if dark:
        st.markdown(_DARK_CSS, unsafe_allow_html=True)


def sidebar_controls() -> str:
    """繪製側邊欄(不再有全域遊戲切換),回傳目前的導覽選項。"""
    st.sidebar.title("彩券統計分析")
    user = st.session_state.get("user", "")
    if user:
        uc1, uc2 = st.sidebar.columns([2, 1])
        uc1.caption(f"{user}")
        uc2.button("登出", key="logout_btn", on_click=_logout)
    _apply_theme()

    st.sidebar.markdown("### 導覽")
    nav = st.sidebar.radio(
        "功能選單", NAV_ITEMS, key="nav", label_visibility="collapsed",
        on_change=lambda: st.session_state.update(show_docs=False),
    )

    # 三款開獎資料一律同時維護,這裡顯示各自的期數與最新日期
    st.sidebar.markdown("### 開獎資料")
    for g in games.GAMES.values():
        d = load_df(g.key)
        latest = _date_str(d["date"].max()) if not d.empty else "無資料"
        st.sidebar.caption(f"{g.name} — {len(d)} 期,最新 {latest}")

    with st.sidebar.expander("免責聲明(必讀)", expanded=False):
        st.write(constants.DISCLAIMER)
        for g in games.GAMES.values():
            st.caption(f"**{g.name}**({g.num_max}選{g.pick}):{g.prize_note}")
            st.caption(f"　來源:{g.source_note}")

    # 說明 / 算式按鈕:供他人研究與驗算所有統計與凱莉公式
    st.sidebar.button(
        "說明 / 算式(供驗算)",
        width="stretch",
        on_click=lambda: st.session_state.update(show_docs=True),
        help="列出所有統計算式與凱莉公式,連同實際常數值供研究驗算。",
    )
    return nav


_N_PRESETS = (30, 50, 100, 200, 500, 1000)


def _apply_preset(pkey: str, skey: str):
    """點了常用期數 → 把滑桿設到該值(on_change 會在重跑前先執行)。"""
    v = st.session_state.get(pkey)
    if v is not None:
        st.session_state[skey] = int(v)


def _recent_n(key: str, total: int) -> int:
    """最近 N 期:滑桿 + 常用期數快捷選項,回傳要取幾期。

    滑桿拖一下就換區間,不必像 number_input 那樣一格一格點或打字;
    常用期數用 pills 排成一列,手機上不會被撐成好幾列按鈕。
    """
    skey = f"{key}_n"
    if total <= 1:
        return total
    # 值一律走 session_state:快捷選項要能改它,而同時傳 value= 會被 Streamlit 警告。
    # 換遊戲時總期數會變(539 八百多期、天天樂三千多期),舊值要夾回合法範圍,
    # 否則 slider 會因為值超出 max 而報錯。
    cur = min(max(1, int(st.session_state.get(skey, min(100, total)))), total)
    st.session_state[skey] = cur

    presets = [p for p in _N_PRESETS if p < total] + [total]
    # 選中狀態跟著滑桿走:剛好停在某個常用值就亮起來,自己拖到別的值就都不亮
    pkey = f"{key}_preset"
    st.session_state[pkey] = cur if cur in presets else None
    st.pills(
        "常用期數", presets, key=pkey, label_visibility="collapsed",
        format_func=lambda p: "全部" if p == total else str(p),
        on_change=_apply_preset, args=(pkey, skey),
    )
    return int(st.slider("最近期數", min_value=1, max_value=total, step=1, key=skey,
                         help="往右拖看更長期間;最右邊就是全部資料。"))


def _range_selector(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """頁內的分析範圍選擇(全部 / 最近 N 期 / 日期範圍),回傳篩選後資料。"""
    sorted_df = df.sort_values("date").reset_index(drop=True)
    if sorted_df.empty:
        return sorted_df
    c1, c2 = st.columns([1, 2])
    mode = c1.radio("分析範圍", ["全部", "最近 N 期", "日期範圍"], key=f"{key}_mode")
    with c2:
        if mode == "最近 N 期":
            fdf = sorted_df.tail(_recent_n(key, len(sorted_df)))
        elif mode == "日期範圍":
            dmin = sorted_df["date"].iloc[0].date()
            dmax = sorted_df["date"].iloc[-1].date()
            d1, d2 = st.columns(2)
            start = d1.date_input("起始日", value=dmin, min_value=dmin, max_value=dmax,
                                  key=f"{key}_s")
            end = d2.date_input("結束日", value=dmax, min_value=dmin, max_value=dmax,
                                key=f"{key}_e")
            lo, hi = (start, end) if start <= end else (end, start)
            mask = (sorted_df["date"].dt.date >= lo) & (sorted_df["date"].dt.date <= hi)
            fdf = sorted_df.loc[mask]
        else:
            fdf = sorted_df
    fdf = fdf.reset_index(drop=True)
    st.caption(_range_label(fdf))
    return fdf


# ── 1. 統計分析 ───────────────────────────────────────────
def page_stats():
    """統計分析:三款資料都在,頁內選要看哪一款(號碼統計本來就只能一次看一款)。"""
    st.header("統計分析")
    gkey = st.segmented_control(
        "看哪一款", [g.key for g in games.GAMES.values()],
        default=games.DEFAULT_GAME.key,
        format_func=lambda k: games.get(k).name,
        key="stats_game",
    ) or games.DEFAULT_GAME.key
    game = games.get(gkey)
    fdf = _range_selector(load_df(gkey), f"stats_{gkey}")
    _render_stats(fdf, game)


def _render_stats(fdf: pd.DataFrame, game):
    nmax = game.num_max
    n_bands = len(stats.tens_bands(nmax))
    st.subheader(game.name)
    st.caption(f"玩法規格:{nmax} 選 {game.pick};以下統計皆依此規格計算。")
    if fdf.empty:
        st.warning("目前範圍沒有資料,請調整側邊欄的範圍選擇。")
        return

    tabs = st.tabs(
        ["號碼頻率", "冷熱號", "遺漏值", "間隔/連號", "奇偶/大小/和值",
         f"星數統計({n_bands}興)", "卡方檢定", "共現配對", "🎯 預測比對"]
    )

    # 號碼頻率
    with tabs[0]:
        freq = stats.frequency(fdf, nmax)
        fdf_freq = pd.DataFrame({"號碼": list(freq.keys()), "出現次數": list(freq.values())})
        fig = px.bar(fdf_freq, x="號碼", y="出現次數", title="各號碼出現次數")
        st.plotly_chart(fig, theme=None, width='stretch')
        ranked = stats.frequency_ranked(fdf, nmax)[:10]
        st.subheader("出現次數 Top10")
        st.dataframe(
            pd.DataFrame(ranked, columns=["號碼", "出現次數"]),
            width='stretch', hide_index=True,
        )

    # 冷熱號
    with tabs[1]:
        hot, cold = stats.hot_cold(fdf, window=30, num_max=nmax)
        st.caption("以最近 30 期計算。")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("熱號(最常出)")
            st.dataframe(
                pd.DataFrame(hot, columns=["號碼", "近30期次數"]),
                width='stretch', hide_index=True,
            )
        with c2:
            st.subheader("冷號(最少出)")
            st.dataframe(
                pd.DataFrame(cold, columns=["號碼", "近30期次數"]),
                width='stretch', hide_index=True,
            )

    # 遺漏值
    with tabs[2]:
        miss = stats.missing(fdf, nmax)
        rows = [
            {"號碼": n, "目前遺漏": v["current"], "歷史最大遺漏": v["max_gap"]}
            for n, v in miss.items()
        ]
        miss_df = pd.DataFrame(rows).sort_values("目前遺漏", ascending=False).head(10)
        st.subheader("遺漏最久 Top10")
        st.dataframe(miss_df, width='stretch', hide_index=True)

    # 間隔 / 連號
    with tabs[3]:
        gaps, ratio = stats.gaps_consecutive(fdf)
        gap_df = pd.DataFrame({"相鄰間隔": list(gaps.keys()), "次數": list(gaps.values())})
        fig = px.bar(gap_df, x="相鄰間隔", y="次數", title="相鄰號碼間隔分布")
        st.plotly_chart(fig, theme=None, width='stretch')
        st.metric("含連號(相鄰差=1)的期數比例", f"{ratio:.1%}")

    # 奇偶 / 大小 / 和值
    with tabs[4]:
        split = stats.size_split(nmax)
        odd, big, sums = stats.parity_size_sum(fdf, nmax)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("每期奇數個數分布")
            st.dataframe(
                pd.DataFrame({"奇數個數": list(odd.keys()), "次數": list(odd.values())}),
                width='stretch', hide_index=True,
            )
        with c2:
            st.subheader(f"每期大數(>={split})個數分布")
            st.dataframe(
                pd.DataFrame({"大數個數": list(big.keys()), "次數": list(big.values())}),
                width='stretch', hide_index=True,
            )
        st.subheader(f"每期 {game.pick} 號總和分布")
        sum_fig = px.histogram(pd.DataFrame({"和值": sums}), x="和值", nbins=30, title="和值直方圖")
        st.plotly_chart(sum_fig, theme=None, width='stretch')

    # 星數統計(俗稱 4 興:依十位分成 01~09 / 10~19 / 20~29 / 30~39 四組)
    with tabs[5]:
        bands = stats.tens_bands(nmax)
        _note(
            f"星數 = 每期開出的 {game.pick} 顆落在「幾個不同的十位區段」"
            f"({' / '.join(bands)})。同一段內重複(如 10、11 都在 10~19)只算 1 星,"
            f"所以星數介於 1~{n_bands} 星。")
        star_dist, band_totals, pattern_dist = stats.tens_band_stats(fdf, nmax)
        n_draws = len(fdf)

        # 主角:星數分布(1~4 星各幾期)
        star_df = pd.DataFrame(
            {
                "星數": [f"{s} 星" for s in star_dist.keys()],
                "出現期數": list(star_dist.values()),
            }
        )
        star_df["歷史比例"] = (
            (star_df["出現期數"] / n_draws).map(lambda x: f"{x:.1%}") if n_draws else "—"
        )
        fig_star = px.bar(
            star_df, x="星數", y="出現期數", title="每期星數分布(落在幾個不同區段)",
            text="出現期數",
        )
        st.plotly_chart(fig_star, theme=None, width="stretch")
        st.dataframe(star_df, width="stretch", hide_index=True)
        st.caption(
            f"{game.pick} 顆分到 {n_bands} 個區段,最常見是分散的高星數;"
            f"1 星({game.pick} 顆全擠同一段)極罕見。"
        )

        # 補充1:各組號碼出現總次數
        with st.expander("各區段號碼出現總次數"):
            band_df = pd.DataFrame(
                {
                    "區段": list(band_totals.keys()),
                    "出現總次數": list(band_totals.values()),
                }
            )
            band_df["每期平均顆數"] = (
                (band_df["出現總次數"] / n_draws).round(2) if n_draws else 0
            )
            st.dataframe(band_df, width="stretch", hide_index=True)
            st.caption("01~09 只有 9 個號碼、其餘各 10 個,故 01~09 略少屬正常。")

        # 補充2:牌型分布(每期號碼落在各組各幾顆,如 1-2-1-1)
        with st.expander(f"位數分布牌型({n_bands}組各幾顆)Top15"):
            pat_rows = [
                {f"牌型({n_bands}組顆數)": pat, "出現次數": cnt, "歷史比例": f"{ratio:.1%}"}
                for pat, cnt, ratio in pattern_dist[:15]
            ]
            st.dataframe(pd.DataFrame(pat_rows), width="stretch", hide_index=True)

        st.error(
            "誠實提醒:這是「描述過去」的星數分布,不是「預測未來」。每期開獎獨立隨機,"
            "歷史最常出現的星數,下一期出現的機率並不會比較高。"
        )

    # 卡方檢定
    with tabs[6]:
        chi = stats.chi_square(fdf, nmax)
        chi_df = pd.DataFrame(
            {
                "項目": ["卡方統計量", "p 值", "自由度", "每號期望次數", "資料是否足夠"],
                "數值": [
                    f"{chi.statistic:.4f}",
                    f"{chi.p_value:.4f}",
                    str(chi.dof),
                    f"{chi.expected_per_num:.2f}",
                    "是" if chi.enough_data else "否",
                ],
            }
        )
        st.dataframe(chi_df, width='stretch', hide_index=True)
        st.warning(chi.conclusion)

    # 共現配對
    with tabs[7]:
        pairs = stats.top_pairs(fdf, 10)
        pair_rows = [
            {"配對": f"{a} - {b}", "一起出現次數": cnt} for (a, b), cnt in pairs
        ]
        st.subheader("最常一起出現的配對 Top10")
        st.dataframe(pd.DataFrame(pair_rows), width='stretch', hide_index=True)

    # 預測比對:每期存下各策略的預測,開獎後自動比對
    with tabs[8]:
        _render_prediction(game)


def _render_prediction(game):
    """預測比對:先把各策略的預測存下來,開獎後自動比對中幾顆。

    刻意用完整歷史(load_df)而不是側邊欄過濾後的 fdf —— 預測要看得到
    目標期之前的所有資料,比對也得查得到當期開獎號。
    """
    df = load_df(game.key)
    st.subheader("🎯 預測比對")
    st.caption(
        "在開獎前把各策略選的號碼存下來,開獎後自動比對中了幾顆。"
        "預測只吃得到目標期**之前**的資料,一旦存下就不會被覆蓋。"
    )
    st.warning(
        "所有策略的期望中獎率完全相同 —— 下面的排行只是把運氣視覺化,"
        "**不代表哪個策略比較會中**。理性娛樂、量力而為。"
    )

    c1, c2 = st.columns([1, 2])
    target = c1.date_input(
        "目標期(要預測哪一天的開獎)", value=predictor.next_target(df),
        format="YYYY-MM-DD", key=f"pred_date_{game.key}",
    )
    issue = predictor.issue_of(df, target)
    c2.markdown(
        f"　\n期別:**{predictor.period_label(target, issue)}**"
        + ("" if issue else "　<small>(這一款沒有期號,用日期辨識)</small>"),
        unsafe_allow_html=True,
    )

    if st.button("產生各策略預測並存檔", type="primary", key=f"pred_gen_{game.key}"):
        added, rows = predictor.save_for(df, game.key, target)
        if not rows:
            st.error("目標期之前沒有資料可以算,請往後選一天。")
        elif added:
            st.success(f"已存下 {added} 個策略對 {target} 的預測。")
        else:
            st.info("這一期先前已經存過了 —— 預測不會被覆蓋,以保留當初的判斷。")

    evaluated = predictor.evaluate(df, game.key)
    if not evaluated:
        st.info("還沒有任何預測紀錄。選好目標期後按上面的按鈕存第一筆。")
        return

    # ── 本期 ──
    tstr = target.isoformat() if hasattr(target, "isoformat") else str(target)
    cur = [r for r in evaluated if r["target_date"] == tstr]
    if cur:
        st.markdown(f"**這一期({predictor.period_label(tstr, cur[0].get('issue'))})的預測**")
        if cur[0]["pending"]:
            st.caption("⏳ 還沒開獎(或開獎資料還沒抓到),開出來後這裡會自動比對。")
        else:
            st.caption(f"開獎號碼:{'  '.join(f'{n:02d}' for n in cur[0]['drawn'])}")
        tables.html_table(pd.DataFrame([{
            "策略": picker.label(r["strategy"]),
            "預測號碼": predictor.marked(r["numbers"], set(r["matched"])),
            "中幾顆": "待開獎" if r["pending"] else f"{r['hits']} 顆",
            "存檔時間": r["created_at"],
        } for r in cur]), mono_cols=("預測號碼",))
        if st.button("刪掉這一期的預測", key=f"pred_del_{game.key}",
                     help="期別選錯時用;刪掉後可以重新產生。"):
            storage.delete_predictions(game.key, tstr)
            st.rerun()
        st.divider()

    # ── 策略排行 ──
    rank = predictor.ranking(evaluated)
    if rank:
        st.markdown("**策略累計戰績**(只計已開獎的期)")
        medals = ["🥇", "🥈", "🥉"]
        tables.html_table(pd.DataFrame([{
            "名次": medals[i] if i < len(medals) else f"第 {i + 1} 名",
            "策略": r["label"],
            "期數": r["periods"],
            "總命中": f"{r['total_hits']} 顆",
            "平均每期": f"{r['avg']:.2f} 顆",
            "單期最佳": f"{r['best']} 顆",
        } for i, r in enumerate(rank)]), mono_cols=("平均每期",))
        st.caption(
            f"參考基準:每期開 {game.pick} 顆、{game.num_max} 選 {game.pick},"
            f"隨便選 {game.pick} 顆的期望命中是 "
            f"{game.pick * game.pick / game.num_max:.2f} 顆。"
        )
        st.divider()

    # ── 逐期明細 ──
    st.markdown("**逐期明細**")
    tables.html_table(pd.DataFrame([{
        "期別": r["label"],
        "策略": picker.label(r["strategy"]),
        "預測號碼": predictor.marked(r["numbers"], set(r["matched"])),
        "中幾顆": "待開獎" if r["pending"] else f"{r['hits']} 顆",
    } for r in evaluated]), mono_cols=("預測號碼",), max_height=420)


# ── 2. 產生參考號碼 ───────────────────────────────────────
def page_picker(fdf: pd.DataFrame, game):
    st.header(f"產生參考號碼 — {game.name}")
    if fdf.empty:
        st.warning("目前範圍沒有資料,請調整側邊欄的範圍選擇。")
        return

    strategy = st.selectbox(
        "選號策略", picker.STRATEGIES, format_func=picker.label
    )
    sets = st.slider("組數", min_value=1, max_value=20, value=5)

    st.warning(
        "提醒:所有策略的期望中獎率完全相同,長期期望報酬率約 "
        f"{game.expected_return():.0%},差異只是運氣。請理性娛樂、量力而為。"
    )

    if st.button("產生號碼", type="primary"):
        # 環境停用系統時鐘,使用固定 seed 確保可重現
        result = picker.pick(fdf, strategy=strategy, sets=int(sets), seed=539)
        rows = [
            {"組別": i + 1, "號碼": "  ".join(f"{n:02d}" for n in nums)}
            for i, nums in enumerate(result)
        ]
        st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)


# ── 3. 策略回測 ───────────────────────────────────────────
def page_backtest(fdf: pd.DataFrame, game):
    st.header(f"策略回測 — {game.name}")
    if len(fdf) < 4:
        st.warning("資料太少,無法回測。請擴大側邊欄的範圍選擇。")
        return

    st.caption("防 look-ahead bias:選第 N 期號碼時只用第 N 期之前的資料。")

    if st.button("執行回測", type="primary"):
        start_index = min(100, len(fdf) // 2)
        with st.spinner("回測中,請稍候…"):
            results = backtest.compare(
                fdf, picker.STRATEGIES, start_index=start_index, game=game
            )
        st.session_state["backtest_results"] = results

    results = st.session_state.get("backtest_results")
    if not results:
        st.info("點擊上方按鈕開始回測。")
        return

    rows = [
        {
            "策略": picker.label(r.strategy),
            "回測期數": r.periods,
            "總投注(NT$)": r.total_bet,
            "總回收(NT$)": r.total_return,
            "報酬率%": round(r.roi * 100, 2),
        }
        for r in results
    ]
    res_df = pd.DataFrame(rows)
    st.dataframe(res_df, width='stretch', hide_index=True)

    fig = px.bar(
        res_df, x="策略", y="報酬率%", title="各策略 ROI%",
        color="報酬率%", color_continuous_scale=["#e63946", "#457b9d"],
    )
    st.plotly_chart(fig, theme=None, width='stretch')

    st.warning(
        f"結果說明:無論哪種策略,長期報酬率都收斂到約 {game.expected_return():.0%},"
        f"沒有任何策略能贏過隨機。這正說明 {game.name} 無法被預測。"
    )


# ── 4. 凱莉投報計算 ───────────────────────────────────────
def page_kelly(game):
    st.header(f"凱莉投報計算 — {game.name}")
    result = kelly.analyze(game)

    c1, c2, c3 = st.columns(3)
    c1.metric("期望報酬率", f"{result.ev_return_rate:.2%}")
    c2.metric("最佳投注比例", f"{result.fraction:.2%}")
    c3.metric(f"每注期望淨利({game.currency})", f"{result.ev_per_bet:.4f}")

    c4, c5 = st.columns(2)
    c4.metric("理論凱莉比例 f*", f"{result.raw_fraction:.4f}")
    c5.metric("對數成長率", f"{result.growth_rate:.4f}")

    st.error(f"凱莉公式算出最佳投注比例為 0%,因為 {game.name} 的期望值(EV)為負。")
    st.warning(result.recommendation)

    st.subheader("互動資金模擬")
    st.caption("示範持續下注時資金長期下滑(對照「完全不下注」)。")
    rounds = st.slider("模擬輪數", min_value=100, max_value=5000, value=1000, step=100)
    assume_pct = st.slider("假設下注比例%", min_value=1, max_value=50, value=10)

    outcomes = kelly.outcomes_for(game)
    no_bet = kelly.simulate_bankroll(0.0, outcomes, rounds=int(rounds))
    with_bet = kelly.simulate_bankroll(
        assume_pct / 100.0, outcomes, rounds=int(rounds)
    )
    chart_df = pd.DataFrame(
        {
            "完全不下注(0%)": no_bet,
            f"假設下注 {assume_pct}%": with_bet,
        }
    )
    st.line_chart(chart_df)


# ── 5. 更新資料 ───────────────────────────────────────────
def _parse_ym(text: str) -> tuple[int, int]:
    """解析 YYYY-MM 字串為 (year, month)。"""
    parts = text.strip().split("-")
    if len(parts) != 2:
        raise ValueError("格式需為 YYYY-MM")
    return int(parts[0]), int(parts[1])


def _update_one_game(game):
    """單一遊戲的抓取 / 匯出區塊(三款各一段)。"""
    path = game_data_path(game)
    df = load_df(game.key)
    latest = _date_str(df["date"].max()) if not df.empty else "無資料"
    st.markdown(f"**{game.name}** — {game.num_max}選{game.pick}|"
                f"目前 {len(df)} 期,最新 {latest}")
    st.caption(f"來源:{game.source_note}")

    c1, c2 = st.columns([2, 1])
    with c2:
        st.download_button(
            f"匯出 CSV({len(df)} 期)",
            data=df.sort_values("date").to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{game.key}_history.csv", mime="text/csv",
            width="stretch", key=f"dl_{game.key}",
        )

    with c1:
        if game.key == "fantasy5":
            pages = st.slider("抓取頁數(每頁約 50 期)", 1, 60, 40, key=f"pg_{game.key}")
            if st.button("抓取並更新", type="primary", key=f"go_{game.key}"):
                _fetch_and_merge(
                    game, df, path,
                    lambda: scraper_fantasy5.fetch_history(pages=int(pages)),
                    scraper_fantasy5.ScrapeError, f"最近約 {pages * 50} 期")
        elif game.key == "marksix":
            pages = st.slider("抓取頁數(每頁約 23 期)", 1, 146, 5, key=f"pg_{game.key}")
            if st.button("抓取並更新", type="primary", key=f"go_{game.key}"):
                _fetch_and_merge(
                    game, df, path,
                    lambda: scraper_marksix.fetch_history(pages=int(pages)),
                    scraper_marksix.ScrapeError, f"最近約 {pages * 23} 期")
        else:  # 今彩539:台灣彩券官方 API,依月份抓
            d1, d2 = st.columns(2)
            start_ym = d1.text_input("起始月份(YYYY-MM)", value="2026-01",
                                     key=f"s_{game.key}")
            end_ym = d2.text_input("結束月份(YYYY-MM)", value="2026-07",
                                   key=f"e_{game.key}")
            if st.button("抓取並更新", type="primary", key=f"go_{game.key}"):
                def _fetch539():
                    rows, failures = scraper.fetch_range(_parse_ym(start_ym),
                                                         _parse_ym(end_ym))
                    if failures:
                        st.warning("以下月份抓取失敗:\n" + "\n".join(
                            f"- {y}-{m:02d}: {msg}" for y, m, msg in failures))
                    return rows
                _fetch_and_merge(game, df, path, _fetch539,
                                 (scraper.ScrapeError, ValueError),
                                 f"{start_ym} ~ {end_ym}")


def _fetch_and_merge(game, df, path, fetch, err_types, what: str):
    """共用的抓取 → 合併 → 存檔流程。"""
    try:
        with st.spinner(f"抓取 {game.name} {what} 中…"):
            new_rows = fetch()
        merged = merge(df, new_rows)
        save(merged, path)
        added = len(merged) - len(df)
        st.success(f"{game.name} 已更新:抓到 {len(new_rows)} 期、新增 {added} 期,"
                   f"目前共 {len(merged)} 期。")
        st.cache_data.clear()
        st.info("資料已更新,請重新整理頁面(F5)以套用。")
    except err_types as e:
        st.error(f"{game.name} 更新失敗:{e}")


# ── 6. 匯出 ───────────────────────────────────────────────
_FMT_REPORT = "一般報表(Excel)"
_FMT_WIDE = "二元虛擬變數寬表(CSV)"


def page_export():
    """匯出頁:選遊戲 → 選範圍 → 選格式。"""
    st.header("匯出")
    gkey = st.segmented_control(
        "匯出哪一款", [g.key for g in games.GAMES.values()],
        default=games.DEFAULT_GAME.key,
        format_func=lambda k: games.get(k).name,
        key="export_game",
    ) or games.DEFAULT_GAME.key
    game = games.get(gkey)
    fdf = _range_selector(load_df(gkey), f"export_{gkey}")

    st.subheader(game.name)
    if fdf.empty:
        st.warning("目前範圍沒有資料,無法匯出。")
        return

    fmt = st.radio("匯出格式", [_FMT_REPORT, _FMT_WIDE], horizontal=True,
                   key="export_fmt")
    st.caption(f"匯出的是上面選的範圍,目前 {len(fdf)} 期({_range_label(fdf)})。")

    if fmt == _FMT_WIDE:
        _export_binary_wide(fdf, game)
    else:
        _export_excel_report(fdf, game)


def _export_excel_report(fdf: pd.DataFrame, game):
    st.markdown(
        """
        匯出的 Excel 報表包含以下工作表:
        - 免責聲明(含本遊戲票價/期望報酬/資料來源)
        - 開獎資料
        - 號碼頻率(含原生長條圖)
        - 回測結果(若已執行回測)
        - 凱莉投報分析
        """
    )

    backtest_results = st.session_state.get("backtest_results")
    if backtest_results:
        st.caption("已偵測到回測結果,將一併寫入報表。")
    else:
        st.caption("尚未執行回測;報表將不含回測工作表(可先到「策略回測」執行)。")

    data = excel_report.build_report_bytes(
        fdf,
        backtest_results=backtest_results,
        kelly_result=kelly.analyze(game),
        game=game,
    )
    st.download_button(
        label="下載 Excel 報表",
        data=data,
        file_name=f"{game.key}_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _export_binary_wide(fdf: pd.DataFrame, game):
    """統計軟體用的寬表:每期一列,開出的號碼記 1、沒開出記 0。"""
    wide = binary_wide.to_binary_wide(fdf, game)
    n_cols = game.num_max
    st.markdown(
        f"""
        每一期是一筆觀察值(一列),欄位為:
        - **期數**:依日期排序的流水序號(資料源沒有官方期別編號)
        - **日期**:YYYY-MM-DD
        - **Num_01 … Num_{n_cols:02d}**:當期開出該號碼記 1,沒開出記 0

        {game.name} 是 **{n_cols} 選 {game.pick}**,所以有 {n_cols} 個號碼欄、
        每列剛好 {game.pick} 個 1。編碼為 utf-8-sig,Excel 直接開不會亂碼。
        """
    )
    st.caption(f"共 {len(wide)} 列 × {len(wide.columns)} 欄。下面是前 5 期的前幾欄:")
    st.dataframe(wide.head(5).iloc[:, :10], width="stretch", hide_index=True)

    st.download_button(
        label="下載寬表 CSV",
        data=binary_wide.to_csv_bytes(fdf, game),
        file_name=f"{game.key}_binary_wide.csv",
        mime="text/csv",
    )


# ── 包牌 / 牌型 / 加碼 ───────────────────────────────────
def page_wheel(fdf: pd.DataFrame, game):
    from core import wheel

    st.header(f"包牌 / 牌型 / 加碼 — {game.name}")
    tab1, tab2, tab3 = st.tabs(["包牌車數 / 資金", "歷史牌型分布", "「加碼回本」現實檢驗"])

    # 1. 包牌試算
    with tab1:
        st.caption("圈選 N 個號碼全包 = 買下這 N 碼的所有 5 碼組合(車)。以每 3 車為一個下注基底。")
        c1, c2 = st.columns(2)
        picked = c1.slider("圈選號碼個數 N", min_value=5, max_value=20, value=7)
        unit = c2.number_input("下注基底(每幾車)", min_value=1, max_value=50, value=3)
        plan = wheel.wheel_plan(picked, game, unit=int(unit))
        m1, m2, m3 = st.columns(3)
        m1.metric("需要車數 C(N,5)", f"{plan.cars:,}")
        m2.metric(f"總資金({game.currency})", f"{plan.cost:,.0f}")
        m3.metric(f"基底單位數(每{int(unit)}車)", f"{plan.units:,}")
        st.metric("命中頭獎機率(5 個開出號全在圈選內)", f"{plan.jackpot_prob:.6%}")
        st.warning(
            f"誠實提醒:包牌只是「多買幾注」,每注期望報酬率仍是 {plan.expected_return:.1%}。"
            "圈越多碼、花越多錢、命中頭獎機率等比例上升,但長期期望不會因此變正,也無法保證獲利。"
        )

    # 2. 歷史牌型分布
    with tab2:
        st.caption("牌型 = (奇偶比 / 大小比 / 和值區間)。以下是歷史出現頻率。")
        if fdf.empty:
            st.warning("目前範圍沒有資料。")
        else:
            rows = wheel.pattern_distribution(fdf, top=12)
            pat_df = pd.DataFrame(
                [{"牌型": k, "出現次數": c, "歷史比例": f"{r:.1%}"} for k, c, r in rows]
            )
            st.dataframe(pat_df, width="stretch", hide_index=True)
        st.error(
            "這是「描述過去」,不是「預測未來」。每期開獎獨立隨機,"
            "歷史最常出現的牌型,下一期出現的機率並不會比較高 —— 牌型無法預測。"
        )

    # 3. 加碼回本現實檢驗
    with tab3:
        st.caption("模擬「每 N 車為基底,輸了下一局就加碼(倍投)把本拿回來」的真實下場。")
        c1, c2, c3 = st.columns(3)
        base = c1.number_input("基底車數", min_value=1, max_value=20, value=3)
        rounds_n = c2.number_input("最多模擬局數", min_value=10, max_value=200, value=40)
        start_cap = c3.number_input(
            f"起始資金({game.currency})", min_value=1000, max_value=10_000_000, value=100_000, step=1000
        )
        if st.button("模擬加碼回本", type="primary"):
            res = wheel.martingale_demo(
                game, base_cars=int(base), rounds=int(rounds_n),
                start_capital=float(start_cap), trials=300,
            )
            mm1, mm2, mm3 = st.columns(3)
            mm1.metric("破產率(300 次模擬)", f"{res.ruin_rate:.0%}")
            mm2.metric("範例:撐幾局", f"{res.rounds_survived}")
            mm3.metric("單局最多被迫下到", f"{res.peak_bet_cars:,} 車")
            st.line_chart(pd.DataFrame({"資金": res.capital_curve}))
            st.error(
                f"結果:破產率 {res.ruin_rate:.0%}。在期望值 {game.expected_return():.0%} 的負期望賭局裡,"
                "「輸了加碼回本」(Martingale)不會提高勝率,只會在連續槓龜時讓下注金額指數爆炸、"
                "資金加速歸零。這是數學上的破產陷阱,不是翻本方法。"
            )


# ── 二合買牌(策略1):三款共用一個損益池 ──────────────────
GAME_LIST = list(games.GAMES.values())          # 目前可下注的遊戲

# 單顆 / 多顆各自一套配色。下錯分頁的代價是真金白銀,所以整塊視覺都要不一樣,
# 不能只靠分頁標題那幾個字。
MODE_THEME = {
    storage.SINGLE: {"color": "#0d9488", "emoji": "🟢", "name": "單顆",
                     "desc": "每款固定押 1 顆,只能調車數"},
    storage.MULTI: {"color": "#d97706", "emoji": "🟠", "name": "多顆",
                    "desc": "每款可自訂押幾顆"},
}
TOTALS_COLOR = "#4f46e5"

_MODE_CSS = f"""
<style>
.mode-banner {{
  padding: 0.5rem 0.8rem; border-radius: 8px; color: #fff !important;
  font-weight: 700; margin: 0.2rem 0 0.8rem 0; line-height: 1.45;
}}
.mode-banner small {{ color: rgba(255,255,255,0.92) !important; font-weight: 400; }}
/* 整個分頁內容掛上左側色條 + 淡底,一眼看得出現在在哪一種下法 */
.st-key-mode_{storage.SINGLE} {{
  border-left: 5px solid {MODE_THEME[storage.SINGLE]['color']};
  background: {MODE_THEME[storage.SINGLE]['color']}0f;
  padding: 0.6rem 0.7rem; border-radius: 0 10px 10px 0;
}}
.st-key-mode_{storage.MULTI} {{
  border-left: 5px solid {MODE_THEME[storage.MULTI]['color']};
  background: {MODE_THEME[storage.MULTI]['color']}0f;
  padding: 0.6rem 0.7rem; border-radius: 0 10px 10px 0;
}}
.st-key-mode_totals {{
  border-left: 5px solid {TOTALS_COLOR}; background: {TOTALS_COLOR}0f;
  padding: 0.6rem 0.7rem; border-radius: 0 10px 10px 0;
}}
/* 主要按鈕(記帳)跟著該下法的顏色走 */
.st-key-mode_{storage.SINGLE} [data-testid="stBaseButton-primary"] {{
  background-color: {MODE_THEME[storage.SINGLE]['color']} !important;
  border-color: {MODE_THEME[storage.SINGLE]['color']} !important; color: #fff !important;
}}
.st-key-mode_{storage.MULTI} [data-testid="stBaseButton-primary"] {{
  background-color: {MODE_THEME[storage.MULTI]['color']} !important;
  border-color: {MODE_THEME[storage.MULTI]['color']} !important; color: #fff !important;
}}
/* 區塊標題也上色,捲到一半也知道自己在哪 */
.st-key-mode_{storage.SINGLE} h3 {{
  color: {MODE_THEME[storage.SINGLE]['color']} !important; }}
.st-key-mode_{storage.MULTI} h3 {{
  color: {MODE_THEME[storage.MULTI]['color']} !important; }}
.st-key-mode_totals h3 {{ color: {TOTALS_COLOR} !important; }}
</style>
"""


def _numeric_keyboard():
    """讓手機在「車數 / 顆數」這類欄位跳出數字鍵盤。

    Streamlit 的表格編輯器與 number_input 都沒有設 inputmode,手機因此會跳出
    全鍵盤,要按好幾下才切到數字。這裡用一小段腳本補上 inputmode="numeric",
    並用 MutationObserver 追新出現的輸入框(表格的編輯器是點下去才產生的)。

    只作用在數字類欄位:number_input、type=number、以及表格編輯器的 portal。
    純屬體驗優化 —— 就算哪天 Streamlit 改了 DOM 讓它失效,也只是退回全鍵盤。
    """
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const SEL = [
          'input[type="number"]',
          '[data-testid="stNumberInputField"]',
          '#portal input',                      /* 表格 cell 的編輯器 */
          '[data-testid="stDataFrameResizable"] input',
        ].join(',');
        function markNumeric() {
          doc.querySelectorAll(SEL).forEach(function (el) {
            if (el.getAttribute('inputmode') === 'numeric') return;
            el.setAttribute('inputmode', 'numeric');
            el.setAttribute('pattern', '[0-9]*');
          });
        }
        markNumeric();
        new MutationObserver(markNumeric).observe(doc.body,
          {childList: true, subtree: true});
        </script>
        """,
        height=0,
    )


def _mode_banner(mode: str):
    """分頁最上方的色條,寫明現在這一頁是哪一種下法。"""
    t = MODE_THEME[mode]
    st.markdown(
        f'<div class="mode-banner" style="background:{t["color"]}">'
        f'{t["emoji"]} 現在是「{t["name"]}下注」'
        f'<br><small>{t["desc"]} — 這一頁的下注、回填、紀錄、清除都只作用在'
        f'{t["name"]}</small></div>',
        unsafe_allow_html=True,
    )


def _history_games(by_game: dict) -> list:
    """歷史統計要顯示的遊戲:目前啟用的 + 已停用但還有紀錄的。"""
    keys = [g.key for g in GAME_LIST]
    keys += [k for k in by_game if k not in keys]
    return [games.get(k) for k in keys if k in by_game]
RECENT_N = 8          # 主畫面「最近紀錄」顯示幾筆


def _persist_setting(skey: str, setting_key: str, widget_key: str):
    """on_change 回呼:把 number_input 的新值存進 SQLite。"""
    storage.set_setting(skey, setting_key, st.session_state[widget_key])


def _game_settings(user: str, g) -> dict:
    """讀出某遊戲的盤口設定(每車成本 / 中獎可得 / 押幾顆 / 回本後起始車數)。"""
    skey = f"{user}::{g.key}"
    return {
        "game": g,
        "skey": skey,
        "cost_per_car": storage.get_setting(skey, "cost_per_car", g.default_cost_per_car),
        "win_payout": storage.get_setting(skey, "win_payout", g.default_win_payout),
        "n_numbers": int(storage.get_setting(skey, "n_numbers", 5)),
        "base": int(storage.get_setting(skey, "base", 3)),
    }


def _kick_autoupdate(game):
    """背景補抓該遊戲的開獎資料(資料日期==系統日期則跳過)。"""
    full_df = load_df(game.key)
    latest = full_df["date"].max() if not full_df.empty else None
    autoupdate.kick(game.key, game_data_path(game), latest, on_done=load_df.clear)


# ── 戰績列 ───────────────────────────────────────────────
def _render_scoreboard(tot: dict):
    """整個帳號(三款合計)的成本、回收、損益。"""
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "累積損益", f"{tot['net']:+,.0f}",
        delta="虧損中" if tot["net"] < 0 else "獲利中",
        delta_color="inverse" if tot["net"] < 0 else "normal",
    )
    c2.metric("總投入", f"{tot['cost']:,.0f}")
    c3.metric("總回收", f"{tot['payout']:,.0f}")
    c4.metric("報酬率", f"{tot['roi']:+.1%}" if tot["cost"] else "—")
    c5.metric("局數", f"{tot['rounds']}",
              delta=f"中獎 {tot['wins']}({tot['win_rate']:.0%})" if tot["settled"]
              else "尚未對獎", delta_color="off")


# ── 一、今天下哪幾款 ──────────────────────────────────────
def _plans_of(cfgs: dict, keys: list[str]) -> dict:
    return {k: (cfgs[k]["n_numbers"], cfgs[k]["cost_per_car"], cfgs[k]["win_payout"])
            for k in keys}


def _record(user: str, cfgs: dict, picks: list[str], cars: dict,
            draw_date, hits: dict | None = None, mode: str = storage.MULTI,
            nums: dict | None = None):
    """把選定的幾款一次記進流水;hits 沒填的款視為待開獎。記完把車數欄位還原成自動。

    mode 同時當作 session key 前綴與寫進資料庫的下注模式(single / multi)。
    nums 是用選號盤下注時各款圈的號碼;填數量的話留空。
    """
    hits = hits or {}
    nums = nums or {}
    for k in picks:
        cfg = cfgs[k]
        cost = cfg["n_numbers"] * int(cars[k]) * cfg["cost_per_car"]
        storage.add_round(
            user, k, draw_date.isoformat(), cfg["n_numbers"], int(cars[k]),
            hits.get(k), cost, cfg["win_payout"], mode=mode,
            picked=nums.get(k),
        )
        _kick_autoupdate(games.get(k))
    _reset_car_inputs(mode)
    for k in picks:                       # 記完就把號碼盤清空,下一筆重選
        numpad.clear(f"{mode}_pad_{k}")
    st.rerun()


def _reset_car_inputs(prefix: str = "multi"):
    """把車數欄位交還給系統建議(清掉自訂值與表格的編輯狀態)。

    prefix 區隔「多顆 / 單顆」兩個 tab 的輸入狀態,兩邊互不干擾。
    """
    st.session_state.pop(f"{prefix}_today_editor", None)
    st.session_state[f"{prefix}_today_fixed_cars"] = {}
    st.session_state[f"{prefix}_today_hits"] = {}


@st.dialog("中更多顆的金額", width="large")
def _hits_payout_dialog(rows: list[dict], cum: float, total: float):
    """依你填的車數,列出各款中 1 顆、2 顆…各能拿多少、扣掉當天總成本後累積變多少。"""
    st.caption(
        f"以下都用你在表格裡填的車數計算。當天總成本 {total:,.0f} 是三款一起算的 —— "
        f"所以「中後累積」= 目前累積 {cum:+,.0f} + 該款回收 − {total:,.0f}。"
    )
    for r in rows:
        st.markdown(
            f"**{r['name']}** — {r['cars']} 車 × 押 {r['n']} 顆,"
            f"該款成本 {r['cost']:,.0f},每中 1 顆 +{r['cars'] * r['payout']:,.0f}"
        )
        table = []
        for k in range(1, r["n"] + 1):
            gross = k * r["cars"] * r["payout"]
            after = cum + gross - total
            table.append({
                "中幾顆": f"{k} 顆",
                "機率": f"{r['dist'].get(k, 0):.2%}",
                "可得(總回收)": f"{gross:,.0f}",
                "扣當天總成本後": f"{gross - total:+,.0f}",
                "中後累積": f"{after:+,.0f}",
                "是否回本": "回本" if after >= 0 else f"還差 {-after:,.0f}",
            })
        st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)
        st.caption(f"這款全沒中(0 顆)的機率 {r['dist'].get(0, 0):.1%}")
        st.divider()


def _after_label(after: float, ok: bool, strict: bool = True) -> str:
    """中 1 顆之後的累積損益,直接標明有沒有達標。

    嚴格模式的目標是「回本」(累積 >= 0);平攤模式的目標只是「拿回自己那份」,
    所以標示要跟著模式走,不然平攤下每一列都寫「不足」會誤導。
    """
    mark = ("回本" if strict else "達標") if ok else "不足"
    return f"{after:+,.0f}({mark})"


def _parse_hits(raw) -> int | None:
    """把表格裡的「中獎顆數」字串轉成整數;空白或非數字視為還沒填。"""
    text = str(raw or "").strip()
    return int(text) if text.isdigit() else None


# 「還沒開獎」在下拉選單裡的顯示字樣(多顆用;單顆用下面那組三選一)
PENDING_LABEL = "待開獎"

# 單顆模式的「中獎顆數」只有三種可能,用下拉選單比填數字直覺
SINGLE_HITS = {"待開獎": None, "中了": 1, "沒中": 0}
SINGLE_HITS_REV = {None: "待開獎", 1: "中了", 0: "沒中"}


def _single_intro(cfgs: dict):
    """單顆 tab 開頭:說清楚它跟多顆差在哪,並用目前盤口把數字算出來。"""
    st.caption(
        "每款固定押 1 顆,只調車數。中的機率低很多,但中了的淨利大很多 —— "
        "連敗時虧損成長慢,同樣的資金撐得比較久。"
        "**兩個 tab 請當成今天二選一**,同一天兩邊都記帳的話成本會互相吃掉。"
    )
    rows = []
    for k, cfg in cfgs.items():
        g = games.get(k)
        c, w = cfg["cost_per_car"], cfg["win_payout"]
        for label, n in (("單顆", 1), (f"多顆({int(cfg['n_numbers'])} 顆)",
                                       int(cfg["n_numbers"]))):
            if n < 1 or w <= 0:
                continue
            ratio = n * c / w
            p_hit = 1.0 - erhe.hit_distribution(n, g.pick, g.num_max)[0]
            rows.append({
                "遊戲": g.label, "下法": label,
                "成本係數 k": f"{ratio:.3f}",
                "至少中 1 顆": f"{p_hit:.1%}",
                "每車中 1 顆淨利": f"{w - n * c:+,.0f}",
                "連敗虧損放大": (f"{1 / (1 - ratio):.2f}×" if ratio < 1 else "無解"),
            })
        if int(cfg["n_numbers"]) == 1:
            rows.pop()          # 這款本來就設 1 顆,兩列一樣就不重複列
    with st.expander("單顆 vs 多顆:用你現在的盤口比一比"):
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(
            "k = 押幾顆 × 每車成本 ÷ 中獎可得,決定連敗時虧損的成長速度"
            "(每敗一局,追平所需的金額乘以 1/(1−k))。k 越小撐越久,"
            "但每局中獎機率也越低。**兩種下法的期望值完全一樣**,都是負的;"
            "單顆只是把破產風險往後推,不會讓你變成正期望。"
        )


def _hit_options(cfgs: dict, picks: list[str]) -> list[str]:
    """多顆的「中獎顆數」下拉選項:待開獎 + 0 到「最多可能中幾顆」。

    上限 = 各款「押幾顆」與「每期開幾顆」取小之後的最大值 ——
    押 4 顆最多中 4 顆;押 8 顆但 539 每期只開 5 顆,最多也只能中 5 顆。
    用下拉而不是自由輸入,是為了不讓人填出不可能發生的顆數。
    """
    max_hits = max(min(int(cfgs[k]["n_numbers"]), games.get(k).pick) for k in picks)
    return [PENDING_LABEL] + [str(i) for i in range(max_hits + 1)]


MAX_PICK_MULTI = 20          # 多顆下法最多能圈幾顆(與「押幾顆」欄的上限一致)

# 策略的短名:表格欄位放得下的版本。
# picker 的完整標籤(如「均衡(奇偶/和值落常見區間)」)在手機上會把欄寬撐爆,
# 完整說明改放在「帶入」按鈕的 tooltip。
STRATEGY_SHORT = {"random": "隨機", "hot": "熱號", "cold": "冷號",
                  "frequency": "頻率", "balanced": "均衡"}


def _pad_key(mode: str, game_key: str) -> str:
    return f"{mode}_pad_{game_key}"


def _picked_map(picks: list[str], mode: str) -> dict[str, list[int]]:
    """讀各款目前圈了哪些號(沒開過號碼盤就是空的)。

    這也是「填數量 / 選號碼」的自動判斷依據 —— 圈了號就存號碼,
    沒圈就跟以前一樣只記數量,不必再叫使用者先選模式。
    """
    return {k: numpad.get_picked(_pad_key(mode, k)) for k in picks}


@st.dialog("圈選號碼", width="large", on_dismiss="rerun")
def _pick_dialog(game_key: str, mode: str, single: bool, preset_n: int):
    """號碼盤彈窗:在這裡點號碼,關掉後押幾顆就跟著圈的顆數走。

    st.dialog 繼承 st.fragment 的行為 —— 在彈窗裡點號碼只會重跑這個函式,
    不會重跑整個頁面,所以彈窗自己會保持開著,**不需要**外部旗標去撐住它。
    (先前用旗標撐,結果按 X 關掉後旗標還在,之後隨便點個東西彈窗就又跳出來。)
    on_dismiss="rerun":使用者按 X / ESC / 點外面關掉後重跑一次,
    外面的按鈕才會即時換成剛圈好的號碼。
    """
    g = games.get(game_key)
    cap = 1 if single else MAX_PICK_MULTI
    st.caption(
        f"**{g.name}** — 1~{g.num_max} 號,每期開 {g.pick} 顆。"
        + ("這個 tab 固定押 **1 顆**,點另一顆會直接換過去。" if single else
           f"圈幾顆就押幾顆(目前設定 {preset_n} 顆,最多 {cap} 顆)。"))
    numpad.number_pad(key=_pad_key(mode, game_key), num_max=g.num_max, max_pick=cap)
    c1, c2 = st.columns([1, 1])
    if c1.button("完成", type="primary", width="stretch", key=f"pad_ok_{mode}_{game_key}"):
        st.rerun()                      # 關掉彈窗並重跑,外面才看得到新號碼
    if c2.button("不選號(改用填數量)", width="stretch", key=f"pad_cancel_{mode}_{game_key}"):
        numpad.clear(_pad_key(mode, game_key))
        st.rerun()


def _pad_buttons(picks: list[str], mode: str, nums_map: dict,
                 single: bool, cfgs: dict) -> None:
    """表格底下的「選號碼」按鈕列:一款一顆,順便顯示已經圈了什麼。

    直接在按鈕的 if 裡叫彈窗 —— 只有真的按下這顆按鈕才會開,
    切換遊戲、改車數之類的重跑都不會誤觸。
    """
    cols = st.columns(len(picks))
    for col, k in zip(cols, picks):
        got = nums_map.get(k) or []
        label = (f"🎯 {games.get(k).label}　" +
                 (" ".join(f"{n:02d}" for n in got) if got else "選號碼"))
        if col.button(label, key=f"{mode}_openpad_{k}", width="stretch",
                      type="primary" if got else "secondary",
                      help="打開號碼盤圈號;圈了號就會連號碼一起存,開獎後可自動對獎。"):
            _pick_dialog(k, mode, single, int(cfgs[k]["n_numbers"]))


def _pred_panel(picks: list[str], mode: str, single: bool, draw_date) -> None:
    """下注頁裡的策略預測:對「今天這一期」產生各策略的號碼,可一鍵帶進號碼盤。

    目標期直接沿用上面的下注日期 —— 你正在為那一期下注,預測自然是對那一期。
    完整的逐期戰績與排行仍在「統計分析 → 預測比對」。
    """
    tstr = draw_date.isoformat() if hasattr(draw_date, "isoformat") else str(draw_date)
    with st.expander(f"🎯 各策略對 {tstr} 的預測(參考用,可帶進號碼盤)"):
        st.caption(
            "所有策略的期望中獎率完全相同,這只是把不同選號方式的結果攤出來看,"
            "**不是準度排名**。預測只吃得到這一期之前的資料,存下後不會被覆蓋。"
        )
        if st.button("產生並存檔", key=f"{mode}_pred_gen", type="primary"):
            added_txt, kept = [], []
            for k in picks:
                added, rows = predictor.save_for(load_df(k), k, draw_date)
                if not rows:
                    continue
                (added_txt if added else kept).append(
                    f"{games.get(k).label} {added} 筆" if added
                    else games.get(k).label)
            if added_txt:
                st.success("已存下:" + "、".join(added_txt))
            if kept:
                st.info("、".join(kept) + " 這一期先前已經存過了 —— "
                        "預測不會被覆蓋,以保留當初的判斷。")
            if not added_txt and not kept:
                st.error("這一期之前沒有資料可以算,請確認下注日期。")

        # 排成矩陣:一列一個策略(Y),一欄一款遊戲(X),格子裡是號碼 + 帶入。
        # 「帶入」要是真的按鈕,沒辦法塞進 <table>,所以用欄位排出表格結構。
        by_cell = {}                       # (遊戲, 策略) -> 該筆預測
        drawn_note = []
        for k in picks:
            got = predictor.evaluate(load_df(k), k, tstr)
            for r in got:
                by_cell[(k, r["strategy"])] = r
            if got and not got[0]["pending"]:
                drawn_note.append(f"{games.get(k).label} 開出 "
                                  + " ".join(f"{n:02d}" for n in got[0]["drawn"]))
        if not by_cell:
            return
        if drawn_note:
            st.caption("　|　".join(drawn_note))

        # 表格本身用 <table> 畫(格線、斑馬紋都有,縮放也不會糊);
        # 「帶入」是真按鈕、塞不進表格,所以排在表格底下。
        cols = [games.get(k).label for k in picks]
        matrix = []
        for s in picker.STRATEGIES:
            if not any((k, s) in by_cell for k in picks):
                continue
            row = {"策略": STRATEGY_SHORT.get(s, s)}
            for k in picks:
                r = by_cell.get((k, s))
                row[games.get(k).label] = (
                    "—" if not r else
                    predictor.marked(r["numbers"], set(r["matched"]))
                    + ("" if r["pending"] else f"　中 {r['hits']}")
                )
            matrix.append(row)
        tables.html_table(pd.DataFrame(matrix), mono_cols=tuple(cols))

        cap = 1 if single else MAX_PICK_MULTI      # 單顆下法只帶第 1 顆
        st.caption("把某個策略的號碼帶進號碼盤:")
        for k in picks:
            if len(picks) > 1:                     # 只下一款就不必重複標遊戲名
                st.markdown(f"**{games.get(k).label}**")
            # 這裡刻意用一般的 st.columns —— 手機放不下 5 顆時就讓它自然堆疊,
            # 每顆按鈕才有足夠寬度(硬壓成一列會把「隨機」拆成兩個直排的字)
            bc = st.columns(len(picker.STRATEGIES))
            for i, s in enumerate(picker.STRATEGIES):
                r = by_cell.get((k, s))
                if bc[i].button(STRATEGY_SHORT.get(s, s),
                                key=f"{mode}_use_{k}_{s}", width="stretch",
                                disabled=not r,
                                help=f"{picker.label(s)} —— 把這組號碼填進"
                                     f"「{games.get(k).label}」的號碼盤"
                                     + ("(單顆下法只帶第 1 顆)" if single else "")):
                    numpad.set_picked(_pad_key(mode, k), r["numbers"][:cap])
                    st.rerun()


def _render_today(user: str, cfgs: dict, cum: float, mode: str = storage.MULTI):
    """今天要下哪幾款的輸入 + 試算。

    mode="multi"  每款可自訂押幾顆(現行玩法)。
    mode="single" 每款固定押 1 顆,只能改車數 —— 成本係數 k 小很多,
                  連敗時虧損成長慢,但中獎頻率也低。
    """
    single = mode == storage.SINGLE
    if single:
        # 顆數鎖 1:只覆寫這次試算用的值,不動「設定」頁存的多顆顆數
        cfgs = {k: {**v, "n_numbers": 1} for k, v in cfgs.items()}

    st.subheader("一、今天下哪幾款" + ("(每款固定押 1 顆)" if single else ""))
    picks = st.segmented_control(
        "今天要下注的遊戲(預設一款;要下多款就多勾)",
        [g.key for g in GAME_LIST], selection_mode="multi",
        default=[GAME_LIST[0].key],
        format_func=lambda k: games.get(k).name, key=f"{mode}_today_games",
    )
    # 換了勾選的組合就把表格編輯狀態清掉(避免舊的自訂值套到別款)
    if st.session_state.get(f"{mode}_today_picks") != list(picks):
        _reset_car_inputs(mode)
        st.session_state[f"{mode}_today_picks"] = list(picks)
    if not picks:
        st.info("勾選至少一款,系統就會算出今天要下幾車。")
        return

    # ── 輸入方式自動判斷:圈了號碼就用號碼,沒圈就跟以前一樣只記數量 ──
    nums_map = _picked_map(picks, mode)
    by_pick = any(nums_map.values())
    # 有圈號的款,押幾顆一律以圈的顆數為準(沒圈的維持設定值)
    cfgs = {k: {**v, "n_numbers": (len(nums_map.get(k) or []) or v["n_numbers"])}
            for k, v in cfgs.items()}

    fixed = {k: v for k, v in st.session_state.get(f"{mode}_today_fixed_cars", {}).items()
             if k in picks}
    hits_state = {k: v for k, v in st.session_state.get(f"{mode}_today_hits", {}).items()
                  if k in picks}

    # 下多款時要先決定「回本責任」怎麼算(只下一款時兩者是同一條式子,不用問)
    n_games = len(picks)
    if n_games >= 2:
        mode = st.radio(
            "多款一起下時,怎麼算才算回本?",
            ["平攤:每款各負擔 1/N", "嚴格:任一款中 1 顆就全部回本"],
            horizontal=True, key=f"{mode}_share_mode",
            help="平攤比較便宜,但要每一款都中才完全回本;"
                 "嚴格是任何一款中 1 顆就回本,但成本高很多,而且 k ≥ 1 時無解。",
        )
        share = n_games if mode.startswith("平攤") else 1
    else:
        share = 1

    plans = _plans_of(cfgs, picks)
    res = erhe.simultaneous_recovery(
        cum, plans, base_cars=max(cfgs[k]["base"] for k in picks),
        fixed=fixed, share=share)

    if not res["feasible"]:
        odds = {k: (cfgs[k]["cost_per_car"], cfgs[k]["win_payout"])
                for k in picks if k not in fixed}
        n_max = erhe.max_numbers_for_combo(odds, margin=share * 0.999)
        st.error(
            f"這樣下算不出車數:成本係數 k = {res['k']:.2f},必須小於 {share:g} 才有解。"
            "因為任何一款中獎,都要先扣掉當天全部的下注成本 —— 成本是好幾份、回收只有一份。"
        )
        c1, c2 = st.columns(2)
        if share == 1 and n_games >= 2:
            c1.warning("改用「平攤」就會有解(但要每一款都中才完全回本)。")
        targets = [k for k in picks if k not in fixed] or list(picks)
        if single:
            # 顆數已經是最小的 1 了,只剩盤口本身太差(每車成本相對中獎金額過高)
            c2.warning(
                "單顆已經是最省的下法,還是無解就代表盤口的「每車成本 ÷ 中獎可得」太高;"
                "請到「設定」確認金額,或今天少下幾款。")
        elif n_max >= 1:
            c2.warning(f"或把這幾款的「押幾顆」降到 {n_max} 顆以內。")
            if c2.button(f"把這 {len(targets)} 款的押幾顆都改成 {n_max} 顆",
                         key=f"{mode}_fix_n", type="primary"):
                for k in targets:
                    storage.set_setting(cfgs[k]["skey"], "n_numbers", n_max)
                    st.session_state.pop(f"set_n_{k}", None)
                st.rerun()
        else:
            c2.warning("這個組合連每款押 1 顆都無解,今天請少下幾款。")
        return

    d1, _ = st.columns([1, 3])
    draw_date = d1.date_input("下注日期", value=dt.date.today(), format="YYYY-MM-DD",
                              key=f"{mode}_bet_date")
    _note(
        ("- 這個 tab **固定每款押 1 顆**,顆數不能改,只能改 **下幾車**。\n"
         if single else
         "- **押幾顆 / 下幾車 / 中獎顆數** 這三欄可以直接在表格裡改。\n")
        + "- **建議車數** 已經把當天所有款的成本算進去了 —— 照它下,"
        + ("中任何一款 1 顆就回本。\n" if share == 1
           else f"{n_games} 款都中 1 顆才完全回本。\n")
        + "- **中1顆後累積** 是那一款中 1 顆、扣掉當天全部成本後的累積損益;"
        "顯示「不足」就代表這樣下中了也還是虧。\n"
        + ("- 中了就選「中了」、槓龜選「沒中」;還沒開獎留「待開獎」,"
           "之後在「二、開獎後回填」補。"
           if single else
           "- 中獎顆數是下拉選單(0 顆到最多可能中的顆數);"
           "留「待開獎」= 還沒開獎,之後在「二、開獎後回填」補。")
    )

    loss = max(0.0, -cum)
    # 只有真的圈過號才多一欄「號碼」;純填數量的人看到的表跟以前一模一樣
    def _row_nums(k: str) -> str:
        got = nums_map.get(k) or []
        return " ".join(f"{n:02d}" for n in got) if got else "—"

    num_col = {"號碼": st.column_config.TextColumn(
        "號碼", help="在下方號碼盤圈的號碼;沒圈號的款顯示「—」,一樣只記數量。")}

    # 輸入表:只放可以改的欄,手機不必左右滑。單顆模式連「押幾顆」都不放。
    if single:
        table = pd.DataFrame([{
            "遊戲": games.get(k).label,
            **({"號碼": _row_nums(k)} if by_pick else {}),
            "下幾車": int(res["cars"][k]),
            "開獎結果": SINGLE_HITS_REV[hits_state.get(k)],
        } for k in picks], index=list(picks))
        col_cfg = {
            "下幾車": st.column_config.NumberColumn(
                "下幾車", min_value=1, max_value=100_000, step=1, required=True,
                help="這個 tab 唯一能改的欄位。你改過的那款會固定住,其餘款依剩下的成本重算。"),
            "開獎結果": st.column_config.SelectboxColumn(
                "開獎結果", options=list(SINGLE_HITS), required=True,
                help="押 1 顆只有中或沒中兩種結果;還沒開獎就留「待開獎」。"),
            **(num_col if by_pick else {}),
        }
    else:
        hit_opts = _hit_options(cfgs, picks)
        table = pd.DataFrame([{
            "遊戲": games.get(k).label,
            **({"號碼": _row_nums(k)} if by_pick else {}),
            "押幾顆": int(cfgs[k]["n_numbers"]),
            "下幾車": int(res["cars"][k]),
            "中獎顆數": (PENDING_LABEL if hits_state.get(k) is None
                     else str(hits_state[k])),
        } for k in picks], index=list(picks))
        col_cfg = {
            "押幾顆": st.column_config.NumberColumn(
                "押幾顆", min_value=1, max_value=20, step=1, required=True,
                help=("由上面圈了幾顆決定,改這裡沒有用 —— 要改請回號碼盤加減。"
                      if by_pick else
                      "今天這款要押幾個號碼。改了會一併更新「設定」頁的盤口。")),
            "下幾車": st.column_config.NumberColumn(
                "下幾車", min_value=1, max_value=100_000, step=1, required=True,
                help="可直接修改。你改過的那款會固定住,其餘款依剩下的成本重算。"),
            "中獎顆數": st.column_config.SelectboxColumn(
                "中獎顆數", options=hit_opts, required=True,
                help="中了幾顆就選幾;還沒開獎就留「待開獎」,"
                     "之後在「二、開獎後回填」補。"),
            **(num_col if by_pick else {}),
        }

    st.markdown("**填這裡**")
    # 有圈號的款「押幾顆」是號碼盤算出來的,鎖住避免兩邊打架;
    # 「號碼」欄只是顯示,要改請回號碼盤
    locked = (["遊戲"] + (["押幾顆"] if (by_pick and not single) else [])
              + (["號碼"] if by_pick else []))
    edited = st.data_editor(
        table, key=f"{mode}_today_editor", hide_index=True, width="stretch",
        disabled=locked, column_config=col_cfg,
    )
    _pad_buttons(picks, mode, nums_map, single, cfgs)
    _pred_panel(picks, mode, single, draw_date)

    # 比對「送進表格的值」與「改完的值」,不同的就是使用者手動指定的。
    # 押幾顆存進設定,車數/顆數存進 session,再重跑一次讓建議依它重算。
    changed = False
    for k in picks:                      # 以遊戲代號取值,排序過也不會對錯行
        if not single and not by_pick:   # 選號模式的顆數來自號碼盤,不寫回設定
            n_new = edited.loc[k, "押幾顆"]
            if n_new and int(n_new) != int(table.loc[k, "押幾顆"]):
                storage.set_setting(cfgs[k]["skey"], "n_numbers", int(n_new))
                st.session_state.pop(f"set_n_{k}", None)
                changed = True
        v = edited.loc[k, "下幾車"]
        if v and int(v) != int(table.loc[k, "下幾車"]):
            fixed[k] = int(v)
            changed = True
        hv = (SINGLE_HITS[edited.loc[k, "開獎結果"]] if single
              else _parse_hits(edited.loc[k, "中獎顆數"]))
        if hv != hits_state.get(k):
            hits_state[k] = hv
            changed = True
    if changed:
        st.session_state[f"{mode}_today_fixed_cars"] = fixed
        st.session_state[f"{mode}_today_hits"] = hits_state
        st.rerun()

    # 合計一律用表格上真正的數字重算,保證跟每一列對得起來
    cars = {k: int(edited.loc[k, "下幾車"]) for k in picks}
    hits = {k: v for k, v in hits_state.items() if v is not None}
    bad_hits = [games.get(k).name for k, v in hits.items() if v > cfgs[k]["n_numbers"]]
    if bad_hits:
        st.error(
            f"**{'、'.join(bad_hits)}** 的中獎顆數超過押的顆數了,不可能發生。"
            "請改小後再記帳。"
        )
    total = sum(cfgs[k]["n_numbers"] * cars[k] * cfgs[k]["cost_per_car"] for k in picks)
    gains = {k: cars[k] * cfgs[k]["win_payout"] for k in picks}
    quota = (loss + total) / share          # 每款該負擔的回收額
    worst = cum + min(gains.values()) - total
    all_hit = cum + sum(gains.values()) - total
    p_miss = {}
    for k in picks:
        g = games.get(k)
        p_miss[k] = erhe.hit_distribution(cfgs[k]["n_numbers"], g.pick, g.num_max)[0]
    p_all_miss = 1.0
    p_all_hit = 1.0
    for k in picks:
        p_all_miss *= p_miss[k]
        p_all_hit *= (1.0 - p_miss[k])

    hit_word = "中了" if single else "中 1 顆"
    st.markdown("**試算結果**")
    st.dataframe(pd.DataFrame([{
        "遊戲": games.get(k).label,
        "建議車數": f"{int(res['cars'][k])} 車",
        "本局成本": f"{cfgs[k]['n_numbers'] * cars[k] * cfgs[k]['cost_per_car']:,.0f}",
        ("中了拿多少" if single else "每中1顆拿多少"): f"{gains[k]:,.0f}",
        f"{hit_word}後累積": _after_label(
            cum + gains[k] - total, gains[k] >= quota - 1e-6, share == 1),
    } for k in picks]), width="stretch", hide_index=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("目前累積", f"{cum:+,.0f}")
    m2.metric("今天總成本", f"{total:,.0f}")
    m3.metric(f"只中一款{'' if single else ' 1 顆'}後", f"{worst:+,.0f}",
              delta="不再虧損" if worst >= 0 else "仍是虧的",
              delta_color="normal" if worst >= 0 else "inverse")
    if n_games >= 2:
        m4.metric(f"{n_games} 款都{hit_word}後", f"{all_hit:+,.0f}",
                  delta=f"發生機率 {p_all_hit:.0%}", delta_color="off")
    else:
        m4.metric("這款沒中的機率" if single else "這款全沒中的機率",
                  f"{p_all_miss:.0%}")

    short = [games.get(k).name for k in picks if k in res["short"]]
    if short:
        st.warning(f"**{'、'.join(short)}** 車數不夠,中 1 顆也回不了本。")
    elif share > 1:
        st.warning(f"平攤:要 {n_games} 款都中才回本({p_all_hit:.0%} 機率)。")
    elif cum >= 0:
        st.success("目前沒有虧損要追,車數用起始值。")

    detail = []
    if cum < 0:
        detail.append(
            f"- 車數怎麼來的:目前虧 {loss:,.0f} + 今天要花 {total:,.0f},"
            f"所以每款中 1 顆的回收必須 ≥ **{(loss + total) / share:,.0f}**"
            + (f"(總額 {loss + total:,.0f} ÷ {n_games} 款)" if share > 1 else ""))
    if short:
        detail.append(
            f"- **{'、'.join(short)}** 中 1 顆也達不到那個門檻 —— "
            "把它的車數調高,或把別款調低。")
    if n_games >= 2:
        detail.append(
            f"- 機率:今天全槓龜 {p_all_miss:.0%}、至少中一款 {1 - p_all_miss:.0%}、"
            f"{n_games} 款都中 {p_all_hit:.0%}")
        if share > 1:
            detail.append(
                f"- **平攤的代價**:只有一款中 1 顆時累積會變成 {worst:+,.0f}"
                f"(比現在的 {cum:+,.0f} 更差);要 {n_games} 款都中才回到 "
                f"{all_hit:+,.0f}。想「中任何一款就回本」請改選「嚴格」。")
    if detail:
        _note("\n".join(detail), "這些數字怎麼來的")

    # 單顆只有中/沒中兩種結果,沒有「中更多顆」可看,那顆按鈕就不放了
    cols = st.columns([2, 1] if single else [2, 1.2, 1])
    b1, b_last = cols[0], cols[-1]
    if b1.button(
            "記帳" + ("(留「待開獎」的就當作還沒對獎)" if single
                      else "(中獎顆數留空的就當作待開獎)"),
            key=f"{mode}_record", type="primary", width="stretch",
            disabled=bool(bad_hits)):
        # 圈了號的款連號碼一起存,沒圈的只存數量 —— 同一次記帳可以混著來
        _record(user, cfgs, picks, cars, draw_date, hits, mode=mode, nums=nums_map)
    if not single and cols[1].button(
            "查看中更多顆的金額", key=f"{mode}_more", width="stretch",
            help="依你填的車數,列出中 1 顆、2 顆…各拿多少、累積會變多少。"):
        _hits_payout_dialog([{
            "name": games.get(k).name,
            "cars": cars[k],
            "n": cfgs[k]["n_numbers"],
            "payout": cfgs[k]["win_payout"],
            "cost": cfgs[k]["n_numbers"] * cars[k] * cfgs[k]["cost_per_car"],
            "dist": erhe.hit_distribution(cfgs[k]["n_numbers"],
                                          games.get(k).pick, games.get(k).num_max),
        } for k in picks], cum, total)
    if b_last.button("車數重設為建議", key=f"{mode}_reset", width="stretch",
                     disabled=not fixed,
                     help="把你手動改過的車數還原,交還給系統計算。"):
        _reset_car_inputs(mode)
        st.rerun()


# ── 二、開獎後回填 ────────────────────────────────────────
def _balls(nums: list[int], hit: set[int] | None = None) -> str:
    """把號碼排成一列;中的號碼加粗標色,其餘淡色。"""
    hit = hit or set()
    out = []
    for n in nums:
        if n in hit:
            out.append(f"<span style='background:#16a34a;color:#fff;padding:1px 6px;"
                       f"border-radius:4px;font-weight:700'>{n:02d}</span>")
        else:
            out.append(f"<span style='color:#64748b'>{n:02d}</span>")
    return " ".join(out)


def _auto_check(r: dict) -> dict:
    """用該款的開獎資料替一筆紀錄對獎(沒選號或沒資料就回 ok=False)。"""
    return checker.check(load_df(r["game"]), r["draw_date"], r.get("picked") or [])


def _render_pending(rows: list[dict]):
    """待對獎清單(呼叫端已經只傳該下法的紀錄進來)。

    用選號盤下的紀錄會自動比對開獎號碼算出中幾顆,按一下就回填;
    填數量的舊紀錄沒有號碼可比,維持手動輸入。
    """
    pend = [r for r in rows if r["pending"]]
    if not pend:
        return
    st.subheader(f"二、開獎後回填({len(pend)} 筆待對獎)")

    checked = {int(r["id"]): _auto_check(r) for r in pend}
    auto_ok = [r for r in pend if checked[int(r["id"])]["ok"]]
    if auto_ok:
        st.caption(f"其中 {len(auto_ok)} 筆已經比對到開獎號碼,可以直接回填。")
        if st.button(f"✅ 一次回填這 {len(auto_ok)} 筆", type="primary",
                     key="fill_all_auto",
                     help="依開獎號碼自動算出的中獎顆數,一次寫進所有能判定的紀錄。"):
            for r in auto_ok:
                storage.update_round_result(int(r["id"]),
                                            int(checked[int(r["id"])]["hits"]))
            st.rerun()
    else:
        st.caption("填上中了幾顆,回收依下注當時的盤口結算。")

    for r in pend:
        g = games.get(r["game"])
        res = checked[int(r["id"])]
        picked = r.get("picked") or []
        c1, c2, c3 = st.columns([5, 2, 1.4])
        head = (f"**{r['draw_date']} {g.label}**  \n"
                f"{int(r['cars'])} 車 × 押 {int(r['numbers'])} 顆,"
                f"成本 {r['cost']:,.0f},"
                f"每中 1 顆 +{int(r['cars']) * float(r['payout_rate'] or 0):,.0f}")
        c1.markdown(head)
        if picked:
            c1.markdown("我的號碼　" + _balls(picked, set(res["matched"])),
                        unsafe_allow_html=True)
        if res["ok"]:
            c1.markdown("開獎號碼　" + _balls(res["drawn"], set(res["matched"])),
                        unsafe_allow_html=True)
            c1.success(f"自動判定:中 {res['hits']} 顆", icon="🎯")
        elif picked:
            c1.info(res["reason"], icon="⏳")

        default_hit = int(res["hits"]) if res["ok"] else 0
        hit = c2.number_input(
            "重幾顆", min_value=0, max_value=int(r["numbers"]), value=default_hit,
            key=f"fill_hits_{r['id']}", label_visibility="collapsed",
            help="自動判定的結果可以直接改;沒有開獎資料時就自己填。",
        )
        if c3.button("回填", key=f"fill_btn_{r['id']}", type="primary"):
            storage.update_round_result(int(r["id"]), int(hit))
            st.rerun()
    st.divider()


# ── 三、紀錄 ─────────────────────────────────────────────
# 流水表裡要靠等寬字型對齊的欄(號碼與金額)
_LEDGER_MONO = ("號碼", "成本", "回收", "本局損益", "累積損益")


def _marked_numbers(r: dict) -> str:
    """把該筆圈的號碼排成字串,中的號碼用【】框起來。

    需要比對當期開獎號碼才知道哪幾顆中 —— 查不到開獎資料(還沒開 / 沒抓到)
    就只列號碼不加記號,不會擅自標成沒中。
    """
    picked = r.get("picked") or []
    if not picked:
        return "—"
    matched: set[int] = set()
    if not r["pending"]:
        res = checker.check(load_df(r["game"]), r["draw_date"], picked)
        if res["ok"]:
            matched = set(res["matched"])
    return " ".join(f"【{n:02d}】" if n in matched else f"{n:02d}" for n in picked)


def _detail_df(rows: list[dict]) -> pd.DataFrame:
    # 全部都是手動填數量的話就不放「號碼」欄,表格維持原樣(手機也不用左右滑)
    any_picked = any(r.get("picked") for r in rows)
    return pd.DataFrame([{
        "#": i + 1,
        "日期": r["draw_date"],
        "遊戲": games.get(r["game"]).label,
        "車數": int(r["cars"]),
        "押幾顆": int(r["numbers"]),
        # 中的號碼在 ui/tables 會被畫成綠色標籤,欄名不必再標示【】
        **({"號碼": _marked_numbers(r)} if any_picked else {}),
        "重幾顆": "待開獎" if r["pending"] else f"{int(r['hits'])} 顆",
        "成本": f"{r['cost']:,.0f}",
        "回收": f"{r['payout']:,.0f}",
        "本局損益": f"{r['net']:+,.0f}",
        "累積損益": f"{r['cumulative']:+,.0f}",
    } for i, r in enumerate(rows)])


def _render_mode_records(user: str, mode: str, rows: list[dict]):
    """三、紀錄:只顯示目前這個下法的紀錄,撤銷與清除也只作用在它身上。"""
    name = storage.MODE_NAMES[mode]
    st.subheader(f"三、紀錄({name})")
    if not rows:
        st.info(f"還沒有{name}下注的紀錄。用上面的「記帳」送出第一筆。")
        return

    t = storage.totals(user, mode)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{name}損益", f"{t['net']:+,.0f}")
    c2.metric("投入", f"{t['cost']:,.0f}")
    c3.metric("回收", f"{t['payout']:,.0f}")
    c4.metric("局數", f"{t['rounds']}",
              delta=f"中獎 {t['wins']}" if t["settled"] else "尚未對獎",
              delta_color="off")
    st.caption(
        f"最近 {min(RECENT_N, len(rows))} 筆(共 {len(rows)} 筆)。"
        "「累積」欄是整個帳號的共用損益池,所以會把另一種下法的損益也算進去。")
    tables.html_table(_detail_df(rows).tail(RECENT_N),
                      mono_cols=_LEDGER_MONO, max_height=420)

    b1, b2 = st.columns(2)
    if b1.button(f"撤銷剛剛記的那筆({name})", key=f"undo_{mode}", width="stretch",
                 help=f"刪除{name}最後寫入的一筆,累積損益自動重算。"):
        storage.undo_last_round(user, mode)
        st.rerun()
    if b2.button(f"清除{name}的全部紀錄", key=f"reset_{mode}", width="stretch"):
        st.session_state[f"confirm_reset_{mode}"] = True
    if st.session_state.get(f"confirm_reset_{mode}"):
        st.warning(
            f"確定清除這個帳號**{name}下注**的全部紀錄({len(rows)} 筆、"
            f"三款合計)?另一種下法的紀錄不受影響。\n\n"
            "清除前會自動備份整個資料庫,誤刪可還原。")
        r1, r2 = st.columns(2)
        if r1.button("確定清除", key=f"confirm_{mode}", type="primary"):
            n = storage.reset(user, mode)
            st.session_state.pop(f"confirm_reset_{mode}", None)
            st.session_state["last_reset_note"] = f"已清除{name} {n} 筆(已自動備份)"
            st.rerun()
        if r2.button("取消", key=f"cancel_{mode}"):
            st.session_state.pop(f"confirm_reset_{mode}", None)
            st.rerun()
    note = st.session_state.pop("last_reset_note", None)
    if note:
        st.success(note)

    with st.expander(f"{name}的完整流水(每日彙總 / 逐筆明細 / 分款統計 / 走勢圖)"):
        _render_full_ledger(user, rows, mode)


def _render_full_ledger(user: str, rows: list[dict], mode: str | None = None):
    suffix = f"_{mode}" if mode else ""
    tab_day, tab_all, tab_game = st.tabs(["每日彙總", "逐筆明細", "分款統計"])

    with tab_day:
        daily = storage.totals_by_date(user, mode)
        st.dataframe(pd.DataFrame([{
            "日期": d["draw_date"], "筆數": d["rounds"],
            "當日成本": f"{d['cost']:,.0f}", "當日回收": f"{d['payout']:,.0f}",
            "當日損益": f"{d['net']:+,.0f}", "累積損益": f"{d['cumulative']:+,.0f}",
        } for d in daily]), width="stretch", hide_index=True)
        if len(daily) >= 2:
            fig = px.line(
                pd.DataFrame({"日期": [d["draw_date"] for d in daily],
                              "累積損益": [d["cumulative"] for d in daily]}),
                x="日期", y="累積損益", markers=True,
                title=f"累積損益走勢({storage.MODE_NAMES.get(mode, '全部')}、三款合併)")
            fig.add_hline(y=0, line_dash="dash", line_color="#888")
            st.plotly_chart(fig, theme=None, width="stretch", key=f"cum_chart{suffix}")

    with tab_all:
        tables.html_table(_detail_df(rows), mono_cols=_LEDGER_MONO, max_height=520)
        st.download_button(
            "下載流水 CSV", key=f"dl_ledger{suffix}",
            data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
            file_name=f"erhe_ledger{suffix}.csv", mime="text/csv")
        st.markdown("**修改 / 刪除指定的一筆**")
        opts = {
            f"#{i + 1} {r['draw_date']} {games.get(r['game']).name} "
            f"{int(r['cars'])}車 "
            + (" ".join(f"{n:02d}" for n in r["picked"]) + " " if r.get("picked") else "")
            + f"損益{r['net']:+,.0f}": r
            for i, r in enumerate(rows)
        }
        choice = st.selectbox("選一筆", list(opts), key=f"edit_pick{suffix}")
        row = opts[choice]
        e1, e2, e3 = st.columns([1.4, 1, 1])
        new_date = e1.date_input("改日期", value=dt.date.fromisoformat(row["draw_date"]),
                                 format="YYYY-MM-DD", key=f"edit_date{suffix}")
        new_hits = e2.number_input("改中獎顆數", min_value=0, max_value=int(row["numbers"]),
                                   value=0 if row["pending"] else int(row["hits"]),
                                   key=f"edit_hits{suffix}")
        e3.markdown("&nbsp;", unsafe_allow_html=True)
        if e3.button("套用", key=f"edit_apply{suffix}", width="stretch"):
            storage.update_round_result(int(row["id"]), int(new_hits))
            storage.set_round_date(int(row["id"]), new_date.isoformat())
            st.rerun()
        if st.button("刪除這一筆", key=f"edit_del{suffix}"):
            storage.delete_round(int(row["id"]))
            st.rerun()

    with tab_game:
        by_game = storage.totals_by_game(user, mode)
        gm_rows = []
        shown = _history_games(by_game)
        for g in shown:
            t = by_game[g.key]
            settled = t["rounds"] - t["pending"]
            gm_rows.append({
                "遊戲": g.name + ("(已停用)" if not games.is_active(g.key) else ""),
                "局數": t["rounds"], "中獎局": t["wins"],
                "勝率": f"{t['wins'] / settled:.0%}" if settled else "—",
                "投入": f"{t['cost']:,.0f}", "回收": f"{t['payout']:,.0f}",
                "損益": f"{t['net']:+,.0f}",
                "報酬率": f"{t['net'] / t['cost']:+.1%}" if t["cost"] else "—",
            })
        if gm_rows:
            st.dataframe(pd.DataFrame(gm_rows), width="stretch", hide_index=True)
            fig = px.bar(
                pd.DataFrame({"遊戲": [r["遊戲"] for r in gm_rows],
                              "損益": [by_game[g.key]["net"] for g in shown]}),
                x="遊戲", y="損益",
                title=f"各款累積損益({storage.MODE_NAMES.get(mode, '全部')})", color="損益",
                color_continuous_scale=["#e63946", "#457b9d"])
            st.plotly_chart(fig, theme=None, width="stretch", key=f"game_chart{suffix}")


# ── 回本試算:依目前總損益,單押一款要幾車 ──────────────────
def _recovery_rows(cfgs: dict, cum: float, mode: str | None = None) -> list[dict]:
    """各款(在指定下法下)單押一款、中 1 顆就把總損益一次打平所需的車數。

    mode 傳 None 則單顆與多顆都列,供跨下法比較。
    """
    rows = []
    for g in GAME_LIST:
        cfg = cfgs[g.key]
        c, w = cfg["cost_per_car"], cfg["win_payout"]
        n_multi = int(cfg["n_numbers"])
        plans = [(storage.SINGLE, 1), (storage.MULTI, n_multi)]
        if mode is not None:
            plans = [p for p in plans if p[0] == mode]
        elif n_multi == 1:
            plans = plans[:1]     # 多顆本來就設 1 顆時兩者相同,不重複列
        for m, n in plans:
            res = erhe.next_cars_for_recovery(cum, n, c, w, base_cars=int(cfg["base"]))
            row = {"遊戲": g.label, "下法": storage.MODE_NAMES[m], "押幾顆": n}
            if not res["can_recover_1hit"]:
                row.update({"回本車數": "無解", "本局成本": "—", "中1顆可得": "—",
                            "中後累積": "中 1 顆也回不了本", "_cost": float("inf")})
            else:
                cars, cost = int(res["next_cars"]), res["next_cost"]
                gain = cars * w
                row.update({"回本車數": f"{cars:,} 車", "本局成本": f"{cost:,.0f}",
                            "中1顆可得": f"{gain:,.0f}",
                            "中後累積": f"{cum + gain - cost:+,.0f}", "_cost": cost})
            rows.append(row)
    return rows


def _recovery_df(rows: list[dict], drop_mode: bool = False) -> pd.DataFrame:
    skip = {"_cost"} | ({"下法"} if drop_mode else set())
    return pd.DataFrame([{k: v for k, v in r.items() if k not in skip} for r in rows])


_RECOVERY_NOTE = (
    "- 這裡假設**只下這一款**。同一天下多款時,每一款的中獎都要先扣掉當天"
    "全部的下注成本,所需車數會比表上的多 —— 那種情況請用「一、今天下哪幾款」。\n"
    "- 車數 = ⌈目前虧損 ÷ (中獎可得 − 押幾顆 × 每車成本)⌉,"
    "也就是「中 1 顆的淨利要能覆蓋整個坑」。\n"
    "- **單顆的車數永遠比多顆少**:押越多顆,每車要付的成本越高,"
    "中 1 顆的淨利就越薄。但單顆中獎機率也低得多,這是代價不是免費午餐。\n"
    "- 這只是算術,改變不了每局的負期望;追虧損會讓下注金額幾何成長。"
)


def _render_mode_recovery(cfgs: dict, cum: float, mode: str):
    """分頁內的建議車數:只算這一種下法,不跟另一種混在一起。"""
    name = storage.MODE_NAMES[mode]
    st.subheader(f"四、回本要下幾車({name})")
    if cum >= 0:
        st.success(f"{name}目前累積 {cum:+,.0f},沒有虧損要追,車數用各款的起始值就好。")
        return

    rows = _recovery_rows(cfgs, cum, mode)
    ok = [r for r in rows if r["_cost"] != float("inf")]
    cheapest = min(ok, key=lambda r: r["_cost"]) if ok else None

    m1, m2, m3 = st.columns(3)
    m1.metric(f"{name}累積損益", f"{cum:+,.0f}", delta="虧損中",
              delta_color="inverse")
    if cheapest:
        m2.metric(f"{name}最省的一款", cheapest["遊戲"],
                  delta=cheapest["回本車數"], delta_color="off")
        m3.metric("那一注要花", cheapest["本局成本"],
                  delta=f"中1顆得 {cheapest['中1顆可得']}", delta_color="off")
    else:
        m2.metric(f"{name}最省的一款", "無解", delta="中 1 顆都追不回", delta_color="off")

    st.dataframe(_recovery_df(rows, drop_mode=True), width="stretch", hide_index=True)
    st.caption(f"這裡用的是**{name}自己的累積損益**({cum:+,.0f}),不含另一種下法;"
               "兩者合計看「📊 總損益」那頁。")
    _note(_RECOVERY_NOTE, "這張表怎麼算的")


# ── 總損益分頁:兩種下法的合計與對照 ────────────────────────
def _render_totals_tab(user: str, cfgs: dict, cum: float, rows: list[dict]):
    st.markdown(
        f'<div class="mode-banner" style="background:{TOTALS_COLOR}">'
        f'📊 總損益(單顆 + 多顆合計)'
        f'<br><small>兩種下法共用同一個損益池,這一頁看的是合起來的結果</small></div>',
        unsafe_allow_html=True,
    )
    _render_scoreboard(storage.totals(user))

    st.markdown("**兩種下法各自的成績**")
    per_mode = {m: storage.totals(user, m) for m in storage.MODES}
    st.dataframe(pd.DataFrame([{
        "下法": f"{MODE_THEME[m]['emoji']} {storage.MODE_NAMES[m]}",
        "局數": t["rounds"], "中獎局": t["wins"],
        "投入": f"{t['cost']:,.0f}", "回收": f"{t['payout']:,.0f}",
        "損益": f"{t['net']:+,.0f}",
        "報酬率": f"{t['roi']:+.1%}" if t["cost"] else "—",
    } for m, t in per_mode.items()]), width="stretch", hide_index=True)

    if not rows:
        st.info("還沒有任何紀錄。")
        return

    daily = storage.totals_by_date(user)
    if len(daily) >= 2:
        fig = px.line(
            pd.DataFrame({"日期": [d["draw_date"] for d in daily],
                          "累積損益": [d["cumulative"] for d in daily]}),
            x="日期", y="累積損益", markers=True, title="累積損益走勢(兩種下法合計)")
        fig.add_hline(y=0, line_dash="dash", line_color="#888")
        st.plotly_chart(fig, theme=None, width="stretch", key="cum_chart_totals")

    st.markdown("**回本要下幾車 — 兩種下法對照**")
    if cum >= 0:
        st.success(f"目前總損益 {cum:+,.0f},沒有虧損要追。")
        return
    rec = _recovery_rows(cfgs, cum, None)
    st.dataframe(_recovery_df(rec), width="stretch", hide_index=True)
    ok = [r for r in rec if r["_cost"] != float("inf")]
    if ok:
        best = min(ok, key=lambda r: r["_cost"])
        st.info(
            f"要一次把 {-cum:,.0f} 追回來,最省的是 **{best['遊戲']}·{best['下法']}**:"
            f"{best['回本車數']},成本 {best['本局成本']}。")
    _note(_RECOVERY_NOTE, "這張表怎麼算的")


# ── 策略頁主體 ───────────────────────────────────────────
def page_strategy(user: str):
    st.header("二合買牌")
    _note(
        "- 三個分頁:🟢 **單顆下注**、🟠 **多顆下注**、📊 **總損益**。"
        "兩個下注頁的底色與按鈕顏色不一樣,別下錯頁。\n"
        "- 下注、回填、紀錄、清除、建議車數**全部跟著你所在的分頁走**,"
        "互不干擾 —— 清單顆不會動到多顆。\n"
        "- **每種下法各算各的累積**:單顆頁的建議車數只追單顆的虧損,"
        "多顆頁只追多顆的。兩者合起來的數字看「📊 總損益」那頁。\n"
        "- 多顆中得勤但回本慢,單顆中得少但一中就整碗端回去。\n"
        "- 建議車數依「合併累積虧損 + 今天要花的總成本」計算 —— "
        "所以多下一款,大家的車數都會變多。\n"
        "- 中獎顆數可以先填,也可以開獎後再回填。",
        "這頁怎麼用")

    st.markdown(_MODE_CSS, unsafe_allow_html=True)
    cfgs = {g.key: _game_settings(user, g) for g in GAME_LIST}
    rows = storage.load_rounds(user)
    cum = storage.current_cumulative(user)
    counts = {m: sum(1 for r in rows if r["mode"] == m) for m in storage.MODES}

    # 一層 tab:兩種下法各自獨立(下注 / 回填 / 紀錄 / 建議車數都跟著它),
    # 再加一個看合計的總損益頁。
    labels = [f"{MODE_THEME[m]['emoji']} {storage.MODE_NAMES[m]}下注({counts[m]})"
              for m in storage.MODES] + ["📊 總損益"]
    # 給 key 讓分頁記住選了哪一頁 —— 否則每次重跑(記帳、開關號碼盤、改車數)
    # 都會跳回第一頁,人在多顆頁操作卻被彈回單顆頁。
    tabs = st.tabs(labels, key="mode_tabs")

    for tab, mode in zip(tabs, storage.MODES):
        with tab, st.container(key=f"mode_{mode}"):
            _mode_banner(mode)
            if mode == storage.SINGLE:
                _single_intro(cfgs)
            # 建議車數用「這一種下法自己的累積」,不被另一種的盈虧帶偏
            mode_rows = storage.load_rounds(user, mode)
            mode_cum = storage.current_cumulative(user, mode)
            _render_today(user, cfgs, mode_cum, mode=mode)
            st.divider()
            _render_pending(mode_rows)
            _render_mode_records(user, mode, mode_rows)
            # 多顆頁不放回本試算 —— 「📊 總損益」那頁的對照表已經涵蓋
            if mode == storage.SINGLE:
                st.divider()
                _render_mode_recovery(cfgs, mode_cum, mode)

    with tabs[-1], st.container(key="mode_totals"):
        _render_totals_tab(user, cfgs, cum, rows)

    if any(autoupdate.status(g.key).get("running") for g in GAME_LIST):
        st.caption("開獎資料背景補抓中…(關閉網頁也會繼續)")
    _note(
        "回本車數只是算術,改變不了每局的負期望。\n\n"
        "連敗時虧損是**幾何成長**:每敗一局,虧損乘以 1/(1−k)。"
        "k 主要由「押幾顆」決定 —— 押越多顆、下越多款,k 越接近 1,"
        "車數與成本就爆炸性上升,可承受的連敗次數也急速縮短。\n\n"
        "長期而言仍是淨輸,且有破產風險。詳細推導見側邊欄「說明 / 算式」。",
        "誠實提醒(必讀)")


# ── 排行榜:各帳號的合併損益 ──────────────────────────────
def page_leaderboard(current_user: str):
    st.header("排行榜")
    st.caption("各帳號在二合買牌三款合併後的累積損益。")

    entries = [e for e in storage.latest_cumulatives() if e["account"]]
    if not entries:
        st.info("目前還沒有任何帳號的下注紀錄。")
        return

    entries.sort(key=lambda d: d["cumulative"], reverse=True)
    st.dataframe(pd.DataFrame([{
        "名次": i + 1,
        "帳號": f"{e['account']}(你)" if e["account"] == current_user else e["account"],
        "累積損益": f"{e['cumulative']:+,.0f}",
        "投入成本": f"{e['cost']:,.0f}",
        "報酬率": f"{e['cumulative'] / e['cost']:+.1%}" if e["cost"] else "—",
        "局數": e["rounds"],
    } for i, e in enumerate(entries)]), width="stretch", hide_index=True)

    top = entries[:10]
    fig = px.bar(
        pd.DataFrame({"帳號": [e["account"] for e in top],
                      "累積損益": [e["cumulative"] for e in top]}),
        x="帳號", y="累積損益", title=f"合併累積損益排名(前 {len(top)} 名)",
        color="累積損益", color_continuous_scale=["#e63946", "#457b9d"])
    st.plotly_chart(fig, theme=None, width="stretch")

    with st.expander("我的分款戰績"):
        by_game = storage.totals_by_game(current_user)
        if by_game:
            st.dataframe(pd.DataFrame([{
                "遊戲": g.name + ("(已停用)" if not games.is_active(g.key) else ""),
                "局數": by_game[g.key]["rounds"],
                "投入": f"{by_game[g.key]['cost']:,.0f}",
                "回收": f"{by_game[g.key]['payout']:,.0f}",
                "損益": f"{by_game[g.key]['net']:+,.0f}",
            } for g in _history_games(by_game)]), width="stretch", hide_index=True)
        else:
            st.caption("你還沒有任何紀錄。")

    st.error(
        "誠實提醒:排行榜只是過去結果的比較,二合長期期望為負,"
        "排名高僅代表運氣好,不代表方法有效或未來會繼續贏。"
    )


# ── 設定頁:盤口 + 開獎資料 ───────────────────────────────
def page_settings(user: str):
    st.header("設定")
    tab_odds, tab_data = st.tabs(["盤口設定", "開獎資料"])

    with tab_odds:
        _note(
            "這裡設定你跟組頭的盤口。**「押幾顆」是成本的主要槓桿** —— "
            "它直接決定成本係數 k = 押幾顆 × 每車成本 ÷ 中獎可得,"
            "而連敗時虧損每局乘以 1/(1−k)。顆數越多、款數越多,k 越接近 1,"
            "車數與成本就爆炸性上升。")
        cfgs = {g.key: _game_settings(user, g) for g in GAME_LIST}
        for g in GAME_LIST:
            cfg, skey = cfgs[g.key], cfgs[g.key]["skey"]
            dan = g.dan_prob
            st.markdown(
                f"**{g.name}** — {g.num_max}選{g.pick},1 膽拖 {g.notes_per_car} 號 = 1 車"
                f"({g.notes_per_car} 注),膽中機率 {dan:.2%}"
            )
            c1, c2, c3, c4 = st.columns(4)
            kc, kw = f"set_cost_{g.key}", f"set_pay_{g.key}"
            kn, kb = f"set_n_{g.key}", f"set_base_{g.key}"
            c1.number_input("每車成本", min_value=1.0, max_value=1_000_000.0,
                            value=cfg["cost_per_car"], step=5.0, key=kc,
                            on_change=_persist_setting, args=(skey, "cost_per_car", kc))
            c2.number_input("中獎可得(每車中時)", min_value=1.0, max_value=10_000_000.0,
                            value=cfg["win_payout"], step=100.0, key=kw,
                            on_change=_persist_setting, args=(skey, "win_payout", kw))
            c3.number_input("押幾顆", min_value=1, max_value=20,
                            value=cfg["n_numbers"], step=1, key=kn,
                            on_change=_persist_setting, args=(skey, "n_numbers", kn))
            c4.number_input("回本後起始車數", min_value=1, max_value=20,
                            value=cfg["base"], step=1, key=kb,
                            on_change=_persist_setting, args=(skey, "base", kb))
            ev = erhe.car_ev_rate(cfg["cost_per_car"], cfg["win_payout"], dan)
            st.caption(
                f"期望報酬率/車 {ev:+.2%};損益兩平中獎金額 "
                f"{cfg['cost_per_car'] / dan:,.0f}(目前 {cfg['win_payout']:,.0f})"
            )
            st.divider()

        odds = {g.key: (cfgs[g.key]["cost_per_car"], cfgs[g.key]["win_payout"])
                for g in GAME_LIST}
        n = len(GAME_LIST)
        st.info(
            "以目前盤口,「中 1 顆就回本」(嚴格)的押顆數上限:"
            + "、".join(
                f"只下{g.name} {erhe.max_numbers_for_combo({g.key: odds[g.key]})} 顆"
                for g in GAME_LIST)
            + f";{n} 款同下每款 {erhe.max_numbers_for_combo(odds)} 顆"
            + f"(改用平攤則放寬到 {erhe.max_numbers_for_combo(odds, margin=n * 0.999)} 顆)。"
        )

    with tab_data:
        st.caption("三款開獎資料各自獨立維護;回報下注時也會在背景自動補抓。")
        for i, game in enumerate(GAME_LIST):
            _update_one_game(game)
            if i < len(GAME_LIST) - 1:
                st.divider()


# ── 帳號登入 / 註冊(cookie 持久登入)──────────────────────
_COOKIE_NAME = "auth_token"
_COOKIE_PATH = "/539"


def _write_auth_cookie(token: str):
    """把登入 token 寫進瀏覽器 cookie(預設 30 天),重整後自動還原登入。"""
    max_age = 60 * 60 * 24 * auth.TOKEN_DAYS
    cookie = (
        f"{_COOKIE_NAME}={token}; path={_COOKIE_PATH}; "
        f"max-age={max_age}; samesite=lax"
    )
    components.html(
        f"<script>var c={cookie!r};"
        "try{window.parent.document.cookie=c;}catch(e){document.cookie=c;}</script>",
        height=0,
    )


def _clear_auth_cookie():
    """清除登入 cookie(登出時)。"""
    cookie = f"{_COOKIE_NAME}=; path={_COOKIE_PATH}; max-age=0"
    components.html(
        f"<script>var c={cookie!r};"
        "try{window.parent.document.cookie=c;}catch(e){document.cookie=c;}</script>",
        height=0,
    )


def _restore_login_from_cookie():
    """重整 / 重開分頁時,從 cookie 還原登入狀態(無須重新輸入)。

    注意:st.context.cookies 取自連線當下的請求標頭,同一個 session 內登出後
    它仍會看到舊 cookie,故以 _logged_out 旗標避免登出後又被自動還原。
    """
    if st.session_state.get("user") or st.session_state.get("_logged_out"):
        return
    try:
        token = st.context.cookies.get(_COOKIE_NAME)
    except Exception:
        token = None
    user = auth.verify_token(token) if token else None
    if user:
        st.session_state["user"] = user


def _logout():
    """登出:清除登入狀態 + 標記清除 cookie,並抑制本 session 的自動還原。"""
    st.session_state.pop("user", None)
    st.session_state["_logged_out"] = True
    st.session_state["_logout_pending"] = True


def _login_gate() -> bool:
    """未登入時顯示登入/註冊表單;已登入回 True。

    各帳號的二合累積損益、倍頭進程與凱莉對照設定完全獨立(以帳號命名空間隔離)。
    登入狀態以 cookie 持久保存,重整頁面 / 重開分頁都不必再輸入。
    """
    _restore_login_from_cookie()
    if st.session_state.get("user"):
        return True

    # 登出後清除瀏覽器 cookie
    if st.session_state.pop("_logout_pending", False):
        _clear_auth_cookie()

    st.title("彩券統計分析 — 登入")
    st.caption("各帳號的二合累積損益、倍頭進程與凱莉對照完全獨立、互不干擾。")
    tab_login, tab_reg = st.tabs(["登入", "註冊(需邀請碼)"])

    with tab_login:
        u = st.text_input("帳號", key="login_user")
        p = st.text_input("密碼", type="password", key="login_pw")
        if st.button("登入", type="primary", key="login_btn"):
            if auth.verify(u, p):
                st.session_state["user"] = u.strip()
                st.session_state.pop("_logged_out", None)  # 解除登出抑制
                # 標記待寫入 cookie,登入後保持 30 天免重複輸入
                st.session_state["_login_token"] = auth.make_token(u.strip())
                st.rerun()
            else:
                st.error("帳號或密碼錯誤。")

    with tab_reg:
        st.caption("註冊需要邀請碼,取得後才能建立新帳號。")
        ru = st.text_input("帳號(至少 2 字元)", key="reg_user")
        rp = st.text_input("密碼(至少 4 字元)", type="password", key="reg_pw")
        rp2 = st.text_input("確認密碼", type="password", key="reg_pw2")
        code = st.text_input("邀請碼", key="reg_code")
        if st.button("註冊", type="primary", key="reg_btn"):
            if rp != rp2:
                st.error("兩次輸入的密碼不一致。")
            else:
                ok, msg = auth.register(ru, rp, code)
                (st.success if ok else st.error)(msg)

    return False


# ── 主程式 ────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="彩券統計分析(539 / 天天樂 / 六合彩)",
                       page_icon="", layout="wide")
    if not _login_gate():
        return
    # 剛登入:把 token 寫進 cookie(重整 / 重開分頁自動保持登入)
    token = st.session_state.pop("_login_token", None)
    if token:
        _write_auth_cookie(token)
    user = st.session_state.get("user", "")
    nav = sidebar_controls()

    # 說明 / 算式頁(由側邊欄按鈕觸發,覆蓋主畫面;點任一導覽即返回)
    if st.session_state.get("show_docs"):
        docs.render()
        return

    if nav == "二合買牌":
        page_strategy(user)
    elif nav == "統計分析":
        page_stats()
    elif nav == "匯出":
        page_export()
    elif nav == "排行榜":
        page_leaderboard(user)
    elif nav == "設定":
        page_settings(user)


if __name__ == "__main__":
    main()
