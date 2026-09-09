"""多顆「中獎顆數」下拉選項(app._hit_options)測試。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app  # noqa: E402


def _cfg(n):
    return {"n_numbers": n}


def test_options_cap_at_numbers_bet():
    """押幾顆就最多中幾顆。"""
    assert app._hit_options({"lotto539": _cfg(4)}, ["lotto539"]) == [
        "待開獎", "0", "1", "2", "3", "4"]
    assert app._hit_options({"lotto539": _cfg(1)}, ["lotto539"]) == ["待開獎", "0", "1"]


def test_options_cap_at_balls_drawn():
    """押 8 顆但 539 每期只開 5 顆 —— 最多也只能中 5 顆。"""
    assert app._hit_options({"lotto539": _cfg(8)}, ["lotto539"])[-1] == "5"
    assert app._hit_options({"marksix": _cfg(8)}, ["marksix"])[-1] == "6"   # 49 選 6


def test_options_take_max_across_picked_games():
    opts = app._hit_options({"lotto539": _cfg(2), "marksix": _cfg(5)},
                            ["lotto539", "marksix"])
    assert opts == ["待開獎", "0", "1", "2", "3", "4", "5"]


def test_pending_label_parses_back_to_none():
    """下拉選「待開獎」要被當成還沒對獎,而不是中 0 顆。"""
    assert app._parse_hits(app.PENDING_LABEL) is None
    assert app._parse_hits("0") == 0
    assert app._parse_hits("3") == 3
