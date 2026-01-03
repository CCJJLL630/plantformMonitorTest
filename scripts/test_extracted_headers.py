"""测试使用提取的 headers 直接调用 API"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json

# 使用上面提取到的 headers
headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'App-Version': '5.26.0',
    'AppVersion': '5.26.0',
    'Content-Type': 'application/json',
    'Referer': 'https://www.youpin898.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'appType': '1',
    'b3': '7e66298eb8b54833ab896c1d53811505-cbf7c80f86a5821a-1',
    'deviceId': '6c909288-6425-4538-a1a9-6e8b517a226c',
    'deviceUk': '5HoFQoNfpyVQbJ8jAk65siFraOmDZbIIvApMgZY9cahOytnOTlqC9KBjHDRehKf1N',
    'platform': 'pc',
    'secret-v': 'h5_v1',
    'traceparent': '00-7e66298eb8b54833ab896c1d53811505-cbf7c80f86a5821a-01',
    'uk': '5HoFeFDjtwytoyGnY78y3RrMNHOqQTo1mLgdrMKADlKUDtRawmS6uZoPnzGgV3t1O',
}

url = 'https://api.youpin898.com/api/homepage/pc/goods/market/queryOnSaleCommodityList'

payload = {
    "templateId": "109545",
    "listSortType": 1,
    "sortType": 0,
    "pageIndex": 2,
    "pageSize": 20
}

print("Testing page 2...")
response = requests.post(url, json=payload, headers=headers, timeout=10)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
else:
    print(f"Error: {response.text[:500]}")
