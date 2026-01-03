"""悠悠有品平台监控"""
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse, parse_qs
import re
import time
import json
import logging
import requests
from .base import PlatformMonitor


class YoupinMonitor(PlatformMonitor):
    """悠悠有品平台监控器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._driver = None
        self._driver_initialized = False
        self.logger = logging.getLogger('YoupinMonitor')

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
            
            self._driver = webdriver.Chrome(options=chrome_options)
            self._driver_initialized = True
            
            # 访问主页并注入 Cookie
            cookie_str = self.session.headers.get('Cookie', '')
            if cookie_str:
                self._driver.get('https://www.youpin898.com')
                time.sleep(1)
                
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
    
    def _fetch_market_data_with_requests(self, template_id: int, page_index: int, cookies: Dict[str, str], request_headers: Dict[str, str] = None) -> Optional[Dict]:
        """使用 requests 调用 API（带 Selenium 提取的 Cookie 和 Headers）"""
        try:
            url = 'https://api.youpin898.com/api/homepage/pc/goods/market/queryOnSaleCommodityList'
            
            # 如果提供了从 Selenium 提取的 headers，就使用它们
            if request_headers:
                headers = request_headers.copy()
            else:
                # 否则使用默认 headers
                headers = {
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Content-Type': 'application/json',
                    'Origin': 'https://www.youpin898.com',
                    'Referer': f'https://www.youpin898.com/market/goods-list?templateId={template_id}',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
                }
            
            payload = {
                "templateId": str(template_id),
                "listSortType": 1,  # 按价格排序
                "sortType": 0,      # 升序
                "pageIndex": page_index,
                "pageSize": 20
            }
            
            response = requests.post(url, json=payload, headers=headers, cookies=cookies, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"API 请求失败 (page={page_index}): status={response.status_code}")
                return None
                
        except Exception as e:
            self.logger.warning(f"requests 调用 API 失败 (page={page_index}): {e}")
            return None
    
    def _fetch_market_data_selenium(self, template_id: int, page_index: int = 1, page_size: int = 20) -> Optional[Dict]:
        """使用 Selenium 获取市场在售商品数据（通过性能日志捕获API响应）"""
        if not self._driver:
            self._init_selenium()
        
        if not self._driver:
            self.logger.error("Selenium 不可用")
            return None
        
        try:
            # 构建URL
            url = f'https://www.youpin898.com/market/goods-list?templateId={template_id}&gameId=730&listType=10'
            
            if page_index == 1:
                # 第一页：直接访问并捕获
                self._driver.get(url)
                self.logger.info(f"已加载页面: {url}")
                
                # 等待商品列表加载完成（通过等待特定元素）
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    
                    # 等待商品列表加载
                    WebDriverWait(self._driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='goodsList'], .goods-list, [class*='commodity']"))
                    )
                    self.logger.info("商品列表已加载")
                    time.sleep(3)  # 额外等待确保API响应被捕获
                except Exception as e:
                    self.logger.warning(f"等待商品列表超时: {e}")
                    time.sleep(8)  # 备用等待时间
                
                self.logger.info("等待完成，准备提取性能日志")
            else:
                # 第2页及以后：等待分页控件出现并点击
                current_url = self._driver.current_url
                if 'youpin898.com/market/goods-list' not in current_url:
                    self._driver.get(url)
                    time.sleep(8)
                
                try:
                    from selenium.webdriver.common.by import By
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    
                    # 等待分页控件出现（最多15秒）
                    self.logger.info(f"等待分页控件出现...")
                    pagination = WebDriverWait(self._driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-pagination, [class*='pagination']"))
                    )
                    self.logger.info("分页控件已找到")
                    
                    # 从当前页点击到目标页
                    clicks_needed = page_index - 1
                    
                    for i in range(clicks_needed):
                        time.sleep(2)
                        
                        # 使用JavaScript点击（更可靠）
                        click_success = self._driver.execute_script("""
                            const nextBtn = document.querySelector('.ant-pagination-next:not(.ant-pagination-disabled)');
                            if (nextBtn) {
                                nextBtn.click();
                                return true;
                            }
                            
                            const nextBtn2 = document.querySelector('li.ant-pagination-next');
                            if (nextBtn2 && !nextBtn2.classList.contains('ant-pagination-disabled')) {
                                nextBtn2.click();
                                return true;
                            }
                            
                            return false;
                        """)
                        
                        if not click_success:
                            self.logger.warning(f"第 {i+1} 次点击下一页失败（按钮未找到或已禁用）")
                            return None
                        
                        self.logger.info(f"已点击下一页按钮 ({i+1}/{clicks_needed})")
                        time.sleep(4)  # 等待新数据加载
                    
                    self.logger.info(f"成功翻到第 {page_index} 页")
                    time.sleep(3)  # 额外等待确保数据加载完成
                    
                except Exception as e:
                    self.logger.warning(f"翻页操作失败 (page={page_index}): {e}")
                    return None

            
            # 从性能日志中提取 API 响应
            # 清除之前的性能日志，只获取最新的
            time.sleep(1)  # 确保日志已生成
            logs = self._driver.get_log('performance')
            self.logger.info(f"获取到 {len(logs)} 条性能日志")
            
            # 第一页检查所有日志，后续页只看最近的100条
            if page_index == 1:
                recent_logs = logs
            else:
                recent_logs = logs[-100:] if len(logs) > 100 else logs
            
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
                                    self.logger.info(f"成功获取第 {page_index} 页数据")
                                    return api_data
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
                self._driver.quit()
            except:
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
            
            self._ensure_token_headers(None)
            
            # 使用 Selenium 获取多页市场数据
            self.logger.info(f"开始获取市场在售商品: {item_name} (templateId={template_id})")
            
            # 收集多页数据（最多5页）
            all_items = []
            for page in range(1, 6):
                self.logger.info(f"获取第 {page} 页数据...")
                api_data = self._fetch_market_data_selenium(template_id, page, 20)
                
                if not api_data:
                    self.logger.warning(f"第 {page} 页获取失败")
                    break
                
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
                
                # 输出本页磨损范围
                wears_in_page = []
                for item in items:
                    abrade_str = item.get('abrade') or item.get('Abrade', '0')
                    try:
                        wear = float(abrade_str)
                        wears_in_page.append(wear)
                    except:
                        pass
                
                if wears_in_page:
                    min_wear = min(wears_in_page)
                    max_wear = max(wears_in_page)
                    self.logger.info(f"第 {page} 页获取到 {len(items)} 个商品，磨损范围: {min_wear:.4f} - {max_wear:.4f}")
                else:
                    self.logger.info(f"第 {page} 页获取到 {len(items)} 个商品")
                
                # 找到了足够的数据就停止（至少4页）
                if page >= 4 and len(all_items) >= 40:
                    break
            
            self.logger.info(f"共获取 {len(all_items)} 个在售商品（{min(page, 10)} 页）")
            
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
