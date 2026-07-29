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

from core import auth, backtest, constants, erhe, excel_report, games, kelly, picker
from core import autoupdate, scraper, scraper_fantasy5, scraper_marksix, stats, storage
from core.loader import DataError, load_history, merge, save
from ui import docs


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
NAV_ITEMS = [
    "🎯 二合買牌(策略1)",
    "📊 統計分析",
    "🏆 排行榜",
    "🔄 更新資料",
]


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
@media (max-width: 640px) {
  html, body, .stApp, .stMarkdown, .stApp p, .stApp li { font-size: 18px !important; }
  .block-container { padding: 2.8rem 0.6rem 1rem 0.6rem !important; }
  [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
  [data-testid="stMetricLabel"] { font-size: 1rem !important; }
  [data-testid="stDataFrame"], [data-testid="stTable"] { font-size: 16px !important; }
  button[data-baseweb="tab"] { font-size: 0.95rem !important; padding: 0.3rem 0.55rem !important; }
  h1 { font-size: 1.7rem !important; } h2 { font-size: 1.4rem !important; }
  h3 { font-size: 1.2rem !important; }
  .stButton button { font-size: 1.05rem !important; padding: 0.55rem !important; }
}
</style>
"""


def _apply_theme():
    """套用主題:預設亮色(原生);深色模式開關;手機放大字級。"""
    import plotly.io as pio

    st.markdown(_MOBILE_CSS, unsafe_allow_html=True)  # 手機放大,永遠套用
    dark = st.sidebar.toggle("🌙 深色模式", value=False, key="dark_mode")
    pio.templates.default = "plotly_dark" if dark else "plotly_white"
    if dark:
        st.markdown(_DARK_CSS, unsafe_allow_html=True)


def sidebar_controls() -> str:
    """繪製側邊欄(不再有全域遊戲切換),回傳目前的導覽選項。"""
    st.sidebar.title("彩券統計分析")
    user = st.session_state.get("user", "")
    if user:
        uc1, uc2 = st.sidebar.columns([2, 1])
        uc1.caption(f"👤 {user}")
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
        st.sidebar.caption(f"{g.emoji} {g.name} — {len(d)} 期,最新 {latest}")

    with st.sidebar.expander("免責聲明(必讀)", expanded=False):
        st.write(constants.DISCLAIMER)
        for g in games.GAMES.values():
            st.caption(f"**{g.name}**({g.num_max}選{g.pick}):{g.prize_note}")
            st.caption(f"　來源:{g.source_note}")

    # 說明 / 算式按鈕:供他人研究與驗算所有統計與凱莉公式
    st.sidebar.button(
        "📖 說明 / 算式(供驗算)",
        width="stretch",
        on_click=lambda: st.session_state.update(show_docs=True),
        help="列出所有統計算式與凱莉公式,連同實際常數值供研究驗算。",
    )
    return nav


def _range_selector(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """頁內的分析範圍選擇(全部 / 最近 N 期 / 日期範圍),回傳篩選後資料。"""
    sorted_df = df.sort_values("date").reset_index(drop=True)
    if sorted_df.empty:
        return sorted_df
    c1, c2 = st.columns([1, 2])
    mode = c1.radio("分析範圍", ["全部", "最近 N 期", "日期範圍"], key=f"{key}_mode")
    with c2:
        if mode == "最近 N 期":
            n = st.number_input("最近期數 N", min_value=1, max_value=len(sorted_df),
                                value=min(100, len(sorted_df)), step=10, key=f"{key}_n")
            fdf = sorted_df.tail(int(n))
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
    st.header("📊 統計分析")
    gkey = st.segmented_control(
        "看哪一款", [g.key for g in games.GAMES.values()],
        default=games.DEFAULT_GAME.key,
        format_func=lambda k: f"{games.get(k).emoji} {games.get(k).name}",
        key="stats_game",
    ) or games.DEFAULT_GAME.key
    game = games.get(gkey)
    fdf = _range_selector(load_df(gkey), f"stats_{gkey}")
    _render_stats(fdf, game)


def _render_stats(fdf: pd.DataFrame, game):
    nmax = game.num_max
    n_bands = len(stats.tens_bands(nmax))
    st.subheader(f"{game.emoji} {game.name}")
    st.caption(f"玩法規格:{nmax} 選 {game.pick};以下統計皆依此規格計算。")
    if fdf.empty:
        st.warning("目前範圍沒有資料,請調整側邊欄的範圍選擇。")
        return

    tabs = st.tabs(
        ["號碼頻率", "冷熱號", "遺漏值", "間隔/連號", "奇偶/大小/和值",
         f"星數統計({n_bands}興)", "卡方檢定", "共現配對"]
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
        st.caption(
            f"星數 = 每期開出的 {game.pick} 顆落在「幾個不同的十位區段」"
            f"({' / '.join(bands)})。同一段內重複(如 10、11 都在 10~19)只算 1 星,"
            f"所以星數介於 1~{n_bands} 星。"
        )
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
    st.markdown(f"**{game.emoji} {game.name}** — {game.num_max}選{game.pick}|"
                f"目前 {len(df)} 期,最新 {latest}")
    st.caption(f"來源:{game.source_note}")

    c1, c2 = st.columns([2, 1])
    with c2:
        st.download_button(
            f"📥 匯出 CSV({len(df)} 期)",
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
    """共用的抓取→合併→存檔流程。"""
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


def page_update():
    st.header("🔄 更新資料")
    st.caption("三款開獎資料各自獨立維護;回報下注時也會在背景自動補抓。")
    for i, game in enumerate(games.GAMES.values()):
        _update_one_game(game)
        if i < len(games.GAMES) - 1:
            st.divider()


# ── 6. Excel 匯出 ─────────────────────────────────────────
def page_export(fdf: pd.DataFrame, game):
    st.header(f"Excel 匯出 — {game.name}")
    if fdf.empty:
        st.warning("目前範圍沒有資料,無法匯出。")
        return

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
GAME_LIST = list(games.GAMES.values())


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


def _label(g) -> str:
    return f"{g.emoji} {g.name}"


# ── 1. 合併戰績 ──────────────────────────────────────────
def _render_scoreboard(tot: dict):
    """頂部 KPI:整個帳號(三款合計)的成本、回收、損益。"""
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "累積損益", f"{tot['net']:+,.0f}",
        delta="虧損中" if tot["net"] < 0 else "獲利中",
        delta_color="inverse" if tot["net"] < 0 else "normal",
    )
    c2.metric("總投入成本", f"{tot['cost']:,.0f}")
    c3.metric("總回收", f"{tot['payout']:,.0f}")
    c4.metric("報酬率", f"{tot['roi']:+.1%}" if tot["cost"] else "—")
    c5.metric(
        "局數 / 勝率",
        f"{tot['rounds']} 局",
        delta=f"中獎 {tot['wins']} 局({tot['win_rate']:.0%})" if tot["settled"] else "尚未對獎",
        delta_color="off",
    )
    if tot["pending"]:
        st.info(
            f"其中 {tot['pending']} 筆還沒回填中獎顆數 —— 成本已計入累積損益,"
            "回填後回收才會加回來。"
        )


# ── 2. 待回填中獎顆數 ─────────────────────────────────────
def _render_pending(rows: list[dict]):
    pend = [r for r in rows if r["pending"]]
    if not pend:
        return
    with st.expander(f"⏳ 待回填中獎顆數({len(pend)} 筆)", expanded=True):
        st.caption("開獎後回來把「重幾顆」填上,回收會依當初下注的盤口自動結算。")
        for r in pend:
            g = games.get(r["game"])
            c1, c2, c3 = st.columns([5, 2, 1.4])
            c1.markdown(
                f"**{r['draw_date']}** · {_label(g)} · {int(r['cars'])} 車 × 押 "
                f"{int(r['numbers'])} 顆 · 成本 {r['cost']:,.0f} · "
                f"每中 1 顆 +{int(r['cars']) * float(r['payout_rate'] or 0):,.0f}"
            )
            hit = c2.number_input(
                "重幾顆", min_value=0, max_value=int(r["numbers"]), value=0,
                key=f"fill_hits_{r['id']}", label_visibility="collapsed",
            )
            if c3.button("回填", key=f"fill_btn_{r['id']}", type="primary"):
                storage.update_round_result(int(r["id"]), int(hit))
                st.rerun()


# ── 3. 本局建議下注 ───────────────────────────────────────
def _render_suggestion(user: str, cfgs: dict, cum: float) -> dict:
    """依合併累積損益算本局建議;回傳 {遊戲代號: 建議車數} 供回報表單帶入預設值。"""
    st.subheader("📌 本局建議下注")
    st.caption(
        "車數目標:**中 1 顆就把「合併累積虧損 + 本局成本」全部拿回來**。"
        "已回本時回到各款設定的起始車數。"
    )
    mode = st.radio(
        "下注方式",
        ["🎯 今天只打一款", "🧮 今天同時打多款"],
        horizontal=True, key="sug_mode",
        help="兩者的車數算法不同:只打一款時本局成本只有那一款;"
             "同時打多款時,任何一款中獎都要先扣掉當天全部的下注成本。",
    )

    if mode.startswith("🎯"):
        rows, suggest = [], {}
        for g in GAME_LIST:
            cfg = cfgs[g.key]
            rec = erhe.next_cars_for_recovery(
                cum, cfg["n_numbers"], cfg["cost_per_car"], cfg["win_payout"],
                base_cars=cfg["base"])
            cars, ok = rec["next_cars"], rec["next_cars"] != float("inf")
            suggest[g.key] = int(cars) if ok else cfg["base"]
            gross = cars * cfg["win_payout"] if ok else 0.0
            after = cum + gross - rec["next_cost"] if ok else float("-inf")
            hd = erhe.hit_distribution(cfg["n_numbers"], g.pick, g.num_max)
            rows.append({
                "遊戲": _label(g),
                "玩法": f"{g.num_max}選{g.pick}",
                "押幾顆": cfg["n_numbers"],
                "建議車數": f"{int(cars)} 車" if ok else "無法回本",
                "本局成本": f"{rec['next_cost']:,.0f}" if ok else "—",
                "中1顆可得": f"{gross:,.0f}" if ok else "—",
                "中後累積": f"{after:+,.0f}" if ok else "—",
                "中0顆機率": f"{hd.get(0, 0):.0%}",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(
            "⚠️ 這三列是**各自獨立**的試算 —— 每一列都假設「今天只打這一款」。"
            "若你三款都下,任何一款中 1 顆都不足以回本(成本是三份、回收只有一份),"
            "請改用上面的「今天同時打多款」。"
        )
        return suggest

    # 同時打多款:聯立求解
    picked = st.multiselect(
        "今天要打哪幾款", [g.key for g in GAME_LIST],
        default=[g.key for g in GAME_LIST],
        format_func=lambda k: _label(games.get(k)), key="sug_combo",
    )
    if not picked:
        st.info("請至少選一款。")
        return {g.key: cfgs[g.key]["base"] for g in GAME_LIST}

    plans = {k: (cfgs[k]["n_numbers"], cfgs[k]["cost_per_car"], cfgs[k]["win_payout"])
             for k in picked}
    base = max(cfgs[k]["base"] for k in picked)
    res = erhe.simultaneous_recovery(cum, plans, base_cars=base)

    k_val = res["k"]
    st.caption(
        f"成本係數 k = Σ(押幾顆 × 每車成本 ÷ 中獎可得) = **{k_val:.3f}**"
        "(k ≥ 1 就無解:本局成本永遠追不上單一款的回收)。"
    )
    if not res["feasible"]:
        odds = {k: (cfgs[k]["cost_per_car"], cfgs[k]["win_payout"]) for k in picked}
        n_max = erhe.max_numbers_for_combo(odds)
        st.error(
            f"**k = {k_val:.3f} ≥ 1 → 這個組合無解。**"
            f"同時下這 {len(picked)} 款、每款各押目前的顆數,不管加到幾車,"
            "「中 1 顆」的回收都追不回當天的總成本。"
        )
        if n_max >= 1:
            st.warning(
                f"要讓「任一款中 1 顆即回本」成立,這 {len(picked)} 款**每款最多押 "
                f"{n_max} 顆**(到下方「三款盤口設定」把押幾顆改小),"
                "或是改成今天只打一款。"
            )
        else:
            st.warning("這個組合連每款押 1 顆都無解,今天請只打一款。")
        return {g.key: cfgs[g.key]["base"] for g in GAME_LIST}

    cars = res["cars"]
    m1, m2, m3 = st.columns(3)
    m1.metric("本局總成本(全下)", f"{res['total_cost']:,.0f}")
    m2.metric("最壞情況中後累積", f"{res['worst_after']:+,.0f}",
              delta="任一款中 1 顆都回本 ✅" if res["worst_after"] >= 0 else "仍未回本",
              delta_color="normal" if res["worst_after"] >= 0 else "inverse")
    m3.metric("目前累積損益", f"{cum:+,.0f}")

    rows = []
    for k in picked:
        g, cfg = games.get(k), cfgs[k]
        cost = cfg["n_numbers"] * cars[k] * cfg["cost_per_car"]
        gross = cars[k] * cfg["win_payout"]
        rows.append({
            "遊戲": _label(g),
            "押幾顆": cfg["n_numbers"],
            "建議車數": f"{cars[k]} 車",
            "該款成本": f"{cost:,.0f}",
            "中1顆可得": f"{gross:,.0f}",
            "扣全部成本後累積": f"{cum + gross - res['total_cost']:+,.0f}",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption(
        "「扣全部成本後累積」= 目前累積 + 該款中 1 顆的回收 − 當天三款的總成本。"
        "全部 ≥ 0 才代表不管中哪一款都回本。"
    )
    out = {g.key: cfgs[g.key]["base"] for g in GAME_LIST}
    out.update({k: int(v) for k, v in cars.items()})
    return out


# ── 4. 回報下注 ──────────────────────────────────────────
def _render_report_form(user: str, cfgs: dict, suggest: dict, has_rows: bool):
    st.subheader("📝 回報下注")
    gkey = st.segmented_control(
        "遊戲", [g.key for g in GAME_LIST], default=GAME_LIST[0].key,
        format_func=lambda k: _label(games.get(k)), key="rep_game",
    ) or GAME_LIST[0].key
    g, cfg = games.get(gkey), cfgs[gkey]
    st.caption(
        f"{_label(g)} — 每車成本 {cfg['cost_per_car']:,.0f}、中獎可得 "
        f"{cfg['win_payout']:,.0f}、1 車 = {g.notes_per_car} 注"
    )

    with st.form("report_form", clear_on_submit=False):
        c1, c2, c3, c4 = st.columns([1.4, 1, 1, 1])
        draw_date = c1.date_input("下注日期", value=dt.date.today(), format="YYYY-MM-DD")
        cars = c2.number_input("下注車數", min_value=1, max_value=100_000,
                               value=int(suggest.get(gkey, cfg["base"])), step=1)
        n_numbers = c3.number_input("押幾顆", min_value=1, max_value=20,
                                    value=int(cfg["n_numbers"]), step=1)
        hits = c4.number_input("中獎顆數(可留空)", min_value=0, max_value=20,
                               value=None, step=1,
                               placeholder="還沒開獎就留空")
        cost = float(n_numbers) * float(cars) * cfg["cost_per_car"]
        st.caption(
            f"本局成本 = {int(n_numbers)} 顆 × {int(cars)} 車 × {cfg['cost_per_car']:,.0f} "
            f"= **{cost:,.0f}**;每中 1 顆回收 {cars * cfg['win_payout']:,.0f}。"
        )
        submitted = st.form_submit_button("✅ 送出這一筆", type="primary", width="stretch")

    if submitted:
        if hits is not None and int(hits) > int(n_numbers):
            st.error(f"中獎顆數 {int(hits)} 不可能大於押的顆數 {int(n_numbers)},請確認後再送出。")
            return
        if int(n_numbers) != cfg["n_numbers"]:
            # 記住新顆數;丟掉盤口設定 widget 的舊狀態,讓它下次從資料庫重新初始化
            storage.set_setting(cfg["skey"], "n_numbers", int(n_numbers))
            st.session_state.pop(f"set_n_{gkey}", None)
        storage.add_round(
            user, gkey, draw_date.isoformat(), int(n_numbers), int(cars),
            None if hits is None else int(hits), cost, cfg["win_payout"],
        )
        _kick_autoupdate(g)
        st.rerun()

    b1, b2 = st.columns(2)
    if b1.button("↩️ 撤銷剛剛輸入的那筆", disabled=not has_rows, width="stretch",
                 help="刪除最後寫入的一筆(不論日期),累積損益自動重算 —— 可放心試算。"):
        storage.undo_last_round(user)
        st.rerun()
    if b2.button("🗑️ 重置全部紀錄", disabled=not has_rows, width="stretch"):
        st.session_state["confirm_reset"] = True
    if st.session_state.get("confirm_reset"):
        st.warning("確定要清除這個帳號**全部三款**的下注紀錄嗎?此動作無法復原。")
        r1, r2 = st.columns(2)
        if r1.button("確定清除", type="primary"):
            storage.reset(user)
            st.session_state.pop("confirm_reset", None)
            st.rerun()
        if r2.button("取消"):
            st.session_state.pop("confirm_reset", None)
            st.rerun()


# ── 5. 盤口設定 ──────────────────────────────────────────
def _render_odds_settings(cfgs: dict):
    with st.expander("⚙️ 三款盤口設定(每車成本 / 中獎可得 / 押幾顆 / 起始車數)"):
        for g in GAME_LIST:
            cfg = cfgs[g.key]
            skey = cfg["skey"]
            dan = g.dan_prob
            ev = erhe.car_ev_rate(cfg["cost_per_car"], cfg["win_payout"], dan)
            st.markdown(
                f"**{_label(g)}** — {g.num_max}選{g.pick},1 膽拖 {g.notes_per_car} 號 = 1 車"
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
            fair = cfg["cost_per_car"] / dan
            (st.success if ev >= 0 else st.caption)(
                f"期望報酬率/車 {ev:+.2%};損益兩平中獎金額 {fair:,.0f}"
                f"(目前 {cfg['win_payout']:,.0f})"
            )
            st.divider()


# ── 6. 流水帳 ────────────────────────────────────────────
def _render_ledger(user: str, rows: list[dict]):
    st.subheader("📒 下注流水")
    if not rows:
        st.info("還沒有任何紀錄。用上面的「回報下注」送出第一筆吧。")
        return

    tab_day, tab_all, tab_game = st.tabs(["每日彙總", "逐筆明細", "分款統計"])

    with tab_day:
        daily = storage.totals_by_date(user)
        day_df = pd.DataFrame([{
            "日期": d["draw_date"],
            "筆數": d["rounds"],
            "當日成本": f"{d['cost']:,.0f}",
            "當日回收": f"{d['payout']:,.0f}",
            "當日損益": f"{d['net']:+,.0f}",
            "累積損益": f"{d['cumulative']:+,.0f}",
        } for d in daily])
        st.dataframe(day_df, width="stretch", hide_index=True)
        if len(daily) >= 2:
            fig = px.line(
                pd.DataFrame({"日期": [d["draw_date"] for d in daily],
                              "累積損益": [d["cumulative"] for d in daily]}),
                x="日期", y="累積損益", markers=True, title="累積損益走勢(三款合併)",
            )
            fig.add_hline(y=0, line_dash="dash", line_color="#888")
            st.plotly_chart(fig, theme=None, width="stretch")

    with tab_all:
        detail = pd.DataFrame([{
            "#": i + 1,
            "日期": r["draw_date"],
            "遊戲": _label(games.get(r["game"])),
            "車數": int(r["cars"]),
            "押幾顆": int(r["numbers"]),
            "重幾顆": "⏳ 待回填" if r["pending"] else f"{int(r['hits'])} 顆",
            "成本": f"{r['cost']:,.0f}",
            "回收": f"{r['payout']:,.0f}",
            "本局損益": f"{r['net']:+,.0f}",
            "累積損益": f"{r['cumulative']:+,.0f}",
        } for i, r in enumerate(rows)])
        st.dataframe(detail, width="stretch", hide_index=True)
        st.download_button(
            "📥 下載流水 CSV",
            data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
            file_name="erhe_ledger.csv", mime="text/csv",
        )
        with st.expander("✏️ 修改 / 刪除指定的一筆"):
            opts = {
                f"#{i + 1} {r['draw_date']} {games.get(r['game']).name} "
                f"{int(r['cars'])}車 損益{r['net']:+,.0f}": r
                for i, r in enumerate(rows)
            }
            choice = st.selectbox("選一筆", list(opts), key="edit_pick")
            row = opts[choice]
            e1, e2, e3 = st.columns([1.4, 1, 1])
            new_date = e1.date_input(
                "改日期", value=dt.date.fromisoformat(row["draw_date"]),
                format="YYYY-MM-DD", key="edit_date")
            new_hits = e2.number_input(
                "改中獎顆數", min_value=0, max_value=int(row["numbers"]),
                value=0 if row["pending"] else int(row["hits"]), key="edit_hits")
            e3.markdown("&nbsp;", unsafe_allow_html=True)
            if e3.button("💾 套用", key="edit_apply", width="stretch"):
                storage.update_round_result(int(row["id"]), int(new_hits))
                storage.set_round_date(int(row["id"]), new_date.isoformat())
                st.rerun()
            if st.button("🗑️ 刪除這一筆", key="edit_del"):
                storage.delete_round(int(row["id"]))
                st.rerun()

    with tab_game:
        by_game = storage.totals_by_game(user)
        gm_rows = []
        for g in GAME_LIST:
            t = by_game.get(g.key)
            if not t:
                continue
            settled = t["rounds"] - t["pending"]
            gm_rows.append({
                "遊戲": _label(g),
                "局數": t["rounds"],
                "中獎局": t["wins"],
                "勝率": f"{t['wins'] / settled:.0%}" if settled else "—",
                "投入成本": f"{t['cost']:,.0f}",
                "回收": f"{t['payout']:,.0f}",
                "損益": f"{t['net']:+,.0f}",
                "報酬率": f"{t['net'] / t['cost']:+.1%}" if t["cost"] else "—",
            })
        if gm_rows:
            st.dataframe(pd.DataFrame(gm_rows), width="stretch", hide_index=True)
            chart = pd.DataFrame({
                "遊戲": [r["遊戲"] for r in gm_rows],
                "損益": [by_game[g.key]["net"] for g in GAME_LIST if g.key in by_game],
            })
            fig = px.bar(chart, x="遊戲", y="損益", title="各款累積損益", color="損益",
                         color_continuous_scale=["#e63946", "#457b9d"])
            st.plotly_chart(fig, theme=None, width="stretch")
        else:
            st.info("還沒有分款資料。")


# ── 策略頁主體 ───────────────────────────────────────────
def page_strategy(user: str):
    st.header("🎯 二合買牌(策略1)")
    st.caption(
        "三款遊戲共用**同一個損益池**:不管今天打哪一款,盈虧都累加在一起,"
        "建議車數也依「合併累積虧損」計算。"
    )

    cfgs = {g.key: _game_settings(user, g) for g in GAME_LIST}
    tot = storage.totals(user)
    rows = storage.load_rounds(user)
    cum = storage.current_cumulative(user)

    _render_scoreboard(tot)
    _render_pending(rows)
    st.divider()
    suggest = _render_suggestion(user, cfgs, cum)
    st.divider()
    _render_report_form(user, cfgs, suggest, bool(rows))
    _render_odds_settings(cfgs)
    st.divider()
    _render_ledger(user, rows)

    au_msgs = [autoupdate.status(g.key) for g in GAME_LIST]
    if any(a.get("running") for a in au_msgs):
        st.caption("🔄 開獎資料背景補抓中…(關閉網頁也會繼續)")

    st.error(
        "誠實提醒:合併損益池與回本車數都只是**算術**,改變不了每局的負期望。"
        "「中 1 顆回本」的代價是沒中時要一直加碼,連敗時下注額指數成長,"
        "長期(含偶爾連敗)仍是淨輸,且有破產風險。"
    )


# ── 排行榜:各帳號的合併損益 ──────────────────────────────
def page_leaderboard(current_user: str):
    st.header("🏆 排行榜 — 誰賺最多")
    st.caption("彙整各帳號在「二合買牌(策略1)」三款合併後的累積損益。")

    entries = [e for e in storage.latest_cumulatives() if e["account"]]
    if not entries:
        st.info("目前還沒有任何帳號的下注紀錄。到「二合買牌(策略1)」回報幾筆後就會出現排名。")
        return

    entries.sort(key=lambda d: d["cumulative"], reverse=True)
    medals = {0: "🥇", 1: "🥈", 2: "🥉"}
    table_rows = []
    for i, e in enumerate(entries):
        name = e["account"]
        if name == current_user:
            name = f"⭐ {name}(你)"
        table_rows.append({
            "名次": medals.get(i, f"{i + 1}"),
            "帳號": name,
            "累積損益": f"{e['cumulative']:+,.0f}",
            "投入成本": f"{e['cost']:,.0f}",
            "報酬率": f"{e['cumulative'] / e['cost']:+.1%}" if e["cost"] else "—",
            "局數": e["rounds"],
        })
    st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True)

    top = entries[:10]
    fig = px.bar(
        pd.DataFrame({"帳號": [e["account"] for e in top],
                      "累積損益": [e["cumulative"] for e in top]}),
        x="帳號", y="累積損益", title=f"合併累積損益排名(前 {len(top)} 名)",
        color="累積損益", color_continuous_scale=["#e63946", "#457b9d"],
    )
    st.plotly_chart(fig, theme=None, width="stretch")

    with st.expander("我的分款戰績"):
        by_game = storage.totals_by_game(current_user)
        if by_game:
            st.dataframe(pd.DataFrame([{
                "遊戲": _label(g),
                "局數": by_game[g.key]["rounds"],
                "投入": f"{by_game[g.key]['cost']:,.0f}",
                "回收": f"{by_game[g.key]['payout']:,.0f}",
                "損益": f"{by_game[g.key]['net']:+,.0f}",
            } for g in GAME_LIST if g.key in by_game]), width="stretch", hide_index=True)
        else:
            st.caption("你還沒有任何紀錄。")

    st.error(
        "誠實提醒:排行榜只是「過去結果」的比較,二合長期期望為負,"
        "排名高僅代表運氣好,不代表方法有效或未來會繼續贏。"
    )


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

    st.title("🔐 彩券統計分析 — 登入")
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
                       page_icon="🎰", layout="wide")
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

    if nav == "🎯 二合買牌(策略1)":
        page_strategy(user)
    elif nav == "📊 統計分析":
        page_stats()
    elif nav == "🏆 排行榜":
        page_leaderboard(user)
    elif nav == "🔄 更新資料":
        page_update()


if __name__ == "__main__":
    main()
