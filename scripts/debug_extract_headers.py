"""调试脚本：查看从 Selenium 提取的 cookies 和 headers"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitors.youpin import YoupinMonitor
import json

# 创建监控器
config = {
    'items': [{
        'name': '宙斯x27电击枪 | 鼾龙传说 (久经沙场)',
        'youpin_template_id': '109545',
        'wear_range': [0.15, 0.2605]
    }]
}

monitor = YoupinMonitor(config)

# 初始化 Selenium 并访问页面
monitor._init_selenium()

if monitor._driver:
    print("=" * 80)
    print("访问页面...")
    url = 'https://www.youpin898.com/market/goods-list?templateId=109545&gameId=730&listType=10'
    monitor._driver.get(url)
    
    import time
    time.sleep(5)  # 等待页面加载
    
    # 提取 cookies
    print("=" * 80)
    print("Cookies:")
    cookies = monitor._extract_cookies_from_selenium()
    for name, value in cookies.items():
        print(f"  {name}: {value[:50]}...")
    
    # 提取 headers
    print("=" * 80)
    print("Headers from performance logs:")
    headers = monitor._extract_headers_from_selenium()
    for name, value in headers.items():
        if isinstance(value, str) and len(value) > 100:
            print(f"  {name}: {value[:100]}...")
        else:
            print(f"  {name}: {value}")
    
    # 清理
    monitor.__del__()
    
    print("=" * 80)
else:
    print("Failed to initialize Selenium")
