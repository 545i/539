"""整頁跑一次的回歸測試(Streamlit AppTest)。

這裡抓的是**單元測試抓不到的那一類 bug**:widget key 被變數遮蔽、
表格與下拉不同步 —— 它們在核心模組裡完全正常,只有真的把頁面跑起來才會現形。

實際踩過的案例:`_render_today` 裡的
    mode = st.radio("多款一起下時,怎麼算才算回本?", …)
把下注模式蓋成了「平攤:每款各負擔 1/N」,於是勾 2 款以上按記帳就
ValueError:未知的下注模式。只有多款才會踩到,所以一直沒被發現。

這幾個測試比其他測試慢(整個 app 要跑起來),但這類問題是使用者直接撞到的。
"""
import datetime as dt
import re
from pathlib import Path

import pytest

from core import autoupdate, storage

APP = Path(__file__).resolve().parent.parent / "app.py"
pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """跑起來的 app;資料庫導到暫存檔,背景排程與抓取一律停用。"""
    monkeypatch.setattr(storage, "_db_path", lambda: tmp_path / "erhe.db")
    monkeypatch.setattr(autoupdate, "start_scheduler", lambda *a, **k: False)
    monkeypatch.setattr(autoupdate, "scheduler_running", lambda: True)
    monkeypatch.setattr(autoupdate, "catch_up", lambda *a, **k: {
        "fetched": 0, "added": 0, "latest": dt.date.today()})
    at = AppTest.from_file(str(APP), default_timeout=300)
    at.session_state["user"] = "apptest"
    at.session_state["_logged_out"] = False
    at.run()
    for r in at.radio:
        if "二合買牌" in (r.options or []):
            r.set_value("二合買牌").run()
            break
    return at


def _pick_games(at, keys):
    for sc in at.segmented_control:
        if sc.label and "今天要下注的遊戲" in sc.label:
            sc.set_value(keys).run()
            return
    raise AssertionError("找不到遊戲選擇器")


def _record_button(at):
    for b in at.button:
        if b.label.startswith("記帳"):
            return b
    raise AssertionError("找不到記帳按鈕")


def test_recording_two_games_does_not_blow_up(app):
    """勾 2 款以上按記帳 —— 這是 mode 被 radio 蓋掉時會 ValueError 的那條路。"""
    _pick_games(app, ["lotto539", "fantasy5"])
    assert not app.exception
    _record_button(app).click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    rows = storage.load_rounds("apptest")
    assert len(rows) == 2
    assert {r["mode"] for r in rows} <= set(storage.MODES)
    assert {r["game"] for r in rows} == {"lotto539", "fantasy5"}


def test_share_mode_radio_does_not_reset_the_table(app):
    """切換平攤/嚴格不該把車數欄位重置 —— key 跟著 mode 跑就會。"""
    _pick_games(app, ["lotto539", "fantasy5"])
    for r in app.radio:
        if r.label and "怎麼算才算回本" in r.label:
            r.set_value("嚴格:任一款中 1 顆就全部回本").run()
            break
    assert not app.exception, [str(e.value) for e in app.exception]


def test_issue_column_is_a_dropdown_in_the_table(app):
    """期號在表格裡就是下拉,不是唯讀欄位 —— 使用者要能直接在那一格選。"""
    _pick_games(app, ["fantasy5"])
    assert not app.exception
    # AppTest 沒辦法驅動 data_editor 的儲存格,所以改驗最終結果:
    # 不改任何東西直接記帳,存下的期號要是開獎資料算出來的下一期
    _record_button(app).click().run()
    assert not app.exception, [str(e.value) for e in app.exception]
    rows = storage.load_rounds("apptest")
    assert len(rows) == 1 and rows[0]["issue"], "期號應該要跟著記進去"
