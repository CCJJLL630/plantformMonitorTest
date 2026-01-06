"""悠悠有品平台监控（纯 requests 版）"""
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs
import base64
import json
import random
import re
import time
import logging
from .base import PlatformMonitor


class YoupinMonitor(PlatformMonitor):
    """悠悠有品平台监控器（通过官方/移动端 API，避免 Selenium）"""

    DEFAULT_MARKET_API_PATH = '/api/homepage/pc/goods/market/queryOnSaleCommodityList'
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.logger = logging.getLogger('YoupinMonitor')

    def _normalize_name(self, name: str) -> str:
        # 归一化：去空白与常见分隔符，并去掉磨损括号部分，降低中英文标点差异影响
        s = (name or '').strip().lower()
        s = re.split(r'[\(（]', s, maxsplit=1)[0]
        s = re.sub(r'[\s\|\-–—_\[\]【】\(\)（）]', '', s)
        return s

    def _get_goods_list_url(self) -> Optional[str]:
        url = self.config.get('goods_list_url')
        return str(url) if url else None

    def _parse_template_params(self, url: str) -> Dict[str, int]:
        q = parse_qs(urlparse(url).query)

        def _int(key: str, default: int) -> int:
            v = q.get(key, [None])[0]
            if v is None:
                return default
            try:
                return int(v)
            except ValueError:
                return default

        return {
            'listType': _int('listType', 10),
            'templateId': _int('templateId', 0),
            'gameId': _int('gameId', 730),
        }

    def _ensure_token_headers(self, referer: Optional[str]):
        """确保请求头包含必要的 Cookie/Token 与移动端 UA"""
        cookie = self.session.headers.get('Cookie', '')
        m = re.search(r'(?:^|;\s*)uu_token=([^;]+)', cookie)
        if m:
            token = m.group(1)
            # 同时尝试多个头以兼容不同的后端校验
            self.session.headers.setdefault('uu-token', token)
            self.session.headers.setdefault('UU-Token', token)
            self.session.headers.setdefault('token', token)
            # 抓包显示 PC 端使用的是 raw token（无 Bearer 前缀）
            self.session.headers.setdefault('authorization', token)
            self.session.headers.setdefault('Authorization', token)

            # 部分风控会校验 deviceId/version（通常包含在 JWT payload 里）
            payload = self._try_decode_jwt_payload(token)
            if payload:
                device_id = payload.get('deviceId') or payload.get('deviceid')
                version = payload.get('version')
                if device_id:
                    self.session.headers.setdefault('deviceId', str(device_id))
                    self.session.headers.setdefault('deviceid', str(device_id))
                    self.session.headers.setdefault('DeviceId', str(device_id))
                    self.session.headers.setdefault('Device-Id', str(device_id))
                if version:
                    self.session.headers.setdefault('version', str(version))

        # 使用手机端 User-Agent 以获取精确的价格（含小数）
        self.session.headers.setdefault(
            'User-Agent',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
        )
        self.session.headers.setdefault('Origin', 'https://www.youpin898.com')
        if referer:
            self.session.headers.setdefault('Referer', referer)
        self.session.headers.setdefault('Accept', 'application/json, text/plain, */*')
        self.session.headers.setdefault('Accept-Language', 'zh-CN,zh;q=0.9')
        self.session.headers.setdefault('Content-Type', 'application/json;charset=UTF-8')
        self.session.headers.setdefault('X-Requested-With', 'XMLHttpRequest')

    def _try_decode_jwt_payload(self, token: str) -> Optional[Dict[str, Any]]:
        """尽力解析 uu_token 的 JWT payload（失败返回 None）。"""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            payload_b64 = parts[1]
            # base64url padding
            payload_b64 += '=' * (-len(payload_b64) % 4)
            raw = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
            obj = json.loads(raw.decode('utf-8', errors='ignore'))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    def _log_http_block(self, url: str, resp) -> None:
        """记录 403/429 等拦截信息，便于对照浏览器抓包。"""
        try:
            ct = resp.headers.get('content-type', '')
            rid = resp.headers.get('x-request-id') or resp.headers.get('X-Request-Id')
            self.logger.warning(
                f"Youpin 请求被拦截: status={resp.status_code} content-type={ct} request-id={rid} url={url}"
            )
            body = resp.text or ''
            body = body.strip().replace('\r', ' ').replace('\n', ' ')
            if body:
                self.logger.warning(f"响应体片段: {body[:300]}")
        except Exception:
            # 日志失败不应影响主流程
            return

    def _iter_api_bases(self) -> List[str]:
        bases = []
        for key in ('api_base_url', 'base_url'):
            v = self.config.get(key)
            if v:
                bases.append(str(v).rstrip('/'))
        bases.append('https://api.youpin898.com')
        return list(dict.fromkeys(bases))  # 去重保持顺序

    def _extract_items(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从响应 JSON 中提取商品列表"""
        # 一些接口直接在顶层返回列表（例如: {Code, Msg, Data: [...], TotalCount}
        for k in ('data', 'Data', 'result', 'Result'):
            top = payload.get(k)
            if isinstance(top, list):
                return top

        candidates = [payload]
        for k in ('data', 'Data', 'result', 'Result'):
            if isinstance(payload.get(k), dict):
                candidates.append(payload[k])

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            for key in (
                'itemsInfos', 'items', 'list', 'records',
                'commodityList', 'CommodityList', 'Items', 'Lists'
            ):
                lst = candidate.get(key)
                if isinstance(lst, list):
                    return lst
        return []

    def _fetch_market_data(self, template_id: int, page_index: int = 1, page_size: int = 50) -> Optional[List[Dict[str, Any]]]:
        """通过 requests 调用显式配置的市场 API 获取在售列表

        注意：默认不再调用 `inventory/list`，避免误拿账号库存。
        必须在配置中提供 `market_api_url`（完整 URL）或 `market_api_path`（与 api_base_url 拼接）。
        """

        market_api_url = self.config.get('market_api_url')
        market_api_path = self.config.get('market_api_path')
        if not (market_api_url or market_api_path):
            self.logger.info(f"未配置 Youpin 市场 API，尝试默认 {self.DEFAULT_MARKET_API_PATH}")
            market_api_path = self.DEFAULT_MARKET_API_PATH

        # 防御：禁止误用 inventory/list
        for check in ('inventory/list', '/inventory/'):
            if market_api_url and check in market_api_url:
                self.logger.error("检测到 inventory/list 端点，已拒绝请求以避免获取账号库存。请提供正确的市场在售 API。")
                return None
            if market_api_path and check in market_api_path:
                self.logger.error("检测到 inventory/list 端点，已拒绝请求以避免获取账号库存。请提供正确的市场在售 API。")
                return None

        referer = self._get_goods_list_url() or f'https://www.youpin898.com/market/goods-list?templateId={template_id}&gameId=730&listType=10'
        self._ensure_token_headers(referer)

        info = {
            'templateId': int(template_id),
            'gameId': int(self.config.get('game_id', 730)),
            'listType': int(self.config.get('list_type', 10)),
        }
        # 只保留最常见的参数组合，避免瞬间大量请求导致 429
        payload_post = {'pageIndex': page_index, 'pageSize': page_size, **info}
        payload_get = {'pageIndex': page_index, 'pageSize': page_size, **info}

        method_pref = str(self.config.get('market_method', 'POST')).upper()
        methods_to_try = [method_pref] if method_pref in ('GET', 'POST') else ['POST']
        if method_pref != 'GET':
            methods_to_try.append('GET')
        if method_pref != 'POST':
            methods_to_try.append('POST')

        extra_headers = self.config.get('market_headers') or self.config.get('market_request_headers') or {}

        # Resolve base URL
        url_candidates = []
        if market_api_url:
            url_candidates.append(market_api_url.rstrip('/'))
        elif market_api_path:
            for base in self._iter_api_bases():
                url_candidates.append(f"{base}{market_api_path}")

        def _build_attempts() -> List[Tuple[str, Dict[str, Any]]]:
            attempts: List[Tuple[str, Dict[str, Any]]] = []
            for m in methods_to_try:
                if m == 'POST':
                    attempts.append(('POST', payload_post))
                elif m == 'GET':
                    attempts.append(('GET', payload_get))
            # 去重
            seen = set()
            uniq: List[Tuple[str, Dict[str, Any]]] = []
            for m, p in attempts:
                key = (m, tuple(sorted(p.items())))
                if key not in seen:
                    seen.add(key)
                    uniq.append((m, p))
            return uniq

        attempts = _build_attempts()

        # 退避参数（可在配置中覆盖）
        max_attempts = int(self.config.get('market_max_attempts', 4))
        backoff_base = float(self.config.get('market_backoff_base', 0.8))
        backoff_cap = float(self.config.get('market_backoff_cap', 8.0))
        request_delay = float(self.config.get('market_request_delay_seconds', 0.25))

        tried = 0
        for url in url_candidates:
            for method, payload in attempts:
                if tried >= max_attempts:
                    break
                tried += 1

                # 每次请求单独传 headers，避免污染 session 全局头
                call_headers = dict(extra_headers) if isinstance(extra_headers, dict) else {}

                try:
                    self.logger.debug(f"Youpin request: {method} {url} page={page_index}")
                    resp = self.session.request(
                        method,
                        url,
                        timeout=12,
                        headers=call_headers,
                        json=payload if method == 'POST' else None,
                        params=payload if method == 'GET' else None,
                    )

                    # 403 基本是风控/权限，继续狂试只会更糟
                    if resp.status_code == 403:
                        self._log_http_block(url, resp)
                        return None

                    # 429：做退避再尝试下一次（避免瞬间触发更严格限制）
                    if resp.status_code == 429:
                        self._log_http_block(url, resp)
                        sleep_s = min(backoff_cap, backoff_base * (2 ** (tried - 1)))
                        sleep_s = sleep_s * (0.85 + random.random() * 0.3)  # jitter
                        time.sleep(sleep_s)
                        continue

                    if resp.status_code != 200:
                        # 其他状态：记录片段并继续
                        self._log_http_block(url, resp)
                        time.sleep(request_delay)
                        continue

                    try:
                        data = resp.json()
                    except Exception:
                        self._log_http_block(url, resp)
                        time.sleep(request_delay)
                        continue

                    code = None
                    if isinstance(data, dict):
                        code = data.get('code')
                        if code is None:
                            code = data.get('Code')
                    # 常见成功码：0；也可能直接没有 code
                    if code not in (None, 0, '0'):
                        # 85100 常见于版本/网络限制
                        if str(code) == '85100':
                            self.logger.warning(f"Youpin 返回限制码 85100，可能需要补齐 app-version/设备信息/浏览器指纹头。")
                        self.logger.debug(f"{url} returned code={code}")
                        time.sleep(request_delay)
                        continue

                    items = self._extract_items(data)
                    if items:
                        return items
                    time.sleep(request_delay)
                except Exception as e:
                    # 网络错误等：稍微等一下再继续
                    self.logger.debug(f"Youpin request exception: {e}")
                    time.sleep(max(request_delay, 0.5))
                    continue

        return None
    
    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取悠悠有品平台商品价格（requests API）
        
        Args:
            item_name: 商品名称
            wear_min: 最小磨损
            wear_max: 最大磨损
            item_config: 商品配置
            
        Returns:
            价格信息列表
        """
        results = []
        
        try:
            # 获取 templateId
            template_id = None
            if item_config:
                template_id = item_config.get('youpin_template_id') or item_config.get('youpin_goods_id')
            
            if not template_id:
                goods_list_url = self._get_goods_list_url()
                if goods_list_url:
                    parsed = self._parse_template_params(goods_list_url)
                    template_id = parsed.get('templateId')
            
            if not template_id:
                self.logger.error(
                    '悠悠有品缺少 templateId：请在 items 中配置 youpin_template_id，或在 platforms.youpin 中配置 goods_list_url'
                )
                return results

            # 直接使用 API 多页拉取
            self.logger.info(f"开始获取市场在售商品: {item_name} (templateId={template_id})")

            # 收集多页数据（从配置读取最大页数，默认2页确保获取前80个商品）
            all_items = []
            pages_fetched = 0
            max_pages = int(self.config.get('max_pages', 2))  # 默认2页x50=100个商品
            page_delay = float(self.config.get('market_page_delay_seconds', 2.0))
            for page in range(1, max_pages + 1):
                self.logger.info(f"获取第 {page} 页数据... (API)")

                items = self._fetch_market_data(template_id, page, 50)
                if not items:
                    self.logger.warning(f"第 {page} 页无数据或请求失败，停止")
                    break

                pages_fetched += 1
                all_items.extend(items)

                # 翻页间隔：降低触发 429/84104 的概率，增加随机性
                if page_delay > 0 and page < max_pages:
                    # 增加10-30%的随机延迟，避免固定间隔被识别
                    jitter = random.uniform(0.1, 0.3)
                    actual_delay = page_delay * (1 + jitter)
                    self.logger.debug(f"等待 {actual_delay:.2f} 秒后请求下一页...")
                    time.sleep(actual_delay)
                
                # 输出本页磨损范围和每个商品的详细信息
                wears_in_page = []
                prices_in_page = []
                for item in items:
                    abrade_raw = item.get('abrade') or item.get('Abrade') or item.get('wear') or item.get('Wear')
                    price_raw = item.get('price') or item.get('Price') or item.get('sellingPrice') or item.get('SellingPrice')
                    commodity_name = item.get('commodityName') or item.get('CommodityName') or item.get('name') or item.get('goods_name') or ''
                    try:
                        wear = float(abrade_raw)
                        if wear > 1:
                            wear = wear / 100.0
                        price = float(price_raw)
                        wears_in_page.append(wear)
                        prices_in_page.append(price)
                        # 打印每个商品的详细信息
                        self.logger.debug(f"  [{page}页] {commodity_name[:20]}... 价格:{price} 磨损:{wear:.4f}")
                    except Exception:
                        pass
                
                if wears_in_page:
                    min_wear = min(wears_in_page)
                    max_wear = max(wears_in_page)
                    min_price = min(prices_in_page)
                    max_price = max(prices_in_page)
                    self.logger.info(f"第 {page} 页: {len(items)}个商品 | 磨损: {min_wear:.4f}~{max_wear:.4f} | 价格: ¥{min_price:.2f}~¥{max_price:.2f}")
                else:
                    self.logger.info(f"第 {page} 页获取到 {len(items)} 个商品")

            self.logger.info(f"共获取 {len(all_items)} 个在售商品（{pages_fetched}/{max_pages} 页）")
            
            # 过滤和排序
            expected = self._normalize_name(item_name)
            filtered = []
            
            for item in all_items:
                commodity_name = item.get('commodityName') or item.get('CommodityName') or item.get('name') or item.get('goods_name') or ''
                actual = self._normalize_name(commodity_name)
                
                if expected != actual:
                    continue
                
                # 解析价格和磨损
                price_raw = item.get('price') or item.get('Price') or item.get('sellingPrice') or item.get('SellingPrice') or 0
                abrade_raw = item.get('abrade') or item.get('Abrade') or item.get('wear') or item.get('Wear') or 0
                
                try:
                    price = float(price_raw)
                    wear = float(abrade_raw)
                    if wear > 1:
                        wear = wear / 100.0
                except (ValueError, TypeError):
                    continue
                
                # 磨损区间过滤
                if wear_min <= wear <= wear_max:
                    filtered.append({
                        'platform': 'youpin',
                        'item_name': item_name,
                        'price': price,
                        'wear': wear,
                        'url': f'https://www.youpin898.com/market/goods-list?templateId={template_id}',
                        'timestamp': int(time.time()),
                        'id': item.get('id') or item.get('Id'),
                    })
            
            # 按价格升序排序，取前20个
            filtered.sort(key=lambda x: x['price'])
            results = filtered[:20]
            
            self.logger.info(f"磨损区间 {wear_min}-{wear_max} 内找到 {len(filtered)} 个商品，返回前 {len(results)} 个")
            
            # 打印结果
            for item in results:
                self.logger.info(
                    f"找到匹配商品 - 价格: {item['price']}, 磨损: {item['wear']:.6f}"
                )
        
        except Exception as e:
            self.logger.error(f"获取悠悠有品价格失败: {e}", exc_info=True)
        
        return results
