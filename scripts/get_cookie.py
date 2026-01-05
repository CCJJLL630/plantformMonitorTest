"""
Cookie获取工具
用于获取各平台的Cookie并自动更新到config.json
"""

import json
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 平台配置
PLATFORMS = {
    "1": {
        "name": "ECOSteam",
        "url": "https://www.ecosteam.cn",
        "config_key": "ecosteam",
        "cookie_field": "Cookie"
    },
    "2": {
        "name": "悠悠有品",
        "url": "https://www.youpin898.com",
        "config_key": "youpin",
        "cookie_field": "Cookie"
    },
    "3": {
        "name": "网易BUFF",
        "url": "https://buff.163.com",
        "config_key": "buff",
        "cookie_field": "Cookie"
    }
}


def get_config_path():
    """获取配置文件路径"""
    # 从scripts目录向上一级找config.json
    script_dir = Path(__file__).parent
    config_path = script_dir.parent / "config.json"
    return config_path


def load_config():
    """加载配置文件"""
    config_path = get_config_path()
    if not config_path.exists():
        print(f"❌ 配置文件不存在: {config_path}")
        return None
    
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    """保存配置文件"""
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    print(f"✅ 配置已保存到: {config_path}")


def init_driver():
    """初始化Chrome浏览器"""
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    # 不使用headless模式，让用户可以看到浏览器进行登录
    # chrome_options.add_argument("--headless")
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"❌ 初始化Chrome失败: {e}")
        print("请确保已安装Chrome浏览器和ChromeDriver")
        return None


def get_cookies_from_browser(url, platform_name):
    """从浏览器获取Cookie"""
    print(f"\n{'='*60}")
    print(f"正在打开 {platform_name} 登录页面...")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    driver = init_driver()
    if not driver:
        return None
    
    try:
        # 打开目标网站
        driver.get(url)
        
        print(f"\n📌 请在打开的浏览器窗口中完成以下操作：")
        print(f"   1. 手动登录 {platform_name}")
        print(f"   2. 登录成功后，确保可以正常浏览页面")
        print(f"   3. 回到此命令行窗口，按 Enter 键继续...")
        
        input("\n按 Enter 键继续获取Cookie...")
        
        # 获取所有Cookie
        cookies = driver.get_cookies()
        
        # 将Cookie转换为字符串格式
        cookie_str = "; ".join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])
        
        print(f"\n✅ 成功获取Cookie (共 {len(cookies)} 个)")
        print(f"\nCookie预览 (前200字符):")
        print(f"{cookie_str[:200]}...")
        
        return cookie_str
        
    except Exception as e:
        print(f"❌ 获取Cookie失败: {e}")
        return None
    finally:
        driver.quit()
        print("\n浏览器已关闭")


def update_config_cookie(platform_key, cookie_field, cookie_value):
    """更新配置文件中的Cookie"""
    config = load_config()
    if not config:
        return False
    
    # 确保平台配置存在
    if "platforms" not in config:
        config["platforms"] = {}
    
    if platform_key not in config["platforms"]:
        config["platforms"][platform_key] = {}
    
    # 更新Cookie
    config["platforms"][platform_key][cookie_field] = cookie_value
    
    # 保存配置
    save_config(config)
    return True


def main():
    """主函数"""
    print("="*60)
    print("Cookie获取工具".center(60))
    print("="*60)
    
    # 显示平台选择菜单
    print("\n请选择要获取Cookie的平台：")
    for key, platform in PLATFORMS.items():
        print(f"  {key}. {platform['name']}")
    print("  0. 退出")
    
    choice = input("\n请输入选项 (0-3): ").strip()
    
    if choice == "0":
        print("👋 已退出")
        return
    
    if choice not in PLATFORMS:
        print("❌ 无效的选项")
        return
    
    platform = PLATFORMS[choice]
    platform_name = platform["name"]
    platform_url = platform["url"]
    config_key = platform["config_key"]
    cookie_field = platform["cookie_field"]
    
    # 获取Cookie
    cookie_str = get_cookies_from_browser(platform_url, platform_name)
    
    if not cookie_str:
        print("\n❌ 未能获取到Cookie")
        return
    
    # 询问是否保存到配置文件
    print(f"\n是否将Cookie保存到配置文件？")
    print(f"   平台: {platform_name}")
    print(f"   配置路径: platforms.{config_key}.{cookie_field}")
    
    save_choice = input("\n保存到配置文件? (y/n): ").strip().lower()
    
    if save_choice == "y":
        if update_config_cookie(config_key, cookie_field, cookie_str):
            print(f"\n✅ Cookie已成功保存到配置文件")
            print(f"\n下次运行监控程序时将自动使用此Cookie")
        else:
            print(f"\n❌ 保存Cookie失败")
    else:
        print(f"\n📋 Cookie内容（请手动复制到配置文件）：")
        print(f"\n{cookie_str}\n")
        print(f"请将上述内容添加到 config.json 的以下位置：")
        print(f'"platforms" -> "{config_key}" -> "{cookie_field}"')


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 用户取消操作")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()
