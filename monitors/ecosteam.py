"""ECOSteam平台监控（优先使用官方 API SellGoodsQuery）"""
from typing import Dict, List, Any, Optional
import re
import time
import random
from urllib.parse import urlparse
from .base import PlatformMonitor


class EcosteamMonitor(PlatformMonitor):
    """ECOSteam平台监控器（API 优先，HTML 作为备用）"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        # Add a few browser-like defaults (do not overwrite user-provided headers).
        self.session.headers.setdefault(
            'Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        )
        self.session.headers.setdefault('Accept-Language', 'zh-CN,zh;q=0.9,en;q=0.8')

        # Simple per-instance rate limiter for ecosteam requests.
        self._ecosteam_last_request_ts = 0.0

    def _throttle(self) -> None:
        """Throttle ECOSteam requests to lower anti-bot probability.

        Config knobs (optional):
        - request_min_interval_seconds: minimum interval between requests (default 0.9)
        - request_jitter_seconds: additional random jitter (default 0.6)
        """

        min_interval = float(self.config.get('request_min_interval_seconds', 0.9))
        jitter = float(self.config.get('request_jitter_seconds', 0.6))

        now = time.monotonic()
        last = getattr(self, '_ecosteam_last_request_ts', 0.0) or 0.0
        elapsed = now - last

        base_sleep = max(0.0, min_interval - elapsed)
        # Add jitter even if base_sleep==0 to avoid an obvious pattern.
        extra = random.uniform(0.05, max(0.05, jitter))
        time.sleep(base_sleep + extra)
        self._ecosteam_last_request_ts = time.monotonic()

    def _request(self, url: str, method: str = 'GET', *, referer: Optional[str] = None, timeout: float = 20.0, **kwargs):
        """ECOSteam-specific request wrapper with throttling."""
        self._throttle()

        headers = dict(kwargs.pop('headers', {}) or {})
        if referer:
            headers.setdefault('Referer', referer)
        # Keep the header minimal; session already has UA/Accept defaults.
        kwargs['headers'] = headers

        if self.proxies and 'proxies' not in kwargs:
            kwargs['proxies'] = self.proxies

        return self.session.request(method, url, timeout=timeout, **kwargs)

    def _try_bypass_acw_sc_v2(self, url: str, html: str) -> Optional[str]:
        """尝试绕过 ECOSteam 的 acw_sc__v2 JS Challenge。

        若命中挑战页，会在 session.cookies 中写入 acw_sc__v2，然后重试 GET。
        返回重试后的 HTML；如果未命中或解算失败则返回 None。
        """

        if not html:
            return None

        # Typical challenge page includes arg1 and sets document.cookie='acw_sc__v2=...'; then reload.
        if "acw_sc__v2" not in html or "var arg1=" not in html or "document" not in html:
            return None

        try:
            m_arg1 = re.search(r"var\s+arg1\s*=\s*'([0-9A-Fa-f]+)'", html)
            if not m_arg1:
                return None
            arg1 = m_arg1.group(1)

            # Extract permutation list m=[0xf,0x23,...]
            m_m = re.search(r"\bm\s*=\s*\[([^\]]+)\]", html)
            if not m_m:
                return None
            m_tokens = re.findall(r"0x[0-9A-Fa-f]+|\d+", m_m.group(1))
            if not m_tokens:
                return None
            perm = [int(t, 16) if t.lower().startswith("0x") else int(t) for t in m_tokens]

            # Extract obfuscated string array N=['...','...'] from function a0i().
            # NOTE: This array is rotated by a self-invoking loop before being used.
            m_n = re.search(r"var\s+N\s*=\s*\[([\s\S]*?)\]", html)
            if not m_n:
                return None
            table = re.findall(r"'([^']*)'", m_n.group(1))
            if len(table) < 30:
                return None

            def _custom_b64_decode(s: str) -> str:
                """Decode using the same obfuscated routine embedded in the challenge page.

                It is effectively a base64 decoder but with a custom alphabet ordering.
                """

                alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/="
                out = bytearray()
                q = 0
                r = 0

                for ch in s:
                    idx = alphabet.find(ch)
                    if idx < 0:
                        continue
                    if idx == 64:
                        # '=' padding
                        break

                    # JS: r = q%4 ? r*0x40 + s : s
                    if q % 4:
                        r = r * 64 + idx
                    else:
                        r = idx

                    # JS uses q++%4 in condition, so output happens when old_q%4 != 0
                    old_q = q
                    q += 1
                    if old_q % 4 == 0:
                        continue

                    # JS: 0xff & (r >> ((-2*q) & 6))
                    shift = ((-2 * q) & 6)
                    out.append((r >> shift) & 0xFF)

                try:
                    return bytes(out).decode("utf-8", errors="ignore")
                except Exception:
                    return ""

            def _parse_int_js(s: str) -> int:
                # Emulate JS parseInt(s) (base10, stops at first non-digit)
                m = re.match(r"\s*([+-]?\d+)", str(s))
                if not m:
                    raise ValueError(f"parseInt failed: {s!r}")
                return int(m.group(1))

            def _a0j(idx_hex: int) -> str:
                # Mirror: idx = idx_hex - 0xfb
                i = idx_hex - 0xFB
                if i < 0 or i >= len(table):
                    return ""
                val = table[i]
                # Cache decoded strings back into the table
                if isinstance(val, str) and val and not val.startswith("__decoded__:"):
                    decoded = _custom_b64_decode(val)
                    table[i] = "__decoded__:" + decoded
                    return decoded
                if isinstance(val, str) and val.startswith("__decoded__:"):
                    return val[len("__decoded__:") :]
                return str(val)

            # The challenge script rotates the table until a numeric expression matches 0x760bf.
            # We replicate that exact loop to align indices.
            target = 0x760BF
            for _ in range(len(table) + 5):
                try:
                    e = (
                        -_parse_int_js(_a0j(0x117)) / 0x1 * (_parse_int_js(_a0j(0x111)) / 0x2)
                        + -_parse_int_js(_a0j(0x0FB)) / 0x3 * (_parse_int_js(_a0j(0x10E)) / 0x4)
                        + -_parse_int_js(_a0j(0x101)) / 0x5 * (-_parse_int_js(_a0j(0x0FD)) / 0x6)
                        + -_parse_int_js(_a0j(0x102)) / 0x7 * (_parse_int_js(_a0j(0x122)) / 0x8)
                        + _parse_int_js(_a0j(0x112)) / 0x9
                        + _parse_int_js(_a0j(0x11D)) / 0xA * (_parse_int_js(_a0j(0x11C)) / 0xB)
                        + _parse_int_js(_a0j(0x114)) / 0xC
                    )
                    # allow float rounding differences
                    if int(e) == target:
                        break
                    table.append(table.pop(0))
                except Exception:
                    table.append(table.pop(0))

            p = str(_a0j(0x115))
            p_hex = re.sub(r"[^0-9A-Fa-f]", "", p)
            # p should be a non-trivial hex string used as XOR key
            if len(p_hex) < 20:
                return None

            # Build u by permuting arg1 according to perm (1-based indices in perm)
            q_chars: List[str] = [""] * len(perm)
            for i, ch in enumerate(arg1):
                one_based = i + 1
                for j, idx in enumerate(perm):
                    if idx == one_based:
                        q_chars[j] = ch
            u = "".join(q_chars)

            # XOR u and p (hex pairs)
            max_len = min(len(u), len(p_hex))
            max_len -= max_len % 2
            v = []
            for i in range(0, max_len, 2):
                a = int(u[i : i + 2], 16)
                b = int(p_hex[i : i + 2], 16)
                v.append(f"{a ^ b:02x}")
            cookie_value = "".join(v)
            if not cookie_value:
                return None

            # Set cookie to session for ecosteam domain, then retry.
            host = ""
            try:
                host = urlparse(self.base_url).hostname or ""
            except Exception:
                host = ""
            if host:
                self.session.cookies.set("acw_sc__v2", cookie_value, domain=host)
            else:
                self.session.cookies.set("acw_sc__v2", cookie_value)

            self.logger.warning("ECOSteam 命中 acw_sc__v2 反爬挑战页，已自动解算并重试请求")

            # Backoff a bit before retrying, to look more human.
            backoff = float(self.config.get('challenge_backoff_seconds', 2.0))
            time.sleep(backoff + random.uniform(0.0, 1.0))

            resp2 = self._request(url, referer=url)
            return resp2.text
        except Exception as e:
            self.logger.warning(f"ECOSteam 可能命中反爬挑战页，但自动解算失败: {e}")
            return None

    def _get_goods_detail_url(self, item_config: Optional[Dict[str, Any]]) -> Optional[str]:
        if item_config:
            url = item_config.get('eco_goods_url') or item_config.get('ecosteam_goods_url')
            if url:
                return str(url)
        url = self.config.get('goods_detail_url')
        return str(url) if url else None

    def _parse_sell_list_from_html(self, goods_url: str) -> List[Dict[str, float]]:
        """从商品详情页 HTML 中解析在售列表。

        依据前端结构：
        - 磨损在 <p class="WearRate"> ... <span>0.xxx</span>
        - 分页链接形如: /goods/...-0-2.html 且带 data-page
        """
        import random

        def _detect_max_page(page_html: str) -> int:
            nums = [int(m.group(1)) for m in re.finditer(r'data-page="(\d+)"', page_html)]
            return max(nums) if nums else 1

        def _page_url(base_url: str, page: int) -> str:
            return re.sub(r'-0-\d+\.html$', f'-0-{page}.html', base_url)

        def _parse_rows(page_html: str) -> List[Dict[str, float]]:
            rows: List[Dict[str, float]] = []

            wear_re = re.compile(
                r'<p\s+class="WearRate"[^>]*>[\s\S]*?<span[^>]*>\s*([0-9]+(?:\.[0-9]+)?)\s*</span>[\s\S]*?</p>',
                re.IGNORECASE,
            )
            price_re = re.compile(r'￥\s*([0-9]+(?:\.[0-9]+)?)')

            for m in wear_re.finditer(page_html):
                try:
                    wear_value = float(m.group(1))
                except ValueError:
                    continue

                # 在磨损块之后的有限窗口内找最近的价格（避免跨行配对错误）
                window = page_html[m.end(): m.end() + 2500]
                pm = price_re.search(window)
                if not pm:
                    continue
                try:
                    price_value = float(pm.group(1))
                except ValueError:
                    continue

                rows.append({'wear': wear_value, 'price': price_value})

            return rows

        # Fetch page 1 with throttling + challenge handling.
        resp1 = self._request(goods_url, referer=goods_url)
        html1 = resp1.text

        # Some challenges may require 1-2 rounds (cookie set then reload).
        max_challenge_retries = int(self.config.get('challenge_max_retries', 2))
        for _ in range(max(0, max_challenge_retries)):
            bypassed = self._try_bypass_acw_sc_v2(goods_url, html1)
            if bypassed is None:
                break
            html1 = bypassed
        max_page_on_site = _detect_max_page(html1)

        all_rows: List[Dict[str, float]] = []
        page1_rows = _parse_rows(html1)
        all_rows.extend(page1_rows)
        
        # 记录第一页的磨损范围
        if page1_rows:
            wears = [r['wear'] for r in page1_rows]
            self.logger.info(f"ECOSteam 第1页：{len(page1_rows)}个商品，磨损范围 {min(wears):.6f}-{max(wears):.6f}")

        # 从配置读取最大页数，默认20页；允许每个商品配置覆盖（减少请求量）
        config_max_pages = int(self.config.get('max_pages', 20))
        item_max_pages = None
        try:
            # item_config is not directly passed here; allow per-url mapping via config if needed.
            # (Kept for future extension)
            pass
        except Exception:
            item_max_pages = None

        actual_max_page = min(max_page_on_site, config_max_pages)
        page_delay = float(self.config.get('page_delay_seconds', 1.0))
        
        if max_page_on_site == 1 and not page1_rows:
            # 极大概率是结构变更或被拦截（挑战页/登录页等）
            if "acw_sc__v2" in html1 or "acw_sc" in html1:
                self.logger.warning("ECOSteam 解析到 0 商品且页数为 1：疑似仍被反爬拦截（acw_sc__v2）")
            else:
                self.logger.warning("ECOSteam 解析到 0 商品且页数为 1：可能页面结构变更或需要登录/验证码")

        self.logger.info(f"ECOSteam 网站共{max_page_on_site}页，将抓取前{actual_max_page}页")

        # 抓取后续页面
        for page in range(2, actual_max_page + 1):
            # 添加随机延迟，避免触发反爬（同时 _request 内也有节流）
            if page_delay > 0:
                jitter = random.uniform(0.10, 0.45)
                actual_delay = page_delay * (1 + jitter)
                time.sleep(actual_delay)
            
            url = _page_url(goods_url, page)
            page_html = self._request(url, referer=goods_url).text
            # Handle challenge page on subsequent pages too
            bypassed = self._try_bypass_acw_sc_v2(url, page_html)
            if bypassed is not None:
                page_html = bypassed
            page_rows = _parse_rows(page_html)
            all_rows.extend(page_rows)
            
            # 记录每页的磨损范围
            if page_rows:
                wears = [r['wear'] for r in page_rows]
                self.logger.info(f"ECOSteam 第{page}页：{len(page_rows)}个商品，磨损范围 {min(wears):.6f}-{max(wears):.6f}")
            else:
                self.logger.warning(f"ECOSteam 第{page}页未解析到数据")

        self.logger.info(f"ECOSteam HTML解析完成：共{len(all_rows)}个商品（{actual_max_page}页）")
        return all_rows

    def _parse_goods_url(self, url: str) -> Dict[str, int]:
        """从 goods URL 中提取 gameId 和 goodsId（ecosteam 内部 ID 不是此 ID，但可用于参考）"""
        m = re.search(r"/goods/(\d+)-(\d+)-", url)
        if not m:
            return {}
        return {"gameId": int(m.group(1)), "goodsId": int(m.group(2))}

    def _resolve_hash_name(self, goods_url: str, item_config: Optional[Dict[str, Any]]) -> Optional[str]:
        # 允许在 item_config 中直接提供 hash_name，避免额外请求
        if item_config:
            hash_name = item_config.get('eco_hash_name') or item_config.get('ecosteam_hash_name')
            if hash_name:
                return str(hash_name)

        try:
            html = self._make_request(goods_url).text
            m = re.search(r'data-HashName="([^"]+)"', html)
            return m.group(1) if m else None
        except Exception:
            return None

    def _resolve_internal_id(self, hash_name: str, game_id: int) -> Optional[str]:
        try:
            resp = self._make_request(
                f"{self.base_url.rstrip('/')}/Api/SteamGoods/GoodsDetailQueryPost",
                method='POST',
                json={'GameId': game_id, 'HashName': hash_name},
            ).json()
            sd = resp.get('StatusData') or {}
            rd = sd.get('ResultData') or {}
            internal_id = rd.get('Id') or rd.get('GoodsId') or rd.get('SteamGoodsId')
            return internal_id
        except Exception:
            return None

    def _fetch_sell_list_api(self, hash_name: str, internal_id: Optional[str], game_id: int, page_size: int = 40) -> List[Dict[str, Any]]:
        """调用 SellGoodsQuery API 分页获取在售列表"""
        sell_url = f"{self.base_url.rstrip('/')}/Api/SteamGoods/SellGoodsQuery"
        all_items: List[Dict[str, Any]] = []
        page_index = 1
        total_record: Optional[int] = None

        while True:
            payload = {
                'GameId': game_id,
                'HashName': hash_name,
                'PageIndex': page_index,
                'PageSize': page_size,
            }
            if internal_id:
                payload['GoodsId'] = internal_id

            resp = self._make_request(sell_url, method='POST', json=payload).json()
            sd = resp.get('StatusData') or {}
            rc = str(sd.get('ResultCode'))
            if rc not in ('0', '200', 'OK', 'SUCCESS'):
                self.logger.warning(f"SellGoodsQuery 返回错误: code={rc} msg={sd.get('ResultMsg')}")
                break

            rd = sd.get('ResultData') or {}
            if total_record is None:
                total_record = rd.get('TotalRecord')

            items = rd.get('PageResult') or rd.get('List') or rd.get('Items') or []
            if not items:
                break

            for it in items:
                if isinstance(it, dict):
                    it.setdefault('__pageIndex', page_index)
            all_items.extend(items)

            if isinstance(total_record, int) and len(all_items) >= total_record:
                break

            page_index += 1
            if page_index > 50:
                break
            self._sleep(0.5)

        return all_items

    def _parse_wear(self, item: Dict[str, Any]) -> Optional[float]:
        for key in ('Scale', 'scale', 'Abrade', 'abrade', 'Wear', 'wear'):
            if key in item:
                try:
                    wear = float(item[key])
                    if wear > 1:
                        wear = wear / 100.0
                    return wear
                except (ValueError, TypeError):
                    continue
        return None

    def _parse_price(self, item: Dict[str, Any]) -> Optional[float]:
        for key in ('SellingPrice', 'sellingPrice', 'BottomPrice', 'Price', 'price'):
            if key in item:
                try:
                    return float(item[key])
                except (ValueError, TypeError):
                    continue
        return None

    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """获取ECOSteam平台商品价格（仅使用 HTML 解析）。"""
        results: List[Dict[str, Any]] = []
        observed_wears: List[float] = []

        try:
            goods_url = self._get_goods_detail_url(item_config)
            if not goods_url:
                self.logger.error('ECOSteam 缺少 goods_detail_url（商品详情页 URL）')
                return results

            # Per-item max pages override to reduce requests when monitoring many items.
            # Example in config item: "ecosteam_max_pages": 3
            if item_config and item_config.get('ecosteam_max_pages') is not None:
                try:
                    per_item_pages = int(item_config.get('ecosteam_max_pages'))
                    if per_item_pages > 0:
                        # Temporarily clamp for this call
                        old = self.config.get('max_pages')
                        self.config['max_pages'] = min(int(self.config.get('max_pages', 20)), per_item_pages)
                    else:
                        old = None
                except Exception:
                    old = None
            else:
                old = None

            # 仅使用 HTML 解析在售列表
            for row in self._parse_sell_list_from_html(goods_url):
                wear_value = float(row.get('wear', 0))
                price = float(row.get('price', 0))

                if len(observed_wears) < 30:
                    observed_wears.append(wear_value)

                if wear_min <= wear_value <= wear_max:
                    results.append({
                        'platform': 'ecosteam',
                        'item_name': item_name,
                        'price': price,
                        'wear': wear_value,
                        'url': goods_url,
                        'timestamp': int(time.time())
                    })

            # 只需要“磨损区间内的数据”，然后按价格升序排列（不再按磨损参与排序）
            if results:
                results.sort(key=lambda x: (x.get('price', float('inf'))))
                for r in results:
                    self.logger.info(
                        f"找到匹配商品 - 价格: {r.get('price')}, 磨损: {float(r.get('wear', 0)):.6f}"
                    )

            if not results and observed_wears:
                self.logger.info(
                    f"ECOSteam 未命中磨损区间: {wear_min}-{wear_max}；样本磨损范围: {min(observed_wears):.6f}-{max(observed_wears):.6f}"
                )

            if old is not None:
                # restore
                self.config['max_pages'] = old

        except Exception as e:
            self.logger.error(f"获取ECOSteam价格失败: {e}")

        return results
