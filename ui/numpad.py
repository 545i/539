"""日曆式號碼盤:用點選取代打字,直接把要下的號碼圈出來。

排版沿用 539 民間「三柱」分區(見 539-SPEC 的三柱分區),把號碼切成三區:

    第一柱  10 11 12 13 14 15 16 17 18                    (9 顆)
    第二柱  20 21 22 23 24 25 26 27 28 29                 (10 顆)
    第三柱  01 02 03 04 05 06 07 08 09 19                 (其餘)
            30 31 32 33 34 35 36 37 38 39

每列固定 10 格,所以三柱各自都排得剛好 —— 第三柱的「01~09 + 19」正好湊滿
第一列,30 之後每十顆一列。號碼範圍跟著 GameConfig.num_max 走:今彩539 與
天天樂是 1~39,六合彩是 1~49(第三柱多出 40~49 一列),不必為各款各寫一份。

選幾顆由呼叫端給 max_pick:
  max_pick == 1  單顆下法 —— 點別顆會直接換過去(像 radio,不用先取消)
  max_pick >  1  多顆下法 —— 選滿之後再點會擋下來,要先取消才能換
"""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

# 分柱的定義住在 core.pillar(三柱 1800碰 的算式也用同一份),
# 這裡只轉出來用 —— 兩邊各寫一份的話,哪天調了邊界就會對不起來。
from core.pillar import (PILLAR_NAMES, pillar_counts,  # noqa: F401  (轉出給呼叫端)
                         pillar_of, pillars)


# 三柱各自的球色(未選中時的邊框與字色;選中時填滿同色)
_TONE = ("#2563eb", "#ea580c", "#0f766e")     # 藍 / 橘 / 墨綠

# 一列 10 顆時整列的寬度上限。球是「一列平分寬度 + 正方形」長出來的,
# 所以沒有上限的話,號碼盤放在整頁寬的地方每顆會撐到 90px 以上,大得誇張。
# 420px / 10 顆 ≈ 40px,是手指好按又不佔版面的尺寸;螢幕比這窄就照螢幕縮。
_ROW_MAX_PX = 420

_CSS = """
<style>
/* ── 號碼球:把 Streamlit 的方形按鈕改成圓形彩球 ───────────── */
div[class*="lotto-pad-"] div[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;   /* 一列就是一列,窄螢幕也不准換行 */
    gap: .16rem !important;
    container-type: inline-size;    /* 讓球的字體能跟著這一列的寬度縮放 */
    max-width: %ROWMAX%px;          /* 見 _ROW_MAX_PX:不加上限球會撐爆 */
}
div[class*="lotto-pad-"] div[data-testid="stColumn"] {
    min-width: 0 !important;        /* 讓 10 欄能一起壓縮而不是擠爆 */
    flex: 1 1 0 !important;
}
/* 外層容器也要放行,否則按鈕被 40px 的最小高度撐成橢圓 */
div[class*="lotto-pad-"] div[data-testid="stElementContainer"],
div[class*="lotto-pad-"] div[data-testid="stButton"] {
    min-height: 0 !important;
    margin: 0 !important;
}
div[class*="lotto-pad-"] .stButton > button {
    border-radius: 50% !important;  /* 圓形 */
    aspect-ratio: 1 / 1 !important;
    width: 100% !important;
    min-width: 0 !important;
    min-height: 0 !important;       /* Streamlit 預設 40px,會壓成橢圓 */
    height: auto !important;
    padding: 0 !important;
    font-weight: 700 !important;
    font-variant-numeric: tabular-nums;
    white-space: nowrap !important; /* 「01」不准拆成兩行 */
    overflow: hidden;
    /* 一列 10 顆,每顆約佔 10cqw;字大約取球徑的 4 成 */
    font-size: clamp(9px, 3.8cqw, 17px) !important;
    line-height: 1 !important;
    border-width: 2px !important;
    transition: transform .08s ease;
}
div[class*="lotto-pad-"] .stButton > button:hover { transform: scale(1.12); }
div[class*="lotto-pad-"] .stButton > button:active { transform: scale(.94); }
/* 未選中:白底 + 柱色外框;選中(primary):柱色填滿 */
%SCOPED%
</style>
"""


def _scoped_css() -> str:
    """替三柱各產生一組配色規則。

    `.pad-on` / `.pad-off` 是**樂觀更新**用的:點下去先由瀏覽器立刻套上,
    不等伺服器來回(見 _optimistic_js)。伺服器回來重畫後由 kind 接手,
    所以它們的樣式必須跟 primary / secondary 完全一樣。
    """
    out = []
    for i, tone in enumerate(_TONE, start=1):
        out.append(f"""
div[class*="lotto-pad-p{i}"] .stButton > button[kind="secondary"],
div[class*="lotto-pad-p{i}"] .stButton > button.pad-off {{
    background: #fff !important; color: {tone} !important;
    border-color: {tone}55 !important;
    box-shadow: none !important;
}}
div[class*="lotto-pad-p{i}"] .stButton > button[kind="secondary"]:hover {{
    border-color: {tone} !important;
}}
div[class*="lotto-pad-p{i}"] .stButton > button[kind="primary"],
div[class*="lotto-pad-p{i}"] .stButton > button.pad-on {{
    background: {tone} !important; color: #fff !important;
    border-color: {tone} !important;
    box-shadow: 0 2px 6px {tone}66;
}}""")
    return "\n".join(out)


# 點下去到畫面更新,實測本機約 160~200ms(伺服器只佔 23ms,其餘是 Streamlit 的
# client 往返 + React 重繪),經過網路只會更久 —— 那就是「選號有延遲」的來源。
# 伺服器端已經沒東西可壓了,所以改成**先在瀏覽器把顏色換掉**:點擊當下就套用
# .pad-on / .pad-off,伺服器回來重畫時再以它為準。狀態仍然完全由伺服器決定,
# 這裡只是把「看得到的回饋」提前,不會改變任何一次下注的內容。
#
# 選滿之後再點別顆,伺服器會擋下來(見 _toggle),所以這裡也要照同一條規則
# 判斷 —— 不然會先亮起來再被打回去,閃一下反而更糟。
_OPTIMISTIC_JS = """
<script>
(function () {
  var doc = window.parent.document;
  if (doc.__lottoPadOptimistic) return;   // 整頁只掛一次
  doc.__lottoPadOptimistic = true;
  doc.addEventListener('click', function (e) {
    var btn = e.target.closest('div[class*="lotto-pad-"] .stButton > button');
    if (!btn) return;
    var pad = btn.closest('div[class*="lotto-pad-"]').className.match(/lotto-pad-p\\d+-(\\S+)/);
    var scope = pad ? pad[1] : null;
    var cap = Number(doc.body.dataset['padCap_' + scope] || 0);
    var on = function (b) {
      return b.classList.contains('pad-on') ||
             (b.getAttribute('kind') === 'primary' && !b.classList.contains('pad-off'));
    };
    if (on(btn)) {                       // 取消:一定成立,直接熄掉
      btn.classList.remove('pad-on'); btn.classList.add('pad-off');
      return;
    }
    if (cap === 1) {                     // 單顆:其餘全熄,這顆亮
      var sel = '[class*="lotto-pad-"] .stButton > button';
      Array.prototype.forEach.call(doc.querySelectorAll(sel), function (b) {
        if (b.closest('div[class*="-' + scope + '"]') && on(b)) {
          b.classList.remove('pad-on'); b.classList.add('pad-off');
        }
      });
      btn.classList.remove('pad-off'); btn.classList.add('pad-on');
      return;
    }
    if (cap > 1) {                       // 多顆:選滿就不亮(伺服器也會擋)
      var n = 0, sel2 = '[class*="lotto-pad-"] .stButton > button';
      Array.prototype.forEach.call(doc.querySelectorAll(sel2), function (b) {
        if (b.closest('div[class*="-' + scope + '"]') && on(b)) n++;
      });
      if (n >= cap) return;
    }
    btn.classList.remove('pad-off'); btn.classList.add('pad-on');
  }, true);
})();
</script>
"""


def _inject_optimistic() -> None:
    """把樂觀更新的腳本送進頁面。

    st.markdown 不會執行 <script>,所以跟 app._numeric_keyboard 一樣走
    components.html(高度 0)再回頭操作 parent document。腳本自己會擋重複掛載。
    純屬體驗優化 —— 哪天 Streamlit 改了 DOM 讓它失效,也只是退回原本的等待。
    """
    components.html(_OPTIMISTIC_JS, height=0)


def inject_css() -> None:
    """把號碼球的樣式送進頁面(整頁只需要一次;重複送也無害)。"""
    st.markdown(
        _CSS.replace("%SCOPED%", _scoped_css()).replace("%ROWMAX%", str(_ROW_MAX_PX)),
        unsafe_allow_html=True)


def _state_key(key: str) -> str:
    return f"{key}__picked"


def get_picked(key: str) -> list[int]:
    """讀某個號碼盤目前選了哪些號(呼叫端不必碰 session_state)。"""
    return sorted(st.session_state.get(_state_key(key), []))


def set_picked(key: str, nums: list[int]) -> None:
    """外部指定選號(用於預填、隨機帶入、清空)。"""
    st.session_state[_state_key(key)] = sorted({int(n) for n in nums})


def clear(key: str) -> None:
    st.session_state.pop(_state_key(key), None)


def number_pad(
    *,
    key: str,
    num_max: int,
    max_pick: int,
    default: list[int] | None = None,
    label: str | None = None,
    show_toolbar: bool = True,
) -> list[int]:
    """畫出三柱號碼盤並回傳已選號碼(由小到大)。

    key       這個盤的識別字;同一頁有多個盤(多款一起下)時務必給不同 key
    num_max   號碼上限(39 或 49),直接取自 GameConfig.num_max
    max_pick  最多可選幾顆;1 = 單顆下法
    default   第一次渲染時的預選號碼
    """
    state = _state_key(key)
    if state not in st.session_state:
        st.session_state[state] = sorted(set(default or []))

    inject_css()
    _inject_optimistic()
    # 把這個盤的上限告訴樂觀更新腳本(它要照同一條規則決定亮不亮)
    components.html(
        f"<script>window.parent.document.body.dataset['padCap_{key}'] = "
        f"'{int(max_pick)}';</script>", height=0)
    if label:
        st.markdown(f"**{label}**")

    cols3 = pillars(num_max)
    for idx, nums in enumerate(cols3):
        if not nums:
            continue
        picked_now: list[int] = st.session_state[state]
        hit = sum(1 for n in nums if n in picked_now)
        rng = f"{nums[0]:02d}-{nums[-1]:02d}" if idx < 2 else "其餘"
        st.caption(
            f"<span style='color:{_TONE[idx]};font-weight:700'>●</span> "
            f"**{PILLAR_NAMES[idx]}**({rng},{len(nums)} 顆)"
            + (f"　— 已選 {hit} 顆" if hit else ""),
            unsafe_allow_html=True,
        )
        # container 的 key 會變成 DOM class(st-key-…),CSS 靠它找到這一柱
        with st.container(key=f"lotto-pad-p{idx + 1}-{key}"):
            _grid(key, state, nums, max_pick)

    picked = sorted(st.session_state[state])
    if show_toolbar:
        _toolbar(key, state, picked, max_pick, num_max)
    return picked


def _grid(key: str, state: str, nums: list[int], max_pick: int) -> None:
    """一柱的號碼球:每列 10 顆,不足的補空位維持十位對齊。"""
    picked: list[int] = st.session_state[state]
    for start in range(0, len(nums), 10):
        row = nums[start:start + 10]
        cols = st.columns(10, gap="small")
        for i, col in enumerate(cols):
            if i >= len(row):
                col.markdown("&nbsp;", unsafe_allow_html=True)   # 補空位
                continue
            n = row[i]
            # 用 on_click 而不是 if button(): callback 會在腳本重跑「之前」執行,
            # 重繪時就拿得到新狀態,球才會立刻變色。
            # (在 if 區塊裡改狀態要等下一輪才看得到;若在裡面補 st.rerun(),
            #  這顆按鈕在下一輪仍為 True,會把剛選的號又切掉。)
            col.button(
                f"{n:02d}",
                key=f"{key}_btn_{n}",
                type="primary" if n in picked else "secondary",
                width="stretch",
                on_click=_toggle,
                args=(state, n, max_pick),
            )


def _toggle(state: str, n: int, max_pick: int) -> None:
    """點一顆號碼:已選就取消;沒選就加入(依 max_pick 決定滿了怎麼辦)。"""
    picked: list[int] = st.session_state[state]
    if n in picked:
        picked.remove(n)
        return
    if max_pick == 1:
        st.session_state[state] = [n]      # 單顆:直接換過去
        return
    if len(picked) >= max_pick:
        st.toast(f"最多選 {max_pick} 顆,要換的話先取消一顆。", icon="⚠️")
        return
    picked.append(n)


def _toolbar(key: str, state: str, picked: list[int],
             max_pick: int, num_max: int) -> None:
    """盤下方的狀態列:選了幾顆、三柱怎麼分、選了哪些、清除。"""
    left, right = st.columns([4, 1])
    n = len(picked)
    if n == 0:
        left.caption(f"還沒選號 —— 請點上面的號碼(要選 {max_pick} 顆)")
    else:
        c1, c2, c3 = pillar_counts(picked, num_max)
        nums = " ".join(f"{v:02d}" for v in picked)
        tone = "✅" if n == max_pick else "⏳"
        left.markdown(
            f"{tone} **已選 {n}/{max_pick} 顆**　"
            f"<span style='color:#64748b'>三柱 {c1}-{c2}-{c3}</span>　`{nums}`",
            unsafe_allow_html=True,
        )
    right.button("清除", key=f"{key}_clear", width="stretch", disabled=(n == 0),
                 on_click=_clear_state, args=(state,))


def _clear_state(state: str) -> None:
    st.session_state[state] = []
