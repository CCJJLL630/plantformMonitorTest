"""汇总所有平台的监控结果并输出到文件

这个脚本会在每轮监控完成后，把所有平台的结果汇总到一个文件中
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


def save_monitoring_results(all_prices: List[Dict[str, Any]], item_name: str, wear_min: float, wear_max: float) -> None:
    """保存监控结果到汇总文件
    
    Args:
        all_prices: 所有平台的价格列表
        item_name: 商品名称
        wear_min: 最小磨损
        wear_max: 最大磨损
    """
    if not all_prices:
        return
    
    # 按平台分组
    by_platform: Dict[str, List[Dict[str, Any]]] = {}
    for price in all_prices:
        platform = price.get('platform', 'unknown')
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(price)
    
    # 对每个平台的结果按价格排序
    for platform in by_platform:
        by_platform[platform].sort(key=lambda x: (x['price'], x['wear']))
    
    # 构造输出数据
    output = {
        'item_name': item_name,
        'wear_range': {'min': wear_min, 'max': wear_max},
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            platform: {
                'count': len(items),
                'min_price': min(item['price'] for item in items) if items else None,
                'max_price': max(item['price'] for item in items) if items else None,
            }
            for platform, items in by_platform.items()
        },
        'details': by_platform
    }
    
    # 保存到文件
    output_dir = Path('data')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'latest_monitoring_result.json'
    
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    
    # 同时保存一份带时间戳的备份
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = output_dir / f'monitoring_result_{timestamp}.json'
    backup_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    
    print(f"监控结果已保存到: {output_path}")
    print(f"备份文件: {backup_path}")
