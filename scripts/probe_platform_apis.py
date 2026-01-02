import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def get_cookie(platform: str) -> str:
    plat = CFG.get("platforms", {}).get(platform, {})
    return plat.get("cookie") or plat.get("Cookie") or ""


def parse_youpin_list_url(url: str) -> dict:
    q = parse_qs(urlparse(url).query)
    def pick_int(key: str, default: Optional[int] = None) -> Optional[int]:
        v = q.get(key, [None])[0]
        if v is None:
            return default
        try:
            return int(v)
        except ValueError:
            return default

    return {
        "listType": pick_int("listType", 10),
        "templateId": pick_int("templateId"),
        "gameId": pick_int("gameId", 730),
    }


def parse_eco_goods_url(url: str) -> dict:
    # Example: /goods/730-15231-1-laypagesale-0-1.html
    m = re.search(r"/goods/(\d+)-(\d+)-", url)
    if not m:
        return {}
    return {"gameId": int(m.group(1)), "goodsId": int(m.group(2))}


def probe_youpin() -> None:
    plat = CFG.get("platforms", {}).get("youpin", {})
    goods_list_url = plat.get("goods_list_url") or "https://www.youpin898.com/market/goods-list?listType=10&templateId=109545&gameId=730"
    info = parse_youpin_list_url(goods_list_url)
    print("\n=== YOUPIN url params:", info)

    base = plat.get("base_url", "https://www.youpin898.com").rstrip("/")
    # Some deployments only allow this API on api.youpin898.com
    api_bases = [base, "https://api.youpin898.com"]

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": goods_list_url,
        "Origin": "https://www.youpin898.com",
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
    })
    ck = get_cookie("youpin")
    if ck:
        s.headers["Cookie"] = ck

    # Some YOUPIN APIs may require token as header instead of Cookie
    token = None
    m = re.search(r"(?:^|;\s*)uu_token=([^;]+)", ck)
    if m:
        token = m.group(1)
        s.headers["uu-token"] = token
        s.headers["UU-Token"] = token
        s.headers["token"] = token
        s.headers["Authorization"] = f"Bearer {token}"

    # Try a few payload variants
    payloads = [
        {"pageIndex": 1, "pageSize": 20, **info},
        {"page": 1, "pageSize": 20, **info},
        {"pageIndex": 1, "pageSize": 20, "sortType": 0, **info},
    ]

    for api_base in api_bases:
        api = api_base.rstrip("/") + "/api/youpin/pc/inventory/list"
        for i, data in enumerate(payloads, start=1):
            try:
                r = s.post(api, json=data, timeout=20)
                print(f"\nYOUPIN {api_base} POST try #{i} status={r.status_code} ct={r.headers.get('Content-Type','')}")
                print(r.text[:300].replace("\n", "\\n"))
                j = r.json()
                print("keys:", list(j.keys())[:20])
                # guess list container
                for k in ("data", "result", "content", "Data"):
                    if isinstance(j.get(k), dict):
                        inner = j[k]
                        print(" inner keys:", list(inner.keys())[:20])
                        for lk in ("list", "items", "records", "List"):
                            if isinstance(inner.get(lk), list) and inner[lk]:
                                print(" first item keys:", list(inner[lk][0].keys())[:30])
                                return
            except Exception as e:
                print("YOUPIN error:", e)


def probe_eco() -> None:
    plat = CFG.get("platforms", {}).get("ecosteam", {})
    goods_url = plat.get("goods_detail_url") or "https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html"
    info = parse_eco_goods_url(goods_url)
    print("\n=== ECO url params:", info)

    base = plat.get("base_url", "https://www.ecosteam.cn").rstrip("/")

    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": goods_url,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
    })
    ck = get_cookie("ecosteam")
    if ck:
        s.headers["Cookie"] = ck

    # Extract HashName from goods detail page HTML (contains the canonical market hash name)
    try:
        html = s.get(goods_url, timeout=20).text
        m = re.search(r'data-HashName="([^"]+)"', html)
        hash_name = m.group(1) if m else None
    except Exception:
        hash_name = None
    print("ECO extracted HashName:", hash_name)

    # Step 1: query goods detail by HashName (API expects PascalCase keys)
    internal_goods_id = None
    if hash_name:
        try:
            r = s.post(
                base + "/Api/SteamGoods/GoodsDetailQueryPost",
                json={"GameId": info.get("gameId"), "HashName": hash_name},
                timeout=20,
            )
            print(f"\nECO detail-by-hash status={r.status_code} ct={r.headers.get('Content-Type','')}")
            print(r.text[:300].replace("\n", "\\n"))
            j = r.json()
            sd = (j.get("StatusData") or {})
            rd = (sd.get("ResultData") or {})
            internal_goods_id = rd.get("Id") or rd.get("GoodsId") or rd.get("SteamGoodsId")
            print("detail ResultCode/Msg:", sd.get("ResultCode"), sd.get("ResultMsg"))
            print("internal_goods_id:", internal_goods_id)
        except Exception as e:
            print("ECO detail-by-hash error:", e)

    candidates = [
        # Try sell list by internal id / hash name
        (
            "POST",
            base + "/Api/SteamGoods/SellGoodsQuery",
            {
                "GameId": info.get("gameId"),
                "GoodsId": internal_goods_id,
                "HashName": hash_name,
                "PageIndex": 1,
                "PageSize": 20,
            },
        ),
        (
            "POST",
            base + "/Api/SteamGoods/SellGoodsQuery",
            {
                "GameId": info.get("gameId"),
                "HashName": hash_name,
                "PageIndex": 1,
                "PageSize": 20,
            },
        ),
        (
            "POST",
            base + "/Api/SteamGoods/SellGoodsQuery",
            {
                "GameId": info.get("gameId"),
                "GoodsId": internal_goods_id,
                "PageIndex": 1,
                "PageSize": 20,
            },
        ),
        # Other potential list endpoints
        (
            "GET",
            base + "/Api/ReSellGoods/GetReSellDetail",
            {"GoodsId": internal_goods_id, "HashName": hash_name},
        ),
    ]

    for method, url, data in candidates:
        try:
            if method == "GET":
                r = s.get(url, params=data, timeout=20)
            else:
                r = s.post(url, json=data, timeout=20)

            print(f"\nECO {method} {url} status={r.status_code} ct={r.headers.get('Content-Type','')}")
            print(r.text[:300].replace("\n", "\\n"))
            try:
                j = r.json()
            except Exception:
                continue
            print("keys:", list(j.keys())[:20])
            # ECO uses StatusData nesting
            if "StatusData" in j and isinstance(j.get("StatusData"), dict):
                sd = j["StatusData"]
                rd = sd.get("ResultData")
                if isinstance(rd, dict):
                    print(" ResultCode/Msg:", sd.get("ResultCode"), sd.get("ResultMsg"))
                    for lk in ("PageResult", "List", "Items"):
                        if isinstance(rd.get(lk), list) and rd[lk]:
                            print(" first item keys:", list(rd[lk][0].keys())[:40])
                            return
            for k in ("data", "result"):
                if isinstance(j.get(k), dict):
                    inner = j[k]
                    print(" inner keys:", list(inner.keys())[:30])
                    for lk in ("list", "items", "records", "rows"):
                        if isinstance(inner.get(lk), list) and inner[lk]:
                            print(" first item keys:", list(inner[lk][0].keys())[:40])
                            return
        except Exception as e:
            print("ECO error:", e)


def main() -> None:
    probe_youpin()
    probe_eco()


if __name__ == "__main__":
    main()
