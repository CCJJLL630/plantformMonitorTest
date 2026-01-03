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
│   ├── youpin.py          # 悠悠有品监控（Selenium）
│   └── ecosteam.py        # ECOSteam监控（HTML解析兜底）
├── utils/                  # 工具模块
│   ├── __init__.py
│   ├── config.py          # 配置管理
│   ├── database.py        # 数据库操作
│   ├── notification.py    # 通知模块
│   └── result_saver.py    # 结果汇总保存
├── scripts/                # 工具脚本（可选）
│   ├── dump_ecosteam_html_sell_list.py    # 导出ECOSteam完整数据
│   ├── filter_ecosteam_dump.py            # 筛选和排序数据
│   └── probe_platform_apis.py             # API探测工具
├── data/                   # 数据存储目录
│   ├── price_history.db                   # 价格历史数据库（自动创建）
│   ├── latest_monitoring_result.json      # 最新监控结果汇总
│   └── monitoring_result_*.json           # 历史监控结果备份
└── logs/                   # 日志目录
    └── monitor.log        # 运行日志（自动创建）
```

## 快速开始

### 1. 环境要求

- Python 3.7+
- pip

> 本仓库已在 Windows + Python 3.9 下验证可运行。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

建议使用虚拟环境（Windows PowerShell）：

```powershell
cd E:\CjlFile\PlantformMonitor
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
```

### 3. 配置设置

复制配置模板并编辑：

```powershell
# CMD
copy config.json.example config.json

# PowerShell
Copy-Item config.json.example config.json
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

重要：如需访问需要登录/鉴权的平台接口，通常需要在对应平台配置中加入 `Cookie`（或 `cookie`）字段。该字段通常包含敏感信息，请勿提交到公开仓库。

**ECOSteam Cookie 配置示例**：
```json
"ecosteam": {
    "enabled": true,
    "base_url": "https://www.ecosteam.cn",
    "Cookie": "SessionID=你的SessionID; PHPSESSID=你的PHPSESSID; 其他必需字段"
}
```

获取 Cookie 的方法：
1. 浏览器登录 ECOSteam
2. F12 打开开发者工具 → Network 标签页 → 刷新页面
3. 找到任意请求 → Headers → Request Headers → 复制 Cookie 值
4. 将完整 Cookie 字符串粘贴到 config.json 的 ecosteam.Cookie 字段

### 4. 运行程序

```bash
python main.py
```

Windows + venv：

```powershell
./venv/Scripts/python.exe main.py
```

一次性运行一轮（不进入无限循环，便于验证配置是否正确）：

```powershell
./venv/Scripts/python.exe -c "from main import PriceMonitor; m=PriceMonitor('config.json'); items=m.config.get_items(); print(f'loaded_items={len(items)}'); prices=(m.monitor_item(items[0]) if items else []); print(f'prices_returned={len(prices)}')"
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

部分平台支持在 `items` 中增加平台专用字段以提升稳定性：

- BUFF：`buff_goods_id`（推荐填写，避免依赖搜索接口）
- 悠悠有品：`youpin_template_id`（或兼容字段 `youpin_goods_id`）
- ECOSteam：可在 `items` 中配置 `eco_goods_url`/`ecosteam_goods_url` 指向商品详情页（否则使用 `platforms.ecosteam.goods_detail_url`）

> 这些字段均为可选，但填写后更容易“精准定位”商品。

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

### 悠悠有品（Youpin）说明

- 当前实现为 **直接使用 Selenium** 从网页请求中捕获接口响应（避免 `requests` 直连接口被 403/拦截）。
- 需要安装 `selenium`，并确保本机已安装 Chrome 且 `chromedriver` 与 Chrome 版本匹配（或已在 PATH 中可用）。

### ECOSteam 说明

- ECOSteam 的“在售列表（含磨损 float）”接口通常需要有效登录态。
- 若日志出现“用户未登录 / Cookie 可能已过期 / refreshToken 过期”等提示，请更新 `config.json` 中 `platforms.ecosteam.Cookie`（通常包含 `loginToken` / `refreshToken` / `clientId` 等）。

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

### Q: ECOSteam 提示 API 返回空结果或错误？

A: 通常是 Cookie 过期导致：
1. 检查日志中是否有 "ResultCode 400001" 或 "4001" 等错误码
2. 按照上述步骤重新获取 Cookie 并更新 config.json
3. 确保 Cookie 包含 SessionID、PHPSESSID 等必需字段
4. 注意：即使 API 失败，程序会自动切换到 HTML 解析模式继续运行

### Q: Selenium 卡住或 Chrome 进程过多？

A: 处理方法：
1. 手动停止所有 Chrome 进程：`Stop-Process -Name chrome -Force`
2. 程序已内置超时保护（页面加载45秒，脚本执行30秒）
3. 确保没有其他程序占用 Chrome 浏览器
4. 如仍有问题，可增大 `youpin.py` 中的 timeout 值

### Q: 如何停止程序？

A: 在命令行中按 `Ctrl+C` 即可安全停止程序

### Q: 数据库文件在哪里？

A: 默认保存在 `data/price_history.db`，可在配置文件中修改路径

### Q: 监控结果保存在哪里？

A: 
- 实时结果：`data/latest_monitoring_result.json`
- 历史备份：`data/monitoring_result_YYYYMMDD_HHMMSS.json`
- 价格历史：`data/price_history.db` (SQLite数据库)

## 工具脚本说明

`scripts/` 目录包含一些辅助工具，用于数据分析和测试：

- `probe_platform_apis.py`: 探测和测试各平台 API 接口
- `dump_ecosteam_html_sell_list.py`: 导出 ECOSteam 完整在售商品列表（HTML解析）
- `filter_ecosteam_dump.py`: 筛选指定磨损区间的商品并按价格排序

使用示例：
```powershell
# 导出 ECOSteam 全量数据
./venv/Scripts/python.exe scripts/dump_ecosteam_html_sell_list.py

# 筛选磨损区间 0.15-0.2605 的商品
./venv/Scripts/python.exe scripts/filter_ecosteam_dump.py
```

## 许可证

本项目仅供学习交流使用，请勿用于商业目的。

## 免责声明

本工具仅用于价格监控和信息展示，不涉及任何交易行为。使用本工具时请遵守相关平台的服务条款和法律法规。由于使用本工具造成的任何后果，开发者不承担任何责任。
