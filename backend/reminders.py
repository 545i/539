"""排程提醒:偵測到新開獎後,檢查各款「區間組合斷檔」,達門檻就推 Telegram。

設定讀 backend.watch_store(全站公共),計算走 core.stats.combo_cooccurrence_alerts,
推播走 core.notify(讀環境變數的 token / chat_id,沒設就安靜跳過)。

只在「有新開獎」時檢查(見 backend/main.py 的 on_added 掛鉤),所以每款頂多一天
提醒一次,不會洗版。任何錯誤都吞掉,不拖垮排程。
"""
from __future__ import annotations

from backend import watch_store
from backend.data import all_games, get_game, load_df
from core import notify, stats


def _pairs_hot(df, num_max: int) -> list[dict]:
    """1800碰:兩兩十位段配對,只要 streak>=1(沒開就 +1,不設門檻)。"""
    return [p for p in stats.tens_pair_alerts(df, threshold=1, num_max=num_max)
            if p["streak"] >= 1]


def _nine_hot(df, game_key: str) -> list[dict]:
    """9000碰:全段同開,只要 streak>=1(沒一起開就 +1,不設門檻)。"""
    out = []
    for c in watch_store.get_combos(game_key):
        for r in stats.combo_cooccurrence_alerts(df, [c], threshold=1):
            if r["streak"] >= 1:
                out.append(r)
    return out


def check_combo_watch(game_key: str) -> list[dict]:
    """回這款目前的 9000碰斷檔(streak>=1,不設門檻)。"""
    try:
        return _nine_hot(load_df(game_key), game_key)
    except Exception:       # noqa: BLE001
        return []


def notify_combo_watch(game_key: str) -> bool:
    """有斷檔(1800碰或9000碰 streak>=1)就推一則 Telegram;沒設定 / 沒斷檔回 False。"""
    if not notify.enabled():
        return False
    try:
        df = load_df(game_key)
        pairs = _pairs_hot(df, get_game(game_key).num_max)
        nine = _nine_hot(df, game_key)
    except Exception:       # noqa: BLE001 — 提醒失敗不能影響排程
        return False
    if not pairs and not nine:
        return False
    g = get_game(game_key)
    lines = [f"<b>{g.name} 斷檔提醒</b>"]
    if pairs:
        cells = [f"{p['labels'][0]}×{p['labels'][1]} <b>{p['streak']}</b> 期"
                 for p in pairs]
        lines.append("1800碰(雙雙沒開):" + "、".join(cells))
    for r in nine:
        lines.append(f"9000碰({r['label']}):已 <b>{r['streak']}</b> 期沒全部一起開")
    return notify.send("\n".join(lines))


def on_new_draw(game_key: str) -> None:
    """排程偵測到新開獎時的掛鉤(見 core.autoupdate 的 on_added)。"""
    notify_combo_watch(game_key)


# ── /提醒 指令:開獎狀況 + 區間組合斷檔 + 大區間斷檔(唯讀) ──────────
def _thirds(num_max: int) -> list[tuple[str, list[int]]]:
    """前 / 中 / 後三段(比照使用者的 0~12 / 13~25 / 26~39,依 num_max 等比)。"""
    b1 = round(num_max * 12 / 39)
    b2 = round(num_max * 25 / 39)
    return [
        ("前", list(range(1, b1 + 1))),
        ("中", list(range(b1 + 1, b2 + 1))),
        ("後", list(range(b2 + 1, num_max + 1))),
    ]


def _seg_missing_block(df, num_max: int) -> str:
    """前中後段:精細到單顆遺漏(號碼·幾期沒開,開出歸0),用等寬 <pre> 對齊。

    每格「NN·MM」寬度固定 → 三段各一行、上下對齊,一覽無遺。
    """
    miss = stats.missing(df, num_max)
    rows = []
    for name, nums in _thirds(num_max):
        cells = [f"{n:02d}·{miss.get(n, {}).get('current', 0):02d}" for n in nums]
        rows.append(f"{name} " + " ".join(cells))
    return "<u>前中後段</u>(號碼·遺漏期數)\n<pre>" + "\n".join(rows) + "</pre>"


def _odd_even_line(df) -> str:
    """單雙比:目前『單多』或『雙多』連續幾期(翻面就歸 0)。"""
    draws = stats.draws_as_lists(df)
    if not draws:
        return "單雙比:無資料"

    def side(draw):
        odd = sum(1 for n in draw if n % 2 == 1)
        even = len(draw) - odd
        return "單多" if odd > even else ("雙多" if even > odd else None)

    cur = side(draws[-1])
    if cur is None:
        return "<u>單雙比</u> 最新一期單雙相同(無偏向)"
    streak = 0
    for draw in reversed(draws):
        if side(draw) == cur:
            streak += 1
        else:
            break
    return f"<u>單雙比</u> 目前 <b>{cur}</b> 連續 <b>{streak}</b> 期"


def _latest_line(df) -> str:
    """最新一期:期號(日期)開出的號碼。"""
    if df is None or len(df) == 0:
        return "(尚無開獎資料)"
    row = df.iloc[-1]
    nums = [int(row[c]) for c in df.columns if str(c).startswith("n")]
    date = str(row.get("date", ""))[:10]
    return (f"<u>最新</u> 期{row.get('issue', '')}({date}) "
            f"<b>{'  '.join(f'{n:02d}' for n in nums)}</b>")


def reminder_text() -> str:
    """`/提醒` 的回覆:每款「開獎 + 1800碰 + 9000碰 + 前中後段 + 單雙比」。"""
    blocks = ["<b>開獎與區間提醒</b>"]
    for g in all_games():
        try:
            df = load_df(g.key)
        except Exception:       # noqa: BLE001 — 讀不到資料就跳過該款
            continue
        lines = [f"<b>【{g.name}】</b>", _latest_line(df)]

        # 1800碰(雙雙):兩兩十位段配對,沒開就 +1(不設門檻)
        hot = _pairs_hot(df, g.num_max)
        if hot:
            cells = [f"{p['labels'][0]}×{p['labels'][1]} <b>{p['streak']}</b>"
                     for p in hot]
            lines.append("<u>1800碰</u> 雙雙沒開 " + "、".join(cells) + " 期")
        else:
            lines.append("<u>1800碰</u> 各雙雙配對近期都有開")

        # 9000碰(全段同開):沒一起開就 +1(不設門檻)
        for c in watch_store.get_combos(g.key):
            for r in stats.combo_cooccurrence_alerts(df, [c], threshold=1):
                lines.append(
                    f"<u>9000碰</u> {r['label']} <b>{r['streak']}</b> 期沒一起開"
                    f"(最長 {r['max_gap']})")

        # 前中後段(精細到單顆遺漏)+ 單雙比
        lines.append(_seg_missing_block(df, g.num_max))
        lines.append(_odd_even_line(df))

        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def handle_command(text: str) -> str | None:
    """把收到的訊息文字對應到回覆;認得的指令才回,其他回 None。

    支援 /提醒 與 /提醒@botname(群組裡指令會被 Telegram 加上 @bot)。
    """
    cmd = (text or "").strip().split()[0] if text and text.strip() else ""
    cmd = cmd.split("@", 1)[0]          # 去掉 @botname
    if cmd in ("/提醒", "/remind", "/reminder"):
        return reminder_text()
    return None
