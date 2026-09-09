"""連碰星數盤口的後台設定:每個星數的每碰成本與中一碰派彩。

改的是**全域**成本,不是個人偏好 —— 站上所有人的試算、快速上傳的成本、
返還率都跟著動,所以 PUT 要登入。GET 不用:未登入也看得到現在的價碼,
不然試算頁顯示的數字會沒人講得出是哪裡來的。

實際存哪、怎麼套進計算,見 backend/star_cost_store.py。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import star_cost_store
from backend.deps import current_user
from core import combo

router = APIRouter(prefix="/star-cost", tags=["star-cost"])


def _payload(costs: dict) -> dict:
    """設定 → API 形狀。JSON 的物件鍵一律是字串,所以星數轉成 "2"/"3"/"4"。"""
    return {
        "stars": list(combo.STARS),
        "star_names": {str(k): combo.star_name(k) for k in combo.STARS},
        "costs": {str(k): {"cost": v["cost"], "prize": v["prize"],
                           "custom": v["custom"], "updated": v["updated"],
                           "updated_by": v["updated_by"]}
                  for k, v in costs.items()},
        "defaults": {str(k): v for k, v in combo.market_defaults().items()},
    }


@router.get("")
def get_star_costs():
    """目前生效的每星數盤口(含出廠預設,供前端顯示「原本是多少」)。"""
    return _payload(star_cost_store.get_costs())


class StarCostRow(BaseModel):
    cost: float = Field(..., gt=0)      # 每碰成本
    prize: float = Field(..., gt=0)     # 中一碰可得


class StarCostIn(BaseModel):
    # 鍵是星數(前端送 JSON,鍵一定是字串);只給部分星數就只改那幾個
    costs: dict[str, StarCostRow]


@router.put("")
def put_star_costs(body: StarCostIn, user: str = Depends(current_user)):
    """改盤口(需登入)。寫進資料庫後**立刻**套進 core,不必重啟。"""
    try:
        saved = star_cost_store.set_costs(
            {int(k): v.model_dump() for k, v in body.costs.items()},
            updated_by=user,
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    star_cost_store.apply_to_core()
    return _payload(saved)


@router.delete("")
def reset_star_costs(user: str = Depends(current_user)):
    """還原成程式內建的出廠預設(需登入)。"""
    star_cost_store.reset()
    return _payload(star_cost_store.apply_to_core())
