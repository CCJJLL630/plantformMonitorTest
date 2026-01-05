"""ECOSteam平台监控（Selenium版本）"""
from typing import Dict, List, Any, Optional
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import PlatformMonitor


class EcosteamSeleniumMonitor(PlatformMonitor):
    """ECOSteam平台监控器（Selenium方式）"""

    def __init__(self, config: dict):
        super().__init__(config)
        self._driver = None

    def _get_goods_detail_url(self, item_config: Optional[Dict[str, Any]]) -> Optional[str]:
        """从商品配置中获取商品详情页URL"""
        if item_config:
            url = (item_config.get('ecosteam_goods_detail_url') or 
                   item_config.get('ecosteam_goods_url') or 
                   item_config.get('eco_goods_url'))
            if url:
                return str(url)
        return None

    def _init_driver(self):
        """初始化Chrome WebDriver"""
        if self._driver:
            return
        
        self.logger.info("正在启动 Chrome WebDriver...")
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        # 禁用SSL错误日志
        chrome_options.add_argument("--log-level=3")  # 只显示严重错误
        chrome_options.add_argument("--silent")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # 设置User-Agent
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            self._driver = webdriver.Chrome(options=chrome_options)
            # 大幅增加超时时间，适应慢速网络
            self._driver.set_page_load_timeout(120)  # 2分钟
            self._driver.set_script_timeout(60)  # 1分钟
            self.logger.info("Selenium WebDriver 初始化完成")
        except Exception as e:
            self.logger.error(f"初始化Chrome失败: {e}")
            raise

    def _set_cookies(self):
        """设置Cookie"""
        cookie_str = self.config.get('Cookie', '')
        if not cookie_str:
            self.logger.warning("未配置Cookie")
            return
        
        try:
            # 先访问主页
            self.logger.info("访问ECOSteam主页以设置Cookie...")
            self._driver.get("https://www.ecosteam.cn")
            time.sleep(2)
            
            # 设置Cookie
            cookie_count = 0
            for cookie_pair in cookie_str.split('; '):
                if '=' in cookie_pair:
                    name, value = cookie_pair.split('=', 1)
                    try:
                        self._driver.add_cookie({
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': '.ecosteam.cn'
                        })
                        cookie_count += 1
                    except Exception as e:
                        self.logger.debug(f"设置Cookie {name} 失败: {e}")
            
            self.logger.info(f"已设置 {cookie_count} 个Cookie")
        except Exception as e:
            self.logger.error(f"设置Cookie失败: {e}")

    def _close_driver(self):
        """关闭WebDriver"""
        if self._driver:
            try:
                self.logger.info("正在关闭 Chrome WebDriver...")
                self._driver.quit()
                self._driver = None
            except:
                pass

    def _parse_page_with_selenium(self, url: str, page: int = 1) -> List[Dict[str, float]]:
        """使用Selenium解析单页数据"""
        # 构造页面URL
        page_url = re.sub(r'-0-\d+\.html$', f'-0-{page}.html', url)
        
        self.logger.info(f"访问第 {page} 页: {page_url}")
        
        try:
            self._driver.get(page_url)
            self.logger.info(f"第 {page} 页加载完成")
        except Exception as e:
            self.logger.warning(f"第 {page} 页加载超时，尝试继续: {e}")
        
        # 等待页面渲染 - 增加等待时间
        self.logger.info(f"等待第 {page} 页数据渲染...")
        time.sleep(5)
        
        # 获取页面HTML
        html = self._driver.page_source
        self.logger.info(f"第 {page} 页HTML长度: {len(html)} 字符")
        
        # 解析商品数据
        rows = []
        
        # 正则匹配磨损值和价格
        wear_pattern = re.compile(r'<p\s+class="WearRate"[^>]*>[\s\S]*?<span[^>]*>\s*([0-9]+(?:\.[0-9]+)?)\s*</span>', re.IGNORECASE)
        price_pattern = re.compile(r'￥\s*([0-9]+(?:\.[0-9]+)?)')
        
        wear_matches = list(wear_pattern.finditer(html))
        
        for wear_match in wear_matches:
            try:
                wear_value = float(wear_match.group(1))
                
                # 在磨损值后面的2500字符内找价格
                start_pos = wear_match.end()
                window = html[start_pos:start_pos + 2500]
                price_match = price_pattern.search(window)
                
                if price_match:
                    price_value = float(price_match.group(1))
                    rows.append({'wear': wear_value, 'price': price_value})
            except:
                continue
        
        self.logger.info(f"第 {page} 页解析到 {len(rows)} 个商品")
        return rows

    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取ECOSteam平台商品价格（使用 Selenium）
        
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
            goods_url = self._get_goods_detail_url(item_config)
            if not goods_url:
                self.logger.error(
                    'ECOSteam 缺少商品详情页URL：请在 items 中配置 ecosteam_goods_detail_url'
                )
                return results

            self.logger.info(f"使用 Selenium 从 ECOSteam 获取数据: {goods_url}")
            
            # 初始化WebDriver并设置Cookie
            self._init_driver()
            self._set_cookies()
            
            # 使用Selenium获取多页数据
            all_rows = []
            
            # 获取第一页并检测最大页数
            self.logger.info(f"访问商品页: {goods_url}")
            self.logger.info("页面加载中，请耐心等待（可能需要1-2分钟）...")
            
            try:
                self._driver.get(goods_url)
                self.logger.info("页面加载完成，等待数据渲染...")
                time.sleep(5)  # 等待页面渲染
            except Exception as e:
                self.logger.error(f"页面加载失败: {e}")
                # 如果超时，尝试获取当前页面内容
                self.logger.warning("页面加载超时，尝试获取当前内容...")
            
            html = self._driver.page_source
            
            # 检测最大页数
            page_nums = [int(m.group(1)) for m in re.finditer(r'data-page="(\d+)"', html)]
            max_page = max(page_nums) if page_nums else 1
            max_page = min(max_page, 10)  # 最多10页
            
            self.logger.info(f"检测到最大页数: {max_page}")
            
            # 获取每一页的数据
            for page in range(1, max_page + 1):
                page_rows = self._parse_page_with_selenium(goods_url, page)
                all_rows.extend(page_rows)
                
                if page < max_page:
                    time.sleep(2)  # 页面间隔
            
            self.logger.info(f"总共获取 {len(all_rows)} 个商品")
            
            # 筛选磨损范围内的商品
            import datetime
            current_time = datetime.datetime.now().isoformat()
            
            for row in all_rows:
                wear_value = row.get('wear', 0)
                price = row.get('price', 0)
                
                if wear_min <= wear_value <= wear_max:
                    results.append({
                        'platform': 'ecosteam',
                        'item_name': item_name,
                        'price': price,
                        'wear': wear_value,
                        'timestamp': current_time,
                    })
            
            # 按价格排序
            results.sort(key=lambda x: x['price'])
            
            if results:
                self.logger.info(f"找到 {len(results)} 个磨损区间 {wear_min}-{wear_max} 内的商品")
                self.logger.info(f"价格范围: ¥{results[0]['price']:.2f} - ¥{results[-1]['price']:.2f}")
            
        except Exception as e:
            self.logger.error(f"ECOSteam 获取价格失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._close_driver()
        
        return results
