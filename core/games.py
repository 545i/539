"""遊戲設定中心:今彩539、天天樂(加州 Fantasy 5)與六合彩(香港)。

今彩539 與天天樂都是「39 選 5」,組合數與機率完全相同,差別只在票價與獎金結構;
六合彩(香港)則是「49 選 6」,連號碼範圍與每期開幾顆都不同。
本模組把這些差異集中成 GameConfig(num_max / pick / 票價 / 獎金 / 策略1 預設值),
讓資料驗證、統計、選號與二合買牌都能依所選遊戲套用對應規格。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import comb


@dataclass(frozen=True)
class GameConfig:
    key: str                 # 內部代號:lotto539 / fantasy5 / marksix
    name: str                # 顯示名稱
    data_file: str           # data/ 下的歷史資料檔名
    ticket_price: float      # 每注票價
    currency: str            # 幣別符號
    num_max: int = 39        # 號碼範圍上限(1 ~ num_max)
    pick: int = 5            # 每期開出幾顆號碼
    prize: dict = field(default_factory=dict)  # {中k碼: 獎金}
    prize_note: str = ""     # 獎金結構說明
    source_note: str = ""    # 資料來源說明
    # ── 首頁辨識用(讓各遊戲一眼分得出來)──
    emoji: str = "🎰"        # 專屬圖示
    region: str = ""         # 地區標籤(台灣 / 美國加州 / 香港)
    accent: str = "#e63946"  # 專屬主色(橫幅底色)
    tagline: str = ""        # 一句話特色
    # ── 二合買牌(策略1)的盤口預設值(新帳號第一次進頁面時的初值)──
    default_cost_per_car: float = 2755.0   # 每車成本
    default_win_payout: float = 21200.0    # 每車中獎可得

    # ── 玩法衍生規格 ──────────────────────────────────────
    @property
    def num_min(self) -> int:
        return 1

    @property
    def all_nums(self) -> list[int]:
        """本遊戲的完整號碼清單。"""
        return list(range(1, self.num_max + 1))

    @property
    def total_comb(self) -> int:
        """C(num_max, pick):所有可能開獎組合數。"""
        return comb(self.num_max, self.pick)

    @property
    def dan_prob(self) -> float:
        """單一膽號被開出的機率 = pick / num_max(二合拖牌「整車中」的機率)。"""
        return self.pick / self.num_max

    @property
    def notes_per_car(self) -> int:
        """二合拖牌 1 車的注數 = 1 膽拖其餘 (num_max − 1) 號。"""
        return self.num_max - 1

    def ways(self, k: int) -> int:
        """中 k 碼的組合數。"""
        return comb(self.pick, k) * comb(self.num_max - self.pick, self.pick - k)

    def prob(self, k: int) -> float:
        return self.ways(k) / self.total_comb

    def expected_prize(self) -> float:
        """每注期望獎金。"""
        return sum(self.prob(k) * self.prize.get(k, 0) for k in range(self.pick + 1))

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
    emoji="🇹🇼",
    region="台灣彩券",
    accent="#c1272d",  # 台灣紅
    tagline="每注 NT$50・固定獎金・每週一至六開獎",
)

# ── 天天樂 / 加州 Fantasy 5(pari-mutuel 浮動獎金)─────────
# 注意:Fantasy 5 為彩池均分(pari-mutuel),各獎項金額每期浮動。
# 以下為歷史「平均」估計值,僅供期望值示意,非固定獎金。
FANTASY5 = GameConfig(
    key="fantasy5",
    name="天天樂(加州 Fantasy 5)",
    data_file="history_fantasy5.csv",
    ticket_price=1,
    currency="NT$",
    prize={5: 73_000, 4: 309, 3: 13.49, 2: 1, 1: 0, 0: 0},
    prize_note="加州 Fantasy 5 為 pari-mutuel 浮動獎金,此為歷史平均估計值(中2碼贈免費彩券,以 $1 計)。",
    source_note="加州官方開獎結果(經 lottolyzer.com 彙整;官網 calottery.com 以 WAF 封鎖直連)。",
    emoji="🐻",
    region="美國・加州",
    accent="#1f7a4d",  # 加州熊旗綠
    tagline="浮動彩池獎金・每日開獎",
)

# ── 六合彩(香港,49 選 6)────────────────────────────────
# 香港六合彩為彩池均分(pari-mutuel),頭獎~三獎金額每期浮動,四獎以下固定。
# 下方 prize 是「以港元平均值 ×4 粗略換算台幣」的示意值,僅供期望值顯示,非實際派彩。
# 二合買牌(策略1)用的是台灣組頭盤口(每車成本 / 中獎可得),與官方派彩無關。
MARKSIX = GameConfig(
    key="marksix",
    name="六合彩(香港)",
    data_file="history_marksix.csv",
    ticket_price=40,
    currency="NT$",
    num_max=49,
    pick=6,
    prize={6: 32_000_000, 5: 280_000, 4: 2_560, 3: 160, 2: 0, 1: 0, 0: 0},
    prize_note=(
        "香港六合彩為 pari-mutuel 浮動彩池,此為歷史平均估計值(港元 ×4 換算台幣),"
        "且未計入「特別號」加成獎項,實際派彩每期不同。"
    ),
    source_note="樂透彩幸運發財網(pilio.idv.tw)彙整的香港六合彩開獎結果。",
    emoji="🇭🇰",
    region="香港",
    accent="#6a1b9a",  # 紫,與 539 紅 / 天天樂綠明顯區隔
    tagline="49 選 6・每週二/四/六開獎",
    default_cost_per_car=3528.0,   # 1 膽拖 48 號 = 48 注 × 73.5
    default_win_payout=28500.0,
)

GAMES: dict[str, GameConfig] = {g.key: g for g in (LOTTO539, FANTASY5, MARKSIX)}
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
