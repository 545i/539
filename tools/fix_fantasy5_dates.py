"""一次性修正:把天天樂歷史資料的日期從「加州當地日期」改成「台灣日期」,並補上期號。

背景:
  原本天天樂抓 lottolyzer,它記加州當地日期。加州晚上開獎時台灣已經隔天,
  所以台灣站顯示 08/07 的那期,我們的檔案裡是 08-06 —— 看起來像少了一天,
  實際上號碼一模一樣,只是日期基準差一天。

做法:
  1. 先用彩世界(tof)的最近 100 期驗證:既有資料 +1 天之後,號碼必須逐期完全吻合。
     驗不過就中止,不動任何資料。
  2. 全部日期 +1 天,並把 tof 有的期號回填進去。
  3. 寫回前備份成 <檔名>.bak_datefix。

可重複執行:如果偵測到日期已經是台灣基準(不位移就能對上),直接跳過。

用法:python tools/fix_fantasy5_dates.py [--apply]   (預設乾跑)
"""
from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import games, loader, scraper_tof  # noqa: E402

GAME = games.get("fantasy5")


def _nums(row, pick: int) -> tuple:
    return tuple(int(row[f"n{i}"]) for i in range(1, pick + 1))


def main(path: Path, apply: bool) -> int:
    df = loader.load_history(path, GAME.pick, GAME.num_max)
    if "issue" not in df.columns:
        df["issue"] = ""
    df["issue"] = df["issue"].fillna("").astype(str).str.strip()
    print(f"既有資料 {len(df)} 筆:{df['date'].min().date()} ~ {df['date'].max().date()}")

    tof = scraper_tof.fetch_history("fantasy5", GAME.pick, GAME.num_max)
    by_date = {r["date"]: r for r in tof}
    print(f"對照來源(tof)最近 {len(tof)} 期:{tof[0]['date']} ~ {tof[-1]['date']}")

    # 已經有期號的列 = 之前自動更新從 tof 抓來的,已是台灣日期,不能再動;
    # 沒有期號的列 = 舊的 lottolyzer 資料,記的是加州日期,要 +1 天。
    legacy = df[df["issue"] == ""].copy()
    fixed = df[df["issue"] != ""].copy()
    print(f"  已是台灣基準(有期號){len(fixed)} 筆、待位移(無期號){len(legacy)} 筆")
    if legacy.empty:
        print("\n全部都已修正過,不需要動作。")
        return 0

    # 只用「待位移」那段驗證:它 +1 天之後必須與 tof 逐期吻合
    hit_raw = hit_shift = overlap_raw = overlap_shift = 0
    for _, r in legacy.iterrows():
        d, got = r["date"].date(), _nums(r, GAME.pick)
        if d in by_date:
            overlap_raw += 1
            hit_raw += got == _nums(by_date[d], GAME.pick)
        d1 = d + dt.timedelta(days=1)
        if d1 in by_date:
            overlap_shift += 1
            hit_shift += got == _nums(by_date[d1], GAME.pick)
    print(f"\n待位移那段 —— 不位移:重疊 {overlap_raw} 期吻合 {hit_raw};"
          f"  +1 天:重疊 {overlap_shift} 期吻合 {hit_shift}")

    if overlap_raw and hit_raw == overlap_raw and overlap_shift == 0:
        print("\n日期已經是台灣基準,不需要修正。")
        return 0
    if not overlap_shift or hit_shift != overlap_shift:
        print("\n中止:+1 天之後號碼並非逐期吻合,不能確定位移是對的,不動任何資料。")
        return 1

    legacy["date"] = pd.to_datetime(legacy["date"]) + pd.Timedelta(days=1)
    out = pd.concat([fixed, legacy], ignore_index=True)
    # 回填期號,並讓 tof 那份(有期號)在重複時勝出
    issues = {r["date"]: r["issue"] for r in tof}
    out["issue"] = [issues.get(d.date(), iss)
                    for d, iss in zip(pd.to_datetime(out["date"]), out["issue"])]
    merged = loader.merge(out, tof)

    # 位移後同一期可能同時以「舊列(加州日期)」與「tof 列(台灣日期)」存在。
    # 只清「號碼相同**且日期相鄰**」的那種 —— 相隔數月的相同號碼是真的巧合開出同一組
    # (57 萬種組合,3000 期裡出現幾次很正常),誤刪就是砍掉合法歷史。
    merged = merged.sort_values("date").reset_index(drop=True)
    key = merged[[f"n{i}" for i in range(1, GAME.pick + 1)]].astype(str).agg(",".join,
                                                                            axis=1)
    dates = pd.to_datetime(merged["date"])
    issues = merged["issue"].astype(str)
    drop = set()
    for _, idx in key.groupby(key).groups.items():
        idx = list(idx)
        for a, b in zip(idx, idx[1:]):
            if abs((dates[b] - dates[a]).days) > 2:
                continue                      # 相隔太遠 = 巧合,兩筆都留
            drop.add(a if issues[a].strip() == "" else b)   # 丟掉沒期號的那筆
    dup = len(drop)
    merged = merged.drop(index=list(drop)).reset_index(drop=True)
    filled = int((merged["issue"].astype(str) != "").sum())
    print(f"\n位移後 {len(merged)} 筆:{pd.to_datetime(merged['date']).min().date()} ~ "
          f"{pd.to_datetime(merged['date']).max().date()},"
          f"期號 {filled} 筆,清掉同期重複 {dup} 筆")

    if not apply:
        print("\n[乾跑] 未寫入。確認無誤後加 --apply 執行。")
        return 0

    bak = path.with_name(path.name + ".bak_datefix")
    shutil.copy2(path, bak)
    loader.save(merged, path)
    print(f"\n已備份 {bak}\n已寫入 {path}")
    return 0


if __name__ == "__main__":
    data = Path(__file__).resolve().parent.parent / "data" / GAME.data_file
    raise SystemExit(main(data, "--apply" in sys.argv))
