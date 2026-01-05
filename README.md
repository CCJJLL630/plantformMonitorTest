# 平台价格监控系统

一个用于监控网易BUFF、悠悠有品、ECOSteam等平台指定磨损区间商品价格的Python工具。

## 功能特点

- 🔍 **多平台支持**：支持网易BUFF、悠悠有品、ECOSteam等主流交易平台
- 📊 **精确监控**：可指定商品名称和磨损区间进行精准监控
- 💰 **价格预警**：当价格低于设定阈值时自动发送通知
- 📱 **多种通知方式**：支持邮件、钉钉、企业微信等多种通知方式
- 💾 **数据存储**：自动保存价格历史记录，支持数据分析
- ⚙️ **灵活配置**：通过JSON配置文件轻松管理监控项目
- 🍪 **自动Cookie管理**：提供Cookie自动获取工具，简化配置流程

## 最新更新 (refactor-optimized分支)

**v2.0 重构优化版本**
- ✅ 重写悠悠有品监控器，逻辑更清晰，自动设置Cookie，支持完整翻页
- ✅ ECOSteam使用Selenium版本，解决网络超时和数据获取问题
- ✅ 新增Cookie自动获取工具（`scripts/get_cookie.py`）
- ✅ 清理所有冗余测试和诊断代码，项目结构更简洁
- ✅ 修正磨损范围配置（0.15-0.38完整久经沙场范围）
- ✅ 代码优化：删除1500行冗余代码，新增654行核心功能

**测试验证结果**：
- BUFF平台：✅ 20个商品，价格范围 ¥390-480
- 悠悠有品：✅ 80个商品（8页完整数据），价格范围 ¥308-369
- ECOSteam：✅ 75个商品（8页），13个符合磨损范围，价格范围 ¥376-520

## 项目结构

```
plantformMonitorTest/
├── main.py                     # 主程序入口
├── start_monitor.bat           # Windows启动脚本（推荐使用）
├── config.json                 # 配置文件（需手动创建，参考config.json.example）
├── config.json.example         # 配置文件模板
├── requirements.txt            # Python依赖包
├── README.md                   # 项目说明文档
├── monitors/                   # 平台监控模块
│   ├── __init__.py
│   ├── base.py                # 监控器基类
│   ├── buff.py                # 网易BUFF监控
│   ├── youpin.py              # 悠悠有品监控（Selenium + Cookie自动设置）
│   └── ecosteam_selenium.py   # ECOSteam监控（Selenium完整版）
├── utils/                      # 工具模块
│   ├── __init__.py
│   ├── config.py              # 配置管理
│   ├── database.py            # 数据库操作
│   ├── notification.py        # 通知模块
│   └── result_saver.py        # 结果汇总保存
├── scripts/                    # 工具脚本
│   ├── get_cookie.py          # Cookie自动获取工具（新增）
│   └── get_cookie.bat         # Cookie获取工具Windows启动脚本
├── data/                       # 数据存储目录
│   ├── price_history.db       # 价格历史数据库（自动创建）
│   ├── latest_monitoring_result.json      # 最新监控结果汇总
│   └── monitoring_result_*.json           # 历史监控结果备份
└── logs/                       # 日志目录
    └── monitor.log            # 运行日志（自动创建）
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

#### 方式1：使用Cookie自动获取工具（推荐）

我们提供了自动获取Cookie的工具，无需手动复制粘贴：

```powershell
# Windows用户：双击运行
scripts\get_cookie.bat

# 或者使用命令行
python scripts/get_cookie.py
```

工具会自动：
1. 打开浏览器让你登录各个平台
2. 自动提取Cookie
3. 更新到config.json配置文件

支持的平台：BUFF、悠悠有品(UU)、ECOSteam

#### 方式2：手动配置

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

重要：如需访问需要登录/鉴权的平台接口，需要在对应平台配置中加入 `Cookie` 字段。

**推荐使用 `scripts/get_cookie.py` 工具自动获取Cookie**，或手动获取：

**手动获取 Cookie 的方法**：
1. 浏览器登录对应平台（如 ECOSteam）
2. F12 打开开发者工具 → Network 标签页 → 刷新页面
3. 找到任意请求 → Headers → Request Headers → 复制 Cookie 值
4. 将完整 Cookie 字符串粘贴到 config.json 的对应平台 Cookie 字段

**各平台Cookie配置示例**：

```json
"platforms": {
    "buff": {
        "enabled": true,
        "base_url": "https://buff.163.com",
        "Cookie": "session=你的session值; csrf_token=你的token; Device-Id=设备ID"
    },
    "youpin": {
        "enabled": true,
        "base_url": "https://www.youpin898.com",
        "api_base_url": "https://api.youpin898.com",
        "Cookie": "uu_token=你的JWT_token值"
    },
    "ecosteam": {
        "enabled": true,
        "base_url": "https://www.ecosteam.cn",
        "Cookie": "loginToken=你的token; refreshToken=你的refresh_token; clientId=客户端ID"
    }
}
```

⚠️ **安全提示**：Cookie包含敏感信息，请勿将 `config.json` 提交到公开仓库。

### 4. 运行程序

#### 方式1：使用启动脚本（推荐 - Windows）

双击运行 `start_monitor.bat` 文件，程序将在独立窗口中运行。

**优点**：
- ✅ 避免 PowerShell 后台任务信号干扰
- ✅ 可以直接看到实时输出
- ✅ 按 Ctrl+C 可以安全退出
- ✅ 不会出现意外中断问题

#### 方式2：命令行运行

```bash
# 基础运行
python main.py

# Windows + venv
./venv/Scripts/python.exe main.py
```

**⚠️ 注意**：在 Windows PowerShell 中作为后台任务运行时，可能会因为系统信号触发 KeyboardInterrupt。建议使用启动脚本或前台运行。

#### 方式3：测试运行（单次）

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

部分平台支持在 `items` 中增加平台专用字段以提升稳定性和准确性：

- **BUFF**：`buff_goods_id`（推荐填写，直接定位商品，避免搜索接口问题）
- **悠悠有品**：`youpin_template_id` 或 `youpin_goods_list_url`（推荐填写模板ID）
- **ECOSteam**：`ecosteam_goods_detail_url`（商品详情页完整URL）

**完整配置示例**：

```json
{
    "name": "宙斯x27电击枪 | 鼾龙传说 (久经沙场)",
    "wear_range": {
        "min": 0.15,
        "max": 0.38
    },
    "target_price": 300.0,
    "platforms": ["buff", "youpin", "ecosteam"],
    "buff_goods_id": 968354,
    "youpin_template_id": 109545,
    "ecosteam_goods_detail_url": "https://www.ecosteam.cn/goods/730-15231-1-laypagesale-0-1.html"
}
```

> 这些字段均为可选，但填写后更容易精准定位商品，提高监控成功率。

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

#### QQ消息通知（Qmsg酱）

**推荐**：免费、简单、实时推送

```json
"qmsg": {
    "enabled": true,
    "key": "YOUR_QMSG_KEY",      // 从 https://qmsg.zendee.cn/ 获取
    "msg_type": "send",           // send=私聊, group=群聊
    "qq": ""                      // 留空=发给自己, 填QQ号=指定接收人, 填群号=发给群
}
```

**配置步骤**：
1. 访问 https://qmsg.zendee.cn/ 获取KEY
2. 添加QQ好友 `2082184065` 并发送 `@me` 激活
3. 在 `config.json` 中配置KEY

详细配置指南：[docs/QMSG_GUIDE.md](docs/QMSG_GUIDE.md)

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
4. **Cookie认证**：部分平台可能需要登录才能访问，需要在配置中添加Cookie字段
5. **反爬虫**：使用时请遵守各平台的服务条款，避免被封禁
6. **运行方式**：Windows 用户推荐使用 `start_monitor.bat` 启动，避免后台运行信号干扰

### 悠悠有品（Youpin）说明

**v2.0 优化版本**：
- ✅ 使用 Selenium 自动捕获API响应，稳定可靠
- ✅ 自动设置Cookie，无需手动处理登录态
- ✅ 支持完整翻页，可获取所有页面数据（最多8页）
- ✅ 智能等待和重试机制，适应网络波动

**技术实现**：
- 直接使用 Selenium 从网页性能日志中捕获 `queryOnSaleCommodityList` API响应
- 自动设置Cookie到`.youpin898.com`域名，避免登录弹窗
- 支持自动翻页，每页等待15-20秒确保API加载完成

**环境要求**：
- 需要安装 `selenium` 和 Chrome浏览器
- 确保 ChromeDriver 与 Chrome 版本匹配
- Cookie配置：使用 `scripts/get_cookie.py` 自动获取或手动配置 `uu_token`

**性能说明**：
- 首页加载约20秒，翻页约15秒/页
- 获取8页数据约需2-3分钟
- 程序会自动过滤磨损范围，返回价格最低的20个商品

### ECOSteam 说明

**v2.0 Selenium完整版本**：
- ✅ 使用 Selenium 完整渲染页面，解决网络超时问题
- ✅ 自动设置Cookie，支持登录态
- ✅ 支持多页数据获取（默认8页）
- ✅ 120秒页面加载超时，适应慢速网络

**技术实现**：
- 先访问主页设置Cookie到`.ecosteam.cn`域名
- 逐页访问商品列表，使用正则表达式解析磨损和价格数据
- 每页等待5秒确保数据渲染完成
- 自动过滤磨损范围并按价格排序

**Cookie配置**：
- 包含字段：`loginToken`、`refreshToken`、`clientId` 等
- 使用 `scripts/get_cookie.py` 自动获取（推荐）
- 或手动从浏览器开发者工具复制

**性能说明**：
- 每页加载时间：2-25秒（取决于网络速度）
- 8页数据约需2-4分钟
- 程序会输出每页解析结果和统计信息

## 故障排除

### 程序无法启动

1. 检查 Python 版本：`python --version`（需要 3.7+）
2. 检查依赖是否安装：`pip list | findstr selenium`
3. 检查配置文件：确保 `config.json` 存在且格式正确
4. 查看日志文件：`logs/monitor.log`

### Chrome/Selenium 相关问题

1. **ChromeDriver 版本不匹配**：
   - 查看 Chrome 版本：chrome://version
   - 下载对应版本的 ChromeDriver：https://chromedriver.chromium.org/
   - 将 chromedriver.exe 放在 PATH 路径下

2. **Chrome 无法启动**：
   - 检查是否有残留进程：`Get-Process chrome`
   - 清理进程：`Stop-Process -Name chrome -Force`
   - 重启程序

3. **Selenium 超时**：
   - 程序已设置45秒页面加载超时和30秒脚本执行超时
   - 如需调整，修改 `monitors/youpin.py` 中的 `set_page_load_timeout` 和 `set_script_timeout` 参数

### Cookie 过期问题

所有平台的 Cookie 都有有效期，需要定期更新。

**推荐方法：使用自动获取工具**
```powershell
# 运行Cookie获取工具
python scripts/get_cookie.py
# 或双击 scripts\get_cookie.bat
```

工具会：
1. 打开浏览器让你登录
2. 自动提取Cookie
3. 更新config.json配置文件
4. 无需手动复制粘贴

**手动更新方法**：
1. **获取方法**：浏览器登录 → F12 开发者工具 → Network → 复制 Cookie
2. **更新位置**：`config.json` 中对应平台的 `Cookie` 字段
3. **验证**：重新运行程序，查看日志是否仍有认证错误

**Cookie有效期**：
- BUFF：通常7-30天
- 悠悠有品：JWT token约10天
- ECOSteam：loginToken约7天

### 性能优化建议

1. **减少监控商品数量**：过多商品会导致单轮监控时间过长
2. **调整监控间隔**：根据需要设置合理的 `monitor_interval`（建议300秒以上）
3. **选择性启用平台**：暂时不需要的平台可设置 `"enabled": false`
4. **关闭不必要的通知**：减少邮件/钉钉通知频率

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

### Q: 程序在 Youpin 监控时意外停止？

A: 这是 Windows 后台运行时的已知问题，解决方法：
1. **使用 `start_monitor.bat` 启动**（推荐）：双击运行批处理文件
2. 在 PowerShell 中前台运行（不要使用后台模式）
3. 程序已内置自动重试机制（最多10次），可以应对偶发的信号中断

**技术原因**：Windows PowerShell 作为后台任务管理器时，会向 Python 进程发送 SIGBREAK 信号，导致 `time.sleep()` 和 `Event.wait()` 被中断。程序已实现信号处理和自动恢复机制。

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
1. 手动停止所有 Chrome 进程：`Stop-Process -Name chrome -Force`（PowerShell）或 `taskkill /F /IM chrome.exe`（CMD）
2. 程序已内置超时保护（页面加载45秒，脚本执行30秒）
3. 确保没有其他程序占用 Chrome 浏览器
4. 如仍有问题，可增大 `youpin.py` 中的 timeout 值
5. 检查 Chrome 和 ChromeDriver 版本是否匹配

### Q: 如何停止程序？

A: 
- **前台运行**：在命令行中按 `Ctrl+C` 即可安全停止
- **批处理运行**：在窗口中按 `Ctrl+C`，程序会在当前任务完成后退出
- **强制停止**：关闭命令行窗口或使用任务管理器结束进程

### Q: 收到 "接收到停止信号" 但我没有按 Ctrl+C？

A: 这是 Windows 后台运行的已知问题：
1. 使用 `start_monitor.bat` 启动程序（推荐）
2. 程序已实现自动重试机制，会尝试继续运行
3. 如果频繁出现，建议在前台窗口运行而不是后台任务

### Q: 数据库文件在哪里？

A: 默认保存在 `data/price_history.db`，可在配置文件中修改路径

### Q: 监控结果保存在哪里？

A: 
- 实时结果：`data/latest_monitoring_result.json`
- 历史备份：`data/monitoring_result_YYYYMMDD_HHMMSS.json`
- 价格历史：`data/price_history.db` (SQLite数据库)

## 工具脚本说明

### Cookie自动获取工具（推荐）

`scripts/get_cookie.py` - 自动获取并更新各平台Cookie

**功能**：
- 自动打开浏览器让你登录各平台
- 自动提取Cookie值
- 自动更新到config.json配置文件
- 支持BUFF、悠悠有品(UU)、ECOSteam三个平台

**使用方法**：
```powershell
# 方式1：使用批处理文件（推荐）
scripts\get_cookie.bat

# 方式2：直接运行Python脚本
python scripts/get_cookie.py

# 虚拟环境
./venv/Scripts/python.exe scripts/get_cookie.py
```

**操作步骤**：
1. 运行脚本，会打开Chrome浏览器
2. 在浏览器中登录对应平台（如BUFF、UU、ECOSteam）
3. 登录成功后，脚本自动提取Cookie
4. Cookie自动保存到config.json
5. 无需手动复制粘贴，一键完成配置

## 许可证

本项目仅供学习交流使用，请勿用于商业目的。

## 免责声明

本工具仅用于价格监控和信息展示，不涉及任何交易行为。使用本工具时请遵守相关平台的服务条款和法律法规。由于使用本工具造成的任何后果，开发者不承担任何责任。
