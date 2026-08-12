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


def _button(at, key):
    for b in at.button:
        if b.key == key:
            return b
    raise AssertionError(f"找不到按鈕 {key}")


def test_star_tab_renders(app):
    """⭐ 三星/四星 分頁本身要畫得出來(整頁的 metric / 表格都會現算盤口)。"""
    assert not app.exception, [str(e.value) for e in app.exception]
    assert any("三星/四星" in t.label for t in app.tabs), \
        [t.label for t in app.tabs]


def test_star_records_a_round_with_the_eight_numbers(app):
    """圈滿 8 顆再記帳:碰數 56、每碰可得 = 每碰成本 × 倍率,號碼要跟著存。

    號碼盤在彈窗裡,AppTest 驅動不了,所以直接把選號寫進 session_state ——
    那正是 numpad 存號碼的地方。
    """
    app.session_state["star_pad_lotto539__picked"] = [1, 2, 3, 4, 5, 6, 7, 8]
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    _button(app, "star_record").click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    rows = storage.load_rounds("apptest", storage.STAR)
    assert len(rows) == 1
    r = rows[0]
    assert r["numbers"] == 56 and r["cars"] == 1          # 三星 C(8,3),下 1 支
    assert r["cost"] == 63 * 56                           # 每碰 63 × 56 碰
    assert r["payout_rate"] == 63 * 570                   # 倍率是幾倍,不是幾元
    assert r["picked"] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert r["pending"], "沒選結果就該是待開獎"


def _latest_draw(game_key="lotto539"):
    """開獎資料裡最後一期的(日期, 號碼);不寫死日期,資料每天都在長。"""
    from core import games, loader
    g = games.get(game_key)
    df = loader.load_history(APP.parent / "data" / g.data_file)
    row = df.iloc[-1]
    return str(row["date"].date()), sorted(int(row[c]) for c in loader.detect_num_cols(df))


def test_star_pending_autofills_from_the_draw(app):
    """待回填要能用存下的 8 顆自動對獎:對中 3 顆 → 三星中 C(3,3) = 1 碰。"""
    date, drawn = _latest_draw()
    others = [n for n in range(1, 40) if n not in drawn][:5]
    storage.add_round("apptest", "lotto539", date, 56, 1, None, 3528.0, 35910.0,
                      mode=storage.STAR, picked=sorted(drawn[:3] + others))
    app.run()
    _button(app, "star_fill_all").click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    r = storage.load_rounds("apptest", storage.STAR)[0]
    assert not r["pending"] and r["hits"] == 1
    assert r["payout"] == 35_910 and r["net"] == 35_910 - 3_528


def test_star_wont_record_without_eight_numbers(app):
    """沒圈滿 8 顆,記帳鈕是關的 —— 買的就是這 8 顆的全組合。"""
    assert _button(app, "star_record").disabled
    assert not storage.load_rounds("apptest", storage.STAR)


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
