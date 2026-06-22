"""今彩539 統計分析 Streamlit Web 應用。

把原本的 TUI 介面改造成網頁版,所有分析皆吃側邊欄「全域範圍選擇」篩選後的 fdf。

重要提醒(與 core 模組一致):今彩539 每期為獨立隨機事件,數學上無法預測,
長期期望報酬率約 -44%。本工具僅供統計學習與娛樂用途。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from core import backtest, constants, excel_report, games, kelly, picker, scraper, stats
from core import scraper_fantasy5, storage
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
    以 game_key(字串)當 cache key,讓兩款資料各自快取、互不干擾。
    """
    game = games.get(game_key)
    path = DATA_DIR / game.data_file
    bundled = _BUNDLE_DIR / game.data_file
    # 首次執行(exe 旁無資料)時,把打包內附的歷史資料複製出來(純位元組,避開 CopyFile2)。
    if not path.exists() and bundled.exists() and bundled != path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bundled.read_bytes())
    try:
        return load_history(path)
    except DataError:
        df = generate_sample_safe()
        save(df, path)
        return df


def generate_sample_safe() -> pd.DataFrame:
    """產生固定 seed 的範例資料(避開系統時鐘)。"""
    from core.loader import generate_sample

    return generate_sample(500)


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
def sidebar_controls():
    """繪製側邊欄,回傳 (game 遊戲設定, fdf 篩選後資料, 導覽選項)。"""
    st.sidebar.title("彩券統計分析")

    # 遊戲選擇(兩款統計完全分開)
    game_name = st.sidebar.radio(
        "選擇遊戲",
        [g.name for g in games.GAMES.values()],
        help="今彩539 與 天天樂(加州 Fantasy 5)各自獨立資料與統計。",
    )
    game = games.by_name(game_name)
    df = load_df(game.key)
    st.sidebar.caption(
        f"票價 {game.currency}{game.ticket_price:g}|期望報酬率約 "
        f"{game.expected_return():.2%}"
    )

    with st.sidebar.expander("免責聲明(必讀)", expanded=False):
        st.write(constants.DISCLAIMER)
        st.caption(f"{game.name}:{game.prize_note}")
        st.caption(f"資料來源:{game.source_note}")

    # 說明 / 算式按鈕:供他人研究與驗算所有統計與凱莉公式
    st.sidebar.button(
        "📖 說明 / 算式(供驗算)",
        width="stretch",
        on_click=lambda: st.session_state.update(show_docs=True),
        help="列出所有統計算式與凱莉公式,連同實際常數值供研究驗算。",
    )

    st.sidebar.markdown("### 全域範圍選擇")
    mode = st.sidebar.radio(
        "分析範圍",
        ["全部", "最近 N 期", "日期範圍"],
        help="所有分析(統計、回測、匯出)都會套用此範圍。",
    )

    sorted_df = df.sort_values("date").reset_index(drop=True)

    if mode == "全部":
        fdf = sorted_df
    elif mode == "最近 N 期":
        n = st.sidebar.number_input(
            "最近期數 N", min_value=1, max_value=len(sorted_df),
            value=min(100, len(sorted_df)), step=10,
        )
        fdf = sorted_df.tail(int(n))
    else:  # 日期範圍
        dmin = sorted_df["date"].iloc[0].date()
        dmax = sorted_df["date"].iloc[-1].date()
        start = st.sidebar.date_input("起始日", value=dmin, min_value=dmin, max_value=dmax)
        end = st.sidebar.date_input("結束日", value=dmax, min_value=dmin, max_value=dmax)
        lo, hi = (start, end) if start <= end else (end, start)
        mask = (sorted_df["date"].dt.date >= lo) & (sorted_df["date"].dt.date <= hi)
        fdf = sorted_df.loc[mask]

    fdf = fdf.reset_index(drop=True)
    st.sidebar.info(_range_label(fdf))

    st.sidebar.markdown("### 導覽")
    nav = st.sidebar.radio(
        "功能選單",
        [
            "統計分析",
            "產生參考號碼",
            "二合買牌(策略1)",
            "包牌 / 牌型 / 加碼",
            "策略回測",
            "凱莉投報計算",
            "更新資料",
            "Excel 匯出",
        ],
        label_visibility="collapsed",
        on_change=lambda: st.session_state.update(show_docs=False),
    )
    return game, fdf, nav


# ── 1. 統計分析 ───────────────────────────────────────────
def page_stats(fdf: pd.DataFrame):
    st.header("統計分析")
    if fdf.empty:
        st.warning("目前範圍沒有資料,請調整側邊欄的範圍選擇。")
        return

    tabs = st.tabs(
        ["號碼頻率", "冷熱號", "遺漏值", "間隔/連號", "奇偶/大小/和值", "卡方檢定", "共現配對"]
    )

    # 號碼頻率
    with tabs[0]:
        freq = stats.frequency(fdf)
        fdf_freq = pd.DataFrame({"號碼": list(freq.keys()), "出現次數": list(freq.values())})
        fig = px.bar(fdf_freq, x="號碼", y="出現次數", title="各號碼出現次數")
        st.plotly_chart(fig, width='stretch')
        ranked = stats.frequency_ranked(fdf)[:10]
        st.subheader("出現次數 Top10")
        st.dataframe(
            pd.DataFrame(ranked, columns=["號碼", "出現次數"]),
            width='stretch', hide_index=True,
        )

    # 冷熱號
    with tabs[1]:
        hot, cold = stats.hot_cold(fdf, window=30)
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
        miss = stats.missing(fdf)
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
        st.plotly_chart(fig, width='stretch')
        st.metric("含連號(相鄰差=1)的期數比例", f"{ratio:.1%}")

    # 奇偶 / 大小 / 和值
    with tabs[4]:
        odd, big, sums = stats.parity_size_sum(fdf)
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("每期奇數個數分布")
            st.dataframe(
                pd.DataFrame({"奇數個數": list(odd.keys()), "次數": list(odd.values())}),
                width='stretch', hide_index=True,
            )
        with c2:
            st.subheader("每期大數(>=20)個數分布")
            st.dataframe(
                pd.DataFrame({"大數個數": list(big.keys()), "次數": list(big.values())}),
                width='stretch', hide_index=True,
            )
        st.subheader("每期 5 號總和分布")
        sum_fig = px.histogram(pd.DataFrame({"和值": sums}), x="和值", nbins=30, title="和值直方圖")
        st.plotly_chart(sum_fig, width='stretch')

    # 卡方檢定
    with tabs[5]:
        chi = stats.chi_square(fdf)
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
    with tabs[6]:
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
    st.plotly_chart(fig, width='stretch')

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


def page_update(game):
    st.header(f"更新資料 — {game.name}")
    path = game_data_path(game)
    df = load_df(game.key)

    if game.key == "fantasy5":
        # 天天樂(加州 Fantasy 5):從 lottolyzer 彙整站抓取
        st.caption("從公開彙整站抓取加州官方 Fantasy 5 開獎(官網 calottery 以 WAF 封鎖直連)。")
        pages = st.slider("抓取頁數(每頁約 50 期)", min_value=1, max_value=60, value=40)
        if st.button("抓取並更新", type="primary"):
            try:
                with st.spinner(f"抓取最近約 {pages * 50} 期中…"):
                    new_rows = scraper_fantasy5.fetch_history(pages=int(pages))
                merged = merge(df, new_rows)
                save(merged, path)
                st.success(f"已更新天天樂,合併後共 {len(merged)} 期。")
                st.cache_data.clear()
                st.info("資料已更新,請重新整理頁面(F5)以套用最新資料。")
            except scraper_fantasy5.ScrapeError as e:
                st.error(f"更新失敗:{e}")
        return

    # 今彩539:台灣彩券官方 API,單月 / 月份範圍
    st.caption("從台灣彩券 API 抓取開獎資料並合併進歷史檔。")
    sub = st.radio("更新模式", ["單月", "月份範圍"], horizontal=True)

    if sub == "單月":
        ym = st.text_input("月份(YYYY-MM)", value="2026-05")
        if st.button("抓取並更新", type="primary"):
            try:
                year, month = _parse_ym(ym)
                with st.spinner(f"抓取 {ym} 中…"):
                    new_rows = scraper.fetch_month(year, month)
                merged = merge(df, new_rows)
                save(merged, path)
                st.success(f"已更新 {ym},新增/合併 {len(new_rows)} 筆,目前共 {len(merged)} 期。")
                st.cache_data.clear()
                st.info("資料已更新,請重新整理頁面(F5)以套用最新資料。")
            except (scraper.ScrapeError, ValueError) as e:
                st.error(f"更新失敗:{e}")
    else:
        c1, c2 = st.columns(2)
        start_ym = c1.text_input("起始月份(YYYY-MM)", value="2026-01")
        end_ym = c2.text_input("結束月份(YYYY-MM)", value="2026-05")
        if st.button("抓取並更新", type="primary"):
            try:
                start = _parse_ym(start_ym)
                end = _parse_ym(end_ym)
                with st.spinner(f"抓取 {start_ym} ~ {end_ym} 中…"):
                    new_rows, failures = scraper.fetch_range(start, end)
                merged = merge(df, new_rows)
                save(merged, path)
                st.success(
                    f"已更新 {start_ym} ~ {end_ym},新增/合併 {len(new_rows)} 筆,"
                    f"目前共 {len(merged)} 期。"
                )
                if failures:
                    st.warning(
                        "以下月份抓取失敗:\n"
                        + "\n".join(f"- {y}-{m:02d}: {msg}" for y, m, msg in failures)
                    )
                st.cache_data.clear()
                st.info("資料已更新,請重新整理頁面(F5)以套用最新資料。")
            except (scraper.ScrapeError, ValueError) as e:
                st.error(f"更新失敗:{e}")


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


# ── 二合買牌(策略1)────────────────────────────────────
def page_erhe(fdf: pd.DataFrame, game):
    from core import erhe

    st.header(f"二合買牌(策略1)— {game.name}")
    st.caption(
        "策略1 拖牌包車:拖 1 個膽號配其餘 38 號 = 1 車(38 注)。"
        f"膽號被開出(機率 5/39 ≈ {erhe.DAN_PROB:.1%})時整車中獎。"
    )

    c1, c2 = st.columns(2)
    cost_per_car = c1.number_input("每車成本", min_value=1.0, max_value=1_000_000.0, value=2755.0, step=5.0)
    win_payout = c2.number_input("中獎可得(每車中時)", min_value=1.0, max_value=10_000_000.0, value=21200.0, step=100.0)

    ev = erhe.car_ev_rate(cost_per_car, win_payout)
    kf = erhe.car_kelly_fraction(cost_per_car, win_payout)
    fair_payout = cost_per_car / erhe.DAN_PROB  # 損益兩平所需中獎金額
    m1, m2, m3 = st.columns(3)
    m1.metric("期望報酬率/車", f"{ev:+.2%}")
    m2.metric("損益兩平中獎金額", f"{fair_payout:,.0f}")
    m3.metric("凱莉建議下注比例", f"{kf:.4%}")
    st.caption(
        f"膽中機率 {erhe.DAN_PROB:.4%};期望回收/車 = {erhe.DAN_PROB:.4f} × {win_payout:,.0f} "
        f"= {erhe.DAN_PROB * win_payout:,.0f}。"
    )
    if ev < 0:
        st.error(
            f"中獎金額 {win_payout:,.0f} < 損益兩平 {fair_payout:,.0f} → 期望值為負({ev:+.2%})。"
            "凱莉建議下注比例為 0(不該下注),倍頭(倍投)只會加速破產。"
        )
    else:
        st.success(
            f"中獎金額 {win_payout:,.0f} > 損益兩平 {fair_payout:,.0f} → 期望值為正({ev:+.2%})。"
            f"此時凱莉建議每次投入約 {kf:.2%} 的資金(而非無限加碼)。"
        )

    tab1, tab2, tab3, tab4 = st.tabs(
        ["選號 + 預估開機率", "拖牌包車(3車起)", "倍頭進程 + 凱莉對照", "進程策略(中獎重置)"]
    )

    # 1. 選號 + 預估開機率
    with tab1:
        st.caption("各號碼『被開出』的預估機率;可依不同加權檢視(用來挑膽號)。")
        strat = st.selectbox(
            "預估開機率的加權方式", picker.STRATEGIES, format_func=picker.label, key="erhe_strat"
        )
        if fdf.empty:
            st.warning("目前範圍沒有資料。")
        else:
            probs = picker.draw_probabilities(fdf, strategy=strat)
            prob_df = pd.DataFrame(
                [{"號碼": n, "預估開機率": p} for n, p in probs.items()]
            ).sort_values("預估開機率", ascending=False)
            prob_df["預估開機率"] = prob_df["預估開機率"].map(lambda x: f"{x:.2%}")
            st.dataframe(prob_df.head(15), width="stretch", hide_index=True)
        st.error(
            "誠實提醒:每期開獎獨立隨機,真實膽中機率每個號碼都是 5/39 ≈ 12.8%。"
            "非『隨機』的預估開機率只是歷史傾向,**沒有預測下一期的能力**,"
            "也不會改變二合的期望報酬率(那只由成本與中獎金額決定)。"
        )

    # 2. 拖牌包車
    with tab2:
        cars = st.number_input("買幾車(從 3 車起)", min_value=1, max_value=100, value=3)
        total_cost = cars * cost_per_car
        exp_return = cars * erhe.DAN_PROB * win_payout
        x1, x2, x3 = st.columns(3)
        x1.metric("每車成本", f"{cost_per_car:,.0f}")
        x2.metric(f"{int(cars)} 車 總成本", f"{total_cost:,.0f}")
        x3.metric("期望回收 / 報酬率", f"{exp_return:,.0f} ({ev:+.1%})")
        st.caption(
            "注:多買幾車是多押幾個膽號;期望報酬率與買幾車、選哪些膽號無關,"
            "只由每車成本與中獎金額決定(每車都是 −1.34% 這類固定值)。"
        )

    # 共用:顆數 + 進程 + 資金(放 session 供兩個 tab 用)
    def _parse_prog(text, default):
        try:
            v = [float(x) for x in text.replace("，", ",").split(",") if x.strip()]
            return [int(x) if x == int(x) else x for x in v] or default
        except ValueError:
            return default

    # 3. 互動回本計算:輸入本局結果 → 算下一局車數
    with tab3:
        st.caption(
            "互動回本:輸入「本局下幾車、重了幾顆」,我算累積損益,並告訴你**下一局該下幾車**"
            "(讓你中 1 顆即回本;有賺就自動降回低車階)。"
        )
        c1, c2 = st.columns(2)
        n_numbers = c1.number_input("每局押幾顆", min_value=1, max_value=20, value=5, key="t3_n")
        base = c2.number_input("回本後起始車數", min_value=1, max_value=20, value=3, key="t3_base")

        per1 = erhe.per_car_one_hit_net(int(n_numbers), float(cost_per_car), float(win_payout))
        st.caption(
            f"中 1 顆每車淨利 = 中獎金額 {win_payout:,.0f} − {int(n_numbers)}顆×每車成本 {cost_per_car:,.0f} = "
            f"**{per1:,.0f}/車**。回補虧損 L 的下一局車數 = ⌈L ÷ {per1:,.0f}⌉。"
        )

        # 累積損益狀態(SQLite 持久化,依遊戲分開;重整/重啟都保留)
        cum = storage.current_cumulative(game.key)
        st.caption(f"📀 紀錄已存於 SQLite,依遊戲分開(目前:{game.name})。重整頁面不會遺失。")
        # 本局建議車數:由目前累積損益直接算出(不需使用者輸入)
        cur = erhe.next_cars_for_recovery(cum, int(n_numbers), float(cost_per_car),
                                          float(win_payout), base_cars=int(base))
        cur_cars = cur["next_cars"]

        m1, m2, m3 = st.columns(3)
        m1.metric("目前累積損益", f"{cum:+,.0f}")
        if cur_cars == float("inf"):
            m2.metric("👉 本局建議下注", "無法回本")
            st.error("此設定中 1 顆也無法回本(中獎金額 ≤ 顆數×每車成本),請調整中獎金額或顆數。")
        else:
            m2.metric("👉 本局建議下注", f"{int(cur_cars)} 車")
            m3.metric("本局成本", f"{cur['next_cost']:,.0f}")
            if cum < 0:
                st.warning(
                    f"目前虧損 {-cum:,.0f} → 本局系統建議下 **{int(cur_cars)} 車**"
                    f"(成本 {cur['next_cost']:,.0f}),中 1 顆即回本。"
                    f"中 0 顆機率約 {erhe.hit_distribution(int(n_numbers))[0]:.0%}。"
                )
            else:
                st.success(f"目前已回本/獲利 → 本局回到起始 {int(base)} 車。")

        # 輸入方式:A 系統建議車數 / B 自己輸入車數
        mode = st.radio(
            "輸入方式",
            ["方案A:用系統建議車數,只回報重幾顆", "方案B:自己輸入下了幾車 + 重幾顆"],
            horizontal=True, key="t3_mode",
        )
        disabled = cur_cars == float("inf")

        if mode.startswith("方案A"):
            f1, _ = st.columns([1, 1])
            this_hits = f1.number_input("本局重了幾顆", min_value=0, max_value=int(n_numbers),
                                        value=0, key="t3_hits_a")
            b1, b2 = st.columns([1, 1])
            if b1.button("回報結果 → 算下一局", type="primary", disabled=disabled):
                played = int(cur_cars)
                net = erhe.round_net(played, int(this_hits), int(n_numbers),
                                     float(cost_per_car), float(win_payout))
                storage.add_round(game.key, played, int(this_hits), net, cum + net)
                st.rerun()
        else:  # 方案B:自己輸入車數
            f1, f2 = st.columns([1, 1])
            played_in = f1.number_input("我這局下了幾車", min_value=1, max_value=100000,
                                        value=int(cur_cars) if cur_cars != float("inf") else 3,
                                        key="t3_cars_b")
            this_hits_b = f2.number_input("重了幾顆", min_value=0, max_value=int(n_numbers),
                                          value=0, key="t3_hits_b")
            b1, b2 = st.columns([1, 1])
            if b1.button("送出結果 → 算下一局該回第幾車", type="primary"):
                net = erhe.round_net(int(played_in), int(this_hits_b), int(n_numbers),
                                     float(cost_per_car), float(win_payout))
                storage.add_round(game.key, int(played_in), int(this_hits_b), net, cum + net)
                st.rerun()
        if b2.button("重置紀錄", key="t3_reset"):
            storage.reset(game.key)
            st.rerun()

        log_rows = storage.load_rounds(game.key)
        if log_rows:
            log_df = pd.DataFrame([
                {
                    "局": i + 1, "時間": r["ts"], "車數": r["cars"], "重幾顆": r["hits"],
                    "本局損益": f"{r['net']:+,.0f}", "累積損益": f"{r['cumulative']:+,.0f}",
                }
                for i, r in enumerate(log_rows)
            ])
            st.dataframe(log_df, width="stretch", hide_index=True)
            st.download_button(
                "下載紀錄 CSV",
                data=pd.DataFrame(log_rows).to_csv(index=False).encode("utf-8-sig"),
                file_name=f"erhe_log_{game.key}.csv", mime="text/csv",
            )

        st.error(
            "誠實提醒:這只是『回本所需車數』的算術,改變不了每局 −1.34% 的負期望。"
            "中 1 顆回本的設計,代價是中 0 顆時要一直加碼;長期(含偶爾連敗)仍是淨輸,且有破產風險。"
        )

    # 4. 進程策略(中獎重置)— 蒙地卡羅 + 資金破產率
    with tab4:
        st.caption("策略:每局押 N 顆,連敗加碼,**中 ≥1 號就重置回進程起點**。設定資金額看破產率。")
        c1, c2 = st.columns(2)
        n2 = c1.number_input("每局押幾顆", min_value=1, max_value=20, value=5, key="t4_n")
        prog_text2 = c2.text_input("車數進程(逗號分隔)", value="3, 5, 7, 10, 13", key="t4_prog")
        c3, c4 = st.columns(2)
        cap2 = c3.number_input("資金額", min_value=10000, max_value=1_000_000_000, value=500_000, step=50_000, key="t4_cap")
        rounds_n = c4.number_input("模擬局數", min_value=20, max_value=2000, value=200, step=20, key="t4_rounds")
        if st.button("用此資金模擬", type="primary"):
            progression2 = _parse_prog(prog_text2, [3, 5, 7, 10, 13])
            res = erhe.progression_sim_multi(
                progression=progression2, n_numbers=int(n2),
                cost_per_car=float(cost_per_car), win_payout=float(win_payout),
                capital=float(cap2), rounds=int(rounds_n), trials=500,
            )
            a1, a2, a3 = st.columns(3)
            a1.metric("每局期望報酬率", f"{res.per_round_ev:+.2%}")
            a2.metric("每局輸(全沒中)機率", f"{res.p_lose_round:.1%}")
            a3.metric(f"{int(rounds_n)} 局後破產率", f"{res.ruin_rate:.0%}")
            b1, b2 = st.columns(2)
            b1.metric("平均最終資金", f"{res.avg_final_capital:,.0f}")
            b2.metric("代表路徑最終資金", f"{res.final_capital:,.0f}")
            st.line_chart(pd.DataFrame({"資金": res.curve}))
            if res.per_round_ev < 0:
                st.error(
                    f"每局期望為負({res.per_round_ev:+.2%}),中獎重置改變不了。"
                    f"資金 {cap2:,.0f} 的破產率 {res.ruin_rate:.0%};平均最終資金 {res.avg_final_capital:,.0f}"
                    f"(< 起始 {cap2:,.0f},長期淨流失)。加大資金只是降低破產率,改變不了負期望。"
                )
            else:
                st.warning(
                    f"即使每局正期望({res.per_round_ev:+.2%}),固定進程加碼仍有 {res.ruin_rate:.0%} 破產率"
                    "(過度下注)。唯有凱莉式按比例下注才能在正期望下長期存活。"
                )


# ── 主程式 ────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="彩券統計分析(539 / 天天樂)", page_icon="🎰", layout="wide")
    game, fdf, nav = sidebar_controls()

    # 說明 / 算式頁(由側邊欄按鈕觸發,覆蓋主畫面;點任一導覽即返回)
    if st.session_state.get("show_docs"):
        docs.render()
        return

    if nav == "統計分析":
        page_stats(fdf)
    elif nav == "產生參考號碼":
        page_picker(fdf, game)
    elif nav == "二合買牌(策略1)":
        page_erhe(fdf, game)
    elif nav == "包牌 / 牌型 / 加碼":
        page_wheel(fdf, game)
    elif nav == "策略回測":
        page_backtest(fdf, game)
    elif nav == "凱莉投報計算":
        page_kelly(game)
    elif nav == "更新資料":
        page_update(game)
    elif nav == "Excel 匯出":
        page_export(fdf, game)


if __name__ == "__main__":
    main()
