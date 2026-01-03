"""调试翻页控件"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

chrome_options = Options()
# chrome_options.add_argument('--headless')
chrome_options.add_argument('--disable-gpu')

driver = webdriver.Chrome(options=chrome_options)

print("访问页面...")
driver.get('https://www.youpin898.com/market/goods-list?templateId=109545&gameId=730&listType=10')
time.sleep(8)  # 等待页面完全加载

print("\n查找分页控件...")

# 检查页面HTML
script = """
const pagination = document.querySelector('.ant-pagination');
if (!pagination) {
    return {found: false, message: '未找到 .ant-pagination'};
}

const input = pagination.querySelector('.ant-pagination-options-quick-jumper input');
if (!input) {
    return {
        found: false, 
        message: '找到pagination但没有input',
        html: pagination.outerHTML.substring(0, 500)
    };
}

return {
    found: true,
    message: 'input找到了',
    inputType: input.type,
    inputValue: input.value
};
"""

result = driver.execute_script(script)
print(result)

# 尝试翻页
if result.get('found'):
    print("\n尝试翻页到第2页...")
    jump_script = """
    const input = document.querySelector('.ant-pagination-options-quick-jumper input');
    input.value = 2;
    input.focus();
    
    // 触发 change 事件
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
    
    // 触发 Enter 键
    const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        keyCode: 13,
        which: 13,
        bubbles: true
    });
    input.dispatchEvent(event);
    
    return {done: true};
    """
    
    driver.execute_script(jump_script)
    print("已触发翻页，等待...")
    time.sleep(5)
    
    print("检查当前页码...")
    check_script = """
    const activePage = document.querySelector('.ant-pagination-item-active');
    return activePage ? activePage.textContent : '未知';
    """
    
    current_page = driver.execute_script(check_script)
    print(f"当前页码: {current_page}")

input("按回车关闭浏览器...")
driver.quit()
