"""悠悠有品手机端API监控"""
from typing import Dict, List, Any, Optional
import re
import time
from .base import PlatformMonitor


class YoupinMobileMonitor(PlatformMonitor):
    """悠悠有品手机端监控器"""

    def _normalize_name(self, name: str) -> str:
        s = (name or '').strip().lower()
        s = re.split(r'[\(（]', s, maxsplit=1)[0]
        s = re.sub(r'[\s\|\-–—_\[\]【】\(\)（）]', '', s)
        return s

    def _get_mobile_api_base_url(self) -> str:
        # 手机端API可能使用不同的域名或路径
        return 'https://api.youpin898.com'

    def _ensure_mobile_headers(self):
        """设置手机端请求头"""
        cookie = self.config.get('Cookie', '')
        m = re.search(r'(?:^|;\s*)uu_token=([^;]+)', cookie)
        token = m.group(1) if m else None
        
        # 模拟手机端浏览器
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://m.youpin898.com',
            'Referer': 'https://m.youpin898.com/',
            'Content-Type': 'application/json;charset=UTF-8',
        })
        
        if cookie:
            self.session.headers['Cookie'] = cookie
        
        if token:
            self.session.headers['uu-token'] = token
            self.session.headers['UU-Token'] = token
            self.session.headers['token'] = token
            self.session.headers['Authorization'] = f'Bearer {token}'
    
    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """获取悠悠有品手机端商品价格"""
        results = []
        
        try:
            self._ensure_mobile_headers()
            
            # 尝试手机端API端点
            # 可能的端点：
            # 1. /api/youpin/mobile/goods/list
            # 2. /api/h5/goods/list  
            # 3. /api/mobile/inventory/list
            
            template_id = None
            if item_config:
                template_id = item_config.get('youpin_template_id') or item_config.get('youpin_goods_id')
            
            if not template_id:
                self.logger.error('悠悠有品手机端需要 template_id')
                return results
            
            base_url = self._get_mobile_api_base_url()
            
            # 尝试多个可能的手机端API端点
            mobile_endpoints = [
                '/api/youpin/mobile/inventory/list',
                '/api/h5/inventory/list',
                '/api/mobile/goods/list',
                '/api/youpin/pc/inventory/list'  # 也尝试PC端但用手机UA
            ]
            
            expected = self._normalize_name(item_name)
            all_items = []
            
            for endpoint in mobile_endpoints:
                api_url = f"{base_url}{endpoint}"
                
                # 尝试不同的payload结构
                payloads = [
                    {
                        'templateId': int(template_id),
                        'gameId': 730,
                        'listType': 10,
                        'pageIndex': 1,
                        'pageSize': 100
                    },
                    {
                        'template_id': int(template_id),
                        'game_id': '730',
                        'page': 1,
                        'size': 100
                    }
                ]
                
                for payload in payloads:
                    try:
                        self.logger.info(f"尝试手机端API: {endpoint}")
                        response = self._make_request(api_url, method='POST', json=payload)
                        data = response.json()
                        
                        # 尝试多种响应结构
                        items = None
                        if data.get('code') == 0:
                            items = (data.get('data') or {}).get('itemsInfos')
                            if not items:
                                items = (data.get('data') or {}).get('items')
                            if not items:
                                items = (data.get('data') or {}).get('list')
                        
                        if items:
                            self.logger.info(f"成功获取数据: {len(items)}条")
                            
                            # 收集所有匹配名称的商品
                            for item in items:
                                youpin_name = str(item.get('name', '') or item.get('goods_name', ''))
                                normalized = self._normalize_name(youpin_name)
                                if expected and normalized and normalized == expected:
                                    all_items.append(item)
                            
                            if all_items:
                                break
                    except Exception as e:
                        self.logger.debug(f"端点 {endpoint} 失败: {e}")
                        continue
                
                if all_items:
                    break
                    
                self._sleep(0.5)
            
            if not all_items:
                self.logger.warning("手机端API未返回数据，回退到标准逻辑")
                return results
            
            self.logger.info(f"手机端收集到 {len(all_items)} 个匹配商品")
            
            # 按磨损区间筛选
            for item in all_items:
                try:
                    wear_value = float(item.get('abrade', 0) or item.get('wear', 0))
                    if wear_value > 1:
                        wear_value = wear_value / 100.0

                    if wear_min <= wear_value <= wear_max:
                        price = float(item.get('price', 0))
                        steam_asset_id = item.get('steamAssetId', '') or item.get('asset_id', '')

                        result = {
                            'platform': 'youpin_mobile',
                            'item_name': item_name,
                            'price': price,
                            'wear': wear_value,
                            'url': f"https://m.youpin898.com/goods/{template_id}",
                            'timestamp': int(time.time())
                        }
                        if steam_asset_id:
                            result['asset_id'] = steam_asset_id
                        results.append(result)

                except (ValueError, KeyError) as e:
                    continue

            # 按价格升序排序，取前20个
            results.sort(key=lambda x: x['price'])
            results = results[:20]
            
            self.logger.info(f"手机端磨损区间筛选后: {len(results)} 个商品")
            for result in results:
                self.logger.info(
                    f"找到匹配商品 - 价格: {result['price']}, 磨损: {result['wear']:.6f}"
                )
        
        except Exception as e:
            self.logger.error(f"手机端获取悠悠有品价格失败: {e}")
        
        return results
