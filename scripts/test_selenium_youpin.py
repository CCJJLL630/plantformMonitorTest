"""使用 Selenium 获取悠悠有品市场数据"""
import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

config_path = Path(__file__).parent.parent / 'config.json'
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

cookie_str = config['platforms']['youpin']['Cookie']
template_id = 109545

# 解析 Cookie 字符串
cookies = []
for item in cookie_str.split(';'):
    item = item.strip()
    if '=' in item:
        name, value = item.split('=', 1)
        cookies.append({'name': name.strip(), 'value': value.strip()})

print(f"templateId: {template_id}")
print(f"解析到 {len(cookies)} 个 Cookie")

# 配置 Chrome
chrome_options = Options()
chrome_options.add_argument('--disable-blink-features=AutomationControlled')
chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
chrome_options.add_experimental_option('useAutomationExtension', False)
# 启用性能日志以捕获网络请求
chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

print("\n启动浏览器...")
driver = webdriver.Chrome(options=chrome_options)

try:
    # 访问主页以设置域名
    print("访问悠悠有品主页...")
    driver.get('https://www.youpin898.com')
    time.sleep(2)
    
    # 添加 Cookie
    print("注入 Cookie...")
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
        except Exception as e:
            print(f"  跳过 Cookie {cookie['name']}: {e}")
    
    # 访问市场列表页
    url = f'https://www.youpin898.com/market/goods-list?templateId={template_id}&gameId=730&listType=10'
    print(f"\n访问市场页面: {url}")
    driver.get(url)
    
    # 等待页面加载
    print("等待商品列表加载...")
    time.sleep(8)  # 增加等待时间
    
    # 从性能日志中提取 API 响应
    print("\n分析网络请求日志...")
    logs = driver.get_log('performance')
    
    api_data = None
    for entry in logs:
        try:
            log_entry = json.loads(entry['message'])
            message = log_entry.get('message', {})
            method = message.get('method', '')
            
            # 查找 Network.responseReceived 事件
            if method == 'Network.responseReceived':
                response = message.get('params', {}).get('response', {})
                url_resp = response.get('url', '')
                
                if 'queryOnSaleCommodityList' in url_resp:
                    request_id = message.get('params', {}).get('requestId')
                    print(f"找到目标 API 请求: requestId={request_id}")
                    
                    # 尝试获取响应体
                    try:
                        response_body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': request_id})
                        body_text = response_body.get('body', '')
                        if body_text:
                            api_data = json.loads(body_text)
                            print(f"✓ 成功获取 API 响应数据！")
                            break
                        else:
                            print(f"  响应体为空")
                    except Exception as e:
                        print(f"  获取响应体失败: {type(e).__name__}: {str(e)[:100]}")
        except Exception as e:
            continue
    
    if api_data:
        code = api_data.get('Code') or api_data.get('code')
        msg = api_data.get('Msg') or api_data.get('msg')
        print(f"响应Code: {code}")
        print(f"响应Msg: {msg}")
        print(f"响应keys: {list(api_data.keys())}")
        
        if code == 0 or msg == 'success' or msg == '成功':
            result = api_data.get('Data') or api_data.get('data', {})
            total = api_data.get('TotalCount') or api_data.get('totalCount', 0)
            
            # Data 可能直接是列表或包含列表的字典
            if isinstance(result, list):
                items = result
            else:
                items = result.get('commodityList') or result.get('CommodityList', [])
                if not total:
                    total = result.get('totalCount') or result.get('TotalCount', 0)
            
            print(f"\n总记录数: {total}")
            print(f"当前页: {len(items)} 条")
            
            if items:
                print(f"\n第一条记录示例:")
                first = items[0]
                print(f"  字段: {list(first.keys())[:15]}")
                
                # 统计宙斯商品
                zeus_items = []
                for item in items:
                    name = item.get('commodityName', '')
                    if '宙斯' in name or 'Zeus' in name.lower():
                        price = item.get('price', 0)
                        wear = item.get('paintwear', 0)
                        zeus_items.append((price, wear, name))
                
                zeus_items.sort()
                
                print(f"\n找到 {len(zeus_items)} 个宙斯商品:")
                for price, wear, name in zeus_items[:10]:
                    print(f"  价格: {price}, 磨损: {wear:.6f}")
                
                # 保存完整数据
                output_file = Path(__file__).parent.parent / 'data' / 'youpin_market_sample.json'
                output_file.parent.mkdir(exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(api_data, f, ensure_ascii=False, indent=2)
                print(f"\n完整数据已保存到: {output_file}")
        else:
            print("API 返回错误")
    else:
        print("❌ 未能从日志中找到 API 响应")
        print("\n尝试直接从页面解析商品...")
        
        # 保存页面源码用于调试
        page_source = driver.page_source
        debug_file = Path(__file__).parent.parent / 'data' / 'youpin_page_debug.html'
        debug_file.parent.mkdir(exist_ok=True)
        debug_file.write_text(page_source, encoding='utf-8')
        print(f"页面源码已保存到: {debug_file}")
        
finally:
    print("\n关闭浏览器...")
    driver.quit()
    print("完成")
