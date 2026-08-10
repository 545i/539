"""純 HTML 展示表格(ui/tables.py)的測試。

這個模組存在的理由是避開 st.dataframe 的 canvas 縮放模糊,
所以重點在「產出的是正確且安全的 HTML」。
"""
from __future__ import annotations

import pandas as pd

from ui import tables


def _render(df, **kw) -> str:
    """攔下送進 st.markdown 的 HTML 字串。"""
    sent: list[str] = []
    orig_md, orig_cap = tables.st.markdown, tables.st.caption
    tables.st.markdown = lambda body, **k: sent.append(body)
    tables.st.caption = lambda body, **k: sent.append(body)
    try:
        tables.html_table(df, **kw)
    finally:
        tables.st.markdown, tables.st.caption = orig_md, orig_cap
    return "\n".join(sent)


def test_renders_rows_and_headers():
    df = pd.DataFrame([{"期別": "2026-08-05", "中幾顆": "2 顆"}])
    out = _render(df)
    assert "<th>期別</th>" in out and "<th>中幾顆</th>" in out
    assert "2026-08-05" in out and "2 顆" in out


def test_hit_marks_become_badges():
    """【NN】要變成綠色標籤,不是原樣輸出。"""
    df = pd.DataFrame([{"號碼": "05 【23】 【31】"}])
    out = _render(df)
    assert 'class="lt-hit">23<' in out
    assert 'class="lt-hit">31<' in out
    assert "【" not in out.split("<tbody>")[1]     # 表身裡不該再有原始括號


def test_escapes_html():
    """儲存格內容一律 escape,避免內容把版面弄壞或注入標籤。"""
    df = pd.DataFrame([{"欄": "<script>alert(1)</script>&<b>x</b>"}])
    out = _render(df)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out and "&amp;" in out


def test_escapes_header():
    df = pd.DataFrame([{"<b>壞欄名</b>": 1}])
    out = _render(df)
    assert "<th>&lt;b&gt;壞欄名&lt;/b&gt;</th>" in out


def test_mono_columns_get_class():
    df = pd.DataFrame([{"號碼": "05 12", "策略": "熱號"}])
    out = _render(df, mono_cols=("號碼",))
    assert 'class="lt-num">05 12<' in out
    assert 'class="lt-num">熱號<' not in out       # 沒指定的欄不套


def test_max_height_adds_scroll_box():
    df = pd.DataFrame([{"a": 1}])
    assert "max-height:300px" in _render(df, max_height=300)
    assert "max-height" not in _render(df)


def test_empty_frame_is_safe():
    assert "沒有資料" in _render(pd.DataFrame())
    assert "沒有資料" in _render(None)


def test_none_cell_renders_blank():
    df = pd.DataFrame([{"a": None}])
    out = _render(df)
    assert "<td></td>" in out or "<td><span" in out
    assert "None" not in out.split("<tbody>")[1]
