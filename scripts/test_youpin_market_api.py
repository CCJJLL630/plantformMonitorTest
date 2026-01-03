"""测试悠悠有品市场在售商品API（非库存）"""
import json
import re
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

# 从配置读取
youpin_config = config.get("platforms", {}).get("youpin", {})
cookie = youpin_config.get("Cookie") or youpin_config.get("cookie", "")
template_id = config["items"][0].get("youpin_template_id") or config["items"][0].get("youpin_goods_id", 109545)

# 提取token
token_match = re.search(r'(?:^|;\s*)uu_token=([^;]+)', cookie)
token = token_match.group(1) if token_match else None

print(f"Testing templateId: {template_id}")
print(f"Token: {token[:20]}..." if token else "No token")

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'Referer': 'https://www.youpin898.com/market/goods-list',
    'Origin': 'https://www.youpin898.com',
    'Content-Type': 'application/json;charset=UTF-8',
    'Accept': 'application/json, text/plain, */*',
    'Cookie': cookie
})

if token:
    session.headers['uu-token'] = token
    session.headers['Authorization'] = f'Bearer {token}'

# 测试多个可能的市场在售商品接口
test_endpoints = [
    # 市场商品列表相关接口
    '/api/youpin/pc/goods/list',
    '/api/youpin/pc/market/goods/list',
    '/api/youpin/market/goods/list',
    '/api/market/goods/list',
    '/api/goods/list',
    
    # 在售商品相关接口
    '/api/youpin/pc/sell/list',
    '/api/sell/goods/list',
    
    # 模板商品相关接口
    '/api/youpin/pc/template/goods/list',
    '/api/template/goods',
    
    # 通用商品查询
    '/api/youpin/pc/goods/query',
    '/api/goods/query',
]

payload = {
    'templateId': template_id,
    'gameId': 730,
    'listType': 10,
    'pageIndex': 1,
    'pageSize': 20,
    'sortType': 0  # 可能需要排序类型
}

base_url = 'https://api.youpin898.com'

print(f"\n{'='*60}")
print("测试市场在售商品接口（寻找正确的非库存API）")
print(f"{'='*60}\n")

successful_endpoints = []

for endpoint in test_endpoints:
    url = base_url + endpoint
    try:
        print(f"测试: {endpoint}")
        response = session.post(url, json=payload, timeout=10)
        
        print(f"  状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                code = data.get('code')
                msg = data.get('msg', '')
                
                print(f"  响应code: {code}, msg: {msg}")
                
                if code == 0:
                    # 成功响应，检查数据结构
                    result_data = data.get('data') or data.get('result') or data.get('Data')
                    if result_data:
                        items = None
                        if isinstance(result_data, list):
                            items = result_data
                        elif isinstance(result_data, dict):
                            items = (result_data.get('list') or result_data.get('items') or 
                                   result_data.get('records') or result_data.get('data'))
                        
                        if items and isinstance(items, list) and len(items) > 0:
                            print(f"  ✓ 找到 {len(items)} 个商品")
                            first_item = items[0]
                            print(f"  第一个商品字段: {list(first_item.keys())[:15]}")
                            
                            # 检查是否有价格和磨损字段
                            price_field = (first_item.get('price') or first_item.get('Price') or 
                                         first_item.get('salePrice') or first_item.get('unitPrice'))
                            wear_field = (first_item.get('paintwear') or first_item.get('abrasion') or 
                                        first_item.get('wear') or first_item.get('assetWear'))
                            
                            print(f"  价格示例: {price_field}")
                            print(f"  磨损示例: {wear_field}")
                            
                            successful_endpoints.append({
                                'endpoint': endpoint,
                                'count': len(items),
                                'sample': first_item
                            })
                        else:
                            print(f"  数据结构: {list(result_data.keys()) if isinstance(result_data, dict) else 'list'}")
                else:
                    print(f"  接口返回错误码")
            except json.JSONDecodeError:
                print(f"  响应不是JSON: {response.text[:100]}")
        else:
            print(f"  HTTP错误")
            
    except requests.exceptions.Timeout:
        print(f"  超时")
    except Exception as e:
        print(f"  异常: {e}")
    
    print()

print(f"\n{'='*60}")
print(f"成功的接口 ({len(successful_endpoints)} 个):")
print(f"{'='*60}\n")

for ep_info in successful_endpoints:
    print(f"端点: {ep_info['endpoint']}")
    print(f"商品数: {ep_info['count']}")
    print(f"示例: {ep_info['sample']}")
    print()
