"""ECOSteam平台监控"""
from typing import Dict, List, Any, Optional
import re
from urllib.parse import urlparse
import time
from .base import PlatformMonitor


class EcosteamMonitor(PlatformMonitor):
    """ECOSteam平台监控器"""

    def _ajax_headers(self, referer: str) -> Dict[str, str]:
        return {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': self.base_url,
            'Referer': referer,
            'X-Requested-With': 'XMLHttpRequest',
        }

    def _get_goods_detail_url(self, item_config: Optional[Dict[str, Any]]) -> Optional[str]:
        if item_config:
            url = item_config.get('eco_goods_url') or item_config.get('ecosteam_goods_url')
            if url:
                return str(url)
        url = self.config.get('goods_detail_url')
        return str(url) if url else None

    def _extract_hash_name(self, goods_url: str) -> Optional[str]:
        # ECOSteam 商品详情页包含 data-HashName 属性
        response = self._make_request(goods_url)
        m = re.search(r'data-HashName="([^"]+)"', response.text)
        return m.group(1) if m else None

    def _parse_sell_list_from_html(self, goods_url: str) -> List[Dict[str, float]]:
        """从商品详情页 HTML 中解析在售列表（作为 API 失效/返回空时的兜底）。"""
        response = self._make_request(goods_url)
        html = response.text

        # 页面表格行中常见形式："磨损： 0.332..." 与 "￥287.00"
        # 这里用一个宽松的正则直接抓取磨损与价格（按出现顺序配对）
        matches = re.findall(r'磨损：\s*([0-9]+\.[0-9]+)[\s\S]*?￥\s*([0-9]+(?:\.[0-9]+)?)', html)
        rows: List[Dict[str, float]] = []
        for wear_s, price_s in matches[:300]:
            try:
                rows.append({'wear': float(wear_s), 'price': float(price_s)})
            except ValueError:
                continue
        return rows

    def _query_internal_goods_id(self, game_id: int, hash_name: str, referer: str) -> Optional[str]:
        api_url = f"{self.base_url}/Api/SteamGoods/GoodsDetailQueryPost"
        payload = {
            'GameId': game_id,
            'HashName': hash_name,
        }
        response = self._make_request(
            api_url,
            method='POST',
            json=payload,
            headers=self._ajax_headers(referer),
        )
        data = response.json()
        status = data.get('StatusData') or {}
        if status.get('ResultCode') != '0':
            self.logger.error(
                f"ECOSteam 详情查询失败: code={status.get('ResultCode')}, msg={status.get('ResultMsg')}"
            )
            return None
        result = status.get('ResultData') or {}
        return result.get('Id')
    
    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取ECOSteam平台商品价格
        
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
            goods_url = self._get_goods_detail_url(item_config)
            if not goods_url:
                self.logger.error('ECOSteam 缺少 goods_detail_url（商品详情页 URL），无法定位 HashName')
                return results

            game_id = 730
            try:
                # 尝试从 URL 路径中解析 gameId（/goods/730-...）
                path = urlparse(goods_url).path
                m = re.search(r'/goods/(\d+)-', path)
                if m:
                    game_id = int(m.group(1))
            except Exception:
                pass

            self.logger.info(f"获取ECOSteam商品详情: {goods_url}")
            hash_name = self._extract_hash_name(goods_url)
            if not hash_name:
                self.logger.error('ECOSteam 未能从商品页提取 data-HashName')
                return results

            internal_goods_id = self._query_internal_goods_id(game_id, hash_name, goods_url)
            if not internal_goods_id:
                return results

            # 拉取在售列表，多页扫描避免“第一页没有落在磨损区间”
            sell_url = f"{self.base_url}/Api/SteamGoods/SellGoodsQuery"
            max_pages = 5
            # 站点侧常见默认 PageSize 为 40，过大可能返回错误
            page_size = 40

            for page_index in range(1, max_pages + 1):
                payload = {
                    'GameId': game_id,
                    'GoodsId': internal_goods_id,
                    'HashName': hash_name,
                    'PageIndex': page_index,
                    'PageSize': page_size,
                }

                self.logger.info(f"获取ECOSteam在售列表: {hash_name} (page={page_index})")
                response = self._make_request(
                    sell_url,
                    method='POST',
                    json=payload,
                    headers=self._ajax_headers(goods_url),
                )
                data = response.json()

                status = data.get('StatusData') or {}
                if status.get('ResultCode') != '0':
                    self.logger.error(
                        f"ECOSteam 在售列表失败: code={status.get('ResultCode')}, msg={status.get('ResultMsg')}"
                    )
                    # 兜底：尝试从页面 HTML 解析在售列表
                    self.logger.info("尝试从 ECOSteam 商品页 HTML 解析在售列表")
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
                    break

                page = status.get('ResultData') or {}
                items = page.get('PageResult') or []
                if not items:
                    break

                for item in items:
                    try:
                        wear_value = float(item.get('Scale', 0))
                        # 有些数据可能是百分比（例如 15.23），统一转为 0-1
                        if wear_value > 1:
                            wear_value = wear_value / 100.0

                        if len(observed_wears) < 30:
                            observed_wears.append(wear_value)

                        if wear_min <= wear_value <= wear_max:
                            price = float(item.get('SellingPrice', 0))
                            goods_num = item.get('GoodsNum', '')

                            result = {
                                'platform': 'ecosteam',
                                'item_name': item_name,
                                'price': price,
                                'wear': wear_value,
                                'url': goods_url,
                                'timestamp': int(time.time())
                            }
                            if goods_num:
                                result['goods_num'] = goods_num
                            results.append(result)
                            self.logger.info(
                                f"找到匹配商品 - 价格: {price}, 磨损: {wear_value:.6f}"
                            )

                    except (ValueError, KeyError) as e:
                        self.logger.warning(f"解析商品数据失败: {e}")
                        continue

                if results:
                    break

                self._sleep(0.6)

            if not results and observed_wears:
                self.logger.info(
                    f"ECOSteam 未命中磨损区间: {wear_min}-{wear_max}；样本磨损范围: {min(observed_wears):.6f}-{max(observed_wears):.6f}"
                )
        
        except Exception as e:
            self.logger.error(f"获取ECOSteam价格失败: {e}")
        
        return results
