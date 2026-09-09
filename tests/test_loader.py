import pandas as pd
import pytest

from core import loader


def test_generate_sample_is_reproducible():
    a = loader.generate_sample(50, seed=1)
    b = loader.generate_sample(50, seed=1)
    pd.testing.assert_frame_equal(a, b)


def test_generate_sample_valid_ranges():
    df = loader.generate_sample(100, seed=7)
    for _, row in df.iterrows():
        nums = [row[f"n{i}"] for i in range(1, 6)]
        assert len(set(nums)) == 5
        assert all(1 <= n <= 39 for n in nums)


def test_generate_sample_skips_sundays():
    df = loader.generate_sample(60, seed=3)
    assert not (pd.to_datetime(df["date"]).dt.weekday == 6).any()


def test_load_history_roundtrip(tmp_path):
    df = loader.generate_sample(30, seed=5)
    p = tmp_path / "h.csv"
    loader.save(df, p)
    loaded = loader.load_history(p)
    assert len(loaded) == 30
    assert list(loaded.columns) == loader.COLUMNS


def test_load_rejects_out_of_range(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("date,n1,n2,n3,n4,n5\n2024-01-01,1,2,3,4,40\n")
    with pytest.raises(loader.DataError):
        loader.load_history(p)


def test_load_rejects_duplicate_numbers(tmp_path):
    p = tmp_path / "dup.csv"
    p.write_text("date,n1,n2,n3,n4,n5\n2024-01-01,1,1,3,4,5\n")
    with pytest.raises(loader.DataError):
        loader.load_history(p)


def test_merge_dedupes_by_date():
    df = loader.generate_sample(10, seed=2)
    new = [{"date": df["date"].iloc[0], "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5}]
    merged = loader.merge(df, new)
    assert len(merged) == 10  # 同日期不新增
