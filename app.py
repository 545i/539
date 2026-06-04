"""今彩539 統計分析 Streamlit Web 應用。

把原本的 TUI 介面改造成網頁版,所有分析皆吃側邊欄「全域範圍選擇」篩選後的 fdf。

重要提醒(與 core 模組一致):今彩539 每期為獨立隨機事件,數學上無法預測,
長期期望報酬率約 -44%。本工具僅供統計學習與娛樂用途。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from core import backtest, constants, excel_report, kelly, picker, scraper, stats
from core.loader import DataError, load_history, merge, save
from ui import docs

# ── 資料路徑與載入 ────────────────────────────────────────
DATA_PATH = Path(__file__).resolve().parent / "data" / "history.csv"


@st.cache_data(show_spinner=False)
def load_df() -> pd.DataFrame:
    """讀取歷史開獎資料;若檔案不存在/格式錯誤,產生範例資料並存檔後回傳。"""
    try:
        return load_history(DATA_PATH)
    except DataError:
        df = generate_sample_safe()
        save(df, DATA_PATH)
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


# ── 側邊欄:全域範圍選擇 + 導覽 ───────────────────────────
def sidebar_controls(df: pd.DataFrame):
    """繪製側邊欄,回傳 (fdf 篩選後資料, 導覽選項)。"""
    st.sidebar.title("今彩539 統計分析")

    with st.sidebar.expander("免責聲明(必讀)", expanded=False):
        st.write(constants.DISCLAIMER)

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
            "策略回測",
            "凱莉投報計算",
            "更新資料",
            "Excel 匯出",
        ],
        label_visibility="collapsed",
        on_change=lambda: st.session_state.update(show_docs=False),
    )
    return fdf, nav


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
def page_picker(fdf: pd.DataFrame):
    st.header("產生參考號碼")
    if fdf.empty:
        st.warning("目前範圍沒有資料,請調整側邊欄的範圍選擇。")
        return

    strategy = st.selectbox("選號策略", picker.STRATEGIES)
    sets = st.slider("組數", min_value=1, max_value=20, value=5)

    st.warning(
        "提醒:所有策略的期望中獎率完全相同,長期期望報酬率約 "
        f"{constants.EXPECTED_RETURN:.0%},差異只是運氣。請理性娛樂、量力而為。"
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
def page_backtest(fdf: pd.DataFrame):
    st.header("策略回測")
    if len(fdf) < 4:
        st.warning("資料太少,無法回測。請擴大側邊欄的範圍選擇。")
        return

    st.caption("防 look-ahead bias:選第 N 期號碼時只用第 N 期之前的資料。")

    if st.button("執行回測", type="primary"):
        start_index = min(100, len(fdf) // 2)
        with st.spinner("回測中,請稍候…"):
            results = backtest.compare(
                fdf, picker.STRATEGIES, start_index=start_index
            )
        st.session_state["backtest_results"] = results

    results = st.session_state.get("backtest_results")
    if not results:
        st.info("點擊上方按鈕開始回測。")
        return

    rows = [
        {
            "策略": r.strategy,
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
        "結果說明:無論哪種策略,長期報酬率都收斂到約 -44%,沒有任何策略能贏過隨機。"
        "這正說明今彩539 無法被預測。"
    )


# ── 4. 凱莉投報計算 ───────────────────────────────────────
def page_kelly(fdf: pd.DataFrame):
    st.header("凱莉投報計算")
    result = kelly.analyze_539()

    c1, c2, c3 = st.columns(3)
    c1.metric("期望報酬率", f"{result.ev_return_rate:.2%}")
    c2.metric("最佳投注比例", f"{result.fraction:.2%}")
    c3.metric("每注期望淨利(NT$)", f"{result.ev_per_bet:.2f}")

    c4, c5 = st.columns(2)
    c4.metric("理論凱莉比例 f*", f"{result.raw_fraction:.4f}")
    c5.metric("對數成長率", f"{result.growth_rate:.4f}")

    st.error("凱莉公式算出最佳投注比例為 0%,因為今彩539 的期望值(EV)為負。")
    st.warning(result.recommendation)

    st.subheader("互動資金模擬")
    st.caption("示範持續下注時資金長期下滑(對照「完全不下注」)。")
    rounds = st.slider("模擬輪數", min_value=100, max_value=5000, value=1000, step=100)
    assume_pct = st.slider("假設下注比例%", min_value=1, max_value=50, value=10)

    outcomes = kelly.outcomes_539()
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


def page_update():
    st.header("更新資料")
    st.caption("從台灣彩券 API 抓取開獎資料並合併進歷史檔。")

    sub = st.radio("更新模式", ["單月", "月份範圍"], horizontal=True)
    df = load_df()

    if sub == "單月":
        ym = st.text_input("月份(YYYY-MM)", value="2026-05")
        if st.button("抓取並更新", type="primary"):
            try:
                year, month = _parse_ym(ym)
                with st.spinner(f"抓取 {ym} 中…"):
                    new_rows = scraper.fetch_month(year, month)
                merged = merge(df, new_rows)
                save(merged, DATA_PATH)
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
                save(merged, DATA_PATH)
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
def page_export(fdf: pd.DataFrame):
    st.header("Excel 匯出")
    if fdf.empty:
        st.warning("目前範圍沒有資料,無法匯出。")
        return

    st.markdown(
        """
        匯出的 Excel 報表包含以下工作表:
        - 免責聲明
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
        kelly_result=kelly.analyze_539(),
    )
    st.download_button(
        label="下載 Excel 報表",
        data=data,
        file_name="lotto539_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── 主程式 ────────────────────────────────────────────────
def main():
    st.set_page_config(page_title="今彩539 統計分析", page_icon="🎰", layout="wide")
    df = load_df()
    fdf, nav = sidebar_controls(df)

    # 說明 / 算式頁(由側邊欄按鈕觸發,覆蓋主畫面;點任一導覽即返回)
    if st.session_state.get("show_docs"):
        docs.render()
        return

    if nav == "統計分析":
        page_stats(fdf)
    elif nav == "產生參考號碼":
        page_picker(fdf)
    elif nav == "策略回測":
        page_backtest(fdf)
    elif nav == "凱莉投報計算":
        page_kelly(fdf)
    elif nav == "更新資料":
        page_update()
    elif nav == "Excel 匯出":
        page_export(fdf)


if __name__ == "__main__":
    main()
