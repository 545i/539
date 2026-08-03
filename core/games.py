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
    short_name: str = ""     # 表格用的短名稱(手機版避免被長名撐開)
    prize_note: str = ""     # 獎金結構說明
    source_note: str = ""    # 資料來源說明
    # ── 二合買牌(策略1)的盤口預設值(新帳號第一次進頁面時的初值)──
    default_cost_per_car: float = 2755.0   # 每車成本
    default_win_payout: float = 21200.0    # 每車中獎可得

    @property
    def label(self) -> str:
        """表格/選單用的簡短名稱;沒設就用完整名稱。"""
        return self.short_name or self.name

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
    short_name="今彩539",
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
    short_name="天天樂",
    data_file="history_fantasy5.csv",
    ticket_price=1,
    currency="NT$",
    prize={5: 73_000, 4: 309, 3: 13.49, 2: 1, 1: 0, 0: 0},
    prize_note="加州 Fantasy 5 為 pari-mutuel 浮動獎金,此為歷史平均估計值(中2碼贈免費彩券,以 $1 計)。",
    source_note="加州官方開獎結果(經 lottolyzer.com 彙整;官網 calottery.com 以 WAF 封鎖直連)。",
)

# ── 六合彩(香港,49 選 6)────────────────────────────────
# 香港六合彩為彩池均分(pari-mutuel),頭獎~三獎金額每期浮動,四獎以下固定。
# 下方 prize 是「以港元平均值 ×4 粗略換算台幣」的示意值,僅供期望值顯示,非實際派彩。
# 二合買牌(策略1)用的是台灣組頭盤口(每車成本 / 中獎可得),與官方派彩無關。
MARKSIX = GameConfig(
    key="marksix",
    name="六合彩",
    short_name="六合彩",
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
    default_cost_per_car=3528.0,   # 1 膽拖 48 號 = 48 注 × 73.5
    default_win_payout=28500.0,
)

# 目前啟用的遊戲(下注、統計、資料更新都跑這些)
GAMES: dict[str, GameConfig] = {g.key: g for g in (LOTTO539, FANTASY5, MARKSIX)}
DEFAULT_GAME = LOTTO539

# 已停用、但歷史下注紀錄還在的遊戲。
# 不放進 GAMES(所以不會出現在下注/統計介面),但 get() 仍查得到 ——
# 這樣舊紀錄在流水與分款統計裡才會顯示正確的名稱,而不是被誤標成別款。
# 目前沒有停用中的遊戲;要停用哪一款就把它從 GAMES 移到這裡。
RETIRED: dict[str, GameConfig] = {}


def get(key: str) -> GameConfig:
    """以代號取得 GameConfig(含已停用的遊戲);找不到回傳預設。"""
    return GAMES.get(key) or RETIRED.get(key, DEFAULT_GAME)


def is_active(key: str) -> bool:
    """該遊戲目前是否可以下注。"""
    return key in GAMES


def by_name(name: str) -> GameConfig:
    """以顯示名稱取得 GameConfig。"""
    for g in GAMES.values():
        if g.name == name:
            return g
    return DEFAULT_GAME
