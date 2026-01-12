"""网易BUFF平台监控"""
from typing import Dict, List, Any, Optional
import atexit
import time
import os
import json
from .base import PlatformMonitor


class BuffMonitor(PlatformMonitor):
    """网易BUFF平台监控器"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        atexit.register(self._close_playwright)

    def _close_playwright(self) -> None:
        for obj in (self._page, self._context, self._browser):
            try:
                if obj is not None:
                    obj.close()
            except Exception:
                pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def _load_cookies_from_file(self) -> None:
        """尝试从 data/buff_cookies.json 加载 Cookie。

        注意：仅当文件包含登录态关键字段时才使用文件 Cookie 覆盖，以免把有效登录 Cookie 覆盖成不完整 Cookie。
        """
        cookie_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data',
            'buff_cookies.json',
        )
        if not os.path.exists(cookie_file):
            return

        try:
            with open(cookie_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cookies_list = data.get('cookies', [])
            if not isinstance(cookies_list, list) or not cookies_list:
                return

            key_names = {c.get('name') for c in cookies_list if isinstance(c, dict)}
            has_auth_cookie = any(n in key_names for n in ('session', 'remember_me', 'qr_code_verify_ticket'))
            if not has_auth_cookie:
                self.logger.warning(
                    'BUFF cookie 文件缺少 session/remember_me 等登录态字段，忽略该文件（继续使用 config.json 的 Cookie）。'
                )
                return

            for cookie in cookies_list:
                if not isinstance(cookie, dict):
                    continue
                name = cookie.get('name')
                value = cookie.get('value')
                domain = cookie.get('domain')
                if not name or value is None:
                    continue
                if domain:
                    self.session.cookies.set(name, value, domain=domain)
                else:
                    self.session.cookies.set(name, value)

            self.logger.info(f"已从文件加载 BUFF Cookie: {cookie_file}")
        except Exception as e:
            self.logger.error(f"加载 BUFF Cookie 文件失败: {e}")

    def _use_playwright(self) -> bool:
        return bool(self.config.get('use_playwright', False))

    def _ensure_playwright(self) -> None:
        if self._page is not None:
            return

        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            raise RuntimeError(
                "Playwright 未安装或不可用。请先执行: python3 -m pip install playwright && python3 -m playwright install chromium"
            ) from e

        self._pw = sync_playwright().start()

        headless = bool(self.config.get('playwright_headless', True))

        # 可选：为 BUFF 配置浏览器代理（对机房 IP 风控非常关键）
        proxy_cfg = self.config.get('playwright_proxy') or self.config.get('proxy') or self.config.get('proxies')
        launch_kwargs: Dict[str, Any] = {'headless': headless}
        if isinstance(proxy_cfg, str) and proxy_cfg.strip():
            launch_kwargs['proxy'] = {'server': proxy_cfg.strip()}
        elif isinstance(proxy_cfg, dict) and proxy_cfg.get('server'):
            launch_kwargs['proxy'] = {
                'server': proxy_cfg.get('server'),
                'username': proxy_cfg.get('username'),
                'password': proxy_cfg.get('password'),
            }

        self._browser = self._pw.chromium.launch(**launch_kwargs)

        # 继承 session 的 UA（尽量保持一致）
        user_agent = self.session.headers.get('User-Agent')
        extra_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.7,en;q=0.6',
        }
        self._context = self._browser.new_context(user_agent=user_agent, extra_http_headers=extra_headers)
        self._page = self._context.new_page()

        # 将当前 requests cookie jar 同步到浏览器上下文（cookie-file 已在 get_item_price 里加载）
        cookies = []
        for c in self.session.cookies:
            try:
                name = getattr(c, 'name', None)
                value = getattr(c, 'value', None)
                domain = getattr(c, 'domain', None) or 'buff.163.com'
                path = getattr(c, 'path', None) or '/'
                if not name or value is None:
                    continue
                cookies.append({'name': name, 'value': str(value), 'domain': domain, 'path': path})
            except Exception:
                continue

        if cookies:
            try:
                self._context.add_cookies(cookies)
            except Exception:
                # cookie 格式不完全合法时不影响主流程
                pass

    def _pw_preheat(self, goods_id: str) -> None:
        self._ensure_playwright()
        url = f"{self.base_url}/goods/{goods_id}"
        try:
            self._page.goto(url, wait_until='domcontentloaded', timeout=20000)
            # 给前端 JS 一点时间设置风控相关 cookie
            self._page.wait_for_timeout(800)
        except Exception:
            return

    def _pw_get_json(self, url: str, params: Dict[str, Any], referer: Optional[str] = None) -> Dict[str, Any]:
        """使用浏览器上下文发起请求，携带浏览器侧 cookie/指纹。"""
        self._ensure_playwright()
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.base_url,
        }
        if referer:
            headers['Referer'] = referer

        # 同步 csrf_token 到头（BUFF 的 API 常要求此头，否则 403）
        try:
            ck = self._context.cookies(self.base_url)
            csrf = None
            for c in ck or []:
                if c.get('name') == 'csrf_token':
                    csrf = c.get('value')
                    break
            if csrf:
                headers['X-CSRF-TOKEN'] = csrf
                headers['X-CSRFToken'] = csrf
                headers['csrf_token'] = csrf
        except Exception:
            pass

        # 403 时 BUFF 可能下发新 cookie；预热+重试一次
        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                resp = self._context.request.get(url, params=params, headers=headers, timeout=20000)
                if resp.status == 403 and attempt == 0:
                    self.logger.warning('BUFF Playwright 请求 403，预热页面后重试一次')
                    if referer:
                        # goods 页面预热通常能刷新 cookie
                        try:
                            self._page.goto(referer, wait_until='domcontentloaded', timeout=20000)
                            self._page.wait_for_timeout(800)
                        except Exception:
                            pass
                    continue
                if resp.status != 200:
                    raise RuntimeError(f"BUFF Playwright status={resp.status}")
                return resp.json()
            except Exception as e:
                last_exc = e

        if last_exc:
            raise last_exc
        raise RuntimeError('BUFF Playwright 请求失败')

    def _ensure_csrf_headers(self) -> None:
        """将 csrf_token Cookie 同步到常见 CSRF 头。"""
        csrf = self.session.cookies.get('csrf_token')
        if not csrf:
            return
        self.session.headers['X-CSRF-TOKEN'] = csrf
        self.session.headers['X-CSRFToken'] = csrf
        self.session.headers['csrf_token'] = csrf

    def _preheat_goods_page(self, goods_id: str) -> None:
        """预热商品页以刷新 session/csrf 等 Cookie。"""
        try:
            self.session.get(f"{self.base_url}/goods/{goods_id}", timeout=10)
        except Exception:
            return

    def _get_json_with_csrf_retry(self, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """GET JSON：遇到 403 时刷新 csrf 并重试一次。"""
        last_err: Optional[Exception] = None
        for attempt in range(2):
            try:
                self._ensure_csrf_headers()
                resp = self.session.get(url, params=params, timeout=12)
                if resp.status_code == 403 and attempt == 0:
                    # 403 往往伴随 Set-Cookie 新 csrf/session，刷新头后再试一次
                    self.logger.warning("BUFF 返回 403，刷新 CSRF 后重试一次")
                    continue
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_err = e
        if last_err:
            raise last_err
        raise RuntimeError('BUFF 请求失败')
    
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
            # 尝试加载文件 Cookie（只有完整登录态才会覆盖）
            self._load_cookies_from_file()

            # 如果启用 Playwright：尽量用浏览器上下文请求（更容易通过风控）
            if self._use_playwright():
                # goods_id 建议在配置里提供，否则搜索接口也可能被风控
                item_id = None
                if item_config is not None:
                    item_id = item_config.get('buff_goods_id')
                    if item_id:
                        self.logger.info(f"(Playwright) 使用配置的 BUFF goods_id: {item_id}")

                if not item_id:
                    # 尝试用 Playwright 搜索
                    search_url = f"{self.base_url}/api/market/search"
                    self._pw_preheat('')
                    payload = self._pw_get_json(search_url, params={'game': 'csgo', 'page_num': 1, 'search': item_name}, referer=f"{self.base_url}/")
                    if payload.get('code') != 'OK' or not payload.get('data', {}).get('items'):
                        self.logger.warning(f"(Playwright) 未找到商品: {item_name}")
                        return results
                    item_id = payload['data']['items'][0]['id']

                goods_url = f"{self.base_url}/goods/{item_id}"
                self._pw_preheat(str(item_id))

                sell_url = f"{self.base_url}/api/market/goods/sell_order"
                max_pages = 10
                page_size = 50
                max_results = 100

                for page_num in range(1, max_pages + 1):
                    params = {
                        'game': 'csgo',
                        'goods_id': item_id,
                        'page_num': page_num,
                        'page_size': page_size,
                        'sort_by': 'price.asc',
                    }

                    self.logger.info(f"(Playwright) 获取在售列表: {item_id} (page={page_num})")
                    data = self._pw_get_json(sell_url, params=params, referer=goods_url)
                    if data.get('code') != 'OK':
                        self.logger.error(f"(Playwright) 获取在售列表失败: {data.get('error')}")
                        return results

                    items = data.get('data', {}).get('items', [])
                    if not items:
                        break

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
                                results.append({
                                    'platform': 'buff',
                                    'item_name': item_name,
                                    'price': price,
                                    'wear': wear_value,
                                    'url': goods_url,
                                    'timestamp': int(time.time()),
                                })
                        except Exception:
                            continue

                    if len(results) >= max_results:
                        break

                    time.sleep(0.6)

                results.sort(key=lambda x: x['price'])
                results = results[:20]
                return results

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
            # BUFF 风控经常校验 Referer/Origin/CSRF
            self.session.headers.setdefault('Referer', f"{self.base_url}/goods/{item_id}")
            self.session.headers.setdefault('Origin', self.base_url)
            self.session.headers.setdefault('X-Requested-With', 'XMLHttpRequest')
            self.session.headers.setdefault('Accept', 'application/json, text/plain, */*')
            self.session.headers.setdefault('Accept-Language', 'zh-CN,zh;q=0.9,en-US;q=0.7,en;q=0.6')

            # 预热一次商品页，刷新 session/csrf
            self._preheat_goods_page(str(item_id))

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
                data = self._get_json_with_csrf_retry(sell_url, params=params)

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
