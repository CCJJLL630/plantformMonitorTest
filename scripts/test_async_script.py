"""测试 Selenium execute_async_script"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import json

# 初始化
chrome_options = Options()
# chrome_options.add_argument('--headless')  # 先不用无头模式，方便调试
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

driver = webdriver.Chrome(options=chrome_options)
driver.set_script_timeout(30)  # 设置异步脚本超时时间

print("访问页面...")
driver.get('https://www.youpin898.com/market/goods-list?templateId=109545&gameId=730&listType=10')
time.sleep(5)

print("执行异步脚本...")
try:
    script = """
    const callback = arguments[arguments.length - 1];
    
    fetch('https://api.youpin898.com/api/homepage/pc/goods/market/queryOnSaleCommodityList', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            templateId: '109545',
            listSortType: 1,
            sortType: 0,
            pageIndex: 2,
            pageSize: 20
        })
    })
    .then(response => response.json())
    .then(data => callback(data))
    .catch(error => callback({error: error.toString()}));
    """
    
    result = driver.execute_async_script(script)
    print("结果：")
    print(json.dumps(result, indent=2, ensure_ascii=False)[:500])
    
except Exception as e:
    print(f"错误: {e}")

driver.quit()
