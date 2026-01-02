# 平台价格监控系统

一个用于监控网易BUFF、悠悠有品、ECOSteam等平台指定磨损区间商品价格的Python工具。

## 功能特点

- 🔍 **多平台支持**：支持网易BUFF、悠悠有品、ECOSteam等主流交易平台
- 📊 **精确监控**：可指定商品名称和磨损区间进行精准监控
- 💰 **价格预警**：当价格低于设定阈值时自动发送通知
- 📱 **多种通知方式**：支持邮件、钉钉、企业微信等多种通知方式
- 💾 **数据存储**：自动保存价格历史记录，支持数据分析
- ⚙️ **灵活配置**：通过JSON配置文件轻松管理监控项目

## 项目结构

```
PlantformMonitor/
├── main.py                  # 主程序入口
├── config.json.example      # 配置文件模板
├── requirements.txt         # Python依赖包
├── README.md               # 项目说明文档
├── monitors/               # 平台监控模块
│   ├── __init__.py
│   ├── base.py            # 监控器基类
│   ├── buff.py            # 网易BUFF监控
│   ├── youpin.py          # 悠悠有品监控
│   └── ecosteam.py        # ECOSteam监控
├── utils/                  # 工具模块
│   ├── __init__.py
│   ├── config.py          # 配置管理
│   ├── database.py        # 数据库操作
│   └── notification.py    # 通知模块
├── data/                   # 数据存储目录
│   └── price_history.db   # 价格历史数据库（自动创建）
└── logs/                   # 日志目录
    └── monitor.log        # 运行日志（自动创建）
```

## 快速开始

### 1. 环境要求

- Python 3.7+
- pip

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置设置

复制配置模板并编辑：

```bash
copy config.json.example config.json
```

编辑 `config.json` 文件，配置监控项目：

```json
{
    "monitor_interval": 300,
    "platforms": {
        "buff": {
            "enabled": true,
            "base_url": "https://buff.163.com"
        },
        "youpin": {
            "enabled": true,
            "base_url": "https://www.youpin898.com"
        },
        "ecosteam": {
            "enabled": true,
            "base_url": "https://www.ecosteam.cn"
        }
    },
    "items": [
        {
            "name": "AK-47 | 红线 (久经沙场)",
            "wear_range": {
                "min": 0.15,
                "max": 0.38
            },
            "target_price": 100.0,
            "platforms": ["buff", "youpin", "ecosteam"]
        }
    ]
}
```

### 4. 运行程序

```bash
python main.py
```

## 配置说明

### 基础配置

- `monitor_interval`: 监控间隔时间（秒）
- `platforms`: 平台配置
  - `enabled`: 是否启用该平台
  - `base_url`: 平台的基础URL

### 监控商品配置

每个监控商品包含以下字段：

- `name`: 商品名称（需要与平台上的名称一致）
- `wear_range`: 磨损区间
  - `min`: 最小磨损值
  - `max`: 最大磨损值
- `target_price`: 目标价格（低于此价格将触发通知）
- `platforms`: 要监控的平台列表

### 通知配置

#### 邮件通知

```json
"notification": {
    "email": {
        "enabled": true,
        "smtp_server": "smtp.qq.com",
        "smtp_port": 587,
        "sender": "your-email@qq.com",
        "password": "your-smtp-password",
        "receivers": ["receiver@example.com"]
    }
}
```

#### 钉钉通知

```json
"dingtalk": {
    "enabled": true,
    "webhook": "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
    "secret": "YOUR_SECRET"
}
```

#### 企业微信通知

```json
"wechat": {
    "enabled": true,
    "webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
}
```

## 使用示例

### 监控多个商品

在 `config.json` 的 `items` 数组中添加多个配置：

```json
"items": [
    {
        "name": "AK-47 | 红线 (久经沙场)",
        "wear_range": {"min": 0.15, "max": 0.38},
        "target_price": 100.0,
        "platforms": ["buff", "youpin"]
    },
    {
        "name": "AWP | 二西莫夫 (久经沙场)",
        "wear_range": {"min": 0.15, "max": 0.38},
        "target_price": 200.0,
        "platforms": ["buff", "ecosteam"]
    }
]
```

### 查看日志

程序运行日志保存在 `logs/monitor.log` 文件中：

```bash
# Windows
type logs\monitor.log

# Linux/Mac
cat logs/monitor.log
```

## 注意事项

⚠️ **重要提示**：

1. **API更新**：各平台的API可能会更新，需要根据实际情况调整监控模块代码
2. **请求频率**：避免请求过于频繁，建议设置合理的监控间隔（建议不低于300秒）
3. **数据准确性**：价格数据来源于各平台，请以实际交易页面为准
4. **Cookie认证**：部分平台可能需要登录才能访问，需要在代码中添加Cookie处理
5. **反爬虫**：使用时请遵守各平台的服务条款，避免被封禁

## 开发说明

### 添加新平台

1. 在 `monitors/` 目录下创建新的监控模块
2. 继承 `PlatformMonitor` 基类
3. 实现 `get_item_price` 方法
4. 在 `monitors/__init__.py` 中导出
5. 在 `main.py` 的 `_init_monitors` 方法中注册

示例：

```python
from .base import PlatformMonitor

class NewPlatformMonitor(PlatformMonitor):
    def get_item_price(self, item_name, wear_min, wear_max):
        # 实现具体的价格获取逻辑
        results = []
        # ... 获取价格数据 ...
        return results
```

## 常见问题

### Q: 为什么没有找到商品？

A: 请检查：
- 商品名称是否与平台上完全一致
- 平台是否已启用（enabled: true）
- 磨损区间设置是否合理
- 查看日志文件了解详细错误信息

### Q: 如何停止程序？

A: 在命令行中按 `Ctrl+C` 即可安全停止程序

### Q: 数据库文件在哪里？

A: 默认保存在 `data/price_history.db`，可在配置文件中修改路径

## 许可证

本项目仅供学习交流使用，请勿用于商业目的。

## 免责声明

本工具仅用于价格监控和信息展示，不涉及任何交易行为。使用本工具时请遵守相关平台的服务条款和法律法规。由于使用本工具造成的任何后果，开发者不承担任何责任。
