"""
调试脚本：查看Selenium捕获的所有网络请求URL
"""
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 初始化 Selenium
options = Options()
options.add_argument('--headless=new')
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-blink-features=AutomationControlled')
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(30)

try:
    # 访问页面
    url = 'https://www.youpin898.com/market/goods-list?templateId=109545&gameId=730&listType=10'
    print(f"访问页面: {url}")
    driver.get(url)
    
    print("等待8秒...")
    time.sleep(8)
    
    # 获取性能日志
    logs = driver.get_log('performance')
    print(f"\n总共获取到 {len(logs)} 条性能日志")
    
    # 收集所有API请求URL
    api_urls = set()
    
    for entry in logs:
        try:
            log_entry = json.loads(entry['message'])
            message = log_entry.get('message', {})
            method = message.get('method', '')
            
            if method == 'Network.responseReceived':
                response = message.get('params', {}).get('response', {})
                url_resp = response.get('url', '')
                
                # 只收集API相关的URL
                if 'api.youpin898.com' in url_resp or 'youpin898' in url_resp:
                    api_urls.add(url_resp)
        except:
            continue
    
    print(f"\n找到 {len(api_urls)} 个API URL:")
    for api_url in sorted(api_urls):
        print(f"  {api_url}")
    
    # 搜索包含特定关键词的URL
    keywords = ['market', 'commodity', 'list', 'sale', 'goods', 'query']
    print("\n包含关键词的URL:")
    for keyword in keywords:
        matching = [u for u in api_urls if keyword.lower() in u.lower()]
        if matching:
            print(f"\n  关键词 '{keyword}':")
            for u in matching:
                print(f"    {u}")
    
finally:
    driver.quit()
