"""测试Qmsg酱QQ消息通知"""
import sys
sys.path.insert(0, '.')

from utils.notification import Notifier

# 测试配置
config = {
    "qmsg": {
        "enabled": True,
        "key": "YOUR_QMSG_KEY",  # 请替换为你的KEY
        "msg_type": "send",       # send=私聊, group=群聊
        "qq": ""                  # 留空=发给自己
    }
}

# 创建通知器
notifier = Notifier(config)

# 发送测试消息
print("正在发送测试QQ消息...")
notifier.send(
    title="【测试】价格监控系统",
    content="这是一条测试消息，如果你收到了，说明Qmsg配置成功！",
    price_list=[
        {
            "platform": "buff",
            "item_name": "AK-47 | 红线 (久经沙场)",
            "price": 314.25,
            "wear": 0.203776,
            "url": "https://buff.163.com/goods/968354"
        }
    ]
)

print("\n✅ 测试完成！")
print("如果配置正确，你应该会收到QQ消息。")
print("\n配置步骤：")
print("1. 访问 https://qmsg.zendee.cn/ 获取KEY")
print("2. 添加QQ好友 2082184065 并发送 @me 激活")
print("3. 将上面的 YOUR_QMSG_KEY 替换为你的KEY")
print("4. 重新运行此脚本测试")
