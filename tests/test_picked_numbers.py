"""選號盤(三柱)、選號存取與自動對獎的測試。

涵蓋 2026-08 新增的「圈選號碼」功能:
  ui/numpad.py   三柱分區、每列 10 顆的排版、單顆/多顆的點選規則
  core/storage   picked 欄位的字串化與 v3→v4 遷移
  core/checker   用開獎資料自動算中幾顆
"""
from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from core import checker, games, storage
from ui import numpad


# ── 三柱分區 ──────────────────────────────────────────────
@pytest.mark.parametrize("num_max, sizes", [(39, (9, 10, 20)), (49, (9, 10, 30))])
def test_pillars_sizes(num_max, sizes):
    c1, c2, c3 = numpad.pillars(num_max)
    assert (len(c1), len(c2), len(c3)) == sizes


@pytest.mark.parametrize("num_max", [39, 49])
def test_pillars_is_a_partition(num_max):
    """三柱必須互斥且窮盡 —— 每個號碼剛好屬於一柱。"""
    c1, c2, c3 = numpad.pillars(num_max)
    assert sorted(c1 + c2 + c3) == list(range(1, num_max + 1))
    assert not (set(c1) & set(c2)) and not (set(c2) & set(c3)) and not (set(c1) & set(c3))


def test_pillar_boundaries():
    """19 歸第三柱(第一柱只到 18),這是刻意的不對稱。"""
    assert numpad.pillar_of(10) == 1 and numpad.pillar_of(18) == 1
    assert numpad.pillar_of(19) == 3
    assert numpad.pillar_of(20) == 2 and numpad.pillar_of(29) == 2
    assert numpad.pillar_of(9) == 3 and numpad.pillar_of(30) == 3


def test_pillar_counts():
    assert numpad.pillar_counts([5, 12, 18, 23, 31]) == (2, 1, 2)
    assert numpad.pillar_counts([]) == (0, 0, 0)


@pytest.mark.parametrize("num_max", [39, 49])
def test_rows_of_ten_are_full(num_max):
    """每列 10 顆:第三柱的「01~09 + 19」剛好湊滿一列,之後每十顆一列。

    只有第一柱(9 顆)會不滿,其餘各列都必須是整整 10 顆 —— 這是號碼盤
    在手機上不換行、且十位對齊的前提。
    """
    c1, c2, c3 = numpad.pillars(num_max)
    assert len(c1) == 9                     # 10~18,唯一不滿 10 的一列
    assert len(c2) == 10
    assert len(c3) % 10 == 0                # 39 → 2 列;49 → 3 列
    assert c3[:10] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 19]


def test_game_configs_match_pad():
    """三款遊戲的號碼上限都要能被號碼盤正確切柱。"""
    for key in ("lotto539", "fantasy5", "marksix"):
        g = games.get(key)
        c1, c2, c3 = numpad.pillars(g.num_max)
        assert sorted(c1 + c2 + c3) == list(range(1, g.num_max + 1))


# ── 點選規則(_toggle 不碰 Streamlit runtime,直接餵 dict)──
class _FakeState(dict):
    """夠用的 session_state 替身:_toggle 只會 get/set 一個 key。"""


@pytest.fixture
def fake_state(monkeypatch):
    st = _FakeState()
    monkeypatch.setattr(numpad.st, "session_state", st)
    monkeypatch.setattr(numpad.st, "toast", lambda *a, **k: None)
    return st


def test_toggle_single_replaces(fake_state):
    """單顆下法:點另一顆直接換過去,不必先取消。"""
    fake_state["k"] = []
    numpad._toggle("k", 5, max_pick=1)
    assert fake_state["k"] == [5]
    numpad._toggle("k", 12, max_pick=1)
    assert fake_state["k"] == [12]


def test_toggle_single_can_deselect(fake_state):
    fake_state["k"] = [5]
    numpad._toggle("k", 5, max_pick=1)
    assert fake_state["k"] == []


def test_toggle_multi_accumulates_and_caps(fake_state):
    """多顆下法:累加到上限就擋下,已選的仍可取消。"""
    fake_state["k"] = []
    for n in (5, 12, 23):
        numpad._toggle("k", n, max_pick=3)
    assert fake_state["k"] == [5, 12, 23]
    numpad._toggle("k", 31, max_pick=3)          # 滿了,擋下
    assert fake_state["k"] == [5, 12, 23]
    numpad._toggle("k", 12, max_pick=3)          # 取消一顆
    assert fake_state["k"] == [5, 23]
    numpad._toggle("k", 31, max_pick=3)          # 空出來了才放行
    assert fake_state["k"] == [5, 23, 31]


# ── picked 欄位的字串化 ──────────────────────────────────
@pytest.mark.parametrize("nums, dumped", [
    ([5, 12, 18, 23, 31], "5,12,18,23,31"),
    ([31, 5, 12, 5], "5,12,31"),        # 排序 + 去重
    ([], None),
    (None, None),
])
def test_dump_picked(nums, dumped):
    assert storage.dump_picked(nums) == dumped


@pytest.mark.parametrize("raw, parsed", [
    ("5,12,31", [5, 12, 31]),
    ("", []),
    (None, []),
    ("5, 12 ,31", [5, 12, 31]),
    ("5,abc,31", [5, 31]),              # 壞資料不要炸掉整筆紀錄
])
def test_parse_picked(raw, parsed):
    assert storage.parse_picked(raw) == parsed


# ── 存進資料庫再讀回來 ────────────────────────────────────
@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "picked.db"
    monkeypatch.setattr(storage, "_db_path", lambda: db)
    return db


def test_round_trip_with_and_without_picked(temp_db):
    """圈號的存號碼,填數量的存 NULL —— 兩種可以在同一個帳號並存。"""
    storage.add_round("u", "lotto539", "2026-08-05", 5, 3, None, 1500, 20000,
                      mode=storage.MULTI, picked=[5, 12, 18, 23, 31])
    storage.add_round("u", "lotto539", "2026-08-06", 4, 2, None, 800, 20000,
                      mode=storage.MULTI)
    rows = storage.load_rounds("u")
    assert rows[0]["picked"] == [5, 12, 18, 23, 31]
    assert rows[1]["picked"] == []


def test_migration_adds_picked_column(tmp_path, monkeypatch):
    """舊版(沒有 picked / mode 欄)的資料庫要能就地升級,且不掉資料。"""
    db = tmp_path / "old.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE erhe_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT, game_key TEXT NOT NULL,
            ts TEXT, numbers INTEGER NOT NULL DEFAULT 5, cars INTEGER NOT NULL,
            hits INTEGER NOT NULL, net REAL NOT NULL, cumulative REAL NOT NULL,
            account TEXT, game TEXT, draw_date TEXT, cost REAL, payout REAL,
            payout_rate REAL)
    """)
    conn.execute(
        "INSERT INTO erhe_rounds (game_key, account, game, draw_date, numbers,"
        " cars, hits, cost, payout, payout_rate, net, cumulative)"
        " VALUES ('u','u','lotto539','2026-08-01',5,3,-1,1500,0,20000,-1500,-1500)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(storage, "_db_path", lambda: db)
    rows = storage.load_rounds("u")
    assert len(rows) == 1                       # 舊資料還在
    assert rows[0]["picked"] == []              # 沒號碼,但不會爆
    cols = [r[1] for r in sqlite3.connect(str(db))
            .execute("PRAGMA table_info(erhe_rounds)")]
    assert "picked" in cols


# ── 自動對獎 ─────────────────────────────────────────────
@pytest.fixture
def draw_df():
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-08-05", "2026-08-06"]),
        "n1": [3, 1], "n2": [9, 2], "n3": [23, 3], "n4": [31, 4], "n5": [37, 5],
    })


def test_check_counts_hits(draw_df):
    res = checker.check(draw_df, "2026-08-05", [5, 12, 18, 23, 31])
    assert res["ok"] and res["hits"] == 2
    assert res["matched"] == [23, 31]
    assert res["drawn"] == [3, 9, 23, 31, 37]


def test_check_zero_hits_is_still_ok(draw_df):
    """全沒中要判定成 0 顆(ok=True),不能跟「查不到資料」混為一談。"""
    res = checker.check(draw_df, "2026-08-05", [1, 2, 4])
    assert res["ok"] and res["hits"] == 0 and res["matched"] == []


def test_check_without_draw_data(draw_df):
    res = checker.check(draw_df, "2026-08-09", [5, 12])
    assert not res["ok"] and res["hits"] is None and res["reason"]


def test_check_without_picked(draw_df):
    """填數量的舊紀錄沒有號碼可比,要退回手動。"""
    res = checker.check(draw_df, "2026-08-05", [])
    assert not res["ok"] and res["hits"] is None


def test_draw_of_accepts_date_formats(draw_df):
    import datetime as dt
    want = [3, 9, 23, 31, 37]
    assert checker.draw_of(draw_df, "2026-08-05") == want
    assert checker.draw_of(draw_df, dt.date(2026, 8, 5)) == want
    assert checker.draw_of(draw_df, pd.Timestamp("2026-08-05")) == want


def test_draw_of_handles_empty():
    assert checker.draw_of(pd.DataFrame(), "2026-08-05") is None
    assert checker.draw_of(None, "2026-08-05") is None


def test_count_hits():
    assert checker.count_hits([5, 12, 23], [23, 31, 5]) == 2
    assert checker.count_hits([], [1, 2]) == 0


def test_marked_numbers_formats(monkeypatch, draw_df):
    """紀錄表的號碼欄:中的框【】、待開獎不亂標、沒圈號顯示破折號。"""
    import app

    monkeypatch.setattr(app, "load_df", lambda _k: draw_df)

    hit = {"game": "lotto539", "draw_date": "2026-08-05",
           "picked": [5, 12, 23, 31], "pending": False}
    assert app._marked_numbers(hit) == "05 12 【23】 【31】"

    # 還沒開獎:只列號碼,不能擅自標成沒中
    pending = {**hit, "draw_date": "2026-08-20", "picked": [3, 14], "pending": True}
    assert app._marked_numbers(pending) == "03 14"

    # 手動填數量的舊紀錄沒有號碼
    assert app._marked_numbers({**hit, "picked": []}) == "—"


def test_detail_df_hides_number_column_when_all_manual(monkeypatch, draw_df):
    """全部都是手動填數量時,「號碼」欄不該出現(表格維持原樣)。"""
    import app

    monkeypatch.setattr(app, "load_df", lambda _k: draw_df)
    base = {"draw_date": "2026-08-05", "game": "lotto539", "cars": 3, "numbers": 5,
            "hits": 2, "cost": 1500, "payout": 0, "net": -1500, "cumulative": -1500,
            "pending": False}

    manual_only = app._detail_df([{**base, "picked": []}])
    assert not any("號碼" in c for c in manual_only.columns)

    with_picked = app._detail_df([{**base, "picked": [5, 23]}])
    col = [c for c in with_picked.columns if "號碼" in c]
    assert col, "有圈號時應該要有號碼欄"
    assert with_picked.iloc[0][col[0]] == "05 【23】"


def test_marksix_six_numbers():
    """六合彩開 6 顆,對獎要能吃 n1~n6。"""
    df = pd.DataFrame({
        "date": pd.to_datetime(["2026-08-05"]),
        "n1": [4], "n2": [9], "n3": [25], "n4": [28], "n5": [39], "n6": [45],
    })
    res = checker.check(df, "2026-08-05", [4, 25, 45, 49])
    assert res["ok"] and res["hits"] == 3
    assert res["matched"] == [4, 25, 45]


# ── 下注紀錄的期號(2026-08 新增)────────────────────────────
def test_round_stores_issue(temp_db):
    """期號要能存進下注紀錄;沒填的款維持空值。"""
    storage.add_round("u", "fantasy5", "2026-08-11", 5, 3, None, 1500, 20000,
                      mode=storage.MULTI, picked=[5, 12], issue="11965")
    storage.add_round("u", "marksix", "2026-08-11", 6, 1, None, 500, 20000,
                      mode=storage.MULTI)
    rows = {r["game"]: r for r in storage.load_rounds("u")}
    assert rows["fantasy5"]["issue"] == "11965"
    assert not rows["marksix"]["issue"]


def test_issue_migration_keeps_old_rows(tmp_path, monkeypatch):
    """v4(沒有 issue 欄)的舊庫要能就地升級,舊紀錄不掉。"""
    db = tmp_path / "v4.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE erhe_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT, game_key TEXT NOT NULL, ts TEXT,
            numbers INTEGER NOT NULL DEFAULT 5, cars INTEGER NOT NULL,
            hits INTEGER NOT NULL, net REAL NOT NULL, cumulative REAL NOT NULL,
            account TEXT, game TEXT, draw_date TEXT, cost REAL, payout REAL,
            payout_rate REAL, mode TEXT, picked TEXT)
    """)
    conn.execute(
        "INSERT INTO erhe_rounds (game_key, account, game, draw_date, numbers, cars,"
        " hits, cost, payout, payout_rate, net, cumulative, mode)"
        " VALUES ('u','u','lotto539','2026-08-01',5,3,-1,1500,0,20000,-1500,-1500,'multi')")
    conn.commit()
    conn.close()

    monkeypatch.setattr(storage, "_db_path", lambda: db)
    rows = storage.load_rounds("u")
    assert len(rows) == 1 and not rows[0]["issue"]
    cols = [r[1] for r in sqlite3.connect(str(db))
            .execute("PRAGMA table_info(erhe_rounds)")]
    assert "issue" in cols
