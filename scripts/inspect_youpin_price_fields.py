import json
import re
from pathlib import Path
from typing import Any, Dict, List

import requests

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def get_cookie(platform: str) -> str:
    plat = CFG.get("platforms", {}).get(platform, {})
    return plat.get("cookie") or plat.get("Cookie") or ""


def main() -> None:
    plat = CFG.get("platforms", {}).get("youpin", {})
    item = (CFG.get("items") or [])[0]

    api_base = str(plat.get("api_base_url") or "https://api.youpin898.com").rstrip("/")
    list_url = plat.get("goods_list_url") or "https://www.youpin898.com/"

    template_id = item.get("youpin_template_id") or item.get("youpin_goods_id")
    if not template_id:
        raise SystemExit("Missing templateId: set items[0].youpin_template_id or youpin_goods_id")

    payload: Dict[str, Any] = {
        "listType": int(item.get("youpin_list_type", 10)),
        "gameId": int(item.get("youpin_game_id", 730)),
        "templateId": int(template_id),
        "pageIndex": 1,
        "pageSize": 20,
    }

    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Origin": "https://www.youpin898.com",
            "Referer": list_url,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
        }
    )

    ck = get_cookie("youpin")
    if ck:
        s.headers["Cookie"] = ck

    m = re.search(r"(?:^|;\s*)uu_token=([^;]+)", ck)
    if m:
        tok = m.group(1)
        s.headers["uu-token"] = tok
        s.headers["UU-Token"] = tok
        s.headers["token"] = tok
        s.headers["Authorization"] = f"Bearer {tok}"

    url = api_base + "/api/youpin/pc/inventory/list"
    r = s.post(url, json=payload, timeout=20)
    print("status", r.status_code, "ct", r.headers.get("Content-Type", ""))
    j = r.json()
    print("code", j.get("code"), "msg", j.get("msg"))

    data = j.get("data") or {}
    items: List[Dict[str, Any]] = data.get("itemsInfos") or []
    print("totalCount", data.get("totalCount"), "itemsInfos", len(items))
    if not items:
        return

    # All keys containing 'price'
    price_keys = sorted({k for it in items for k in it.keys() if isinstance(k, str) and "price" in k.lower()})
    print("price-like keys:", price_keys)

    def pick(it: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        return {k: it.get(k) for k in keys if k in it}

    for idx, it in enumerate(items[:10], 1):
        meta = pick(it, ["name", "abrade", "steamAssetId", "marketHashName"]) 
        prices = {k: it.get(k) for k in price_keys}
        # also include the common field used by monitor
        if "price" not in prices:
            prices["price"] = it.get("price")
        print("\n--- item", idx)
        print("meta:", meta)
        print("prices:", prices)

    if "price" in items[0]:
        vals = [it.get("price") for it in items]
        print("\nunique item.price:", sorted(set(vals)))


if __name__ == "__main__":
    main()
