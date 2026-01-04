"""悠悠有品平台监控"""
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
        self._shutdown_event = threading.Event()  # 用于健壮的等待

    def _safe_sleep(self, seconds: float):
        """信号安全的sleep函数，忽略KeyboardInterrupt"""
        try:
            self._shutdown_event.wait(timeout=seconds)
        except KeyboardInterrupt:
            # 在后台运行时，sleep可能会被误触发的信号中断
            # 忽略这些中断，继续执行
            pass

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
    
    def _init_selenium(self):
        """初始化 Selenium WebDriver（延迟加载）"""
        if self._driver_initialized:
            return
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 无头模式，不显示浏览器窗口
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            self.logger.info("正在启动 Chrome WebDriver...")
            self._driver = webdriver.Chrome(options=chrome_options)
            # 设置页面加载和脚本执行超时（秒）
            self._driver.set_page_load_timeout(45)
            self._driver.set_script_timeout(30)
            self._driver_initialized = True
            
            # 访问主页并注入 Cookie
            cookie_str = self.session.headers.get('Cookie', '')
            if cookie_str:
                self._driver.get('https://www.youpin898.com')
                self._safe_sleep(1)
                
                for item in cookie_str.split(';'):
                    item = item.strip()
                    if '=' in item:
                        name, value = item.split('=', 1)
                        try:
                            self._driver.add_cookie({'name': name.strip(), 'value': value.strip()})
                        except:
                            pass
            
            self.logger.info("Selenium WebDriver 初始化完成")
        except Exception as e:
            self.logger.error(f"初始化 Selenium 失败: {e}")
            self._driver = None
            self._driver_initialized = True  # 标记为已尝试，避免重复初始化
    
    def _extract_cookies_from_selenium(self) -> Dict[str, str]:
        """从 Selenium 浏览器中提取 Cookie"""
        if not self._driver:
            return {}
        
        cookies = {}
        try:
            for cookie in self._driver.get_cookies():
                cookies[cookie['name']] = cookie['value']
        except:
            pass
        return cookies
    
    def _extract_headers_from_selenium(self) -> Dict[str, str]:
        """从 Selenium 捕获的请求中提取请求头"""
        if not self._driver:
            return {}
        
        headers = {}
        try:
            logs = self._driver.get_log('performance')
            for entry in logs:
                try:
                    log = json.loads(entry['message'])['message']
                    method = log.get('method')
                    
                    # 找到我们的 API 请求
                    if method == 'Network.requestWillBeSent':
                        request_data = log.get('params', {}).get('request', {})
                        url = request_data.get('url', '')
                        
                        if 'queryOnSaleCommodityList' in url:
                            # 提取这个请求的所有 headers
                            headers = request_data.get('headers', {})
                            break
                except:
                    continue
        except:
            pass
        
        return headers

    
    def _fetch_market_data_selenium(self, template_id: int, page_index: int = 1, page_size: int = 20) -> Optional[Dict]:
        """使用 Selenium 获取市场在售商品数据（通过性能日志捕获API响应）
        
        策略：每次都重新访问页面，通过注入JavaScript直接修改页面状态来请求指定页码的数据
        """
        if not self._driver:
            self._init_selenium()
        
        if not self._driver:
            self.logger.error("Selenium 不可用")
            return None
        
        try:
            # 构建URL
            url = f'https://www.youpin898.com/market/goods-list?templateId={template_id}&gameId=730&listType=10'
            
            # 访问页面（对所有页码都重新加载）
            self._driver.get(url)
            self.logger.info(f"已加载页面（目标第 {page_index} 页）")
            
            # 等待页面初始化
            self._safe_sleep(6)
            
            if page_index > 1:
                # 先等待分页控件出现
                self.logger.info(f"等待分页控件加载...")
                self._safe_sleep(4)
                
                # 滚动到底部，确保分页控件在视图中
                self._driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self._safe_sleep(1)
                
                # 通过JavaScript点击指定页码（使用正确的class名）
                self.logger.info(f"尝试翻页到第 {page_index} 页...")
                
                script = f"""
                // 悠悠有品使用CSS Modules，class名为 paginationItem___xxxxx
                // 方案1：直接点击目标页码
                const items = document.querySelectorAll('[class*="paginationItem"]');
                for (let item of items) {{
                    if (item.textContent.trim() === '{page_index}') {{
                        item.click();
                        return 'direct_click_page_{page_index}';
                    }}
                }}
                
                // 方案2：多次点击下一页按钮
                let clicks = {page_index - 1};
                let completed = 0;
                
                function clickNext() {{
                    if (completed >= clicks) return;
                    
                    // 查找下一页按钮（可能class名也是CSS Modules）
                    const nextSelectors = [
                        '[class*="paginationNext"]',
                        '[class*="pagination"][class*="next"]',
                        '.ant-pagination-next',
                        'button:has-text("下一页")'
                    ];
                    
                    let nextBtn = null;
                    for (let selector of nextSelectors) {{
                        try {{
                            nextBtn = document.querySelector(selector);
                            if (nextBtn && !nextBtn.classList.contains('disabled')) break;
                        }} catch(e) {{}}
                    }}
                    
                    if (nextBtn) {{
                        nextBtn.click();
                        completed++;
                        
                        if (completed < clicks) {{
                            setTimeout(clickNext, 2000);
                        }}
                    }}
                }}
                
                clickNext();
                return 'multi_click_' + clicks;
                """
                
                result = self._driver.execute_script(script)
                self.logger.info(f"点击策略: {result}")
                
                # 等待数据加载
                wait_time = 5 + (page_index - 1) * 3
                self.logger.info(f"等待 {wait_time} 秒让数据加载...")
                self._safe_sleep(wait_time)
                
                # 验证是否真的翻页了（使用新的选择器）
                current_page_num = self._driver.execute_script("""
                    // 查找高亮/激活的页码项
                    const items = document.querySelectorAll('[class*="paginationItem"]');
                    for (let item of items) {
                        const classes = item.className;
                        if (classes.includes('active') || classes.includes('Active') || 
                            classes.includes('current') || classes.includes('Current') ||
                            classes.includes('selected') || classes.includes('Selected')) {
                            return item.textContent.trim();
                        }
                    }
                    
                    return '0';
                """)
                self.logger.info(f"当前页码显示: {current_page_num}")
                
                if str(current_page_num) != str(page_index):
                    self.logger.warning(f"页码验证失败！期望第{page_index}页，实际第{current_page_num}页（继续尝试获取数据）")
            else:
                # 第一页直接等待
                self._safe_sleep(3)
            
            self.logger.info("准备提取性能日志")

            
            # 从性能日志中提取 API 响应
            self._safe_sleep(0.5)  # 减少等待时间
            logs = self._driver.get_log('performance')
            self.logger.info(f"获取到 {len(logs)} 条性能日志")
            
            # 对于所有页面，都检查最近的200条日志（增加范围）
            if page_index == 1:
                recent_logs = logs
            else:
                recent_logs = logs[-200:] if len(logs) > 200 else logs
            
            # 统计匹配的API URL数量
            api_count = 0
            for entry in recent_logs:
                try:
                    log_entry = json.loads(entry['message'])
                    message = log_entry.get('message', {})
                    method = message.get('method', '')
                    
                    if method == 'Network.responseReceived':
                        response = message.get('params', {}).get('response', {})
                        url_resp = response.get('url', '')
                        
                        if 'queryOnSaleCommodityList' in url_resp:
                            api_count += 1
                except:
                    continue
            
            self.logger.info(f"找到 {api_count} 个匹配的API响应")
            
            # 从后往前找最新的API响应
            for entry in reversed(recent_logs):
                try:
                    log_entry = json.loads(entry['message'])
                    message = log_entry.get('message', {})
                    method = message.get('method', '')
                    
                    if method == 'Network.responseReceived':
                        response = message.get('params', {}).get('response', {})
                        url_resp = response.get('url', '')
                        
                        if 'queryOnSaleCommodityList' in url_resp:
                            request_id = message.get('params', {}).get('requestId')
                            
                            try:
                                response_body = self._driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                                body_text = response_body.get('body', '')
                                if body_text:
                                    api_data = json.loads(body_text)
                                    
                                    # 验证数据：检查商品数量，确保不是空数据
                                    data_list = api_data.get('Data') or api_data.get('data', [])
                                    if isinstance(data_list, dict):
                                        data_list = data_list.get('commodityList') or data_list.get('CommodityList', [])
                                    
                                    if len(data_list) > 0:
                                        self.logger.info(f"成功获取第 {page_index} 页数据（{len(data_list)}个商品）")
                                        return api_data
                                    else:
                                        self.logger.warning(f"获取的数据为空，继续查找...")
                                        continue
                            except Exception as e:
                                self.logger.warning(f"获取响应体失败: {e}")
                                continue
                except:
                    continue
            
            self.logger.warning(f"未从性能日志中找到 API 响应 (page={page_index})")
            return None
                
        except Exception as e:
            self.logger.error(f"Selenium 获取市场数据失败 (page={page_index}): {e}")
            return None
    
    def __del__(self):
        """清理 Selenium WebDriver"""
        if hasattr(self, '_driver') and self._driver:
            try:
                self.logger.info("正在关闭 Chrome WebDriver...")
                self._driver.quit()
            except Exception as e:
                self.logger.warning(f"关闭 WebDriver 时出错: {e}")
                # 尝试强制清理
                try:
                    import os
                    import signal
                    if hasattr(self._driver, 'service') and hasattr(self._driver.service, 'process'):
                        pid = self._driver.service.process.pid
                        os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
    
    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取悠悠有品平台商品价格（使用 Selenium 获取市场在售数据）
        
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

            # 直接使用 Selenium 从网页请求中捕获API响应（不走 requests）
            self.logger.info(f"开始获取市场在售商品: {item_name} (templateId={template_id})")

            # 收集多页数据（最多8页）
            all_items = []
            pages_fetched = 0
            for page in range(1, 9):
                self.logger.info(f"获取第 {page} 页数据... (Selenium)")

                api_data = self._fetch_market_data_selenium(template_id, page, 20)
                if not api_data:
                    self.logger.warning(f"第 {page} 页获取失败")
                    break

                pages_fetched += 1
                
                code = api_data.get('Code') or api_data.get('code')
                msg = api_data.get('Msg') or api_data.get('msg', '')
                
                if code != 0 and msg not in ['success', '成功']:
                    self.logger.warning(f"第 {page} 页返回错误: Code={code}, Msg={msg}")
                    break
                
                # 解析数据
                data = api_data.get('Data') or api_data.get('data', [])
                if isinstance(data, list):
                    items = data
                else:
                    items = data.get('commodityList') or data.get('CommodityList', [])
                
                if len(items) == 0:
                    self.logger.info(f"第 {page} 页没有数据，停止翻页")
                    break
                
                all_items.extend(items)
                
                # 输出本页磨损范围和每个商品的详细信息
                wears_in_page = []
                prices_in_page = []
                for item in items:
                    abrade_str = item.get('abrade') or item.get('Abrade', '0')
                    price_str = item.get('price') or item.get('Price', '0')
                    commodity_name = item.get('commodityName') or item.get('CommodityName', '')
                    try:
                        wear = float(abrade_str)
                        price = float(price_str)
                        wears_in_page.append(wear)
                        prices_in_page.append(price)
                        # 打印每个商品的详细信息
                        self.logger.debug(f"  [{page}页] {commodity_name[:20]}... 价格:{price} 磨损:{wear:.4f}")
                    except:
                        pass
                
                if wears_in_page:
                    min_wear = min(wears_in_page)
                    max_wear = max(wears_in_page)
                    min_price = min(prices_in_page)
                    max_price = max(prices_in_page)
                    self.logger.info(f"第 {page} 页: {len(items)}个商品 | 磨损: {min_wear:.4f}~{max_wear:.4f} | 价格: ¥{min_price:.2f}~¥{max_price:.2f}")
                else:
                    self.logger.info(f"第 {page} 页获取到 {len(items)} 个商品")
                
                # 找到了足够的数据就停止（至少6页）
                if page >= 6 and len(all_items) >= 60:
                    break

            self.logger.info(f"共获取 {len(all_items)} 个在售商品（{pages_fetched} 页）")
            
            # 过滤和排序
            expected = self._normalize_name(item_name)
            filtered = []
            
            for item in all_items:
                commodity_name = item.get('commodityName') or item.get('CommodityName', '')
                actual = self._normalize_name(commodity_name)
                
                if expected != actual:
                    continue
                
                # 解析价格和磨损
                price_str = item.get('price') or item.get('Price', '0')
                abrade_str = item.get('abrade') or item.get('Abrade', '0')
                
                try:
                    price = float(price_str)
                    wear = float(abrade_str)
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
