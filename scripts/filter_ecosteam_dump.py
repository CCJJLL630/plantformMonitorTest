"""Filter ECOSteam HTML dump by wear range and sort by price.

Input:
- data/ecosteam_sell_dump_from_html.json (created by dump_ecosteam_html_sell_list.py)
- config.json (uses first item's wear_range by default)

Output:
- data/ecosteam_sell_filtered_sorted.json
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    cfg = _load_json(ROOT / "config.json")
    items = cfg.get("items", [])
    if not items:
        raise SystemExit("config.json has no items")

    item0 = items[0]
    wear_range = item0.get("wear_range") or {}
    wear_min = float(wear_range.get("min", 0.0))
    wear_max = float(wear_range.get("max", 1.0))

    dump_path = ROOT / "data" / "ecosteam_sell_dump_from_html.json"
    dump = _load_json(dump_path)
    rows = dump.get("rows", [])

    filtered: List[Dict[str, Any]] = []
    for r in rows:
        try:
            wear = float(r.get("wear"))
            price = float(r.get("price"))
        except Exception:
            continue
        if wear_min <= wear <= wear_max:
            filtered.append({
                "page": r.get("page"),
                "wear": wear,
                "price": price,
                "seller": r.get("seller"),
            })

    filtered.sort(key=lambda x: (x["price"], x["wear"]))

    out = {
        "goods_url": dump.get("goods_url"),
        "wear_min": wear_min,
        "wear_max": wear_max,
        "count": len(filtered),
        "rows": filtered,
    }

    out_path = ROOT / "data" / "ecosteam_sell_filtered_sorted.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("wear_range=", wear_min, wear_max)
    print("matched=", len(filtered))
    print("dumped=", out_path)

    for i, r in enumerate(filtered[:20], start=1):
        print(f"{i:02d}. price={r['price']:.2f} wear={r['wear']:.6f} page={r.get('page')} seller={r.get('seller')}")


if __name__ == "__main__":
    main()
