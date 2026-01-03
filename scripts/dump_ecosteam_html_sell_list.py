"""Dump ECOSteam sell list by parsing the goods HTML pages.

This script follows the frontend structure:
- Wear is in: <p class="WearRate"> ... <span>0.xxx</span>
- Pagination links: <a href="/goods/...-0-2.html" data-page="2">2</a>

It writes a JSON file under data/ with all parsed rows.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests


ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def get_cookie(platform: str) -> str:
    plat = CFG.get("platforms", {}).get(platform, {})
    return plat.get("cookie") or plat.get("Cookie") or ""


@dataclass
class ParsedRow:
    page: int
    wear: float
    price: float
    seller: Optional[str]


_WEAR_RE = re.compile(
    r"<p\s+class=\"WearRate\"[^>]*>[\s\S]*?<span[^>]*>\s*([0-9]+(?:\.[0-9]+)?)\s*</span>[\s\S]*?</p>",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"￥\s*([0-9]+(?:\.[0-9]+)?)")
_SELLER_RE = re.compile(r"\b(ECO_[A-Za-z0-9_\-]+)\b")
_MAX_PAGE_RE = re.compile(r"data-page=\"(\d+)\"")


def _make_session(base: str, referer: str, cookie: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Referer": referer,
            "Origin": base,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    if cookie:
        s.headers["Cookie"] = cookie
    return s


def _page_url(goods_url: str, page: int) -> str:
    # Example: https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html
    # Replace the trailing page number.
    return re.sub(r"-0-\d+\.html$", f"-0-{page}.html", goods_url)


def _detect_max_page(html: str) -> int:
    nums = [int(m.group(1)) for m in _MAX_PAGE_RE.finditer(html)]
    return max(nums) if nums else 1


def _parse_rows_from_html(html: str, page: int) -> List[ParsedRow]:
    rows: List[ParsedRow] = []
    for m in _WEAR_RE.finditer(html):
        wear_s = m.group(1)
        try:
            wear = float(wear_s)
        except ValueError:
            continue

        # Look ahead a limited window from the wear block to find the nearest price and seller.
        start = m.end()
        window = html[start : start + 2500]

        price_m = _PRICE_RE.search(window)
        if not price_m:
            continue
        try:
            price = float(price_m.group(1))
        except ValueError:
            continue

        seller_m = _SELLER_RE.search(window)
        seller = seller_m.group(1) if seller_m else None

        rows.append(ParsedRow(page=page, wear=wear, price=price, seller=seller))

    return rows


def main() -> None:
    plat = CFG.get("platforms", {}).get("ecosteam", {})
    base = str(plat.get("base_url", "https://www.ecosteam.cn")).rstrip("/")
    goods_url = str(plat.get("goods_detail_url") or "https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html")
    cookie = get_cookie("ecosteam")

    s = _make_session(base=base, referer=goods_url, cookie=cookie)

    print("fetch page 1...", goods_url)
    html1 = s.get(goods_url, timeout=20).text
    max_page = _detect_max_page(html1)

    all_rows: List[ParsedRow] = []

    # Parse page 1 first
    rows1 = _parse_rows_from_html(html1, page=1)
    print(f" parsed rows: {len(rows1)}")
    all_rows.extend(rows1)

    # Parse remaining pages
    for page in range(2, max_page + 1):
        url = _page_url(goods_url, page)
        print(f"fetch page {page}... {url}")
        try:
            html = s.get(url, timeout=20).text
        except Exception as e:
            print(f"  FAILED page {page}: {e}")
            break
        rows = _parse_rows_from_html(html, page=page)
        print(f"  parsed rows: {len(rows)}")
        all_rows.extend(rows)

    out_dir = ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ecosteam_sell_dump_from_html.json"

    payload = {
        "goods_url": goods_url,
        "max_page": max_page,
        "count": len(all_rows),
        "rows": [row.__dict__ for row in all_rows],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"goods_url={goods_url}")
    print(f"max_page={max_page}")
    print(f"rows={len(all_rows)}")
    if all_rows:
        sample = all_rows[:5]
        print("sample:")
        for r in sample:
            print(f"  page={r.page} wear={r.wear:.6f} price={r.price:.2f} seller={r.seller}")
    print(f"dumped={out_path}")


if __name__ == "__main__":
    main()
