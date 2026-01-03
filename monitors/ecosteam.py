"""ECOSteam平台监控"""
from typing import Dict, List, Any, Optional
import re
import time
from .base import PlatformMonitor


class EcosteamMonitor(PlatformMonitor):
    """ECOSteam平台监控器（HTML 解析方式）"""

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
        max_page = _detect_max_page(html1)

        all_rows: List[Dict[str, float]] = []
        all_rows.extend(_parse_rows(html1))

        # 最多抓取前 10 页，避免异常情况下无限翻页
        for page in range(2, min(max_page, 10) + 1):
            url = _page_url(goods_url, page)
            page_html = self._make_request(url).text
            all_rows.extend(_parse_rows(page_html))

        return all_rows

    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取ECOSteam平台商品价格（使用 HTML 解析）
        
        Args:
            item_name: 商品名称
            wear_min: 最小磨损
            wear_max: 最大磨损
            item_config: 商品配置（需包含 goods_detail_url）
            
        Returns:
            价格信息列表
        """
        results = []
        observed_wears: List[float] = []
        
        try:
            goods_url = self._get_goods_detail_url(item_config)
            if not goods_url:
                self.logger.error('ECOSteam 缺少 goods_detail_url（商品详情页 URL）')
                return results

            self.logger.info(f"从 ECOSteam 商品页 HTML 解析在售列表: {goods_url}")
            
            # 直接使用 HTML 解析方法
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

            if not results and observed_wears:
                self.logger.info(
                    f"ECOSteam 未命中磨损区间: {wear_min}-{wear_max}；样本磨损范围: {min(observed_wears):.6f}-{max(observed_wears):.6f}"
                )
        
        except Exception as e:
            self.logger.error(f"获取ECOSteam价格失败: {e}")
        
        return results
