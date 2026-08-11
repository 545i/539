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


def test_issue_dropdown_is_sorted_and_defaults_to_next(app):
    """期號由小到大排,預設停在開獎資料算出來的下一期。"""
    _pick_games(app, ["fantasy5"])
    box = next((sb for sb in app.selectbox if sb.label == "天天樂"), None)
    assert box is not None, "天天樂應該要有期號下拉"

    # AppTest 的 options 拿到的是 format_func 之後的字樣(「11962(下一期)」),
    # 這裡只取前面的期號本身
    options = [int(re.match(r"\d+", o).group()) for o in box.options]
    assert options == sorted(options), f"期號沒有照大小排:{box.options}"
    assert options == list(range(options[0], options[0] + len(options)))
    # 預設值前面有幾期(補登用)、後面有幾期(預先下注用)
    idx = options.index(int(box.value))
    assert idx > 0 and idx < len(options) - 1


def test_recorded_issue_follows_the_dropdown(app):
    """選了補登的期號,存進去的就是那一期;記完帳下拉接續下一期。"""
    _pick_games(app, ["fantasy5"])
    box = next(sb for sb in app.selectbox if sb.label == "天天樂")
    default = int(box.value)
    box.set_value(str(default - 2)).run()
    _record_button(app).click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    rows = storage.load_rounds("apptest")
    assert [r["issue"] for r in rows] == [str(default - 2)]
    after = next(sb for sb in app.selectbox if sb.label == "天天樂")
    assert int(after.value) == default - 1
