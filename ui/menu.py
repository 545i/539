"""questionary 方向鍵選單流程:統計分析 / 選號 / 回測 / 更新資料 / 關於。"""
from __future__ import annotations

from pathlib import Path

import questionary

from core import constants as C
from core import backtest, loader, picker, stats
from ui import charts

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "history.csv"


# ── 資料載入 ─────────────────────────────────────────────
def _ensure_data():
    """載入歷史資料;無檔案時詢問是否產生範例資料。"""
    try:
        df = loader.load_history(DATA_PATH)
        charts.info(f"已載入 {len(df)} 期開獎資料(最後一期 {df['date'].max().date()})。")
        return df
    except loader.DataError as e:
        charts.warn(f"無法載入資料:{e}")
        if questionary.confirm("要產生 500 期均勻隨機範例資料來試用嗎?", default=True).ask():
            df = loader.generate_sample(500)
            loader.save(df, DATA_PATH)
            charts.info(f"已產生並存檔範例資料({len(df)} 期)→ {DATA_PATH}")
            return df
        return None


# ── 1. 統計分析 ──────────────────────────────────────────
def _analyze(df):
    choice = questionary.select(
        "選擇分析項目:",
        choices=[
            "A. 號碼頻率",
            "B. 冷熱號(近 30 期)",
            "C. 遺漏值",
            "D. 間隔 / 連號",
            "E. 奇偶 / 大小 / 和值",
            "F. 卡方檢定(是否均勻隨機)",
            "G. 共現配對 Top 10",
            "← 返回",
        ],
    ).ask()
    if choice is None or choice.startswith("←"):
        return

    if choice.startswith("A"):
        freq = stats.frequency(df)
        charts.bar(list(freq.keys()), list(freq.values()), "號碼歷史出現次數")
        ranked = stats.frequency_ranked(df)[:10]
        charts.rich_table("出現次數 Top 10", ["號碼", "次數"],
                          [[f"{n:02d}", c] for n, c in ranked])

    elif choice.startswith("B"):
        hot, cold = stats.hot_cold(df, window=30)
        charts.rich_table("近 30 期熱號", ["號碼", "次數"], [[f"{n:02d}", c] for n, c in hot])
        charts.rich_table("近 30 期冷號", ["號碼", "次數"], [[f"{n:02d}", c] for n, c in cold])
        charts.warn("提醒:熱號會繼續熱、冷號該回補 —— 兩種說法互相矛盾,皆無統計依據。")

    elif choice.startswith("C"):
        miss = stats.missing(df)
        cur = {n: miss[n]["current"] for n in miss}
        charts.number_grid(cur, "目前遺漏期數(越亮=越久沒開)")
        rows = sorted(miss.items(), key=lambda kv: -kv[1]["current"])[:10]
        charts.rich_table("遺漏最久 Top 10", ["號碼", "目前遺漏", "歷史最大遺漏"],
                          [[f"{n:02d}", d["current"], d["max_gap"]] for n, d in rows])

    elif choice.startswith("D"):
        gaps, ratio = stats.gaps_consecutive(df)
        charts.bar(list(gaps.keys()), list(gaps.values()), "相鄰號碼間隔分布")
        charts.info(f"含連號(差=1)的期數比例:{ratio:.1%}")

    elif choice.startswith("E"):
        odd, big, sums = stats.parity_size_sum(df)
        charts.rich_table("每期奇數個數分布", ["奇數個數", "期數"],
                          [[k, v] for k, v in odd.items()])
        charts.rich_table("每期大數(≥20)個數分布", ["大數個數", "期數"],
                          [[k, v] for k, v in big.items()])
        charts.hist(sums, bins=20, title="每期 5 號總和分布")

    elif choice.startswith("F"):
        r = stats.chi_square(df)
        charts.rich_table("卡方適合度檢定", ["項目", "值"], [
            ["卡方統計量", f"{r.statistic:.2f}"],
            ["p 值", f"{r.p_value:.4f}"],
            ["自由度", r.dof],
            ["每號期望次數", f"{r.expected_per_num:.1f}"],
            ["資料是否足夠", "是" if r.enough_data else "否"],
        ])
        charts.warn(r.conclusion)

    elif choice.startswith("G"):
        pairs = stats.top_pairs(df, top=10)
        charts.rich_table("最常一起出現的配對", ["配對", "次數"],
                          [[f"{a:02d} + {b:02d}", c] for (a, b), c in pairs])
        charts.warn("共現高只是描述歷史,不是「下次會一起出」的訊號。")

    charts.pause()


# ── 2. 產生參考號碼 ──────────────────────────────────────
def _pick(df):
    strategy = questionary.select(
        "選擇選號策略(各策略期望中獎率相同):",
        choices=[
            questionary.Choice("隨機(最誠實的基準)", "random"),
            questionary.Choice("熱號權重", "hot"),
            questionary.Choice("冷號權重(賭徒謬誤)", "cold"),
            questionary.Choice("歷史頻率權重", "frequency"),
            questionary.Choice("均衡(奇偶/和值落常見區間)", "balanced"),
            questionary.Choice("← 返回", None),
        ],
    ).ask()
    if strategy is None:
        return
    sets_str = questionary.text("要產生幾組?", default="5").ask()
    try:
        sets = max(1, min(20, int(sets_str)))
    except (TypeError, ValueError):
        sets = 5

    tickets = picker.pick(df, strategy=strategy, sets=sets)
    rows = [[i + 1, "  ".join(f"{n:02d}" for n in t)] for i, t in enumerate(tickets)]
    charts.rich_table(f"參考號碼 — 策略:{strategy}", ["組", "號碼"], rows)
    charts.warn("僅供娛樂。長期期望報酬率約 -44%,任何策略都改變不了這個數字。")
    charts.pause()


# ── 3. 策略回測 ──────────────────────────────────────────
def _backtest(df):
    if len(df) < 120:
        charts.warn("資料期數偏少,回測結果波動大,僅供參考。")
    charts.info("正在回測 5 種策略(防 look-ahead:選號只用當期之前的資料)...")
    results = backtest.compare(df, picker.STRATEGIES, start_index=min(100, len(df) // 2))

    rows = []
    for r in results:
        rows.append([
            r.strategy, r.periods,
            r.hit_dist[2], r.hit_dist[3], r.hit_dist[4], r.hit_dist[5],
            f"${r.total_bet:,}", f"${r.total_return:,}", f"{r.roi:.1%}",
        ])
    charts.rich_table(
        "策略回測對比",
        ["策略", "期數", "中2", "中3", "中4", "中5", "總投注", "總回收", "報酬率"],
        rows,
    )
    charts.bar([r.strategy for r in results], [r.roi * 100 for r in results],
               "各策略報酬率 (%)", color="red")
    charts.warn(
        f"理論長期報酬率 = {C.EXPECTED_RETURN:.2%}。各策略差異只是樣本雜訊,"
        "沒有一種策略長期贏得過隨機。"
    )
    charts.pause()


# ── 4. 更新資料 ──────────────────────────────────────────
def _update(df):
    from core import scraper
    ym = questionary.text("輸入要抓取的年月 (YYYY-MM,例如 2026-05):").ask()
    if not ym:
        return
    try:
        year, month = (int(x) for x in ym.split("-"))
        new_rows = scraper.fetch_month(year, month)
        merged = loader.merge(df, new_rows)
        loader.save(merged, DATA_PATH)
        charts.info(f"已抓到 {len(new_rows)} 期,合併後共 {len(merged)} 期並存檔。")
        return merged
    except (ValueError, scraper.ScrapeError) as e:
        charts.warn(f"更新失敗:{e}")
    charts.pause()
    return df


# ── 主迴圈 ───────────────────────────────────────────────
def run():
    charts.banner(C.DISCLAIMER)
    df = _ensure_data()
    if df is None:
        charts.warn("沒有資料可用,結束。")
        return

    while True:
        action = questionary.select(
            "今彩539 統計工具 — 主選單(↑↓ 選擇,Enter 確認):",
            choices=[
                questionary.Choice("1. 統計分析", "analyze"),
                questionary.Choice("2. 產生參考號碼", "pick"),
                questionary.Choice("3. 策略回測", "backtest"),
                questionary.Choice("4. 更新資料(爬蟲)", "update"),
                questionary.Choice("5. 關於 / 免責聲明", "about"),
                questionary.Choice("6. 離開", "quit"),
            ],
        ).ask()

        if action in (None, "quit"):
            charts.info("再見,理性娛樂!")
            break
        elif action == "analyze":
            _analyze(df)
        elif action == "pick":
            _pick(df)
        elif action == "backtest":
            _backtest(df)
        elif action == "update":
            df = _update(df) or df
        elif action == "about":
            charts.banner(C.DISCLAIMER)
            charts.pause()
