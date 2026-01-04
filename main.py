"""
平台价格监控程序
用于监控网易BUFF、悠悠有品、ECOSteam等平台指定商品的价格
"""
import logging
import time
import signal
from typing import List, Dict, Any
from logging.handlers import RotatingFileHandler
import os

from monitors import BuffMonitor, YoupinMonitor, EcosteamMonitor
from utils import Config, Database, Notifier
from utils.result_saver import save_monitoring_results


# 全局标志：是否应该退出
_should_exit = False

def signal_handler(signum, frame):
    """信号处理器：只在真正需要退出时设置标志"""
    global _should_exit
    if _should_exit:
        # 第二次Ctrl+C，强制退出
        raise KeyboardInterrupt("强制退出")
    else:
        # 第一次信号，设置标志
        _should_exit = True
        logging.getLogger('PriceMonitor').info("收到退出信号，将在当前任务完成后退出...")


class PriceMonitor:
    """价格监控主类"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化监控器
        
        Args:
            config_path: 配置文件路径
        """
        # 加载配置
        self.config = Config(config_path)
        
        # 设置日志
        self._setup_logging()
        
        # 初始化数据库
        db_config = self.config.get_database_config()
        self.db = Database(db_config.get('path', 'data/price_history.db'))
        
        # 初始化通知器
        notification_config = self.config.get_notification_config()
        self.notifier = Notifier(notification_config)
        
        # 初始化平台监控器
        self.monitors = self._init_monitors()
        
        self.logger.info("价格监控程序初始化完成")
    
    def _setup_logging(self):
        """设置日志"""
        log_config = self.config.get_logging_config()
        log_file = log_config.get('file', 'logs/monitor.log')
        log_level = log_config.get('level', 'INFO')
        max_bytes = log_config.get('max_bytes', 10485760)  # 10MB
        backup_count = log_config.get('backup_count', 5)
        
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 配置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 文件处理器
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, log_level))
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _init_monitors(self) -> Dict[str, Any]:
        """
        初始化平台监控器
        
        Returns:
            监控器字典
        """
        monitors = {}
        enabled_platforms = self.config.get_enabled_platforms()
        
        for platform in enabled_platforms:
            platform_config = self.config.get_platform_config(platform)
            
            if platform == 'buff':
                monitors['buff'] = BuffMonitor(platform_config)
            elif platform == 'youpin':
                monitors['youpin'] = YoupinMonitor(platform_config)
            elif platform == 'ecosteam':
                monitors['ecosteam'] = EcosteamMonitor(platform_config)
            
            self.logger.info(f"已启用平台: {platform}")
        
        return monitors
    
    def monitor_item(self, item_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        监控单个商品
        
        Args:
            item_config: 商品配置
            
        Returns:
            价格信息列表
        """
        item_name = item_config.get('name')
        wear_range = item_config.get('wear_range', {})
        wear_min = wear_range.get('min', 0)
        wear_max = wear_range.get('max', 1)
        target_price = item_config.get('target_price', 0)
        platforms = item_config.get('platforms', [])
        
        self.logger.info(f"开始监控商品: {item_name}")
        
        all_prices = []
        low_price_items = []
        
        # 遍历配置的平台
        for platform in platforms:
            if platform not in self.monitors:
                self.logger.warning(f"平台未启用: {platform}")
                continue
            
            try:
                #  获取价格信息
                monitor = self.monitors[platform]
                
                # 对于可能被信号中断的操作，进行重试（Windows后台运行时可能会收到误触发的信号）
                max_retries = 10  # 增加重试次数
                for retry in range(max_retries):
                    try:
                        prices = monitor.get_item_price(item_name, wear_min, wear_max, item_config=item_config)
                        break  # 成功，跳出重试循环
                    except KeyboardInterrupt:
                        if retry < max_retries - 1:
                            self.logger.warning(f"{platform} 监控被意外中断，重试中... ({retry+1}/{max_retries})")
                            time.sleep(1)  # 缩短重试间隔
                        else:
                            self.logger.error(f"{platform} 监控多次被中断，跳过")
                            prices = []
                            break
                
                if prices:
                    self.logger.info(f"在 {platform} 找到 {len(prices)} 个匹配商品")
                    all_prices.extend(prices)
                    
                    # 检查是否有低于目标价格的商品
                    for price_info in prices:
                        if price_info['price'] <= target_price:
                            low_price_items.append(price_info)
                else:
                    self.logger.info(f"在 {platform} 未找到匹配商品")
                
                # 延迟，避免请求过快
                time.sleep(2)
            
            except Exception as e:
                self.logger.error(f"监控平台 {platform} 时出错: {e}")
        
        # 保存价格记录到数据库
        if all_prices:
            self.db.insert_prices_batch(all_prices)
            self.logger.info(f"已保存 {len(all_prices)} 条价格记录")
            
            # 保存汇总结果到文件
            try:
                save_monitoring_results(all_prices, item_name, wear_min, wear_max)
            except Exception as e:
                self.logger.error(f"保存汇总结果失败: {e}")
        
        # 发送低价通知
        if low_price_items:
            self._send_price_alert(item_name, target_price, low_price_items)
        
        return all_prices
    
    def _send_price_alert(self, item_name: str, target_price: float, price_list: List[Dict[str, Any]]):
        """
        发送价格预警通知
        
        Args:
            item_name: 商品名称
            target_price: 目标价格
            price_list: 价格列表
        """
        title = f"【价格预警】{item_name}"
        content = f"发现低于目标价格 ¥{target_price:.2f} 的商品，共 {len(price_list)} 个"
        
        self.logger.info(f"发送价格预警: {title}")
        self.notifier.send(title, content, price_list)
    
    def run(self):
        """运行监控"""
        global _should_exit
        
        # 设置信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)  # Windows特有
        
        self.logger.info("=" * 50)
        self.logger.info("价格监控程序启动")
        self.logger.info("=" * 50)
        
        items = self.config.get_items()
        interval = self.config.get_monitor_interval()
        
        if not items:
            self.logger.error("未配置任何监控商品，程序退出")
            return
        
        self.logger.info(f"监控商品数量: {len(items)}")
        self.logger.info(f"监控间隔: {interval} 秒")
        
        try:
            while not _should_exit:
                self.logger.info("-" * 50)
                self.logger.info(f"开始新一轮监控 - {time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.logger.info("-" * 50)
                
                # 监控每个商品
                for item_config in items:
                    if _should_exit:
                        break
                    try:
                        self.monitor_item(item_config)
                    except Exception as e:
                        self.logger.error(f"监控商品时出错: {e}", exc_info=True)
                
                if _should_exit:
                    break
                
                self.logger.info(f"本轮监控完成，等待 {interval} 秒...")
                # 分段sleep，以便及时响应退出信号
                for _ in range(interval):
                    if _should_exit:
                        break
                    time.sleep(1)
        
        except KeyboardInterrupt:
            self.logger.info("接收到强制停止信号，程序退出")
        except Exception as e:
            self.logger.error(f"程序运行异常: {e}", exc_info=True)
        finally:
            self.logger.info("程序正常退出")


def main():
    """主函数"""
    # 创建监控器
    monitor = PriceMonitor("config.json")
    
    # 运行监控
    monitor.run()


if __name__ == "__main__":
    main()
