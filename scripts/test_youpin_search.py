"""测试YOUPIN 搜索接口"""
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
    'Referer': 'https://www.youpin898.com/market/search',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json;charset=UTF-8',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# 尝试搜索接口
search_url = 'https://api.youpin898.com/api/homepage/es/template/GetCsGoPagedList'

payload = {
    'gameId': '730',
    'listSortType': '1',  # 1=价格升序
    'listType': '10',
    'pageIndex': 1,
    'pageSize': 20,
    'templateName': '宙斯x27电击枪 | 鼾龙传说'
}

print(f"尝试搜索接口: {search_url}")
response = requests.post(search_url, json=payload, headers=headers)
print(f"状态码: {response.status_code}")

try:
    data = response.json()
    print(f"code: {data.get('code')}, msg: {data.get('msg')}")
    
    items = (data.get('data') or {}).get('dataList') or []
    print(f"返回 {len(items)} 条数据\n")
    
    if items:
        print("前10个商品:")
        for i, item in enumerate(items[:10], 1):
            name = item.get('commodityName', '')
            price = item.get('price', 0)
            print(f"  {i}. {name[:40]}, 价格={price}")
except:
    print("响应解析失败，打印原始内容:")
    print(response.text[:500])
