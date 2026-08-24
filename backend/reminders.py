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


def push_game_update(game_key: str) -> bool:
    """新開獎自動推播:只發「這一款」的完整提醒(格式同 /提醒,0 期不顯示)。

    開獎時刻各款不同(見 core.drawtime),排程的 on_added 會帶入剛更新的
    game_key,所以這裡只推該款,不會把三款全發一遍。沒設定 / 讀不到資料回 False。
    """
    if not notify.enabled():
        return False
    try:
        df = load_df(game_key)
        block = _game_block(get_game(game_key), df)
    except Exception:       # noqa: BLE001 — 推播失敗不能影響排程
        return False
    if not block:
        return False
    return notify.send(block)


def on_new_draw(game_key: str) -> None:
    """排程偵測到新開獎時的掛鉤(見 core.autoupdate 的 on_added)。"""
    push_game_update(game_key)


# ── /提醒 指令:開獎狀況 + 區間組合斷檔 + 大區間斷檔(唯讀) ──────────
def _thirds(num_max: int) -> list[tuple[str, list[int]]]:
    """前 / 中 / 後三段,均分(39 → 前 01~13、中 14~26、後 27~39,各 13 顆)。"""
    b1 = round(num_max / 3)
    b2 = round(num_max * 2 / 3)
    return [
        ("前", list(range(1, b1 + 1))),
        ("中", list(range(b1 + 1, b2 + 1))),
        ("後", list(range(b2 + 1, num_max + 1))),
    ]


def _seg_missing_block(df, num_max: int) -> str:
    """前中後三段各成一直柱(欄)並排,每格「號碼:遺漏」,精細到單顆。

    只列「遺漏 >= 1 期」的號碼(本期剛開出的 0 期不顯示);三段號碼數不同,
    較短的欄補空白對齊。三段都沒遺漏則保留標題、不畫柱。
    CJK 標題(前/中/後)在等寬字型約佔 2 格,補到與資料格同寬 → 上下對齊。
    """
    miss = stats.missing(df, num_max)
    cols = []          # 三段各自的 "NN:MM" 清單(只含遺漏 >= 1)
    names = []
    for name, nums in _thirds(num_max):
        cols.append([f"{n:02d}:{c:02d}" for n in nums
                     if (c := miss.get(n, {}).get("current", 0)) >= 1])
        names.append(name)
    height = max((len(c) for c in cols), default=0)
    if height == 0:
        return "<u>前中後段</u> 目前全部號碼近期皆有開出"

    cell_w = 5         # "NN:MM"
    gap = "  "
    blank = " " * cell_w
    header = gap.join(f"{nm}{' ' * (cell_w - 2)}" for nm in names)  # CJK 約 2 格
    rows = [header.rstrip()]
    for i in range(height):
        row = gap.join(col[i] if i < len(col) else blank for col in cols)
        rows.append(row.rstrip())
    return "<u>前中後段</u>(號碼:遺漏)\n<pre>" + "\n".join(rows) + "</pre>"


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


def _game_block(g, df) -> str:
    """單一遊戲的提醒區塊:開獎 + 1800碰 + 9000碰 + 前中後段 + 單雙比。

    「0 期不顯示」只針對細項 —— 沒斷檔的配對、剛開出的號碼不列;但**區塊標題
    一律保留**,全部都 0(沒有任何斷檔)時改印「目前無斷檔」,不讓區塊整個消失。
    這塊同時給 `/提醒`(彙整全部)與新開獎自動推播(只發該款)共用。
    """
    lines = [f"<b>【{g.name}】</b>", _latest_line(df)]

    # 1800碰(雙雙):只列「連續 >=1 期沒一起開」的十位段配對(0 期不列);全 0 保留標題
    hot_pairs = sorted(
        (p for p in stats.tens_pair_alerts(df, threshold=1, num_max=g.num_max)
         if p["streak"] >= 1),
        key=lambda p: (-p["streak"], p["bands"][0], p["bands"][1]))
    if hot_pairs:
        cells = [f"{p['labels'][0]}+{p['labels'][1]}·{p['streak']:02d}"
                 for p in hot_pairs]
        lines.append("<u>1800碰</u>(配對·幾期沒開)\n<pre>" + "  ".join(cells) + "</pre>")
    else:
        lines.append("<u>1800碰</u> 目前無斷檔(各配對都有一起開)")

    # 9000碰(全段同開):只列連續 >=1 期沒一起開的(0 期不列);全 0 保留標題
    nine = []
    for c in watch_store.get_combos(g.key):
        for r in stats.combo_cooccurrence_alerts(df, [c], threshold=1):
            if r["streak"] >= 1:
                nine.append(
                    f"<u>9000碰</u> {r['label']} <b>{r['streak']}</b> 期沒一起開"
                    f"(最長 {r['max_gap']})")
    if nine:
        lines.extend(nine)
    else:
        lines.append("<u>9000碰</u> 目前無斷檔(各段都有一起開)")

    # 前中後段(精細到單顆遺漏,0 期不列;標題一律保留)+ 單雙比
    lines.append(_seg_missing_block(df, g.num_max))
    lines.append(_odd_even_line(df))
    return "\n".join(lines)


def reminder_text() -> str:
    """`/提醒` 的回覆:彙整每一款的提醒區塊(0 期不顯示)。"""
    blocks = ["<b>開獎與區間提醒</b>"]
    for g in all_games():
        try:
            df = load_df(g.key)
        except Exception:       # noqa: BLE001 — 讀不到資料就跳過該款
            continue
        blocks.append(_game_block(g, df))
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
