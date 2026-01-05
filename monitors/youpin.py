"""悠悠有品平台监控 - 重构版"""
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs
import re
import time
import json
import logging
import threading
from .base import PlatformMonitor


class YoupinMonitor(PlatformMonitor):
    """悠悠有品平台监控器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._driver = None
        self._driver_initialized = False
        self.logger = logging.getLogger('YoupinMonitor')
        self._shutdown_event = threading.Event()

    def _safe_sleep(self, seconds: float):
        """安全的sleep函数"""
        try:
            self._shutdown_event.wait(timeout=seconds)
        except KeyboardInterrupt:
            pass

    def _normalize_name(self, name: str) -> str:
        """归一化商品名称"""
        s = (name or '').strip().lower()
        s = re.split(r'[\(（]', s, maxsplit=1)[0]
        s = re.sub(r'[\s\|\-–—_\[\]【】\(\)（）]', '', s)
        return s

    def _get_goods_list_url(self, item_config: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """从商品配置中获取商品列表URL"""
        if item_config:
            url = item_config.get('youpin_goods_list_url')
            if url:
                return str(url)
        return None

    def _parse_template_params(self, url: str) -> Dict[str, int]:
        """解析URL中的模板参数"""
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

    def _init_selenium(self):
        """初始化 Selenium WebDriver"""
        if self._driver_initialized:
            return
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 启用性能日志
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            self.logger.info("正在启动 Chrome WebDriver...")
            self._driver = webdriver.Chrome(options=chrome_options)
            self._driver.execute_cdp_cmd('Network.enable', {})
            self._driver_initialized = True
            self.logger.info("Selenium WebDriver 初始化完成")
            
            # 设置Cookie
            self._set_cookies()
            
        except Exception as e:
            self.logger.error(f"Selenium 初始化失败: {e}")
            self._driver = None
            self._driver_initialized = True

    def _set_cookies(self):
        """设置Cookie到Selenium"""
        cookie_str = self.session.headers.get('Cookie', '')
        if not cookie_str:
            self.logger.warning("未配置Cookie")
            return
        
        try:
            # 先访问主页
            self.logger.info("访问悠悠有品主页以设置Cookie...")
            self._driver.get("https://www.youpin898.com")
            self._safe_sleep(2)
            
            # 设置Cookie
            cookie_count = 0
            for cookie_pair in cookie_str.split('; '):
                if '=' in cookie_pair:
                    name, value = cookie_pair.split('=', 1)
                    try:
                        self._driver.add_cookie({
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': '.youpin898.com'
                        })
                        cookie_count += 1
                    except Exception as e:
                        self.logger.debug(f"设置Cookie {name} 失败: {e}")
            
            self.logger.info(f"已设置 {cookie_count} 个Cookie")
        except Exception as e:
            self.logger.error(f"设置Cookie失败: {e}")

    def _fetch_page_data(self, template_id: int, page_index: int) -> Optional[List[Dict]]:
        """
        获取指定页的商品数据
        
        Args:
            template_id: 商品模板ID
            page_index: 页码（从1开始）
            
        Returns:
            商品列表，获取失败返回None
        """
        if not self._driver:
            self._init_selenium()
        
        if not self._driver:
            self.logger.error("Selenium WebDriver初始化失败")
            return None
        
        try:
            url = f'https://www.youpin898.com/market/goods-list?templateId={template_id}&gameId=730&listType=10'
            
            # 第一页直接加载URL
            if page_index == 1:
                self._driver.get(url)
                self.logger.info(f"加载首页: {url}")
                self._safe_sleep(20)  # 等待首页加载和API请求
            else:
                # 非第一页需要翻页
                self.logger.info(f"翻页到第 {page_index} 页...")
                
                # 滚动到页面底部确保分页控件可见
                self._driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self._safe_sleep(1)
                
                # 点击对应页码
                click_script = f"""
                const pageItems = document.querySelectorAll('[class*="paginationItem"]');
                for (let item of pageItems) {{
                    if (item.textContent.trim() === '{page_index}') {{
                        item.click();
                        return true;
                    }}
                }}
                return false;
                """
                
                clicked = self._driver.execute_script(click_script)
                if not clicked:
                    self.logger.warning(f"未找到第 {page_index} 页的页码按钮")
                    return None
                
                self._safe_sleep(15)  # 等待翻页后的API请求
            
            # 捕获API响应
            self.logger.info(f"捕获第 {page_index} 页的API响应...")
            performance_logs = self._driver.get_log('performance')
            
            # 从后往前查找最新的API响应
            for entry in reversed(performance_logs):
                try:
                    log_entry = json.loads(entry['message'])
                    message = log_entry.get('message', {})
                    
                    if message.get('method') != 'Network.responseReceived':
                        continue
                    
                    response = message.get('params', {}).get('response', {})
                    if 'queryOnSaleCommodityList' not in response.get('url', ''):
                        continue
                    
                    # 找到目标API，获取响应体
                    request_id = message.get('params', {}).get('requestId')
                    response_body = self._driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                    body_text = response_body.get('body', '')
                    
                    if not body_text:
                        continue
                    
                    api_data = json.loads(body_text)
                    
                    # 提取商品列表
                    data = api_data.get('Data') or api_data.get('data', {})
                    if isinstance(data, list):
                        items = data
                    else:
                        items = data.get('commodityList') or data.get('CommodityList', [])
                    
                    if len(items) > 0:
                        self.logger.info(f"第 {page_index} 页获取成功: {len(items)} 个商品")
                        return items
                    
                except Exception as e:
                    continue
            
            self.logger.warning(f"第 {page_index} 页未找到有效API响应")
            return None
            
        except Exception as e:
            self.logger.error(f"获取第 {page_index} 页数据失败: {e}")
            return None

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
            item_config: 商品配置
            
        Returns:
            价格信息列表
        """
        results = []
        
        try:
            # 1. 获取templateId
            template_id = None
            if item_config:
                template_id = item_config.get('youpin_template_id') or item_config.get('youpin_goods_id')
            
            if not template_id:
                goods_list_url = self._get_goods_list_url(item_config)
                if goods_list_url:
                    parsed = self._parse_template_params(goods_list_url)
                    template_id = parsed.get('templateId')
            
            if not template_id:
                self.logger.error('悠悠有品缺少 templateId：请在 items 中配置 youpin_template_id 或 youpin_goods_list_url')
                return results

            self.logger.info(f"开始获取市场在售商品: {item_name} (templateId={template_id})")

            # 2. 收集所有页面的商品数据
            all_items = []
            max_pages = 8  # 最多获取8页
            
            for page in range(1, max_pages + 1):
                page_items = self._fetch_page_data(template_id, page)
                
                if page_items is None:
                    self.logger.warning(f"第 {page} 页获取失败，停止翻页")
                    break
                
                if len(page_items) == 0:
                    self.logger.info(f"第 {page} 页没有数据，停止翻页")
                    break
                
                all_items.extend(page_items)
                
                # 输出本页统计信息
                wears = []
                prices = []
                for item in page_items:
                    try:
                        wear = float(item.get('abrade') or item.get('Abrade', '0'))
                        price = float(item.get('price') or item.get('Price', '0'))
                        wears.append(wear)
                        prices.append(price)
                    except:
                        pass
                
                if wears:
                    self.logger.info(f"第 {page} 页: {len(page_items)} 个商品 | "
                                   f"磨损: {min(wears):.4f}~{max(wears):.4f} | "
                                   f"价格: ¥{min(prices):.2f}~¥{max(prices):.2f}")

            self.logger.info(f"共获取 {len(all_items)} 个在售商品")
            
            # 3. 筛选符合条件的商品
            expected_name = self._normalize_name(item_name)
            filtered = []
            
            for item in all_items:
                commodity_name = item.get('commodityName') or item.get('CommodityName', '')
                actual_name = self._normalize_name(commodity_name)
                
                # 名称匹配
                if expected_name != actual_name:
                    continue
                
                # 解析价格和磨损
                try:
                    price = float(item.get('price') or item.get('Price', '0'))
                    wear = float(item.get('abrade') or item.get('Abrade', '0'))
                except (ValueError, TypeError):
                    continue
                
                # 磨损范围过滤
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
            
            # 4. 按价格排序，取前20个
            filtered.sort(key=lambda x: x['price'])
            results = filtered[:20]
            
            self.logger.info(f"磨损区间 {wear_min}-{wear_max} 内找到 {len(filtered)} 个商品，返回前 {len(results)} 个")
            
            for item in results:
                self.logger.info(f"找到匹配商品 - 价格: {item['price']}, 磨损: {item['wear']:.6f}")
        
        except Exception as e:
            self.logger.error(f"获取悠悠有品价格失败: {e}", exc_info=True)
        
        return results

    def __del__(self):
        """清理 Selenium WebDriver"""
        if hasattr(self, '_driver') and self._driver:
            try:
                self.logger.info("正在关闭 Chrome WebDriver...")
                self._driver.quit()
            except Exception as e:
                self.logger.warning(f"关闭 WebDriver 时出错: {e}")
