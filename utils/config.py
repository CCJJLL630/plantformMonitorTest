"""配置管理模块"""
import json
import os
from typing import Dict, Any


class Config:
    """配置管理类"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化配置
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"配置文件不存在: {self.config_path}\n"
                "请复制 config.json.example 为 config.json 并修改配置"
            )
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键，支持点号分隔的嵌套键，如 'notification.email.enabled'
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_monitor_interval(self) -> int:
        """获取监控间隔（秒）"""
        return self.get('monitor_interval', 300)
    
    def get_enabled_platforms(self) -> list:
        """获取启用的平台列表"""
        platforms = self.get('platforms', {})
        return [name for name, config in platforms.items() if config.get('enabled', False)]
    
    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """获取指定平台的配置"""
        return self.get(f'platforms.{platform}', {})
    
    def get_items(self) -> list:
        """获取监控商品列表"""
        return self.get('items', [])
    
    def get_notification_config(self) -> Dict[str, Any]:
        """获取通知配置"""
        return self.get('notification', {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self.get('database', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get('logging', {})
