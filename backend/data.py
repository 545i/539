"""共用資料載入:把 core.loader 包一層,給各 router 用。

開獎 CSV 每天由 autoupdate 背景執行緒寫回,所以這裡每次請求重讀(pandas 讀
幾百列很快),不做長效快取,避免拿到陳舊資料。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
from fastapi import HTTPException

from core import games as games_mod
from core import loader
from core.games import GameConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def get_game(key: str) -> GameConfig:
    if not games_mod.is_active(key):
        raise HTTPException(status_code=404, detail=f"未知或已停用的遊戲:{key}")
    return games_mod.get(key)


def game_data_path(game: GameConfig) -> Path:
    return DATA_DIR / game.data_file


def load_df(key: str) -> pd.DataFrame:
    """讀某款遊戲的開獎 DataFrame(舊→新排序)。"""
    game = get_game(key)
    path = game_data_path(game)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"找不到開獎資料:{game.data_file}")
    try:
        return loader.load_history(path, pick=game.pick, num_max=game.num_max)
    except loader.DataError as e:
        raise HTTPException(status_code=500, detail=f"開獎資料格式錯誤:{e}")


def draw_by_issue(key: str, issue: str) -> tuple[list[int], str] | None:
    """某款遊戲某一期的開獎號與日期;查不到(未開 / 無此期)回 None。

    開獎核對用:前端在核對列表改了期數,後端據此抓真實開獎號重新對獎。
    issue 以字串比對(期號在 loader 裡就是 str),回傳 (號碼清單, 日期字串)。
    """
    from core.loader import detect_num_cols

    issue = str(issue).strip()
    if not issue:
        return None
    df = load_df(key)
    if "issue" not in df.columns:
        return None
    hit = df[df["issue"].astype(str).str.strip() == issue]
    if hit.empty:
        return None
    row = hit.iloc[-1]
    nums = [int(row[c]) for c in detect_num_cols(df)]
    return nums, row["date"].strftime("%Y-%m-%d")


@lru_cache(maxsize=1)
def all_games() -> list[GameConfig]:
    return list(games_mod.GAMES.values())
