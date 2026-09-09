"""提醒圖卡:資料包 schema、模板注入、multipart 組裝,以及(有瀏覽器時)實際渲染。"""
from __future__ import annotations

import importlib

import pytest

from backend import reminder_image
from backend.data import get_game, load_df
from core import notify, render


def test_build_card_data_shape():
    g = get_game("lotto539")
    d = reminder_image.build_card_data(g, load_df("lotto539"))
    assert d["game"] == g.name
    assert isinstance(d["nums"], list) and all(isinstance(n, int) for n in d["nums"])
    assert d["time"] == "20:30"
    # 9000碰 支援款 → nine 有 streak/max_gap/alert
    assert d["nine"] is not None
    assert set(d["nine"]) == {"streak", "max_gap", "alert"}
    assert len(d["thirds"]) == 3
    assert {t["name"] for t in d["thirds"]} == {"前段", "中段", "後段"}
    for p in d["pairs"]:
        assert set(p) == {"a", "b", "streak", "alert"}


def test_build_card_data_marksix_no_nine():
    # 六合彩不支援 9000碰 → nine 為 None(圖卡不畫那塊)
    g = get_game("marksix")
    d = reminder_image.build_card_data(g, load_df("marksix"))
    assert d["nine"] is None


def test_inject_replaces_only_placeholder():
    data = {"game": "今彩539", "nums": [1, 2, 3], "pairs": [], "nine": None,
            "thirds": [], "odd_even": None, "issue": "x", "date": "y", "time": ""}
    html = render._inject(data)
    # 佔位被換成 JSON;JS 裡同名哨兵字串保留(才能在預覽時 fallback DEMO)
    assert '"今彩539"' in html
    assert 'raw === "__CARD_JSON__"' in html
    # <script id="card-data"> 內不應再有原始佔位
    seg = html.split('id="card-data"', 1)[1].split("</script>", 1)[0]
    assert "__CARD_JSON__" not in seg


def test_inject_escapes_angle_bracket():
    # 資料含 < 不能提前關掉 <script>
    html = render._inject({"game": "a<b", "nums": [], "pairs": [], "nine": None,
                           "thirds": [], "odd_even": None,
                           "issue": "", "date": "", "time": ""})
    seg = html.split('id="card-data"', 1)[1].split("</script>", 1)[0]
    assert "a<b" not in seg and "a\\u003cb" in seg


def test_multipart_body():
    body, ctype = notify._multipart({"chat_id": "42", "caption": "hi"}, b"\x89PNG\r\n")
    assert ctype.startswith("multipart/form-data; boundary=")
    assert b'name="chat_id"' in body and b"42" in body
    assert b'name="photo"; filename="card.png"' in body
    assert b"\x89PNG" in body


def test_send_photo_no_config_returns_false(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert notify.send_photo(b"x", "cap") is False


def test_render_card_integration():
    # 有 playwright 或系統 chrome 才實跑;都沒有就 skip(render_card 回 None 屬正常)
    if importlib.util.find_spec("playwright") is None and render._chrome_bin() is None:
        pytest.skip("無 playwright / chrome,略過實際渲染")
    g = get_game("lotto539")
    png = render.render_card(reminder_image.build_card_data(g, load_df("lotto539")))
    assert png and png[:8] == b"\x89PNG\r\n\x1a\n"
