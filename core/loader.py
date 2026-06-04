"""開獎資料的讀取、驗證、合併與範例資料產生。

CSV 格式:date,n1,n2,n3,n4,n5
例如:2026-06-03,3,11,18,25,39
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from core.constants import NUM_MAX, NUM_MIN, PICK

NUM_COLS = [f"n{i}" for i in range(1, PICK + 1)]
COLUMNS = ["date"] + NUM_COLS


class DataError(Exception):
    """資料格式或內容錯誤。"""


def _validate_row(idx: int, date, nums: list[int]) -> None:
    if len(nums) != PICK:
        raise DataError(f"第 {idx} 列:應有 {PICK} 個號碼,實際 {len(nums)} 個")
    for n in nums:
        if not (NUM_MIN <= n <= NUM_MAX):
            raise DataError(f"第 {idx} 列:號碼 {n} 超出 {NUM_MIN}~{NUM_MAX} 範圍")
    if len(set(nums)) != PICK:
        raise DataError(f"第 {idx} 列:號碼重複 {nums}")
    if pd.isna(date):
        raise DataError(f"第 {idx} 列:日期無法解析")


def load_history(path: str | Path) -> pd.DataFrame:
    """讀取並驗證歷史開獎 CSV,回傳依日期排序的 DataFrame。"""
    path = Path(path)
    if not path.exists():
        raise DataError(f"找不到資料檔:{path}")

    df = pd.read_csv(path)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise DataError(f"CSV 缺少欄位:{missing}(需要 {COLUMNS})")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in NUM_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for idx, row in df.iterrows():
        nums = [row[c] for c in NUM_COLS]
        if any(pd.isna(n) for n in nums):
            raise DataError(f"第 {idx} 列:號碼欄位非整數")
        _validate_row(idx, row["date"], [int(n) for n in nums])

    for col in NUM_COLS:
        df[col] = df[col].astype(int)

    df = df.sort_values("date").reset_index(drop=True)
    return df


def merge(df: pd.DataFrame, new_rows: list[dict]) -> pd.DataFrame:
    """合併新開獎資料,依日期去重(保留既有),回傳排序後 DataFrame。"""
    if not new_rows:
        return df
    add = pd.DataFrame(new_rows)
    add["date"] = pd.to_datetime(add["date"], errors="coerce")
    combined = pd.concat([df, add], ignore_index=True)
    combined = combined.drop_duplicates(subset="date", keep="first")
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def draws_as_lists(df: pd.DataFrame) -> list[list[int]]:
    """把 DataFrame 轉為每期 5 個號碼的 list(依時間排序)。"""
    return [[int(r[c]) for c in NUM_COLS] for _, r in df.iterrows()]


def generate_sample(n: int = 500, seed: int = 539) -> pd.DataFrame:
    """產生 n 期均勻隨機的範例資料(seed 固定,可重現),供立即 demo。

    日期以 2024-01-01 起、跳過週日(模擬今彩539 週一至週六開獎)。
    """
    rng = random.Random(seed)
    rows = []
    date = pd.Timestamp("2024-01-01")
    for _ in range(n):
        while date.weekday() == 6:  # 6 = 週日,不開獎
            date += pd.Timedelta(days=1)
        nums = sorted(rng.sample(range(NUM_MIN, NUM_MAX + 1), PICK))
        rows.append({"date": date, **{f"n{i+1}": nums[i] for i in range(PICK)}})
        date += pd.Timedelta(days=1)
    return pd.DataFrame(rows)


def save(df: pd.DataFrame, path: str | Path) -> None:
    """將 DataFrame 寫回 CSV(日期格式 YYYY-MM-DD)。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)
