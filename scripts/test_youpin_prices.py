"""测试YOUPIN API返回的价格数据"""
import json
import re
import requests
from pathlib import Path

def test_youpin_prices():
    # 从config.json读取最新的Cookie
    config_path = Path(__file__).parent.parent / 'config.json'
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    cookie = config['platforms']['youpin']['Cookie']
    
    print(f"Cookie长度: {len(cookie)}")
    print(f"Cookie前80字符: {cookie[:80]}...")
    
    m = re.search(r'(?:^|;\s*)uu_token=([^;]+)', cookie)
    token = m.group(1) if m else None
    
    if token:
        print(f"提取到token长度: {len(token)}")
    else:
        print("警告: 未能从Cookie中提取到uu_token")
    
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br'
    }
    
    payload = {
        'templateId': 109545,
        'gameId': 730,
        'listType': 10,
        'pageIndex': 1,
        'pageSize': 20  # 改小一点，方便翻更多页看价格分布
    }
    
    url = 'https://api.youpin898.com/api/youpin/pc/inventory/list'
    
    all_zeus_items = []
    
    # 拉取前5页，尝试不同排序
    for page in range(1, 6):
        payload['pageIndex'] = page
        # 不指定sortType，看看是否有默认排序
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if data.get('code') != 0:
            print(f"第{page}页失败: {data.get('msg')}")
            break
        
        items = (data.get('data') or {}).get('itemsInfos') or []
        print(f"第{page}页返回 {len(items)} 条数据")
        
        if not items:
            break
        
        for item in items:
            name = item.get('name', '')
            if '宙斯' in name and '鼾龙' in name:
                all_zeus_items.append(item)
        
        import time
        time.sleep(0.3)
    
    print(f"响应状态: 200")
    print(f"拉取了 {len(all_zeus_items)} 个宙斯商品")
    
    items = all_zeus_items
    
    # 统计磨损区间 0.15-0.2605 的商品价格分布
    target_items = []
    for item in items:
        abrade = float(item.get('abrade', 0))
        if abrade > 1:
            abrade = abrade / 100.0
        
        if 0.15 <= abrade <= 0.2605:
            name = item.get('name', '')
            if '宙斯' in name and '鼾龙' in name:
                price = float(item.get('price', 0))
                target_items.append({
                    'price': price,
                    'abrade': abrade,
                    'name': name
                })
    
    print(f"符合条件的商品数量: {len(target_items)}")
    print(f"\n价格分布:")
    price_counts = {}
    for item in target_items:
        price = item['price']
        price_counts[price] = price_counts.get(price, 0) + 1
    
    for price in sorted(price_counts.keys()):
        print(f"  {price}: {price_counts[price]}个")
    
    print(f"\n所有符合磨损区间的商品详情（共{len(target_items)}个）:")
    for i, item in enumerate(target_items, 1):
        print(f"  {i}. 价格={item['price']}, 磨损={item['abrade']:.6f}, 名称={item['name'][:30]}")
    
    # 输出第一个商品的所有price相关字段
    if target_items:
        print(f"\n=== 第一个商品的所有字段（用于诊断） ===")
        first_item_raw = None
        for item in items:
            abrade = float(item.get('abrade', 0))
            if abrade > 1:
                abrade = abrade / 100.0
            if 0.15 <= abrade <= 0.2605:
                name = item.get('name', '')
                if '宙斯' in name and '鼾龙' in name:
                    first_item_raw = item
                    break
        
        if first_item_raw:
            print("所有包含'price'的字段:")
            for key, value in first_item_raw.items():
                if 'price' in key.lower() or 'amount' in key.lower():
                    print(f"  {key}: {value}")
    
    # 同时输出不在磨损区间的商品价格分布
    print(f"\n=== 所有商品（不限磨损）各字段价格分布 ===")
    
    # 检查所有宙斯商品的price和其他价格字段
    zeus_items = [item for item in items if '宙斯' in item.get('name', '') and '鼾龙' in item.get('name', '')]
    
    if zeus_items:
        print(f"\n前10个宙斯商品的价格字段对比:")
        for i, item in enumerate(zeus_items[:10], 1):
            abrade = float(item.get('abrade', 0))
            if abrade > 1:
                abrade = abrade / 100.0
            price = item.get('price', 0)
            asset_price = item.get('assetBuyPrice', 0)
            print(f"  {i}. 磨损={abrade:.4f}, price={price}, assetBuyPrice={asset_price}")

if __name__ == '__main__':
    test_youpin_prices()
