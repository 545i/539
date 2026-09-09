"""開獎資料 → 二元虛擬變數(Binary Dummy Variables)的寬資料格式。

每一期是一筆觀察值(一列):期數 + 日期 + Num_01 … Num_NN,
當期開出該號碼記 1、沒開出記 0。這是丟進統計軟體(R / SPSS / Python)
跑卡方、羅吉斯迴歸、關聯規則時最常用的格式。

號碼欄數依各遊戲規格,不是固定 39 ——
今彩539 與天天樂是 39 選 5(Num_01~Num_39),
六合彩是 49 選 6(Num_01~Num_49),硬套 39 欄會丟掉 40~49 的資料。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import loader

ID_COL = "期數"
DATE_COL = "日期"


def num_labels(num_max: int) -> list[str]:
    """該遊戲的號碼欄名:Num_01 … Num_{num_max}。"""
    return [f"Num_{i:02d}" for i in range(1, num_max + 1)]


def to_binary_wide(df: pd.DataFrame, game) -> pd.DataFrame:
    """把 date,n1..n{pick} 的長表轉成二元虛擬變數寬表。

    df    依 core.loader 格式載入的開獎資料(date + n1…n{pick})
    game  GameConfig,決定 pick(每期開幾顆)與 num_max(號碼欄數)

    「期數」是依日期排序後的流水序號 —— 資料源只有開獎日期,
    沒有台彩/馬會的官方期別編號。
    """
    cols = loader.num_cols(game.pick)
    missing = [c for c in ["date"] + cols if c not in df.columns]
    if missing:
        raise loader.DataError(f"缺少欄位:{missing}")

    src = df.sort_values("date").reset_index(drop=True)
    arr = np.zeros((len(src), game.num_max), dtype="int8")
    for c in cols:
        vals = src[c].astype(int)
        bad = vals[(vals < 1) | (vals > game.num_max)]
        if not bad.empty:
            raise loader.DataError(
                f"號碼 {sorted(set(bad))} 超出 1~{game.num_max} 範圍")
        arr[np.arange(len(src)), vals.to_numpy() - 1] = 1

    return pd.concat([
        pd.DataFrame({
            ID_COL: np.arange(1, len(src) + 1),
            DATE_COL: pd.to_datetime(src["date"]).dt.strftime("%Y-%m-%d"),
        }),
        pd.DataFrame(arr, columns=num_labels(game.num_max)),
    ], axis=1)


def to_csv_bytes(df: pd.DataFrame, game) -> bytes:
    """寬表的 CSV bytes(utf-8-sig,Excel 直接開不會亂碼)。"""
    return to_binary_wide(df, game).to_csv(index=False).encode("utf-8-sig")
