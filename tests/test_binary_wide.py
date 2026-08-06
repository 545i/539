"""二元虛擬變數寬表(core.binary_wide)測試。

重點:每列 1 的個數必須等於該遊戲每期開幾顆,號碼欄數必須跟著 num_max 走
(六合彩是 49 欄,不是 39)。
"""
import pandas as pd
import pytest

from core import binary_wide, games, loader


def _df(rows, pick=5):
    cols = loader.num_cols(pick)
    return pd.DataFrame([{"date": d, **dict(zip(cols, nums))} for d, nums in rows])


def test_columns_follow_game_spec():
    """539 是 39 欄、六合彩是 49 欄 —— 號碼欄數跟著 num_max。"""
    w539 = binary_wide.to_binary_wide(
        _df([("2026-01-01", [1, 2, 3, 4, 39])]), games.get("lotto539"))
    w6 = binary_wide.to_binary_wide(
        _df([("2026-01-01", [1, 2, 3, 4, 5, 49])], pick=6), games.get("marksix"))
    assert list(w539.columns) == ["期數", "日期"] + [f"Num_{i:02d}" for i in range(1, 40)]
    assert list(w6.columns) == ["期數", "日期"] + [f"Num_{i:02d}" for i in range(1, 50)]
    assert "Num_49" in w6.columns and "Num_40" not in w539.columns


def test_marks_exactly_the_drawn_numbers():
    wide = binary_wide.to_binary_wide(
        _df([("2026-08-05", [2, 4, 22, 25, 29])]), games.get("lotto539"))
    hit = [c for c in wide.columns if c.startswith("Num_") and wide.loc[0, c] == 1]
    assert hit == ["Num_02", "Num_04", "Num_22", "Num_25", "Num_29"]
    assert wide.loc[0, "期數"] == 1 and wide.loc[0, "日期"] == "2026-08-05"


@pytest.mark.parametrize("key,pick", [("lotto539", 5), ("fantasy5", 5), ("marksix", 6)])
def test_every_row_sums_to_pick(key, pick):
    """每一列的 1 個數 = 該遊戲每期開幾顆。"""
    g = games.get(key)
    rows = [(f"2026-01-{d:02d}", list(range(d, d + pick))) for d in range(1, 10)]
    wide = binary_wide.to_binary_wide(_df(rows, pick), g)
    assert (wide.filter(like="Num_").sum(axis=1) == pick).all()
    assert wide.filter(like="Num_").to_numpy().sum() == len(rows) * pick


def test_sorted_by_date_and_id_is_sequential():
    """輸入順序亂掉也要依日期排序,期數是排序後的流水號。"""
    wide = binary_wide.to_binary_wide(_df([
        ("2026-01-03", [1, 2, 3, 4, 5]),
        ("2026-01-01", [6, 7, 8, 9, 10]),
        ("2026-01-02", [11, 12, 13, 14, 15]),
    ]), games.get("lotto539"))
    assert wide["日期"].tolist() == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert wide["期數"].tolist() == [1, 2, 3]
    assert wide.loc[0, "Num_06"] == 1          # 最早那期是 6~10


def test_out_of_range_number_raises():
    with pytest.raises(loader.DataError, match="超出"):
        binary_wide.to_binary_wide(
            _df([("2026-01-01", [1, 2, 3, 4, 45])]), games.get("lotto539"))


def test_missing_columns_raise():
    with pytest.raises(loader.DataError, match="缺少欄位"):
        binary_wide.to_binary_wide(
            pd.DataFrame({"date": ["2026-01-01"]}), games.get("lotto539"))


def test_csv_bytes_roundtrip():
    """匯出的 CSV 讀回來要跟原本的寬表一致,且是 Excel 友善的 utf-8-sig。"""
    import io
    g = games.get("marksix")
    df = _df([("2026-08-04", [4, 11, 13, 16, 31, 33])], pick=6)
    raw = binary_wide.to_csv_bytes(df, g)
    assert raw.startswith(b"\xef\xbb\xbf")          # BOM
    back = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    assert back.filter(like="Num_").sum(axis=1).tolist() == [6]
    assert back.loc[0, "Num_33"] == 1 and back.loc[0, "Num_34"] == 0


def test_real_data_files_convert_cleanly():
    """實際資料檔跑一遍,確認格式與遊戲規格對得起來。"""
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "data"
    for key in ("lotto539", "fantasy5", "marksix"):
        g = games.get(key)
        path = base / g.data_file
        if not path.exists():
            pytest.skip(f"{path} 不存在")
        df = loader.load_history(path, pick=g.pick, num_max=g.num_max)
        wide = binary_wide.to_binary_wide(df, g)
        assert len(wide) == len(df)
        assert len(wide.columns) == g.num_max + 2
        assert (wide.filter(like="Num_").sum(axis=1) == g.pick).all()
