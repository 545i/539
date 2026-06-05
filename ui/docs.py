"""說明 / 算式文件頁。

把專案用到的所有統計算式與凱莉公式,連同 core 模組的實際常數值,
以 LaTeX 完整呈現,供他人研究與驗算。所有公式與 core/ 程式碼一一對應:
  - 機率與獎金 → core/constants.py
  - 統計分析   → core/stats.py
  - 選號策略   → core/picker.py
  - 策略回測   → core/backtest.py
  - 凱莉公式   → core/kelly.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core import constants


def _prize_prob_table() -> pd.DataFrame:
    """動態產生「中 k 碼」的組合數、機率、獎金對照表(數字直接取自 constants)。"""
    rows = []
    for k in range(constants.PICK, -1, -1):
        p = constants.prob(k)
        rows.append(
            {
                "中 k 碼": k,
                "中獎組合數 WAYS[k]": f"{constants.WAYS[k]:,}",
                "機率 P(k)": f"{p:.8f}",
                "約等於": f"1 / {1 / p:,.0f}" if p > 0 else "—",
                "獎金 PRIZE[k] (NT$)": f"{constants.PRIZE[k]:,}",
                "淨報酬倍率 r=PRIZE/票價-1": f"{constants.PRIZE[k] / constants.TICKET_PRICE - 1:.4f}",
            }
        )
    return pd.DataFrame(rows)


def render() -> None:
    """繪製完整說明 / 算式頁。"""
    st.header("📖 說明 / 算式(供研究與驗算)")
    st.caption(
        "本頁列出工具用到的每一條算式,並對應到原始碼模組,"
        "數字皆由程式即時計算,歡迎自行驗算。符號約定:每期開出 5 個不重複號碼(母體 1~39)。"
    )

    st.info(
        "誠實前提:今彩539 每期為**獨立隨機事件**,以下所有統計皆為「描述歷史」,"
        "不具任何預測未來的能力。卡方檢定通過(隨機)反而證明號碼無法被預測。"
    )

    # ── 一、基礎機率與獎金 ───────────────────────────────
    st.subheader("一、基礎機率與獎金(core/constants.py)")
    st.markdown(
        f"玩法:從 **{constants.NUM_MIN}~{constants.NUM_MAX}** 共 "
        f"**{constants.NUM_MAX}** 個號碼中選 **{constants.PICK}** 個,每注 "
        f"**NT${constants.TICKET_PRICE}**。"
    )

    st.markdown("**總組合數**(所有可能的開獎結果數):")
    st.latex(
        r"\binom{39}{5} = \frac{39!}{5!\,(39-5)!} = "
        + f"{constants.TOTAL_COMB:,}"
    )

    st.markdown("**中 $k$ 碼的中獎組合數**(從開出的 5 個中選 $k$ 個、從其餘 34 個中選 $5-k$ 個):")
    st.latex(r"\mathrm{WAYS}(k) = \binom{5}{k}\binom{39-5}{\,5-k\,} = \binom{5}{k}\binom{34}{5-k}")

    st.markdown("**中 $k$ 碼的理論機率**:")
    st.latex(r"P(k) = \frac{\mathrm{WAYS}(k)}{\binom{39}{5}}")

    st.markdown("**每注期望獎金**與**長期期望報酬率**:")
    st.latex(r"\mathbb{E}[\text{獎金}] = \sum_{k=0}^{5} P(k)\cdot \mathrm{PRIZE}(k)")
    st.latex(
        r"\text{期望報酬率} = \frac{\mathbb{E}[\text{獎金}]}{\text{票價}} - 1"
    )
    st.latex(
        r"\mathbb{E}[\text{獎金}] \approx "
        + f"{constants.expected_prize():.4f}"
        + r"\;\text{NT\$}, \qquad \text{期望報酬率} \approx "
        + f"{constants.EXPECTED_RETURN:.4%}"
    )

    st.markdown("**各獎項對照表(數字即時計算,可逐格驗算)**:")
    st.dataframe(_prize_prob_table(), width="stretch", hide_index=True)

    # ── 二、統計分析算式 ─────────────────────────────────
    st.subheader("二、統計分析算式(core/stats.py)")

    st.markdown("**A. 號碼頻率** — 號碼 $n$ 在所有期數中的出現次數($\\mathbb{1}$ 為指示函數):")
    st.latex(r"f(n) = \sum_{t=1}^{T} \mathbb{1}\{\, n \in D_t \,\}")
    st.caption("D_t 為第 t 期開出的號碼集合,T 為總期數。")

    st.markdown("**B. 冷熱號** — 只取最近 $w$ 期(預設 $w=30$)計算頻率後排序:")
    st.latex(r"f_w(n) = \sum_{t=T-w+1}^{T} \mathbb{1}\{\, n \in D_t \,\}")
    st.caption("熱號 = f_w 最大的前幾名;冷號 = f_w 最小的前幾名。")

    st.markdown("**C. 遺漏值** — 目前遺漏(距今幾期沒開)與歷史最大遺漏:")
    st.latex(r"\text{current}(n) = T - 1 - \max\{\, t : n \in D_t \,\}")
    st.latex(
        r"\text{max\_gap}(n) = \max\big(\text{歷史最長連續未開期數},\ \text{current}(n)\big)"
    )

    st.markdown("**D. 間隔 / 連號** — 把每期 5 號由小到大排序後取相鄰差;含連號的期數比例:")
    st.latex(r"\text{gap} = s_{(i+1)} - s_{(i)}, \quad s_{(1)} < s_{(2)} < \cdots < s_{(5)}")
    st.latex(
        r"\text{連號比例} = \frac{\#\{\,t : \exists\, i,\ s_{(i+1)}-s_{(i)} = 1\,\}}{T}"
    )

    st.markdown("**E. 奇偶 / 大小 / 和值** — 每期統計(大數定義為 $\\geq 20$):")
    st.latex(r"\text{奇數個數} = \sum_{n \in D_t} \mathbb{1}\{\, n \bmod 2 = 1 \,\}")
    st.latex(r"\text{大數個數} = \sum_{n \in D_t} \mathbb{1}\{\, n \geq 20 \,\}")
    st.latex(r"\text{和值} = \sum_{n \in D_t} n")

    st.markdown(
        "**F. 卡方適合度檢定** — 檢驗 39 個號碼出現次數是否符合均勻分布"
        "(虛無假設 $H_0$:每號機率相等):"
    )
    st.latex(r"E = \frac{T \times 5}{39} \quad(\text{每號期望出現次數})")
    st.latex(r"\chi^2 = \sum_{n=1}^{39} \frac{\big(O_n - E\big)^2}{E}, \qquad \text{自由度 } df = 39 - 1 = 38")
    st.caption(
        "O_n 為號碼 n 的實際出現次數。慣例上每格期望 E ≥ 5 卡方近似才可靠"
        "(即期數需 ≥ 39)。p 值由 scipy.stats.chisquare 計算;"
        "p ≥ 0.05 表示「不違反均勻」= 號碼表現隨機 = 無法預測。"
    )

    st.markdown("**G. 共現配對** — 號碼對 $(i, j),\\ i<j$ 一起出現的次數:")
    st.latex(r"\mathrm{co}(i, j) = \sum_{t=1}^{T} \mathbb{1}\{\, i \in D_t \ \wedge\ j \in D_t \,\}")

    # ── 三、選號策略權重 ─────────────────────────────────
    st.subheader("三、選號策略權重(core/picker.py)")
    st.caption("各策略只是改變「加權不放回抽樣」的權重 w(n);期望中獎率完全相同。")
    st.latex(r"\text{random:}\quad w(n) = 1")
    st.latex(r"\text{frequency:}\quad w(n) = f(n) + 1 \quad(\text{+1 平滑,避免 0 權重})")
    st.latex(r"\text{hot:}\quad w(n) = f_{30}(n) + 0.5")
    st.latex(r"\text{cold:}\quad w(n) = \text{current}(n) + 1")
    st.markdown(
        "**balanced**:重抽直到同時滿足 奇數個數 $\\in[2,3]$、大數個數 $\\in[2,3]$、"
        "且和值落在歷史第 10~90 百分位區間 $[P_{10}, P_{90}]$。"
    )
    st.markdown("加權不放回抽樣:第一個號碼依機率 $w(n)/\\sum w$ 抽出,抽出後移除,重複 5 次:")
    st.latex(r"\Pr(\text{抽中 } n) = \frac{w(n)}{\sum_{m \in \text{剩餘池}} w(m)}")

    # ── 四、策略回測算式 ─────────────────────────────────
    st.subheader("四、策略回測算式(core/backtest.py)")
    st.markdown(
        "防 look-ahead bias:回測第 $i$ 期時,選號只用第 $i$ 期**之前**的資料 "
        "$D_1, \\dots, D_{i-1}$。命中數為與實際開獎的交集大小:"
    )
    st.latex(r"k_i = \big|\, \text{ticket}_i \cap D_i \,\big|")
    st.latex(
        r"\text{總投注} = \sum_i \text{票價}, \qquad "
        r"\text{總回收} = \sum_i \mathrm{PRIZE}(k_i)"
    )
    st.markdown("**報酬率(ROI)**:")
    st.latex(r"\mathrm{ROI} = \frac{\text{總回收} - \text{總投注}}{\text{總投注}}")
    st.caption("無論哪種策略,長期 ROI 都收斂到期望報酬率 ≈ -44%。")

    # ── 五、凱莉公式 ─────────────────────────────────────
    st.subheader("五、凱莉公式投報計算(core/kelly.py)")

    st.markdown("**二元凱莉公式**($p$ 為勝率,$b$ 為淨賠率,$q = 1-p$):")
    st.latex(r"f^{*} = \frac{b\,p - q}{b} = \frac{b\,p - (1-p)}{b}")
    st.caption("f* 為建議投注的「資金比例」;f* < 0 代表數學上不該下注。")

    st.markdown("**各結果的淨報酬倍率**(中 $k$ 碼,相對於本金):")
    st.latex(r"r_k = \frac{\mathrm{PRIZE}(k)}{\text{票價}} - 1")

    st.markdown("**多結果凱莉**(539 有多個獎項,需最大化「對數成長率」):")
    st.latex(r"g(f) = \sum_{k=0}^{5} P(k)\,\ln\!\big(1 + f\,r_k\big)")
    st.latex(r"f^{*} = \arg\max_{f} \; g(f)")
    st.caption(
        "g(f) 為凹函數,程式以三分搜尋(ternary search)在 [-0.999, 1.0] 求極大。"
        "對負期望賭局,極大值落在 f ≤ 0,因此實務最佳比例 fraction = max(0, f*) = 0。"
    )

    st.markdown("**對數成長率**(在最佳比例下,每注資金的長期幾何成長速度):")
    st.latex(r"g(f^{*}) \quad(\text{若 } f^{*} \leq 0 \Rightarrow \text{不下注} \Rightarrow g = 0)")

    st.markdown("**資金模擬(蒙地卡羅)** — 每輪以固定比例 $f$ 下注,依各結果機率抽樣:")
    st.latex(r"B_{t+1} = B_t + f\,B_t\,r_t, \qquad r_t \sim \{(P(k),\, r_k)\}")
    st.caption("f=0 → 資金恆定;f>0 且為負 EV → 資金長期必然下滑(可在「凱莉投報計算」頁實際操作)。")

    # ── 六、包牌 / 牌型 / 加碼 ───────────────────────────
    st.subheader("六、包牌 / 牌型 / 加碼(core/wheel.py)")

    st.markdown("**包牌車數**(圈選 $N$ 個號碼全包,即買下所有 5 碼組合):")
    st.latex(r"\text{車數} = \binom{N}{5}, \qquad \text{資金} = \binom{N}{5}\times\text{票價}")
    st.markdown("**包牌命中頭獎機率**(開出的 5 個號全落在你圈選的 $N$ 個之內):")
    st.latex(r"P_{\text{頭獎}} = \frac{\binom{N}{5}}{\binom{39}{5}}")
    st.caption(
        "重點:包牌只是多買幾注,每注期望報酬率不變(仍為負)。"
        "圈越多碼、命中頭獎機率等比例上升,但花的錢也等比例上升,長期期望不會變正。"
    )

    st.markdown("**牌型**:每期以 (奇數個數, 大數個數, 和值區間) 分類,統計歷史頻率。")
    st.caption(
        "這是描述歷史分布,**不能預測下一期**。每期獨立隨機,"
        "歷史最常出現的牌型,下一期出現機率並不會比較高。"
    )

    st.markdown("**加碼回本(Martingale)為何破產**:輸了就把下注額翻倍想一次回本:")
    st.latex(r"\text{第 } t \text{ 局下注} = b \times 2^{(\text{連敗局數})}")
    st.latex(
        r"\mathbb{E}[\text{總損益}] = (\text{總下注})\times(\text{期望報酬率}) < 0"
    )
    st.caption(
        "在負期望賭局裡,任何下注序列的期望損益都是「總下注 × 負報酬率」,恆為負。"
        "翻倍加碼只會讓連敗時的下注額指數爆炸,在資金用盡前必然破產 —— 它改變不了期望值,只放大破產風險。"
    )

    # ── 七、二合(策略1)買牌算式 ───────────────────────
    st.subheader("七、二合(策略1)買牌算式(core/erhe.py)")
    st.markdown(
        "二合 / 二星:選 2 個號碼,當期開出的 5 個號碼若**同時包含**這 2 個即中。"
    )
    st.markdown("**二合單組中獎機率**(任一 2 碼組合都被開出;其餘 3 個開獎號從剩下 37 個中選):")
    st.latex(r"P_{2} = \frac{\binom{37}{3}}{\binom{39}{5}} = \frac{7770}{575757} \approx \frac{1}{74.1}")
    st.markdown("**公平賠率**(損益兩平的賠率):")
    st.latex(r"R_{\text{公平}} = \frac{1}{P_2} \approx 74.1")
    st.latex(r"\text{二合每注期望報酬率} = P_2 \times R - 1 \quad(R<74.1 \Rightarrow \text{負期望})")

    st.markdown(
        "**拖牌包車**:拖 1 個膽號配其餘 38 個號碼 = 1 車(38 注)。"
        "整車「中」的條件是**膽號被開出**:"
    )
    st.latex(r"P_{\text{膽中}} = \frac{5}{39} \approx 12.82\%")
    st.caption("膽號若在開出的 5 個內,其餘 4 個開獎號各與膽號組成一個中獎注(恰 4 注中)。")

    st.markdown("**車級期望報酬率**(以每車成本與中獎金額直接計算):")
    st.latex(
        r"\text{報酬率}_{\text{車}} = \frac{P_{\text{膽中}}\times \text{中獎金額}}{\text{每車成本}} - 1"
    )
    st.markdown("**損益兩平中獎金額**(車級報酬率為 0 時):")
    st.latex(r"\text{中獎金額}_{\text{平}} = \frac{\text{每車成本}}{P_{\text{膽中}}} = \text{每車成本}\times\frac{39}{5}")
    st.caption(
        "例:每車成本 2755、中獎可得 21200 → 報酬率 = (5/39 × 21200)/2755 − 1 ≈ −1.34%;"
        "損益兩平中獎金額 = 2755 × 39/5 = 21,489。"
    )

    st.markdown("**二合凱莉**(車級二元賭局,$p=5/39$,淨賠率 $b=(\\text{中獎金額}-\\text{成本})/\\text{成本}$):")
    st.latex(r"f^{*} = \frac{b\,p - (1-p)}{b}, \qquad f^{*}\le 0 \Rightarrow \text{建議 } 0")

    st.markdown("**倍頭(Martingale)**:連敗時每局車數乘以倍頭 $m$,累積成本指數成長:")
    st.latex(r"\text{第 } t \text{ 局車數} = \text{起始車數}\times m^{\,t-1}")
    st.latex(r"\text{打平需中車數} = \frac{\text{累積成本}}{\text{中獎金額}}")
    st.caption("在負期望下,累積成本與『打平需中車數』都快速膨脹到不可能,資金用盡前必然破產。")

    # ── 八、雙遊戲與預估開機率 ──────────────────────────
    st.subheader("八、雙遊戲與預估開機率(core/games.py / core/picker.py)")
    st.markdown(
        "今彩539 與 天天樂(加州 Fantasy 5)**玩法都是 39 選 5**,"
        "所以組合數與機率(第一節)完全相同,差別只在票價與獎金結構:"
    )
    st.latex(r"\text{期望報酬率}_{\text{遊戲}} = \frac{\sum_{k} P(k)\cdot \text{獎金}_{\text{遊戲}}(k)}{\text{票價}_{\text{遊戲}}} - 1")
    st.caption(
        "今彩539 ≈ −44.16%(固定獎金);天天樂 ≈ −54.66%(pari-mutuel 平均估計)。"
        "兩款各自獨立資料與統計。"
    )
    st.markdown("**預估開機率**:把各策略權重 $w(n)$ 正規化,使總和為每期開出的號碼數 5:")
    st.latex(r"\hat{p}(n) = 5 \times \frac{w(n)}{\sum_{m} w(m)}")
    st.caption(
        "random 時每號 5/39 ≈ 12.8%(也是真實機率)。非 random 只是把歷史傾向視覺化,"
        "**沒有預測下一期的能力** —— 每期獨立隨機,真實開機率永遠均勻。"
    )

    # ── 539 即時結論 ────────────────────────────────────
    st.subheader("九、今彩539 的實際結論(即時計算)")
    from core import kelly

    res = kelly.analyze_539()
    c1, c2, c3 = st.columns(3)
    c1.metric("期望報酬率", f"{res.ev_return_rate:.4%}")
    c2.metric("理論凱莉 f*", f"{res.raw_fraction:.6f}")
    c3.metric("最佳投注比例", f"{res.fraction:.2%}")
    st.error(
        "結論:期望報酬率為負、理論凱莉比例 f* < 0,凱莉準則建議的最佳投注比例為 "
        "**0%(完全不下注)**。任何選號策略都改變不了這個負期望結果。"
    )
