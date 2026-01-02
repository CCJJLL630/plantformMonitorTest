"""平台监控基类"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import requests
import time
import logging


class PlatformMonitor(ABC):
    """平台监控抽象基类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化监控器
        
        Args:
            config: 平台配置
        """
        self.config = config
        self.base_url = config.get('base_url', '')
        self.session = requests.Session()
        # 基础 UA，尽量模拟浏览器
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # 支持在平台配置中自定义额外 Header / Cookie
        extra_headers = config.get('headers')
        if isinstance(extra_headers, dict):
            self.session.headers.update(extra_headers)
        # 兼容配置中使用 "cookie" 或 "Cookie" 写法
        cookie = config.get('cookie') or config.get('Cookie')
        if cookie:
            self.session.headers['Cookie'] = cookie
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def get_item_price(
        self,
        item_name: str,
        wear_min: float,
        wear_max: float,
        item_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取商品价格
        
        Args:
            item_name: 商品名称
            wear_min: 最小磨损
            wear_max: 最大磨损
            item_config: 整个商品配置（可选，用于平台自定义字段，如 goods_id 等）
            
        Returns:
            价格信息列表，每个元素包含：
            - price: 价格
            - wear: 磨损值
            - url: 商品链接
            - timestamp: 时间戳
        """
        pass
    
    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """
        发送HTTP请求
        
        Args:
            url: 请求URL
            method: 请求方法
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        try:
            response = self.session.request(method, url, timeout=10, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            self.logger.error(f"请求失败: {url}, 错误: {e}")
            raise
    
    def _sleep(self, seconds: float = 1.0):
        """延迟，避免请求过快"""
        time.sleep(seconds)
