"""/predict:hot/cold/frequency=確定性排名(對齊統計檢定)、random/balanced=抽樣。

使用者要求「統計檢定後輸出五策略」——熱/冷必須與統計檢定同範圍的排名完全一致,
且同一 game+範圍每次結果相同(切回一致)。用真實資料 + TestClient 驗端到端。
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.data import get_game, load_df
from backend.main import PREFIX, app
from core import analysis as an

client = TestClient(app)
BASE = f"{PREFIX}/api/predict"


def _stats_hot_cold(game: str, n: int):
    g = get_game(game)
    df = load_df(game)
    cnt = an.counts(an.slice_range(df, "periods", n), g.num_max, g.pick)
    hot = sorted(x for x, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:g.pick])
    cold = sorted(x for x, _ in sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]))[:g.pick])
    return hot, cold


def test_hot_cold_match_stats_ranking():
    r = client.get(BASE, params={"game": "lotto539", "mode": "periods", "n": 30}).json()
    by = {s["key"]: s for s in r["strategies"]}
    hot, cold = _stats_hot_cold("lotto539", 30)
    assert by["hot"]["sets"] == [hot], "熱號策略必須等於統計檢定同範圍的熱號排名"
    assert by["cold"]["sets"] == [cold], "冷號策略必須等於統計檢定同範圍的冷號排名"
    assert by["hot"]["ranked"] is True and by["cold"]["ranked"] is True
    assert by["frequency"]["ranked"] is True
    assert by["random"]["ranked"] is False and by["balanced"]["ranked"] is False


def test_ranking_strategies_single_set_regardless_of_sets():
    r = client.get(BASE, params={"game": "lotto539", "sets": 5,
                                 "mode": "periods", "n": 50}).json()
    by = {s["key"]: s for s in r["strategies"]}
    # 排名策略永遠一組;抽樣策略照 sets 給 5 組
    assert len(by["hot"]["sets"]) == 1
    assert len(by["random"]["sets"]) == 5


def test_predict_deterministic_same_range():
    a = client.get(BASE, params={"game": "lotto539", "mode": "periods", "n": 50}).json()
    b = client.get(BASE, params={"game": "lotto539", "mode": "periods", "n": 50}).json()
    assert a["strategies"] == b["strategies"], "同 game+範圍每次結果必須一致(切回一致)"


def test_days_mode_ok():
    r = client.get(BASE, params={"game": "lotto539", "mode": "days", "n": 30})
    assert r.status_code == 200
    assert r.json()["mode"] == "days"


def test_our_combo_eight_unique_labeled():
    """我們的組合:剛好 8 顆、不重複、來源標籤合法,且對齊策略排名。"""
    r = client.get(BASE, params={"game": "lotto539", "mode": "periods", "n": 50}).json()
    combo = r["our_combo"]
    assert len(combo) == 8, "39選5 的組合應剛好 8 顆(2+2+2+2)"
    nums = [c["num"] for c in combo]
    assert len(set(nums)) == 8, "8 顆必須不重複"
    assert all(c["source"] in ("hot", "cold", "history", "parity") for c in combo)

    by = {s["key"]: s for s in r["strategies"]}
    # 前 2 顆熱來源必為 hot 排名前 2(依挑選順序,尚未去重前)
    hot_picks = [c["num"] for c in combo if c["source"] == "hot"]
    assert set(hot_picks) <= set(by["hot"]["sets"][0]), "熱來源號碼須落在 hot 排名前段"
    cold_picks = [c["num"] for c in combo if c["source"] == "cold"]
    assert set(cold_picks) <= set(by["cold"]["sets"][0]), "冷來源號碼須落在 cold 排名前段"
    # 單雙來源:應是 1 奇 + 1 偶(除非奇/偶不夠被 frequency 補走)
    parity = [c["num"] for c in combo if c["source"] == "parity"]
    if len(parity) == 2:
        assert sum(n % 2 for n in parity) == 1, "單雙來源應是 1 奇 1 偶"


def test_our_combo_deterministic():
    a = client.get(BASE, params={"game": "lotto539", "mode": "periods", "n": 50}).json()
    b = client.get(BASE, params={"game": "lotto539", "mode": "periods", "n": 50}).json()
    assert a["our_combo"] == b["our_combo"], "同範圍組合須一致(確定性)"


def test_our_combo_marksix_no_error():
    """六合彩(49選6)不用特別優化,但不能報錯,且仍不重複。"""
    r = client.get(BASE, params={"game": "marksix", "mode": "periods", "n": 50})
    assert r.status_code == 200
    combo = r.json()["our_combo"]
    nums = [c["num"] for c in combo]
    assert len(nums) == len(set(nums)), "組合不得重複"
    assert all(c["source"] in ("hot", "cold", "history", "parity") for c in combo)


def test_review_odd_even_win_only_for_balanced():
    """回測「單雙比中」只適用『均衡』:其餘策略 oe_win=None,不判單雙中獎。"""
    d = client.get(f"{BASE}/review", params={"game": "lotto539", "periods": 8}).json()
    assert d["rows"], "應有回測資料"
    for row in d["rows"]:
        assert row["draw_lean"] in ("單多", "雙多", "平")
        for key, p in row["picks"].items():
            assert p["lean"] in ("單多", "雙多", "平")
            if key == "balanced":
                assert p["oe_win"] == (p["lean"] == row["draw_lean"])
            else:
                assert p["oe_win"] is None       # 其他四個不壓單雙
        bal = row["picks"].get("balanced")
        assert row["oe_win"] == (bal["oe_win"] if bal else None)
    for a in d["ranking"]:
        assert 0 <= a["oe_wins"] <= a["periods"]
        assert 0.0 <= a["oe_rate"] <= 1.0
        if a["strategy"] != "balanced":
            assert a["oe_wins"] == 0            # 只有均衡累積單雙中
