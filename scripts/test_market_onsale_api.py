"""测试真正的市场在售商品API"""
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
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'App-Version': '5.26.0',
    'AppVersion': '5.26.0',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Origin': 'https://www.youpin898.com',
    'Referer': 'https://www.youpin898.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'appType': '1',
    'authorization': token if token else '',
    'platform': 'pc',
    'secret-v': 'h5_v1',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}

url = 'https://api.youpin898.com/api/homepage/pc/goods/market/queryOnSaleCommodityList'

# 使用正确的参数格式（从浏览器获取）
payload = {
    'templateId': '109545',  # 字符串
    'listSortType': 1,
    'sortType': 0,
    'pageIndex': 1,
    'pageSize': 20
}

print(f"{'='*70}")
print("测试市场在售商品API")
print(f"{'='*70}\n")

response = requests.post(url, json=payload, headers=headers, timeout=10)

print(f"状态码: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"响应code: {data.get('code')}")
    print(f"响应msg: {data.get('msg')}")
    
    if data.get('code') == 0:
        result = data.get('data', {})
        print(f"\ndata字段: {list(result.keys())}")
        
        # 尝试不同可能的列表字段名
        items = (result.get('list') or result.get('items') or 
                result.get('itemsInfos') or result.get('commodityList') or [])
        
        total = result.get('totalCount', 0)
        
        print(f"总记录数: {total}")
        print(f"当前页: {len(items)} 条")
        
        if items:
            print(f"\n第一条记录的字段:")
            first = items[0]
            for key, value in first.items():
                print(f"  {key}: {value}")
            
            print(f"\n筛选宙斯商品并按价格排序:")
            zeus_items = []
            for item in items:
                item_name = item.get('commodityName') or item.get('name') or ''
                if '宙斯' in item_name or 'Zeus' in item_name.lower():
                    price = item.get('price') or item.get('unitPrice') or 0
                    wear = item.get('paintwear') or item.get('abrasion') or item.get('assetWear') or 0
                    zeus_items.append((price, wear, item_name))
            
            zeus_items.sort()  # 按价格排序
            
            print(f"找到 {len(zeus_items)} 个宙斯商品:")
            for price, wear, name in zeus_items[:10]:
                print(f"  价格: {price}, 磨损: {wear:.6f}, 名称: {name}")
            
            # 检查价格是否有变化
            prices = [p for p, _, _ in zeus_items]
            unique_prices = set(prices)
            print(f"\n价格种类数: {len(unique_prices)}")
            print(f"价格范围: {min(prices) if prices else 0} - {max(prices) if prices else 0}")
            
            if len(unique_prices) > 1:
                print("✓ 价格有变化，确认为市场在售接口！")
            else:
                print("⚠️  价格都相同")
                
        else:
            print("\n没有返回商品数据")
            print(f"result 内容: {result}")
    else:
        print(f"\n接口返回错误")
        print(f"完整响应: {data}")
else:
    print(f"HTTP错误: {response.text[:500]}")

# 拉取多页测试
print(f"\n{'='*70}")
print("拉取3页数据统计价格分布")
print(f"{'='*70}\n")

all_zeus = []
for page in range(1, 4):
    payload['pageIndex'] = page
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('code') == 0:
            result = data.get('data', {})
            items = (result.get('list') or result.get('items') or 
                    result.get('itemsInfos') or result.get('commodityList') or [])
            
            for item in items:
                item_name = item.get('commodityName') or item.get('name') or ''
                if '宙斯' in item_name or 'Zeus' in item_name.lower():
                    price = item.get('price') or item.get('unitPrice') or 0
                    wear = item.get('paintwear') or item.get('abrasion') or item.get('assetWear') or 0
                    all_zeus.append((price, wear))

all_zeus.sort()
print(f"3页共找到 {len(all_zeus)} 个宙斯商品")

# 按磨损区间筛选
wear_min, wear_max = 0.15, 0.2605
filtered = [(p, w) for p, w in all_zeus if wear_min <= w <= wear_max]
filtered.sort()

print(f"磨损区间 {wear_min}-{wear_max} 内: {len(filtered)} 个")

if filtered:
    from collections import Counter
    price_dist = Counter([p for p, _ in filtered])
    print(f"\n价格分布:")
    for price, count in sorted(price_dist.items())[:20]:
        print(f"  {price}元: {count}个")
    
    print(f"\n前20个按价格排序:")
    for price, wear in filtered[:20]:
        print(f"  价格: {price}, 磨损: {wear:.6f}")
