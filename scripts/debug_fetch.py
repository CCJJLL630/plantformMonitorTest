import json
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"


def load_cookie(config: dict, platform: str) -> str:
    plat = config.get("platforms", {}).get(platform, {})
    return plat.get("cookie") or plat.get("Cookie") or ""


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    targets = [
        (
            "ecosteam",
            "https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html",
        ),
        (
            "youpin",
            "https://www.youpin898.com/market/goods-list?listType=10&templateId=109545&gameId=730",
        ),
    ]

    for name, url in targets:
        cookie = load_cookie(cfg, name)
        s = requests.Session()
        s.headers.update({"User-Agent": "Mozilla/5.0"})
        if cookie:
            s.headers["Cookie"] = cookie

        r = s.get(url, timeout=20)
        text = r.text
        print(f"\n=== {name} status={r.status_code} len={len(text)}")
        print(text[:1200].replace("\n", "\\n"))

        for marker in ["__NUXT__", "__NEXT_DATA__", "window.__NUXT__", "__INITIAL_STATE__"]:
            if marker in text:
                print("FOUND", marker)

        # script sources
        scripts = sorted(set(re.findall(r"<script[^>]+src=\"([^\"]+)\"", text)))
        if scripts:
            print("Script src (first 10):")
            for ssrc in scripts[:10]:
                print(" ", ssrc)

            # Prefer likely business scripts first (e.g., goods detail/list), then scan a few
            preferred = [s for s in scripts if any(k in s.lower() for k in ["goods", "detail", "list", "market", "commodity"])]
            scan_list = (preferred + [s for s in scripts if s not in preferred])[:4]

            for ssrc in scan_list:
                try:
                    if ssrc.startswith("//"):
                        script_url = "https:" + ssrc
                    elif ssrc.startswith("http"):
                        script_url = ssrc
                    else:
                        # same-origin
                        from urllib.parse import urljoin

                        script_url = urljoin(url, ssrc)

                    sr = s.get(script_url, timeout=20)
                    content = sr.text
                    print(f"-- script scan {script_url} status={sr.status_code} len={len(content)}")

                    # API hints in scripts (absolute and relative)
                    abs_api = set(re.findall(r"https?://[^\"']+/api/[^\"'<>\s]+", content))
                    rel_api = set(re.findall(r"/api/[^\"'<>\s]+", content))
                    host_api = set(re.findall(r"https?://api\\.youpin898\\.com[^\"'<>\s]+", content))
                    candidates = sorted(abs_api | host_api | rel_api)
                    if candidates:
                        # surface likely list/search endpoints first
                        keywords = ("list", "search", "goods", "commodity", "market", "sale")
                        ranked = sorted(
                            candidates,
                            key=lambda x: (0 if any(k in x.lower() for k in keywords) else 1, len(x)),
                        )
                        print("   script API candidates (first 60):")
                        for a in ranked[:60]:
                            print("    ", a)

                    # ECO: extract ajax url-like strings as well (not necessarily under /api/)
                    if name == "ecosteam":
                        ajax_urls = set(
                            re.findall(
                                r"url\s*:\s*[\"'](/[^\"']+)[\"']", content
                            )
                        )
                        if ajax_urls:
                            print("   ajax url candidates (first 60):")
                            for a in sorted(ajax_urls)[:60]:
                                print("    ", a)

                    # YOUPIN: show nearby snippet for likely list endpoints
                    if name == "youpin":
                        for needle in ["/api/youpin/pc/inventory/list", "templateId", "goods-list", "goodsList"]:
                            if needle in content:
                                idx = content.find(needle)
                                print(f"   FOUND {needle} near:", content[max(0, idx - 120) : idx + 220])

                    # Additional clue: does script mention templateId?
                    if "templateId" in content:
                        idx = content.find("templateId")
                        print("   FOUND 'templateId' near:", content[max(0, idx - 80) : idx + 120])
                except Exception as e:
                    print(f"-- script scan failed {ssrc}: {e}")

        # absolute + relative api hints
        abs_apis = set(re.findall(r"https?://[^\"']+/api/[^\"']+", text))
        rel_apis = set(re.findall(r"/api/[^\"'<>\s]+", text))
        api_candidates = sorted(abs_apis | rel_apis)
        if api_candidates:
            print("API candidates (first 30):")
            for a in api_candidates[:30]:
                print(" ", a)


if __name__ == "__main__":
    main()
