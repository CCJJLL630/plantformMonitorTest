"""网易BUFF平台监控"""
from typing import Dict, List, Any, Optional
import time
from .base import PlatformMonitor


class BuffMonitor(PlatformMonitor):
    """网易BUFF平台监控器"""
    
    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取BUFF平台商品价格
        
        Args:
            item_name: 商品名称
            wear_min: 最小磨损
            wear_max: 最大磨损
            
        Returns:
            价格信息列表
        """
        results = []
        observed_wears: List[float] = []
        
        try:
            # 优先使用配置中提供的 goods_id，避免依赖可能失效的搜索接口
            item_id = None
            if item_config is not None:
                item_id = item_config.get('buff_goods_id')
                if item_id:
                    self.logger.info(f"使用配置的 BUFF goods_id: {item_id}")
            
            # 如未在配置中提供，则回退到原有搜索逻辑（若接口已失效可能会报错）
            if not item_id:
                search_url = f"{self.base_url}/api/market/search"
                params = {
                    'game': 'csgo',
                    'page_num': 1,
                    'search': item_name
                }
                
                self.logger.info(f"搜索商品: {item_name}")
                response = self._make_request(search_url, params=params)
                data = response.json()
                
                if data.get('code') != 'OK' or not data.get('data', {}).get('items'):
                    self.logger.warning(f"未找到商品: {item_name}")
                    return results
                
                # 获取第一个匹配的商品ID
                item_id = data['data']['items'][0]['id']
                self.logger.info(f"找到商品ID: {item_id}")
                
                self._sleep(1)
            
            # 2. 获取商品在售列表（使用 goods_id），多页扫描收集所有符合磨损区间的商品
            sell_url = f"{self.base_url}/api/market/goods/sell_order"
            max_pages = 10  # 增加翻页上限以收集更多数据
            page_size = 50
            max_results = 100  # 收集足够多的候选项用于排序筛选

            for page_num in range(1, max_pages + 1):
                params = {
                    'game': 'csgo',
                    'goods_id': item_id,
                    'page_num': page_num,
                    'page_size': page_size,
                    # 以价格升序获取更接近最低价的列表
                    'sort_by': 'price.asc'
                }

                self.logger.info(f"获取在售列表: {item_id} (page={page_num})")
                response = self._make_request(sell_url, params=params)
                data = response.json()

                if data.get('code') != 'OK':
                    self.logger.error(f"获取在售列表失败: {data.get('error')}")
                    return results

                items = data.get('data', {}).get('items', [])
                if not items:
                    break

                # 3. 筛选磨损区间内的商品
                for item in items:
                    try:
                        asset_info = item.get('asset_info', {})
                        paintwear = asset_info.get('paintwear')

                        if paintwear is None:
                            continue

                        wear_value = float(paintwear)
                        if len(observed_wears) < 30:
                            observed_wears.append(wear_value)

                        if wear_min <= wear_value <= wear_max:
                            price = float(item.get('price', 0))

                            result = {
                                'platform': 'buff',
                                'item_name': item_name,
                                'price': price,
                                'wear': wear_value,
                                'url': f"{self.base_url}/goods/{item_id}",
                                'timestamp': int(time.time())
                            }
                            results.append(result)

                    except (ValueError, KeyError) as e:
                        self.logger.warning(f"解析商品数据失败: {e}")
                        continue

                # 已收集足够数据，停止翻页
                if len(results) >= max_results:
                    break

                self._sleep(0.8)

            # 按价格升序排序，取前20个
            results.sort(key=lambda x: x['price'])
            results = results[:20]
            
            # 打印日志
            for result in results:
                self.logger.info(
                    f"找到匹配商品 - 价格: {result['price']}, 磨损: {result['wear']:.6f}"
                )

            if not results and observed_wears:
                self.logger.info(
                    f"BUFF 未命中磨损区间: {wear_min}-{wear_max}；样本磨损范围: {min(observed_wears):.6f}-{max(observed_wears):.6f}"
                )
        
        except Exception as e:
            self.logger.error(f"获取BUFF价格失败: {e}")
        
        return results
