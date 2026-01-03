"""Dump one page of ECOSteam SellGoodsQuery using the same session/headers as EcosteamMonitor.

Output: data/ecosteam_sell_raw_via_monitor.json
"""

import json
from pathlib import Path
import sys

# Ensure project root on sys.path when running directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    from monitors.ecosteam import EcosteamMonitor

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    plat = cfg.get("platforms", {}).get("ecosteam", {})

    m = EcosteamMonitor(plat)

    goods_url = plat.get("goods_detail_url") or "https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html"
    goods_url = str(goods_url)

    hash_name = m._extract_hash_name(goods_url)
    if not hash_name:
        raise RuntimeError("failed to extract hash_name")

    internal_id = m._query_internal_goods_id(730, hash_name, goods_url)
    if not internal_id:
        raise RuntimeError("failed to get internal_id")

    sell_url = f"{m.base_url}/Api/SteamGoods/SellGoodsQuery"
    payload = {
        "GameId": 730,
        "GoodsId": internal_id,
        "HashName": hash_name,
        "PageIndex": 1,
        "PageSize": 40,
    }

    resp = m._make_request(
        sell_url,
        method="POST",
        json=payload,
        headers=m._ajax_headers(goods_url),
    ).json()

    out_dir = ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ecosteam_sell_raw_via_monitor.json"
    out_path.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")

    sd = resp.get("StatusData") or {}
    rd = sd.get("ResultData") or {}
    items = rd.get("PageResult") or []

    print("hash_name=", hash_name)
    print("internal_id=", internal_id)
    print("ResultCode=", sd.get("ResultCode"), "TotalRecord=", rd.get("TotalRecord"), "items=", len(items))
    print("dumped=", out_path)


if __name__ == "__main__":
    main()
