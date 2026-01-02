"""测试YOUPIN不同listType"""
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

headers = {
    'Cookie': cookie,
    'uu-token': token,
    'UU-Token': token,
    'token': token,
    'Authorization': f'Bearer {token}' if token else '',
    'Origin': 'https://www.youpin898.com',
    'Referer': 'https://www.youpin898.com/market/goods-list',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json;charset=UTF-8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

url = 'https://api.youpin898.com/api/youpin/pc/inventory/list'

# 尝试listType=10（默认）和其他可能值
for list_type in [10, 20, 1, 2]:
    payload = {
        'templateId': 109545,
        'gameId': 730,
        'listType': list_type,
        'pageIndex': 1,
        'pageSize': 20
    }
    
    print(f"\n=== listType={list_type} ===")
    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    
    if data.get('code') != 0:
        print(f"失败: {data.get('msg')}")
        continue
    
    items = (data.get('data') or {}).get('itemsInfos') or []
    print(f"返回 {len(items)} 条数据")
    
    # 统计宙斯商品价格
    prices = {}
    for item in items:
        name = item.get('name', '')
        if '宙斯' in name:
            price = item.get('price', 0)
            wear = float(item.get('abrade', 0))
            if wear > 1:
                wear /= 100.0
            
            if price not in prices:
                prices[price] = []
            prices[price].append(wear)
    
    print(f"宙斯商品价格分布:")
    for price in sorted(prices.keys()):
        wears = prices[price]
        print(f"  {price}元: {len(wears)}个, 磨损 {min(wears):.3f}-{max(wears):.3f}")
