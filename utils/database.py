
"""数据库模块 - 用于价格历史记录存储"""
import sqlite3
import os
from typing import List, Dict, Any
from datetime import datetime


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_database()
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
    
    def _init_database(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建价格历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                item_name TEXT NOT NULL,
                price REAL NOT NULL,
                wear REAL NOT NULL,
                url TEXT,
                timestamp INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_platform_item 
            ON price_history(platform, item_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON price_history(timestamp)
        ''')
        
        conn.commit()
        conn.close()
    
    def insert_price(self, price_info: Dict[str, Any]):
        """
        插入价格记录
        
        Args:
            price_info: 价格信息字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO price_history (platform, item_name, price, wear, url, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            price_info.get('platform'),
            price_info.get('item_name'),
            price_info.get('price'),
            price_info.get('wear'),
            price_info.get('url'),
            price_info.get('timestamp')
        ))
        
        conn.commit()
        conn.close()
    
    def insert_prices_batch(self, price_list: List[Dict[str, Any]]):
        """
        批量插入价格记录
        
        Args:
            price_list: 价格信息列表
        """
        if not price_list:
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        data = [
            (
                p.get('platform'),
                p.get('item_name'),
                p.get('price'),
                p.get('wear'),
                p.get('url'),
                p.get('timestamp')
            )
            for p in price_list
        ]
        
        cursor.executemany('''
            INSERT INTO price_history (platform, item_name, price, wear, url, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', data)
        
        conn.commit()
        conn.close()
    
    def get_latest_prices(self, platform: str, item_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最新的价格记录
        
        Args:
            platform: 平台名称
            item_name: 商品名称
            limit: 返回记录数量
            
        Returns:
            价格记录列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM price_history
            WHERE platform = ? AND item_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (platform, item_name, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_price_statistics(self, platform: str, item_name: str, days: int = 7) -> Dict[str, Any]:
        """
        获取价格统计信息
        
        Args:
            platform: 平台名称
            item_name: 商品名称
            days: 统计天数
            
        Returns:
            统计信息字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 计算时间戳范围
        import time
        start_timestamp = int(time.time()) - (days * 24 * 3600)
        
        cursor.execute('''
            SELECT 
                COUNT(*) as count,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price
            FROM price_history
            WHERE platform = ? AND item_name = ? AND timestamp >= ?
        ''', (platform, item_name, start_timestamp))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            'count': row[0],
            'min_price': row[1],
            'max_price': row[2],
            'avg_price': row[3]
        }
