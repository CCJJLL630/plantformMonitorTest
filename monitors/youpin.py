"""悠悠有品平台监控"""
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs
import re
import time
from .base import PlatformMonitor


class YoupinMonitor(PlatformMonitor):
    """悠悠有品平台监控器"""

    def _normalize_name(self, name: str) -> str:
        # 归一化：去空白与常见分隔符，并去掉磨损括号部分，降低中英文标点差异影响
        s = (name or '').strip().lower()
        s = re.split(r'[\(（]', s, maxsplit=1)[0]
        s = re.sub(r'[\s\|\-–—_\[\]【】\(\)（）]', '', s)
        return s

    def _get_api_base_url(self) -> str:
        api_base = self.config.get('api_base_url')
        if api_base:
            return str(api_base).rstrip('/')
        return 'https://api.youpin898.com'

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
        cookie = self.session.headers.get('Cookie', '')
        m = re.search(r'(?:^|;\s*)uu_token=([^;]+)', cookie)
        if m:
            token = m.group(1)
            # 这些 header 中不一定都需要，但加上有助于兼容不同鉴权方式
            self.session.headers.setdefault('uu-token', token)
            self.session.headers.setdefault('UU-Token', token)
            self.session.headers.setdefault('token', token)
            self.session.headers.setdefault('Authorization', f'Bearer {token}')

        # 使用手机端 User-Agent 以获取精确的价格（含小数）
        self.session.headers.setdefault('User-Agent', 
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148')
        self.session.headers.setdefault('Origin', 'https://www.youpin898.com')
        if referer:
            self.session.headers.setdefault('Referer', referer)
        self.session.headers.setdefault('Accept', 'application/json, text/plain, */*')
        self.session.headers.setdefault('Content-Type', 'application/json;charset=UTF-8')
    
    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取悠悠有品平台商品价格
        
        Args:
            item_name: 商品名称
            wear_min: 最小磨损
            wear_max: 最大磨损
            
        Returns:
            价格信息列表
        """
        results = []
        
        try:
            # 通过市场列表页的 templateId 调用真实接口获取在售列表
            # 需要：api.youpin898.com + uu_token（Cookie/Token header）

            referer = None
            template_params = None

            # 优先使用商品配置中的 youpin_template_id / youpin_game_id / youpin_list_type
            if item_config:
                # 兼容旧配置键 youpin_goods_id（实际是模板ID）
                template_id = item_config.get('youpin_template_id') or item_config.get('youpin_goods_id')
                if template_id:
                    template_params = {
                        'templateId': int(template_id),
                        'gameId': int(item_config.get('youpin_game_id', 730)),
                        'listType': int(item_config.get('youpin_list_type', 10)),
                    }

            # 若未提供，则从平台配置 goods_list_url 中解析
            if not template_params:
                goods_list_url = self._get_goods_list_url()
                if goods_list_url:
                    referer = goods_list_url
                    parsed = self._parse_template_params(goods_list_url)
                    if parsed.get('templateId'):
                        template_params = parsed

            if not template_params or not template_params.get('templateId'):
                self.logger.error(
                    '悠悠有品缺少 templateId：请在 items 中配置 youpin_template_id，或在 platforms.youpin 中配置 goods_list_url（含 templateId=...）'
                )
                return results

            self._ensure_token_headers(referer)

            api_url = f"{self._get_api_base_url()}/api/youpin/pc/inventory/list"
            max_pages = 20  # 增加翻页上限以全量收集目标商品
            page_size = 80
            expected = self._normalize_name(item_name)
            observed_wears: List[float] = []
            
            # 第一步：全量收集所有匹配名称的商品（不过滤磨损）
            all_items = []
            
            self.logger.info(f"开始全量收集商品: {item_name}")
            
            for page_index in range(1, max_pages + 1):
                payload = {
                    **template_params,
                    'pageIndex': page_index,
                    'pageSize': page_size,
                }

                self.logger.info(
                    f"获取悠悠有品列表: templateId={template_params['templateId']} (page={page_index})"
                )
                response = self._make_request(api_url, method='POST', json=payload)
                data = response.json()

                if data.get('code') != 0:
                    self.logger.error(
                        f"悠悠有品接口返回错误: code={data.get('code')}, msg={data.get('msg')}"
                    )
                    break

                items = (data.get('data') or {}).get('itemsInfos') or []
                if not items:
                    if page_index == 1:
                        self.logger.warning(
                            f"悠悠有品无在售数据: templateId={template_params['templateId']}"
                        )
                    break

                # 只过滤名称，不过滤磨损
                for item in items:
                    try:
                        # 名称匹配：templateId 可能返回多商品，这里必须严格匹配到目标名称
                        youpin_name = str(item.get('name', '') or '')
                        normalized = self._normalize_name(youpin_name)
                        if expected and normalized and normalized != expected:
                            continue
                        
                        all_items.append(item)

                    except (ValueError, KeyError) as e:
                        self.logger.warning(f"解析商品数据失败: {e}")
                        continue

                self._sleep(0.6)

            self.logger.info(f"全量收集完成，共 {len(all_items)} 个匹配商品")
            
            # 第二步：按磨损区间筛选
            for item in all_items:
                try:
                    wear_value = float(item.get('abrade', 0))
                    # 有些接口会返回百分比（例如 15.23），统一转为 0-1
                    if wear_value > 1:
                        wear_value = wear_value / 100.0

                    if len(observed_wears) < 30:
                        observed_wears.append(wear_value)

                    if wear_min <= wear_value <= wear_max:
                        price = float(item.get('price', 0))
                        steam_asset_id = item.get('steamAssetId', '')

                        result = {
                            'platform': 'youpin',
                            'item_name': item_name,
                            'price': price,
                            'wear': wear_value,
                            'url': referer or self.base_url,
                            'timestamp': int(time.time())
                        }
                        if steam_asset_id:
                            result['asset_id'] = steam_asset_id
                        results.append(result)

                except (ValueError, KeyError) as e:
                    continue

            # 第三步：按价格升序排序，取前20个
            results.sort(key=lambda x: x['price'])
            
            # 去重：如果价格完全一致，可能是API限制导致只返回了部分商品
            unique_prices = set(r['price'] for r in results)
            if len(unique_prices) == 1 and len(results) > 5:
                self.logger.warning(
                    f"悠悠有品返回的 {len(results)} 个商品价格完全相同({list(unique_prices)[0]}元)，"
                    "这可能是API限制，实际市场可能有更多不同价格商品"
                )
            
            results = results[:20]
            
            # 打印日志
            self.logger.info(f"磨损区间筛选后: {len(results)} 个商品，价格排序后取前20")
            for result in results:
                self.logger.info(
                    f"找到匹配商品 - 价格: {result['price']}, 磨损: {result['wear']:.6f}"
                )

            if not results and observed_wears:
                self.logger.info(
                    f"悠悠有品 未命中磨损区间: {wear_min}-{wear_max}；样本磨损范围: {min(observed_wears):.6f}-{max(observed_wears):.6f}"
                )
        
        except Exception as e:
            self.logger.error(f"获取悠悠有品价格失败: {e}")
        
        return results
