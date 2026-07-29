"""開獎資料的讀取、驗證、合併與範例資料產生。

CSV 格式:date,n1,n2,…,n{pick}
例如今彩539(39 選 5):2026-06-03,3,11,18,25,39
例如六合彩(49 選 6):2026-07-28,4,7,14,20,21,30

pick / num_max 預設沿用今彩539(5 / 39);六合彩等其他玩法由呼叫端傳入。
"""
from __future__ import annotations

import random
import re
from pathlib import Path

import pandas as pd

from core.constants import NUM_MAX, NUM_MIN, PICK

NUM_COLS = [f"n{i}" for i in range(1, PICK + 1)]
COLUMNS = ["date"] + NUM_COLS

_NUM_COL_RE = re.compile(r"^n\d+$")


class DataError(Exception):
    """資料格式或內容錯誤。"""


def num_cols(pick: int = PICK) -> list[str]:
    """該玩法的號碼欄位名稱(n1 … n{pick})。"""
    return [f"n{i}" for i in range(1, pick + 1)]


def _validate_row(idx: int, date, nums: list[int],
                  pick: int = PICK, num_max: int = NUM_MAX) -> None:
    if len(nums) != pick:
        raise DataError(f"第 {idx} 列:應有 {pick} 個號碼,實際 {len(nums)} 個")
    for n in nums:
        if not (NUM_MIN <= n <= num_max):
            raise DataError(f"第 {idx} 列:號碼 {n} 超出 {NUM_MIN}~{num_max} 範圍")
    if len(set(nums)) != pick:
        raise DataError(f"第 {idx} 列:號碼重複 {nums}")
    if pd.isna(date):
        raise DataError(f"第 {idx} 列:日期無法解析")


def load_history(path: str | Path, pick: int = PICK,
                 num_max: int = NUM_MAX) -> pd.DataFrame:
    """讀取並驗證歷史開獎 CSV,回傳依日期排序的 DataFrame。"""
    path = Path(path)
    if not path.exists():
        raise DataError(f"找不到資料檔:{path}")

    cols = num_cols(pick)
    df = pd.read_csv(path)
    missing = [c for c in ["date"] + cols if c not in df.columns]
    if missing:
        raise DataError(f"CSV 缺少欄位:{missing}(需要 {['date'] + cols})")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for idx, row in df.iterrows():
        nums = [row[c] for c in cols]
        if any(pd.isna(n) for n in nums):
            raise DataError(f"第 {idx} 列:號碼欄位非整數")
        _validate_row(idx, row["date"], [int(n) for n in nums], pick, num_max)

    for col in cols:
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


def detect_num_cols(df: pd.DataFrame) -> list[str]:
    """從 DataFrame 推斷號碼欄位(n1、n2、…),依編號排序。

    讓統計函式不必知道玩法就能同時吃 5 顆(539/天天樂)與 6 顆(六合彩)的資料。
    """
    cols = [c for c in df.columns if _NUM_COL_RE.match(str(c))]
    return sorted(cols, key=lambda c: int(str(c)[1:]))


def draws_as_lists(df: pd.DataFrame) -> list[list[int]]:
    """把 DataFrame 轉為每期開獎號碼的 list(依時間排序)。"""
    cols = detect_num_cols(df) or NUM_COLS
    return [[int(r[c]) for c in cols] for _, r in df.iterrows()]


def generate_sample(n: int = 500, seed: int = 539, pick: int = PICK,
                    num_max: int = NUM_MAX,
                    skip_weekdays: tuple[int, ...] = (6,)) -> pd.DataFrame:
    """產生 n 期均勻隨機的範例資料(seed 固定,可重現),供立即 demo。

    日期以 2024-01-01 起、跳過 skip_weekdays 指定的星期
    (預設跳過週日,模擬今彩539 週一至週六開獎;0=週一、6=週日)。
    """
    rng = random.Random(seed)
    rows = []
    date = pd.Timestamp("2024-01-01")
    for _ in range(n):
        while date.weekday() in skip_weekdays:
            date += pd.Timedelta(days=1)
        nums = sorted(rng.sample(range(NUM_MIN, num_max + 1), pick))
        rows.append({"date": date, **{f"n{i+1}": nums[i] for i in range(pick)}})
        date += pd.Timedelta(days=1)
    return pd.DataFrame(rows)


def save(df: pd.DataFrame, path: str | Path) -> None:
    """將 DataFrame 寫回 CSV(日期格式 YYYY-MM-DD)。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)
