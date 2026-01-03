"""Dump ECOSteam sell list via API and save full raw items.

This exports the raw `PageResult` items so you can inspect which fields
correspond to the UI wear/price.

Output: data/ecosteam_sell_dump_from_api.json
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def get_cookie(platform: str) -> str:
    plat = CFG.get("platforms", {}).get(platform, {})
    return plat.get("cookie") or plat.get("Cookie") or ""


def main() -> None:
    plat = CFG.get("platforms", {}).get("ecosteam", {})
    base = str(plat.get("base_url", "https://www.ecosteam.cn")).rstrip("/")
    goods_url = "https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html"
    cookie = get_cookie("ecosteam")

    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Referer": goods_url,
            "Origin": base,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
    )
    if cookie:
        s.headers["Cookie"] = cookie

    print("fetch goods html...")
    html = s.get(goods_url, timeout=30).text
    m = re.search(r'data-HashName="([^"]+)"', html)
    hash_name = m.group(1) if m else None
    if not hash_name:
        raise RuntimeError("failed to extract data-HashName")
    print("hash_name=", hash_name)

    print("query internal goods id...")
    detail = s.post(
        base + "/Api/SteamGoods/GoodsDetailQueryPost",
        json={"GameId": 730, "HashName": hash_name},
        timeout=30,
    ).json()
    sd = detail.get("StatusData") or {}
    rd = sd.get("ResultData") or {}
    internal_id = rd.get("Id")
    if not internal_id:
        raise RuntimeError(f"failed to resolve internal id: ResultCode={sd.get('ResultCode')} Msg={sd.get('ResultMsg')}")
    print("internal_id=", internal_id)

    sell_url = base + "/Api/SteamGoods/SellGoodsQuery"
    page_size = 40

    all_items: List[Dict[str, Any]] = []
    page_index = 1
    total_record: Optional[int] = None

    while True:
        payload = {
            "GameId": 730,
            "GoodsId": internal_id,
            "HashName": hash_name,
            "PageIndex": page_index,
            "PageSize": page_size,
        }
        print(f"fetch page {page_index}...")
        resp = s.post(sell_url, json=payload, timeout=30).json()
        sd = resp.get("StatusData") or {}
        rc = str(sd.get("ResultCode"))
        if rc != "0":
            raise RuntimeError(f"SellGoodsQuery failed: code={rc} msg={sd.get('ResultMsg')}")

        rd = sd.get("ResultData") or {}
        if total_record is None:
            total_record = rd.get("TotalRecord")

        items = rd.get("PageResult") or []
        if not items:
            break

        for it in items:
            # annotate for easier inspection
            if isinstance(it, dict):
                it.setdefault("__pageIndex", page_index)
        all_items.extend(items)

        # stop if we already got all
        if isinstance(total_record, int) and len(all_items) >= total_record:
            break

        page_index += 1
        if page_index > 50:
            break

    out_dir = ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ecosteam_sell_dump_from_api.json"

    payload_out = {
        "goods_url": goods_url,
        "hash_name": hash_name,
        "internal_id": internal_id,
        "total_record": total_record,
        "count": len(all_items),
        "items": all_items,
    }
    out_path.write_text(json.dumps(payload_out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("total_record=", total_record)
    print("items_dumped=", len(all_items))
    if all_items:
        first = all_items[0]
        if isinstance(first, dict):
            wear_like = [k for k in first.keys() if any(t in k.lower() for t in ["wear", "scale", "float", "abrade", "abras"])][:30]
            print("first_item_wear_like_keys=", wear_like)
    print("dumped=", out_path)


if __name__ == "__main__":
    main()
