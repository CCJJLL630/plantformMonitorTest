"""ECOSteam平台监控（优先使用官方 API SellGoodsQuery）"""
from typing import Dict, List, Any, Optional
import re
import time
from .base import PlatformMonitor


class EcosteamMonitor(PlatformMonitor):
    """ECOSteam平台监控器（API 优先，HTML 作为备用）"""

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

        response = self._make_request(goods_url)
        html1 = response.text
        max_page_on_site = _detect_max_page(html1)

        all_rows: List[Dict[str, float]] = []
        page1_rows = _parse_rows(html1)
        all_rows.extend(page1_rows)
        
        # 记录第一页的磨损范围
        if page1_rows:
            wears = [r['wear'] for r in page1_rows]
            self.logger.info(f"ECOSteam 第1页：{len(page1_rows)}个商品，磨损范围 {min(wears):.6f}-{max(wears):.6f}")

        # 从配置读取最大页数，默认20页
        config_max_pages = int(self.config.get('max_pages', 20))
        actual_max_page = min(max_page_on_site, config_max_pages)
        page_delay = float(self.config.get('page_delay_seconds', 1.0))
        
        self.logger.info(f"ECOSteam 网站共{max_page_on_site}页，将抓取前{actual_max_page}页")

        # 抓取后续页面
        for page in range(2, actual_max_page + 1):
            # 添加随机延迟，避免触发反爬
            if page_delay > 0:
                jitter = random.uniform(0.1, 0.3)
                actual_delay = page_delay * (1 + jitter)
                time.sleep(actual_delay)
            
            url = _page_url(goods_url, page)
            page_html = self._make_request(url).text
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
        """获取ECOSteam平台商品价格（API 优先，失败则回退 HTML）"""
        results: List[Dict[str, Any]] = []
        observed_wears: List[float] = []

        try:
            goods_url = self._get_goods_detail_url(item_config)
            if not goods_url:
                self.logger.error('ECOSteam 缺少 goods_detail_url（商品详情页 URL）')
                return results

            # 准备请求头
            self.session.headers.setdefault('Origin', self.base_url.rstrip('/'))
            self.session.headers.setdefault('Referer', goods_url)
            self.session.headers.setdefault('X-Requested-With', 'XMLHttpRequest')

            # 解析 gameId
            parsed = self._parse_goods_url(goods_url)
            game_id = int(item_config.get('eco_game_id') or parsed.get('gameId') or 730)

            # 先尝试 API
            hash_name = self._resolve_hash_name(goods_url, item_config)
            internal_id = None
            if hash_name:
                internal_id = item_config.get('eco_internal_goods_id') or item_config.get('eco_goods_id')
                internal_id = str(internal_id) if internal_id else self._resolve_internal_id(hash_name, game_id)

            api_items: List[Dict[str, Any]] = []
            if hash_name:
                self.logger.info(f"通过 API 获取 ECOSteam 在售列表: hash_name={hash_name} internal_id={internal_id}")
                api_items = self._fetch_sell_list_api(hash_name, internal_id, game_id)
            else:
                self.logger.warning("未获取到 hash_name，跳过 API，回退 HTML 解析")

            # 如果 API 返回为空，回退到 HTML 解析
            if not api_items:
                self.logger.info("API 未返回数据，改用 HTML 解析")
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
                        self.logger.info(
                            f"找到匹配商品 - 价格: {price}, 磨损: {wear_value:.6f}"
                        )
            else:
                # 使用 API 数据
                for item in api_items:
                    wear_value = self._parse_wear(item)
                    price = self._parse_price(item)
                    if wear_value is None or price is None:
                        continue

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
                        self.logger.info(
                            f"找到匹配商品 - 价格: {price}, 磨损: {wear_value:.6f}"
                        )

            if not results and observed_wears:
                self.logger.info(
                    f"ECOSteam 未命中磨损区间: {wear_min}-{wear_max}；样本磨损范围: {min(observed_wears):.6f}-{max(observed_wears):.6f}"
                )

        except Exception as e:
            self.logger.error(f"获取ECOSteam价格失败: {e}")

        return results
