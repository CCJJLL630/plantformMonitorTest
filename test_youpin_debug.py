"""调试Youpin监控器，捕获详细异常"""
import logging
import sys
import traceback
from utils import Config
from monitors import YoupinMonitor

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_youpin_debug.log', encoding='utf-8')
    ]
)

logger = logging.getLogger('TestYoupin')

def main():
    try:
        logger.info("=" * 60)
        logger.info("开始测试Youpin监控器")
        logger.info("=" * 60)
        
        # 加载配置
        config = Config("config.json")
        youpin_config = config.get_platform_config('youpin')
        
        # 创建监控器
        monitor = YoupinMonitor(youpin_config)
        logger.info("监控器创建成功")
        
        # 获取价格
        item_config = {
            'name': '宙斯x27电击枪 | 鼾龙传说 (久经沙场)',
            'youpin_template_id': 109545
        }
        
        logger.info(f"开始获取价格: {item_config['name']}")
        logger.info(f"Template ID: {item_config['youpin_template_id']}")
        
        results = monitor.get_item_price(
            item_name=item_config['name'],
            wear_min=0.15,
            wear_max=0.38,
            item_config=item_config
        )
        
        logger.info(f"获取结果: {len(results)} 个商品")
        for item in results[:5]:
            logger.info(f"  价格: {item['price']}, 磨损: {item['wear']:.6f}")
        
        logger.info("=" * 60)
        logger.info("测试完成")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"测试失败: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        # 确保清理资源
        if 'monitor' in locals():
            try:
                if hasattr(monitor, '_driver') and monitor._driver:
                    logger.info("清理WebDriver")
                    monitor._driver.quit()
            except Exception as e:
                logger.warning(f"清理失败: {e}")

if __name__ == "__main__":
    main()
