"""测试悠悠有品手机端API"""
import json
import re
import requests
from pathlib import Path

config_path = Path(__file__).parent.parent / 'config.json'
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

cookie = config['platforms']['youpin']['Cookie']
m = re.search(r'(?:^|;\s*)uu_token=([^;]+)', cookie)
token = m.group(1) if m else None

# 手机端请求头
headers = {
    'Cookie': cookie,
    'uu-token': token,
    'UU-Token': token,
    'token': token,
    'Authorization': f'Bearer {token}' if token else '',
    'Origin': 'https://m.youpin898.com',
    'Referer': 'https://m.youpin898.com/',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json;charset=UTF-8',
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

print("=== 测试悠悠有品手机端API ===\n")

# 尝试不同的端点
endpoints = [
    'https://api.youpin898.com/api/youpin/mobile/inventory/list',
    'https://api.youpin898.com/api/h5/inventory/list',
    'https://api.youpin898.com/api/mobile/goods/list',
    'https://api.youpin898.com/api/youpin/pc/inventory/list',  # PC端点用手机UA
]

payload = {
    'templateId': 109545,
    'gameId': 730,
    'listType': 10,
    'pageIndex': 1,
    'pageSize': 50
}

successful_url = None

for url in endpoints:
    print(f"尝试: {url}")
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"  状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            code = data.get('code')
            msg = data.get('msg', '')
            
            print(f"  code: {code}, msg: {msg}")
            
            if code == 0:
                # 尝试多种数据结构
                items = (data.get('data') or {}).get('itemsInfos')
                if not items:
                    items = (data.get('data') or {}).get('items')
                if not items:
                    items = (data.get('data') or {}).get('list')
                
                if items:
                    print(f"  ✓ 成功！返回 {len(items)} 条数据")
                    successful_url = url
                    break
    except Exception as e:
        print(f"  异常: {str(e)[:100]}")
    
    print()

if successful_url:
    print(f"\n=== 使用成功的端点拉取多页数据 ===")
    print(f"端点: {successful_url}\n")
    
    all_zeus_items = []
    
    for page in range(1, 11):  # 拉取10页
        payload['pageIndex'] = page
        try:
            response = requests.post(successful_url, json=payload, headers=headers, timeout=10)
            data = response.json()
            
            if data.get('code') != 0:
                break
            
            items = (data.get('data') or {}).get('itemsInfos') or []
            if not items:
                break
            
            print(f"第{page}页: {len(items)}条")
            
            for item in items:
                name = item.get('name', '')
                if '宙斯' in name and '鼾龙' in name:
                    all_zeus_items.append(item)
            
            import time
            time.sleep(0.3)
        except:
            break
    
    print(f"\n总共收集到 {len(all_zeus_items)} 个宙斯商品")
    
    # 统计所有价格（不限磨损）
    all_prices = {}
    wear_range_prices = {}
    
    for item in all_zeus_items:
        price = item.get('price', 0)
        wear = float(item.get('abrade', 0))
        if wear > 1:
            wear /= 100.0
        
        if price not in all_prices:
            all_prices[price] = []
        all_prices[price].append(wear)
        
        # 目标磨损区间
        if 0.15 <= wear <= 0.2605:
            if price not in wear_range_prices:
                wear_range_prices[price] = []
            wear_range_prices[price].append(wear)
    
    print(f"\n所有宙斯商品价格分布（不限磨损）:")
    for price in sorted(all_prices.keys()):
        wears = all_prices[price]
        print(f"  {price}元: {len(wears)}个, 磨损 {min(wears):.3f}-{max(wears):.3f}")
    
    print(f"\n目标磨损区间(0.15-0.2605)价格分布:")
    if wear_range_prices:
        for price in sorted(wear_range_prices.keys()):
            wears = wear_range_prices[price]
            print(f"  {price}元: {len(wears)}个, 磨损 {min(wears):.3f}-{max(wears):.3f}")
    else:
        print("  无商品")
