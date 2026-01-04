"""调试ECOSteam数据获取"""
import logging
import re
from monitors.ecosteam import EcosteamMonitor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 创建监控器实例
config = {
    'base_url': 'https://www.ecosteam.cn',
    'platform': 'ecosteam'
}
monitor = EcosteamMonitor(config)

# 测试商品配置
item_config = {
    'eco_goods_url': 'https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html'
}

# 直接调用Selenium方法
print("开始获取数据...")
all_rows = monitor._fetch_sell_list_with_selenium(item_config['eco_goods_url'], max_pages=6)

print(f"\n共获取 {len(all_rows)} 个商品")
print(f"\n前10个商品:")
for i, row in enumerate(all_rows[:10], 1):
    print(f"  {i}. 磨损: {row['wear']:.6f}, 价格: {row['price']}")

print(f"\n中间10个商品 (25-35):")
for i, row in enumerate(all_rows[25:35], 26):
    print(f"  {i}. 磨损: {row['wear']:.6f}, 价格: {row['price']}")

print(f"\n最后10个商品:")
for i, row in enumerate(all_rows[-10:], len(all_rows)-9):
    print(f"  {i}. 磨损: {row['wear']:.6f}, 价格: {row['price']}")

# 统计唯一的磨损值
unique_wears = set(row['wear'] for row in all_rows)
print(f"\n唯一磨损值数量: {len(unique_wears)}")
print(f"磨损值范围: {min(unique_wears):.6f} - {max(unique_wears):.6f}")
