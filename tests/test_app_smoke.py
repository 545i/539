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


def _circle(at, keys, mode=storage.SINGLE, nums=(1,)):
    """在號碼盤圈號(盤是直接畫在頁面上的,狀態就存在 session_state)。"""
    for k in keys:
        at.session_state[f"{mode}_pad_{k}__picked"] = list(nums)
    at.run()


def test_recording_two_games_does_not_blow_up(app):
    """勾 2 款以上按記帳 —— 這是 mode 被 radio 蓋掉時會 ValueError 的那條路。"""
    _pick_games(app, ["lotto539", "fantasy5"])
    _circle(app, ["lotto539", "fantasy5"])
    assert not app.exception
    _record_button(app).click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    rows = storage.load_rounds("apptest")
    assert len(rows) == 2
    assert {r["mode"] for r in rows} <= set(storage.MODES)
    assert {r["game"] for r in rows} == {"lotto539", "fantasy5"}
    assert all(r["picked"] for r in rows), "號碼是必填,每一筆都要存下來"


def test_recording_without_numbers_is_refused(app):
    """沒圈號碼不准記帳 —— 那種紀錄事後對不了獎,只能靠人自己記得。

    但按鈕還是要能按、要講清楚缺哪一款,不能靜悄悄什麼都不做。
    """
    _pick_games(app, ["lotto539"])
    btn = _record_button(app)
    assert not btn.disabled, "記帳鈕不該是 disabled,那樣按了完全沒反應"
    btn.click().run()
    assert not app.exception, [str(e.value) for e in app.exception]
    assert not storage.load_rounds("apptest"), "沒號碼不該記進去"
    assert any("還沒圈號碼" in e.value for e in app.error), [e.value for e in app.error]


def test_picked_count_drives_how_many_you_bet(app):
    """多顆下法:**圈幾顆就押幾顆**,不再有「手寫幾顆」那條路。"""
    app.session_state["multi_today_games"] = ["lotto539"]
    app.session_state["multi_pad_lotto539__picked"] = [3, 7, 11, 25]
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    _button(app, "multi_record").click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    rows = [r for r in storage.load_rounds("apptest") if r["mode"] == storage.MULTI]
    assert len(rows) == 1
    assert rows[0]["numbers"] == 4, "押幾顆要等於圈的顆數"
    assert rows[0]["picked"] == [3, 7, 11, 25]


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


def test_combo_tab_renders(app):
    """⭐ 連碰 分頁本身要畫得出來(整頁的 metric / 表格都會現算盤口)。"""
    assert not app.exception, [str(e.value) for e in app.exception]
    assert any("連碰" in t.label for t in app.tabs), [t.label for t in app.tabs]


def _latest_draw(game_key="lotto539"):
    """開獎資料裡最後一期的(日期, 號碼);不寫死日期,資料每天都在長。"""
    from core import games, loader
    g = games.get(game_key)
    df = loader.load_history(APP.parent / "data" / g.data_file)
    row = df.iloc[-1]
    return str(row["date"].date()), sorted(int(row[c]) for c in loader.detect_num_cols(df))


def test_combo_records_a_round_with_the_numbers(app):
    """圈號碼再記帳:注數 = C(拖幾顆, 星數)、中一注可得 = 每注 × 倍率。

    號碼盤在彈窗裡,AppTest 驅動不了,所以直接把選號寫進 session_state ——
    那正是 numpad 存號碼的地方。
    """
    app.session_state["ledger_combo_pad__picked"] = [1, 2, 3, 4, 5, 6, 7, 8]
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    _button(app, "lcombo_record").click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    rows = storage.load_rounds("apptest", storage.COMBO)
    assert len(rows) == 1
    r = rows[0]
    # 預設玩法是**星碰**:一支 = C(8,3) 組星 × 剩下 5 顆搭配 = 280 碰
    assert r["numbers"] == 280 and r["cars"] == 1       # C(8,3) × 剩 5 顆
    assert r["stars"] == 3 and r["dans"] == []
    # 每注成本是**跟星數綁的**(三星 63、四星 50),不是三種共用一個數字
    assert r["cost"] == 63 * 280 == 17_640              # 三星單支成本
    assert r["payout_rate"] == 57_000                    # 三星中一碰可得
    assert r["picked"] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert r["drag"] == r["picked"], "沒有膽時,拖就是全部圈的號碼"
    assert r["pending"], "沒選結果就該是待開獎"


def test_three_and_four_star_have_their_own_cost(app):
    """三星 63、四星 50 是**不同的價**,不能共用一個「每注多少錢」欄位。

    共用的話四星會用三星的成本記帳,損益整個是錯的。這裡切到四星再記一筆,
    成本必須換成四星那一組。
    """
    app.session_state["ledger_combo_pad__picked"] = [1, 2, 3, 4, 5, 6, 7, 8]
    app.session_state["lcombo_stars"] = [4]
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    _button(app, "lcombo_record").click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    r = storage.load_rounds("apptest", storage.COMBO)[0]
    assert r["stars"] == 4 and r["numbers"] == 280         # C(8,4) × 剩 4 顆
    assert r["cost"] == 50 * 280 == 14_000                 # 四星單支成本
    assert r["cost"] != 63 * 280, "四星不該套到三星的每注成本"
    assert r["payout_rate"] == 750_000                     # 四星中一碰可得


def test_three_and_four_star_share_one_pick(app):
    """三星 + 四星 一起下:號碼只圈一次,寫成兩筆但共用同一組號碼。

    注數、每注成本、倍率、中獎注數各星別都不同,塞不進同一筆;
    使用者要的是「不用再圈一次號碼」,那是輸入端的事。
    """
    app.session_state["ledger_combo_pad__picked"] = [1, 2, 3, 4, 5, 6, 7, 8]
    app.session_state["lcombo_stars"] = [3, 4]
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    _button(app, "lcombo_record").click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    rows = storage.load_rounds("apptest", storage.COMBO)
    assert len(rows) == 2, "一次記帳寫兩筆"
    by_star = {r["stars"]: r for r in rows}
    assert set(by_star) == {3, 4}
    # 同一組號碼、同一天、同一期
    assert by_star[3]["picked"] == by_star[4]["picked"] == [1, 2, 3, 4, 5, 6, 7, 8]
    assert by_star[3]["draw_date"] == by_star[4]["draw_date"]
    assert by_star[3]["issue"] == by_star[4]["issue"]
    # 碰數選 8 顆時兩種都是 280,但每注價不同,所以成本各算各的
    assert by_star[3]["numbers"] == 280 and by_star[3]["cost"] == 63 * 280
    assert by_star[4]["numbers"] == 280 and by_star[4]["cost"] == 50 * 280


def _draw_rows(game_key="fantasy5", n=2):
    """開獎資料最後 n 期的 (日期, 期號, 號碼)。"""
    from core import games, loader
    g = games.get(game_key)
    df = loader.load_history(APP.parent / "data" / g.data_file)
    cols = loader.detect_num_cols(df)
    out = []
    for _, row in df.tail(n).iterrows():
        out.append((str(row["date"].date()), str(row["issue"]).strip(),
                    sorted(int(row[c]) for c in cols)))
    return out


def test_combo_autosettles_without_any_button(app):
    """開獎資料到了就自己結算 —— 沒有「開獎後回填」那一段要按。

    對中 3 顆 → 三星中 C(3,3) = 1 注。
    """
    date, drawn = _latest_draw()
    others = [n for n in range(1, 40) if n not in drawn][:5]
    storage.add_round("apptest", "lotto539", date, 280, 1, None, 17640.0, 57000.0,
                      mode=storage.COMBO, picked=sorted(drawn[:3] + others), stars=3)
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]

    r = storage.load_rounds("apptest", storage.COMBO)[0]
    assert not r["pending"], "有開獎資料就該自己結算,不該還掛在待對獎"
    # 星碰:重 3 顆就成一組三星,剩下 5 顆各配一碰 → 5 碰
    assert r["hits"] == 5
    assert r["payout"] == 5 * 57_000 and r["net"] == 5 * 57_000 - 17_640


def test_combo_autosettle_respects_the_dan(app):
    """膽沒開出來整張歸零 —— 即使拖那邊中了 3 顆。"""
    date, drawn = _latest_draw()
    miss = [n for n in range(1, 40) if n not in drawn][0]      # 這一顆沒開
    others = [n for n in range(1, 40) if n not in drawn][1:6]
    picked = sorted(drawn[:3] + others + [miss])
    storage.add_round("apptest", "lotto539", date, 280, 1, None, 17640.0, 57000.0,
                      mode=storage.COMBO, picked=picked, stars=3, dans=[miss])
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    r = storage.load_rounds("apptest", storage.COMBO)[0]
    assert not r["pending"] and r["hits"] == 0


def test_combo_settles_by_issue_not_by_date(app):
    """有期號就以**期號**為準 —— 日期不等於一期。

    實際踩過:同一天記了第 11967、11968 兩期,兩筆都被比對到那天開的
    11966,而 11968 根本還沒開獎 —— 結果用錯的號碼結算,錢就寫錯了。

    這裡刻意把號碼挑成「用對的那一期會中、用日期查到的那一期不會中」,
    所以只要退回用日期查,這個測試就會紅。
    """
    (d_old, i_old, n_old), (d_new, i_new, n_new) = _draw_rows("fantasy5", 2)
    assert i_old != i_new
    # 圈 i_new 的 3 顆 + 5 顆兩期都沒開的 → 用 i_new 結算會中 C(3,3)=1 注,
    # 用 i_old(日期查到的那期)結算則一注都不中
    fillers = [n for n in range(1, 40) if n not in set(n_old) | set(n_new)][:5]
    picked = sorted(n_new[:3] + fillers)
    from core import combo
    # 星碰:重 3 顆 → 5 碰;用日期查到的舊那期一顆都沒重 → 0 碰
    assert combo.star_hits_of(3, n_new, picked) == 5
    assert combo.star_hits_of(3, n_old, picked) == 0, "測試資料要能分辨兩期才有意義"

    # **日期記成舊那期的日期**,期號記成新那期 —— 這正是會踩到的情境
    storage.add_round("apptest", "fantasy5", d_old, 280, 1, None, 17640.0, 57000.0,
                      mode=storage.COMBO, picked=picked, stars=3, issue=i_new)
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]

    r = storage.load_rounds("apptest", storage.COMBO)[0]
    assert r["hits"] == 5, (
        f"第 {i_new} 期該用它自己的開獎號碼 {n_new} 結算,"
        f"不是用日期 {d_old} 查到的 {n_old}")


def test_combo_leaves_undrawn_issues_pending(app):
    """還沒開獎的期就靜靜留著待開獎,不准拿別期的號碼硬套。"""
    d_old, i_old, _ = _draw_rows("fantasy5", 1)[0]
    future = str(int(i_old) + 5)            # 這一期一定還沒開
    storage.add_round("apptest", "fantasy5", d_old, 280, 1, None, 17640.0, 57000.0,
                      mode=storage.COMBO, picked=[1, 2, 3, 4, 5, 6, 7, 8],
                      stars=3, issue=future)
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    assert storage.load_rounds("apptest", storage.COMBO)[0]["pending"]


def test_combo_record_button_always_responds(app):
    """沒圈號碼時記帳鈕**還是要能按**,而且要講清楚缺什麼。

    以前這裡是 disabled —— 按下去毫無反應也沒有訊息,使用者只會覺得鈕壞了。
    """
    btn = _button(app, "lcombo_record")
    assert not btn.disabled, "記帳鈕不該是 disabled,那樣按了完全沒反應"
    btn.click().run()
    assert not app.exception, [str(e.value) for e in app.exception]
    assert not storage.load_rounds("apptest", storage.COMBO), "沒號碼不該記進去"
    assert any("還沒圈號碼" in e.value for e in app.error), \
        [e.value for e in app.error]


def test_combo_calculator_page_renders(app):
    """側邊欄的「連碰計算機」試算頁 —— 跟記帳頁分開,不寫資料庫。"""
    for r in app.radio:
        if r.options and "連碰計算機" in r.options:
            r.set_value("連碰計算機").run()
            break
    assert not app.exception, [str(e.value) for e in app.exception]
    assert not storage.load_rounds("apptest"), "試算頁不該寫進任何紀錄"


def test_issue_column_is_a_dropdown_in_the_table(app):
    """期號在表格裡就是下拉,不是唯讀欄位 —— 使用者要能直接在那一格選。"""
    _pick_games(app, ["fantasy5"])
    _circle(app, ["fantasy5"])
    assert not app.exception
    # AppTest 沒辦法驅動 data_editor 的儲存格,所以改驗最終結果:
    # 不改任何東西直接記帳,存下的期號要是開獎資料算出來的下一期
    _record_button(app).click().run()
    assert not app.exception, [str(e.value) for e in app.exception]
    rows = storage.load_rounds("apptest")
    assert len(rows) == 1 and rows[0]["issue"], "期號應該要跟著記進去"
