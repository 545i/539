"""策略預測追蹤的測試(core/predictor.py + storage 的 predictions 表)。

重點在三件事:
  1. 防 look-ahead —— 預測不能看到目標期當天的開獎結果
  2. 可重現但不撞號 —— 同期重現、不同期不同、各策略之間也不能一樣
  3. 存下來就不覆蓋 —— 預測寫下去之後不該被改掉
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from core import picker, predictor, storage


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "pred.db"
    monkeypatch.setattr(storage, "_db_path", lambda: db)
    return db


@pytest.fixture
def df539():
    """一份夠長的 539 假資料(冷熱號策略需要前置資料)。"""
    rows = []
    for i in range(120):
        d = dt.date(2026, 1, 1) + dt.timedelta(days=i)
        base = (i % 30) + 1
        nums = sorted({base, (base + 5) % 39 + 1, (base + 11) % 39 + 1,
                       (base + 17) % 39 + 1, (base + 23) % 39 + 1})
        while len(nums) < 5:
            nums = sorted(set(nums) | {max(nums) % 39 + 1})
        rows.append({"date": pd.Timestamp(d),
                     **{f"n{j+1}": nums[j] for j in range(5)}})
    return pd.DataFrame(rows)


# ── 期別辨識 ─────────────────────────────────────────────
def test_period_label_prefers_issue():
    """期號是數字就寫成「第 N 期」,期號其實是日期字串時就直接顯示日期。"""
    assert predictor.period_label("115000192", dt.date(2026, 8, 11)) == "第 192 期(08-11)"
    assert predictor.period_label("11965", dt.date(2026, 8, 11)) == "第 11965 期(08-11)"
    assert predictor.period_label("2026-08-11") == "2026-08-11"


def test_issue_of_without_column(df539):
    """539 / 六合彩的資料沒有 issue 欄,不能炸,要回 None。"""
    assert predictor.issue_of(df539, "2026-01-10") is None


def test_issue_of_with_column(df539):
    df = df539.copy()
    df["issue"] = ""
    df.loc[df.index[-1], "issue"] = "115000192"
    last = df.iloc[-1]["date"].date()
    assert predictor.issue_of(df, last) == "115000192"
    assert predictor.issue_of(df, df.iloc[0]["date"].date()) is None   # 該期沒填


# ── 防 look-ahead ────────────────────────────────────────
def test_history_before_excludes_target(df539):
    """餵給策略的資料必須全部早於目標期。"""
    target = df539.iloc[-1]["date"].date()
    past = predictor.history_before(df539, target)
    assert not past.empty
    assert past["date"].max().date() < target


def test_generate_ignores_target_day_draw(df539, temp_db):
    """把目標期當天的號碼改掉,預測結果不該跟著變 —— 代表沒偷看答案。"""
    target = df539.iloc[-1]["date"].date()
    before = predictor.generate_for(df539, "lotto539", target)

    tampered = df539.copy()
    for j in range(5):
        tampered.loc[tampered.index[-1], f"n{j+1}"] = j + 1   # 竄改當期開獎號
    after = predictor.generate_for(tampered, "lotto539", target)

    assert before == after


# ── seed:可重現、不同期不同、各策略不撞號 ────────────────
def test_same_period_is_reproducible(df539):
    target = df539.iloc[-1]["date"].date()
    assert predictor.generate_for(df539, "lotto539", target) == \
           predictor.generate_for(df539, "lotto539", target)


def test_different_periods_differ(df539):
    t1 = df539.iloc[-1]["date"].date()
    t2 = t1 - dt.timedelta(days=1)
    assert predictor.generate_for(df539, "lotto539", t1) != \
           predictor.generate_for(df539, "lotto539", t2)


def test_strategies_do_not_collide(df539):
    """各策略必須抽出不同號碼,否則排行沒有意義(曾經 random 與 frequency 撞號)。"""
    rows = predictor.generate_for(df539, "lotto539", df539.iloc[-1]["date"].date())
    assert len(rows) == len(picker.STRATEGIES)
    assert len({tuple(v) for v in rows.values()}) == len(rows)


def test_seed_for_is_stable():
    d = dt.date(2026, 8, 11)
    assert predictor.seed_for(d) == predictor.seed_for("2026-08-11") == d.toordinal()


# ── 存檔:不覆蓋 ─────────────────────────────────────────
def test_save_then_resave_does_not_overwrite(df539, temp_db):
    target = df539.iloc[-1]["date"].date()
    added, rows = predictor.save_for(df539, "lotto539", target)
    assert added == len(rows) > 0

    again, _ = predictor.save_for(df539, "lotto539", target)
    assert again == 0                                   # 一筆都不該再進去

    stored = storage.load_predictions("lotto539", target.isoformat())
    assert len(stored) == len(rows)                     # 沒有變成兩倍
    assert stored[0]["numbers"] == rows[stored[0]["strategy"]]


def test_save_with_no_history_returns_empty(df539, temp_db):
    """目標期早於所有資料 → 沒東西可算,不能炸。"""
    added, rows = predictor.save_for(df539, "lotto539", dt.date(2020, 1, 1))
    assert (added, rows) == (0, {})


def test_delete_predictions(df539, temp_db):
    target = df539.iloc[-1]["date"].date()
    predictor.save_for(df539, "lotto539", target)
    n = storage.delete_predictions("lotto539", target.isoformat())
    assert n == len(picker.STRATEGIES)
    assert storage.load_predictions("lotto539") == []


# ── 比對與排行 ───────────────────────────────────────────
def test_evaluate_counts_hits(df539, temp_db):
    """已開獎的期要算出正確命中數,並標出中的號碼。"""
    target = df539.iloc[-1]["date"].date()
    predictor.save_for(df539, "lotto539", target)
    drawn = {int(df539.iloc[-1][f"n{j+1}"]) for j in range(5)}

    got = predictor.evaluate(df539, "lotto539")
    assert got and all(not r["pending"] for r in got)
    for r in got:
        assert r["hits"] == len(set(r["numbers"]) & drawn)
        assert set(r["matched"]) == set(r["numbers"]) & drawn


def test_evaluate_pending_when_not_drawn(df539, temp_db):
    """目標期還沒開獎 → pending,不能擅自算成 0 顆。"""
    future = df539.iloc[-1]["date"].date() + dt.timedelta(days=5)
    # 未來期沒有開獎資料,但仍可產生預測(前置資料是足夠的)
    predictor.save_for(df539, "lotto539", future)
    got = predictor.evaluate(df539, "lotto539", future.isoformat())
    assert got and all(r["pending"] and r["hits"] is None for r in got)


def test_ranking_excludes_pending(df539, temp_db):
    """待開獎的期不能計進平均,否則會把戰績拉低。"""
    drawn_target = df539.iloc[-1]["date"].date()
    future = drawn_target + dt.timedelta(days=5)
    predictor.save_for(df539, "lotto539", drawn_target)
    predictor.save_for(df539, "lotto539", future)

    rank = predictor.ranking(predictor.evaluate(df539, "lotto539"))
    assert rank
    assert all(r["periods"] == 1 for r in rank)          # 只算已開獎那一期
    assert rank == sorted(rank, key=lambda r: -r["avg"])  # 依平均排序


def test_ranking_empty_is_safe():
    assert predictor.ranking([]) == []


def test_evaluate_empty_is_safe(df539, temp_db):
    assert predictor.evaluate(df539, "lotto539") == []


# ── 六合彩(49 選 6、無期號)也要走得通 ─────────────────────
def test_marksix_uses_its_own_spec(temp_db):
    """六合彩必須出 6 顆、範圍到 49。

    picker.pick() 原本把 39 選 5 寫死,六合彩會抽出 5 個 1~39 的號碼,
    cold 策略更直接 KeyError(missing() 查不到 40 以上的號)。
    """
    rows = []
    for i in range(90):
        d = dt.date(2026, 1, 1) + dt.timedelta(days=i * 2)
        nums = sorted({(i + k * 7) % 49 + 1 for k in range(6)})
        while len(nums) < 6:
            nums = sorted(set(nums) | {max(nums) % 49 + 1})
        rows.append({"date": pd.Timestamp(d),
                     **{f"n{j+1}": nums[j] for j in range(6)}})
    df = pd.DataFrame(rows)

    got = predictor.generate_for(df, "marksix", df.iloc[-1]["date"].date())
    assert len(got) == len(picker.STRATEGIES), "有策略被吃掉了(cold 曾經 KeyError)"
    for strategy, nums in got.items():
        assert len(nums) == 6, f"{strategy} 出了 {len(nums)} 顆,應為 6"
        assert max(nums) <= 49 and min(nums) >= 1, f"{strategy} 號碼超出 1~49"


def test_lotto539_spec_unchanged(df539, temp_db):
    """539 仍是 39 選 5(確認上面的修正沒有波及既有玩法)。"""
    got = predictor.generate_for(df539, "lotto539", df539.iloc[-1]["date"].date())
    for nums in got.values():
        assert len(nums) == 5
        assert max(nums) <= 39


def test_marksix_flow(temp_db):
    rows = []
    for i in range(80):
        d = dt.date(2026, 1, 1) + dt.timedelta(days=i * 2)
        base = (i % 40) + 1
        nums = sorted({base, base % 49 + 1, (base + 7) % 49 + 1, (base + 13) % 49 + 1,
                       (base + 21) % 49 + 1, (base + 33) % 49 + 1})
        while len(nums) < 6:
            nums = sorted(set(nums) | {max(nums) % 49 + 1})
        rows.append({"date": pd.Timestamp(d),
                     **{f"n{j+1}": nums[j] for j in range(6)}})
    df = pd.DataFrame(rows)
    target = df.iloc[-1]["date"].date()

    added, got = predictor.save_for(df, "marksix", target)
    assert added > 0
    ev = predictor.evaluate(df, "marksix")
    assert ev and all(not r["pending"] for r in ev)
    # 沒有期號 → 期別顯示退回日期
    assert ev[0]["label"] == target.isoformat()


def test_next_target_without_issue_falls_back_to_date(df539):
    """沒有期號的款:期號退化成日期字串,預估開獎日是最後一期的隔天。"""
    issue, day = predictor.next_target(df539)
    expect = df539.iloc[-1]["date"].date() + dt.timedelta(days=1)
    assert day == expect and issue == expect.isoformat()


# ── 期數(而不是日期)才是一期的識別 ────────────────────────
@pytest.fixture
def df_issue():
    """帶期號的資料,最後一期是 11964(2026-08-10 已開獎)。"""
    rows = []
    for i in range(120):
        d = dt.date(2026, 4, 13) + dt.timedelta(days=i)
        base = (i % 30) + 1
        nums = sorted({base, (base + 5) % 39 + 1, (base + 11) % 39 + 1,
                       (base + 17) % 39 + 1, (base + 23) % 39 + 1})
        while len(nums) < 5:
            nums = sorted(set(nums) | {max(nums) % 39 + 1})
        rows.append({"date": pd.Timestamp(d), "issue": str(11845 + i),
                     **{f"n{j+1}": nums[j] for j in range(5)}})
    return pd.DataFrame(rows)


def test_next_issue_is_last_plus_one(df_issue):
    assert df_issue.iloc[-1]["issue"] == "11964"
    assert predictor.next_issue(df_issue) == "11965"
    issue, day = predictor.next_target(df_issue)
    assert issue == "11965"
    assert day == df_issue.iloc[-1]["date"].date() + dt.timedelta(days=1)


def test_can_predict_next_issue_after_today_drawn(df_issue, temp_db):
    """今天已開出 11964,還是要能對下一期 11965 產生預測。

    先前用日期當識別,11964 與 11965 都落在同一天附近就會撞在一起,
    第二次產生會被 UNIQUE 擋掉 —— 這就是「預測沒辦法再次產生」的成因。
    """
    # 先對已開獎的 11964 存一份
    added_now, _ = predictor.save_for(df_issue, "lotto539", "11964")
    assert added_now == len(picker.STRATEGIES)

    # 同一天再對下一期 11965 存 —— 必須成功,而且是另一組紀錄
    added_next, rows_next = predictor.save_for(df_issue, "lotto539", "11965")
    assert added_next == len(picker.STRATEGIES), "下一期應該要能存進去"
    assert rows_next

    issues = {r["target_issue"] for r in storage.load_predictions("lotto539")}
    assert issues == {"11964", "11965"}


def test_next_issue_is_pending_until_drawn(df_issue, temp_db):
    """11965 還沒開獎 → 待開獎;11964 已開 → 算得出中幾顆。"""
    predictor.save_for(df_issue, "lotto539", "11965")
    predictor.save_for(df_issue, "lotto539", "11964")

    nxt = predictor.evaluate(df_issue, "lotto539", "11965")
    assert nxt and all(r["pending"] and r["hits"] is None for r in nxt)

    cur = predictor.evaluate(df_issue, "lotto539", "11964")
    drawn = {int(df_issue.iloc[-1][f"n{j+1}"]) for j in range(5)}
    assert cur and all(not r["pending"] for r in cur)
    for r in cur:
        assert r["hits"] == len(set(r["numbers"]) & drawn)


def test_future_issue_does_not_leak_last_draw(df_issue, temp_db):
    """對未來期預測時,最後一期是可以用的(它已經開了,不算偷看)。"""
    got = predictor.generate_for(df_issue, "lotto539", "11965")
    assert len(got) == len(picker.STRATEGIES)


def test_draw_of_issue_by_number_and_date(df_issue, df539):
    """有期號的用期號查,沒期號的款用日期字串查。"""
    assert predictor.draw_of_issue(df_issue, "11964") == sorted(
        int(df_issue.iloc[-1][f"n{j+1}"]) for j in range(5))
    assert predictor.draw_of_issue(df_issue, "99999") is None      # 還沒開
    last_day = df539.iloc[-1]["date"].date().isoformat()
    assert predictor.draw_of_issue(df539, last_day) is not None    # 無期號→用日期


def test_marked_formats():
    assert predictor.marked([5, 12, 23], {23}) == "05 12 【23】"
    assert predictor.marked([5, 12], None) == "05 12"


# ── 下注期號的候選清單 ───────────────────────────────────
def test_issue_candidates_are_sorted_ascending():
    """期號是連號,一定要照大小排。

    先前把下一期排最前面再接往回、往前,長成 11966 11965 11964 11963 11967,
    看起來像壞掉。
    """
    got = predictor.issue_candidates("11966", back=3, fwd=2)
    assert got == ["11963", "11964", "11965", "11966", "11967", "11968"]
    assert got == sorted(got, key=int)


def test_issue_candidates_centre_on_the_next_issue():
    got = predictor.issue_candidates("100", back=2, fwd=1)
    assert got.index("100") == 2      # 前面 2 期補登、後面 1 期預先下注
    assert got == ["98", "99", "100", "101"]


def test_issue_candidates_do_not_go_below_one():
    assert predictor.issue_candidates("2", back=5, fwd=0) == ["1", "2"]


@pytest.mark.parametrize("value", [None, "", "  ", "沒有期號", "11a"])
def test_issue_candidates_without_a_number(value):
    """該款沒有期號(資料裡沒期號欄)就回空清單,呼叫端據此不顯示這一欄。"""
    assert predictor.issue_candidates(value) == []


def test_issue_label_marks_which_one_is_next():
    assert predictor.issue_label("11966", "11966") == "11966(下一期)"
    assert predictor.issue_label("11965", "11966") == "11965(已開獎)"
    assert predictor.issue_label("11967", "11966") == "11967(更後面)"


def test_issue_of_label_round_trips():
    for issue in ("11963", "11966", "115000194"):
        label = predictor.issue_label(issue, "11966")
        assert predictor.issue_of_label(label) == issue


def test_issue_of_label_on_garbage():
    assert predictor.issue_of_label("—") == ""
    assert predictor.issue_of_label(None) == ""
