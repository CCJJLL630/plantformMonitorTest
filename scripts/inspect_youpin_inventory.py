"""详细检查 inventory/list 返回的数据结构"""
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

# 解码 JWT token 查看用户ID
if token:
    import base64
    try:
        payload_part = token.split('.')[1]
        # 添加padding
        padding = 4 - len(payload_part) % 4
        if padding != 4:
            payload_part += '=' * padding
        decoded = base64.b64decode(payload_part)
        jwt_data = json.loads(decoded)
        my_user_id = jwt_data.get('Id') or jwt_data.get('nameid')
        print(f"当前登录用户ID: {my_user_id}")
    except Exception as e:
        my_user_id = None
        print(f"无法解析token: {e}")
else:
    my_user_id = None

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
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
}

url = 'https://api.youpin898.com/api/youpin/pc/inventory/list'

payload = {
    'templateId': 109545,
    'gameId': 730,
    'listType': 10,
    'pageIndex': 1,
    'pageSize': 20
}

print(f"\n{'='*70}")
print("详细检查返回数据")
print(f"{'='*70}\n")

response = requests.post(url, json=payload, headers=headers, timeout=10)
data = response.json()

print(f"响应code: {data.get('code')}")
print(f"响应msg: {data.get('msg')}")

if data.get('code') == 0:
    result = data.get('data', {})
    print(f"\ndata 字段: {list(result.keys())}")
    
    items = result.get('itemsInfos') or result.get('list') or []
    total = result.get('totalCount', 0)
    
    print(f"总记录数: {total}")
    print(f"当前页记录数: {len(items)}")
    
    if items:
        print(f"\n第一条记录的所有字段:")
        first_item = items[0]
        for key, value in first_item.items():
            print(f"  {key}: {value}")
        
        print(f"\n检查是否为用户库存:")
        
        # 关键判断字段
        seller_id = first_item.get('userId') or first_item.get('sellerId') or first_item.get('ownerId')
        is_my_item = seller_id == my_user_id if (seller_id and my_user_id) else None
        
        print(f"  商品拥有者/卖家ID: {seller_id}")
        print(f"  是否是我的商品: {is_my_item}")
        print(f"  在售状态: {first_item.get('isOnSale')}")
        print(f"  状态: {first_item.get('status')}")
        
        # 统计所有商品的卖家ID
        print(f"\n所有商品的卖家ID分布:")
        seller_ids = {}
        for item in items:
            sid = item.get('userId') or item.get('sellerId') or item.get('ownerId')
            seller_ids[sid] = seller_ids.get(sid, 0) + 1
        
        for sid, count in list(seller_ids.items())[:10]:
            is_me = " (我的)" if sid == my_user_id else ""
            print(f"  {sid}{is_me}: {count}个")
        
        if len(seller_ids) == 1 and my_user_id in seller_ids:
            print(f"\n❌ 确认：这是用户库存接口，所有商品都是当前用户的！")
        elif len(seller_ids) > 5:
            print(f"\n✓ 这可能是市场接口，有 {len(seller_ids)} 个不同卖家")
        else:
            print(f"\n⚠️  不确定：有 {len(seller_ids)} 个不同卖家")

else:
    print(f"接口返回错误")
