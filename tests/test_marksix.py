"""六合彩(49 選 6)支援測試:爬蟲解析、資料驗證、統計泛化、策略1 機率。

爬蟲部分只測 HTML 解析(不打網路),用來源站的真實列格式當樣本。
"""
from math import comb

import pandas as pd
import pytest

from core import erhe, games, loader, picker, scraper_marksix, stats

# 來源站(pilio.idv.tw/ltohk/list.asp)的真實表格片段
SAMPLE_HTML = """
<table>
<tr><td>日期</td><td>六合彩中獎號碼</td><td>特</td></tr>
<tr style="text-align:center;">
    <td class="date-cell">07/28<br>26(二)</td>
    <td class="number-cell">
        04,&nbsp;07,&nbsp;14,&nbsp;20,&nbsp;21,&nbsp;30
    </td>
    <td class="bonus-cell">34</td>
</tr>
<tr>
    <td class="date-cell">07/25<br>26(六)</td>
    <td class="number-cell">05,&nbsp;07,&nbsp;12,&nbsp;26,&nbsp;31,&nbsp;42</td>
    <td class="bonus-cell">11</td>
</tr>
<tr>
    <td class="date-cell">08/24<br>02(六)</td>
    <td class="number-cell">02,&nbsp;07,&nbsp;12,&nbsp;19,&nbsp;23,&nbsp;49</td>
    <td class="bonus-cell">04</td>
</tr>
</table>
"""


# ── 爬蟲解析 ─────────────────────────────────────────────
def test_parse_page_extracts_six_numbers():
    rows = scraper_marksix._parse_page(SAMPLE_HTML)
    assert len(rows) == 3
    first = rows[0]
    assert first["date"] == pd.Timestamp("2026-07-28")
    assert [first[f"n{i}"] for i in range(1, 7)] == [4, 7, 14, 20, 21, 30]
    # 號碼已排序、且不含特別號(34 未混入)
    assert 34 not in [first[f"n{i}"] for i in range(1, 7)]


def test_parse_page_two_digit_year_maps_to_2000s():
    rows = scraper_marksix._parse_page(SAMPLE_HTML)
    assert rows[2]["date"] == pd.Timestamp("2002-08-24")


def test_parse_page_skips_header_and_junk():
    assert scraper_marksix._parse_page("<tr><td>沒有資料</td></tr>") == []


# ── 資料讀寫驗證(6 顆 / 1~49)────────────────────────────
def _write_csv(tmp_path, rows):
    path = tmp_path / "marksix.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_load_history_accepts_six_of_49(tmp_path):
    path = _write_csv(tmp_path, [
        {"date": "2026-07-28", "n1": 4, "n2": 7, "n3": 14, "n4": 20, "n5": 21, "n6": 30},
        {"date": "2026-07-25", "n1": 5, "n2": 7, "n3": 12, "n4": 26, "n5": 31, "n6": 49},
    ])
    df = loader.load_history(path, pick=6, num_max=49)
    assert len(df) == 2
    assert loader.detect_num_cols(df) == ["n1", "n2", "n3", "n4", "n5", "n6"]
    # 依日期排序
    assert df["date"].iloc[0] < df["date"].iloc[1]


def test_load_history_rejects_number_over_49(tmp_path):
    path = _write_csv(tmp_path, [
        {"date": "2026-07-28", "n1": 4, "n2": 7, "n3": 14, "n4": 20, "n5": 21, "n6": 50},
    ])
    with pytest.raises(loader.DataError):
        loader.load_history(path, pick=6, num_max=49)


def test_load_history_rejects_five_numbers_for_marksix(tmp_path):
    path = _write_csv(tmp_path, [
        {"date": "2026-07-28", "n1": 4, "n2": 7, "n3": 14, "n4": 20, "n5": 21},
    ])
    with pytest.raises(loader.DataError):
        loader.load_history(path, pick=6, num_max=49)


def test_generate_sample_respects_spec():
    df = loader.generate_sample(50, pick=6, num_max=49)
    draws = loader.draws_as_lists(df)
    assert all(len(d) == 6 and len(set(d)) == 6 for d in draws)
    assert max(max(d) for d in draws) <= 49


# ── 統計泛化 ─────────────────────────────────────────────
@pytest.fixture
def marksix_df():
    return loader.generate_sample(300, pick=6, num_max=49)


def test_stats_cover_all_49_numbers(marksix_df):
    freq = stats.frequency(marksix_df, num_max=49)
    assert set(freq) == set(range(1, 50))
    assert sum(freq.values()) == 300 * 6  # 每期 6 顆
    assert set(stats.missing(marksix_df, num_max=49)) == set(range(1, 50))


def test_size_split_and_bands():
    assert stats.size_split(39) == 20   # 539:1~19 小 / 20~39 大
    assert stats.size_split(49) == 25   # 六合彩:1~24 小 / 25~49 大
    assert stats.tens_bands(39) == ["01~09", "10~19", "20~29", "30~39"]
    assert stats.tens_bands(49) == ["01~09", "10~19", "20~29", "30~39", "40~49"]


def test_parity_and_star_dist_use_six(marksix_df):
    odd, big, sums = stats.parity_size_sum(marksix_df, num_max=49)
    assert set(odd) == set(range(7))     # 0~6 顆奇數
    assert set(big) == set(range(7))
    assert sum(odd.values()) == 300
    star, bands, _pat = stats.tens_band_stats(marksix_df, num_max=49)
    assert set(star) == set(range(1, 6))  # 1~5 星(五個十位區段)
    assert sum(bands.values()) == 300 * 6


def test_chi_square_dof_follows_num_max(marksix_df):
    assert stats.chi_square(marksix_df, num_max=49).dof == 48
    assert stats.chi_square(loader.generate_sample(300)).dof == 38


def test_draw_probabilities_sum_to_pick(marksix_df):
    for strat in picker.STRATEGIES:
        probs = picker.draw_probabilities(marksix_df, strat, num_max=49, pick=6)
        assert len(probs) == 49
        assert abs(sum(probs.values()) - 6.0) < 1e-9
    # random 為均勻:每號 6/49
    uniform = picker.draw_probabilities(marksix_df, "random", num_max=49, pick=6)
    assert all(abs(p - 6 / 49) < 1e-12 for p in uniform.values())


# ── 策略1(二合拖牌)機率與盤口 ──────────────────────────
def test_hit_distribution_is_hypergeometric_6_of_49():
    dist = erhe.hit_distribution(5, pick=6, num_max=49)
    assert set(dist) == set(range(6))  # 押 5 顆 → 中 0~5 顆
    assert abs(sum(dist.values()) - 1.0) < 1e-12
    expected0 = comb(44, 6) / comb(49, 6)
    assert abs(dist[0] - expected0) < 1e-12
    # 539 的預設值不受影響
    assert abs(erhe.hit_distribution(5)[0] - comb(34, 5) / comb(39, 5)) < 1e-12


def test_car_ev_uses_game_dan_prob():
    g = games.MARKSIX
    ev = erhe.car_ev_rate(g.default_cost_per_car, g.default_win_payout, g.dan_prob)
    # 3528 成本 / 28500 可得 @ 6/49 → 約 −1.08%
    assert -0.011 < ev < -0.010
    # 損益兩平中獎金額 = 3528 × 49/6 = 28,812
    assert abs(g.default_cost_per_car / g.dan_prob - 28812.0) < 1e-6
    # 負期望 → 凱莉建議 0
    assert erhe.car_kelly_fraction(3528.0, 28500.0, g.dan_prob) == 0.0


def test_car_ev_positive_above_breakeven():
    g = games.MARKSIX
    assert erhe.car_ev_rate(3528.0, 29000.0, g.dan_prob) > 0
    assert erhe.car_kelly_fraction(3528.0, 29000.0, g.dan_prob) > 0


def test_next_cars_for_recovery_with_marksix_odds():
    g = games.MARKSIX
    # 押 5 顆時,中 1 顆每車淨利 = 28500 − 5×3528 = 10,860
    per1 = erhe.per_car_one_hit_net(5, g.default_cost_per_car, g.default_win_payout)
    assert per1 == 28500.0 - 5 * 3528.0
    rec = erhe.next_cars_for_recovery(-50_000, 5, g.default_cost_per_car,
                                      g.default_win_payout, base_cars=3)
    assert rec["can_recover_1hit"] is True
    assert rec["next_cars"] == 5           # ⌈50000 / 10860⌉ = 5
    assert rec["next_cost"] == 5 * 5 * 3528.0
    # 已回本 → 回到起始車數
    assert erhe.next_cars_for_recovery(1000, 5, 3528.0, 28500.0, base_cars=3)["next_cars"] == 3
