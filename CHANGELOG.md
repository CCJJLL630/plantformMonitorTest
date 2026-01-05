# 更新日志

## [2.0.0] - 2026-01-05 (refactor-optimized分支)

### 🎉 重大重构优化

#### 新增功能
- ✨ **Cookie自动获取工具** (`scripts/get_cookie.py`)
  - 支持BUFF、悠悠有品、ECOSteam三个平台
  - 自动打开浏览器，提取Cookie，更新配置文件
  - 提供Windows批处理启动脚本 (`get_cookie.bat`)

#### 改进优化
- 🚀 **悠悠有品监控器完全重写**
  - 代码从530行优化到323行，逻辑更清晰
  - 新增Cookie自动设置功能，避免登录弹窗
  - 支持完整8页数据获取（最多80个商品）
  - 改进翻页稳定性和API捕获成功率
  - 智能等待机制，适应网络波动

- 🔧 **ECOSteam监控器升级**
  - 使用Selenium完整版本替代原有实现
  - 解决网络超时问题（120秒超时）
  - 自动Cookie设置到`.ecosteam.cn`域名
  - 支持8页数据完整获取（约75个商品）
  - HTML正则解析更稳定

- 📝 **配置优化**
  - 修正磨损范围：0.15-0.38（完整久经沙场范围）
  - 更新`monitors/__init__.py`导出列表
  - 优化`config.json.example`配置说明

#### 代码清理
- 🗑️ **删除冗余文件**（18个文件，1500行代码）
  - 删除所有测试脚本：`test_*.py`、`diagnose_*.py`
  - 删除调试脚本：`debug_*.py`、`check_*.py`
  - 删除废弃监控器：`ecosteam.py`、`youpin_mobile.py`
  - 删除辅助工具：`dump_*.py`、`filter_*.py`、`probe_*.py`
  
- 📦 **项目结构简化**
  - 只保留核心功能代码
  - 新增654行高质量代码
  - 净减少846行代码
  - 目录结构更清晰

#### 测试验证
- ✅ **BUFF平台**：20个商品，价格范围 ¥390-480
- ✅ **悠悠有品**：80个商品（8页），价格范围 ¥308-369
- ✅ **ECOSteam**：75个商品（8页），13个符合范围，价格范围 ¥376-520

#### 文档更新
- 📚 更新README.md，增加v2.0说明
- 📚 更新项目结构说明
- 📚 增加Cookie自动获取工具使用说明
- 📚 优化各平台技术说明
- 📚 新增CHANGELOG.md版本日志

### 技术细节

#### 悠悠有品监控器改进
```python
# 新增方法
_set_cookies()  # 自动设置Cookie到Selenium
_fetch_page_data()  # 统一的单页数据获取
# 优化流程
初始化Selenium → 设置Cookie → 访问首页 → 捕获API → 翻页获取所有数据 → 筛选排序
```

#### ECOSteam监控器改进
```python
# 关键改进
_init_driver()  # 120秒页面加载超时
_set_cookies()  # Cookie自动设置
_parse_page_with_selenium()  # 正则解析优化
# 流程优化
访问主页设置Cookie → 逐页获取HTML → 正则解析磨损和价格 → 筛选排序
```

### 已知问题修复
- 🐛 修复悠悠有品登录弹窗导致数据获取失败
- 🐛 修复ECOSteam网络超时问题
- 🐛 修复翻页失败导致数据不完整
- 🐛 修复磨损范围配置错误

### 破坏性变更
- ⚠️ 删除 `monitors/ecosteam.py`，使用 `ecosteam_selenium.py` 替代
- ⚠️ 删除 `monitors/youpin_mobile.py`，已整合到 `youpin.py`
- ⚠️ `monitors/__init__.py` 导出 `EcosteamSeleniumMonitor` 而非 `EcosteamMonitor`

### 升级指南

如果从旧版本升级：

1. **更新代码**
   ```bash
   git fetch origin
   git checkout refactor-optimized
   git pull origin refactor-optimized
   ```

2. **更新配置**
   - 检查 `config.json` 中的磨损范围是否为 `0.15-0.38`
   - 使用 `scripts/get_cookie.py` 重新获取Cookie

3. **清理环境**
   ```bash
   # 删除旧的缓存
   rm -rf __pycache__ monitors/__pycache__ utils/__pycache__
   ```

4. **测试运行**
   ```bash
   python main.py
   ```

---

## [1.0.0] - 初始版本

### 初始功能
- ✨ 支持BUFF、悠悠有品、ECOSteam三个平台
- ✨ 价格监控和数据存储
- ✨ 邮件、钉钉、企业微信通知
- ✨ SQLite数据库存储历史数据
- ✨ JSON结果文件导出
