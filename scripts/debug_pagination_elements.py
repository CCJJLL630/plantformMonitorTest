"""
调试脚本：查看页面上的分页元素
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 初始化 Selenium
options = Options()
# options.add_argument('--headless=new')  # 先不用headless，方便调试
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-blink-features=AutomationControlled')
options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

driver = webdriver.Chrome(options=options)
driver.set_page_load_timeout(30)

try:
    # 访问页面
    url = 'https://www.youpin898.com/market/goods-list?templateId=109545&gameId=730&listType=10'
    print(f"访问页面: {url}")
    driver.get(url)
    
    print("等待8秒...")
    time.sleep(8)
    
    # 查找所有分页相关的元素
    print("\n=== 查找分页元素 ===")
    
    # 1. 查找 ant-pagination 容器
    pagination_html = driver.execute_script("""
        const pagination = document.querySelector('.ant-pagination');
        if (pagination) {
            return pagination.outerHTML;
        }
        return null;
    """)
    
    if pagination_html:
        print(f"\n找到分页容器 (.ant-pagination)，HTML长度: {len(pagination_html)} 字符")
        print(f"前500字符:\n{pagination_html[:500]}")
    else:
        print("\n未找到 .ant-pagination 元素")
    
    # 2. 查找下一页按钮
    next_btn_info = driver.execute_script("""
        const selectors = [
            '.ant-pagination-next',
            'li.ant-pagination-next',
            '.ant-pagination-next:not(.ant-pagination-disabled)',
            '[title="下一页"]',
            '.ant-pagination button'
        ];
        
        const results = [];
        for (const selector of selectors) {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
                results.push({
                    selector: selector,
                    count: elements.length,
                    classes: Array.from(elements[0].classList),
                    disabled: elements[0].classList.contains('ant-pagination-disabled')
                });
            }
        }
        return results;
    """)
    
    if next_btn_info:
        print(f"\n找到的下一页按钮:")
        for info in next_btn_info:
            print(f"  选择器: {info['selector']}")
            print(f"  数量: {info['count']}")
            print(f"  class列表: {info['classes']}")
            print(f"  是否禁用: {info['disabled']}")
            print()
    else:
        print("\n未找到任何下一页按钮")
    
    # 3. 查找输入框
    input_info = driver.execute_script("""
        const inputs = document.querySelectorAll('input');
        const results = [];
        for (const input of inputs) {
            results.push({
                type: input.type,
                className: input.className,
                placeholder: input.placeholder,
                value: input.value
            });
        }
        return results;
    """)
    
    print(f"\n找到 {len(input_info)} 个输入框:")
    for i, info in enumerate(input_info):
        print(f"  输入框 {i+1}: type={info['type']}, class={info['className']}, placeholder={info['placeholder']}")
    
    print("\n按回车继续...")
    input()
    
finally:
    driver.quit()
