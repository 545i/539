"""遊戲設定中心:今彩539 與 天天樂(加州 Fantasy 5)。

兩款玩法都是「39 選 5」,所以組合數與機率(core.constants 的 WAYS / prob)完全相同,
差別只在「票價」與「獎金結構」。本模組把這些差異集中成 GameConfig,
讓統計/選號/回測/凱莉/Excel 都能依所選遊戲套用對應設定,達到「兩款統計分開」。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core import constants


@dataclass(frozen=True)
class GameConfig:
    key: str                 # 內部代號:lotto539 / fantasy5
    name: str                # 顯示名稱
    data_file: str           # data/ 下的歷史資料檔名
    ticket_price: float      # 每注票價
    currency: str            # 幣別符號
    prize: dict = field(default_factory=dict)  # {中k碼: 獎金}
    prize_note: str = ""     # 獎金結構說明
    source_note: str = ""    # 資料來源說明

    # 組合數與機率對兩款相同(皆 5/39),直接沿用 constants
    def prob(self, k: int) -> float:
        return constants.prob(k)

    def ways(self, k: int) -> int:
        return constants.WAYS[k]

    def expected_prize(self) -> float:
        """每注期望獎金。"""
        return sum(self.prob(k) * self.prize.get(k, 0) for k in range(constants.PICK + 1))

    def expected_return(self) -> float:
        """每注長期期望報酬率。"""
        return self.expected_prize() / self.ticket_price - 1.0


# ── 今彩539(台灣彩券,固定獎金)──────────────────────────
LOTTO539 = GameConfig(
    key="lotto539",
    name="今彩539",
    data_file="history.csv",
    ticket_price=50,
    currency="NT$",
    prize={5: 8_000_000, 4: 20_000, 3: 300, 2: 50, 1: 0, 0: 0},
    prize_note="台灣彩券固定獎金(頭獎全期上限均分,單注回測不觸發)。",
    source_note="台灣彩券官方 API(api.taiwanlottery.com)。",
)

# ── 天天樂 / 加州 Fantasy 5(pari-mutuel 浮動獎金)─────────
# 注意:Fantasy 5 為彩池均分(pari-mutuel),各獎項金額每期浮動。
# 以下為歷史「平均」估計值,僅供期望值示意,非固定獎金。
FANTASY5 = GameConfig(
    key="fantasy5",
    name="天天樂(加州 Fantasy 5)",
    data_file="history_fantasy5.csv",
    ticket_price=1,
    currency="US$",
    prize={5: 73_000, 4: 309, 3: 13.49, 2: 1, 1: 0, 0: 0},
    prize_note="加州 Fantasy 5 為 pari-mutuel 浮動獎金,此為歷史平均估計值(中2碼贈免費彩券,以 $1 計)。",
    source_note="加州官方開獎結果(經 lottolyzer.com 彙整;官網 calottery.com 以 WAF 封鎖直連)。",
)

GAMES: dict[str, GameConfig] = {g.key: g for g in (LOTTO539, FANTASY5)}
DEFAULT_GAME = LOTTO539


def get(key: str) -> GameConfig:
    """以代號取得 GameConfig,找不到回傳預設(今彩539)。"""
    return GAMES.get(key, DEFAULT_GAME)


def by_name(name: str) -> GameConfig:
    """以顯示名稱取得 GameConfig。"""
    for g in GAMES.values():
        if g.name == name:
            return g
    return DEFAULT_GAME
