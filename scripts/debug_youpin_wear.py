"""调试悠悠有品磨损字段提取"""
import json
from pathlib import Path

# 读取之前保存的市场数据
data_file = Path(__file__).parent.parent / 'data' / 'youpin_market_sample.json'

if not data_file.exists():
    print("数据文件不存在，请先运行 test_selenium_youpin.py")
    exit(1)

with open(data_file, 'r', encoding='utf-8') as f:
    api_data = json.load(f)

data = api_data.get('Data', [])
print(f"总共 {len(data)} 个商品\n")

# 检查所有宙斯商品
zeus_items = []
for item in data:
    name = item.get('commodityName', '')
    if '宙斯' in name or 'Zeus' in name.lower():
        # 检查所有可能的磨损字段
        abrade = item.get('abrade')
        paintwear = item.get('paintwear')
        assetWear = item.get('assetWear')
        wear = item.get('wear')
        
        # 打印原始值
        print(f"商品: {name}")
        print(f"  price: {item.get('price')}")
        print(f"  abrade: {abrade} (type: {type(abrade)})")
        print(f"  paintwear: {paintwear}")
        print(f"  assetWear: {assetWear}")
        print(f"  wear: {wear}")
        
        # 尝试转换
        if abrade:
            try:
                wear_float = float(abrade)
                print(f"  转换后磨损: {wear_float:.6f}")
                zeus_items.append((float(item.get('price', 0)), wear_float, name))
            except:
                print(f"  转换失败！")
        print()

print(f"\n{'='*70}")
print(f"找到 {len(zeus_items)} 个宙斯商品")
print(f"{'='*70}\n")

# 按磨损区间统计
wear_ranges = {
    '0.00-0.07': [],
    '0.07-0.15': [],
    '0.15-0.2605': [],  # 目标区间
    '0.2605-0.45': [],
    '0.45+': [],
}

for price, wear, name in zeus_items:
    if wear <= 0.07:
        wear_ranges['0.00-0.07'].append((price, wear, name))
    elif wear <= 0.15:
        wear_ranges['0.07-0.15'].append((price, wear, name))
    elif wear <= 0.2605:
        wear_ranges['0.15-0.2605'].append((price, wear, name))
    elif wear <= 0.45:
        wear_ranges['0.2605-0.45'].append((price, wear, name))
    else:
        wear_ranges['0.45+'].append((price, wear, name))

print("按磨损区间统计:")
for range_name, items in wear_ranges.items():
    print(f"\n{range_name}: {len(items)} 个")
    for price, wear, name in sorted(items)[:5]:
        print(f"  价格: {price}, 磨损: {wear:.6f}")

print(f"\n{'='*70}")
target_items = wear_ranges['0.15-0.2605']
if target_items:
    print(f"目标区间 (0.15-0.2605) 找到 {len(target_items)} 个商品！")
    print("\n按价格排序:")
    for price, wear, name in sorted(target_items)[:10]:
        print(f"  {price}元 - 磨损{wear:.6f}")
else:
    print("目标区间 (0.15-0.2605) 没有找到商品")
    print("\n所有磨损值范围:")
    if zeus_items:
        all_wears = [w for _, w, _ in zeus_items]
        print(f"  最小: {min(all_wears):.6f}")
        print(f"  最大: {max(all_wears):.6f}")
