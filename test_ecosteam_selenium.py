"""测试ECOSteam的Selenium分页功能"""
import logging
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
    'platform': 'ecosteam',
    'Cookie': 'clientId=ed5b401a24c0bd103860e32dfe17b22b; game=730; userLanguage=zh-CN; Hm_lvt_5992affa40e9ccff6f8f8af8d6b6cb13=1767358792,1767441656; HMACCOUNT=9DA40EDD97115244; refreshToken=24a05212-e6c9-4480-8602-6c73c658ac3e; cdn_sec_tc=dde5cb2017674512359553707e43c36c75f0f1d5f51c34e46d8c4be556; acw_tc=0a065eac17674512359688886e53520388ae3c08a4a7c044b518af8f555959; loginToken=20c9ce66-87c0-474c-b2f5-5877182e3377; Hm_lpvt_5992affa40e9ccff6f8f8af8d6b6cb13=1767451240'
}
monitor = EcosteamMonitor(config)

# 测试商品配置
item_config = {
    'eco_goods_url': 'https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html'
}

# 测试获取价格
print("开始测试ECOSteam Selenium分页...")
results = monitor.get_item_price(
    item_name='宙斯x27电击枪 | 鼾龙传说 (久经沙场)',
    wear_min=0.15,
    wear_max=0.2605,
    item_config=item_config
)

print(f"\n测试完成！共获取到 {len(results)} 个匹配商品")
for result in results:
    print(f"  - 价格: {result['price']}, 磨损: {result['wear']:.6f}")
