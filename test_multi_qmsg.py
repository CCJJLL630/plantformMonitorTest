"""
测试多Qmsg配置功能
"""
import json
from utils.notification import NotificationManager

def test_multi_qmsg():
    """测试多Qmsg配置"""
    
    # 模拟配置（数组格式）
    config_multi = {
        "notification": {
            "qmsg": [
                {
                    "enabled": True,
                    "key": "YOUR_KEY_1",
                    "msg_type": "send",
                    "qq": ""
                },
                {
                    "enabled": True,
                    "key": "YOUR_KEY_2",
                    "msg_type": "group",
                    "qq": "123456789"
                }
            ]
        }
    }
    
    # 模拟配置（单个对象格式 - 向后兼容）
    config_single = {
        "notification": {
            "qmsg": {
                "enabled": True,
                "key": "YOUR_KEY",
                "msg_type": "send",
                "qq": ""
            }
        }
    }
    
    print("=" * 60)
    print("测试1: 多Qmsg配置（数组格式）")
    print("=" * 60)
    manager1 = NotificationManager(config_multi)
    manager1.send(
        "【测试】多Qmsg配置",
        "这是一条测试消息\n\n如果你收到此消息，说明多Qmsg配置功能正常！"
    )
    
    print("\n" + "=" * 60)
    print("测试2: 单Qmsg配置（对象格式 - 向后兼容）")
    print("=" * 60)
    manager2 = NotificationManager(config_single)
    manager2.send(
        "【测试】单Qmsg配置",
        "这是一条测试消息\n\n如果你收到此消息，说明单Qmsg配置依然有效！"
    )
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)
    print("\n提示：")
    print("1. 请检查你的QQ是否收到测试消息")
    print("2. 查看日志文件 logs/monitor.log 确认发送状态")
    print("3. 如果使用多配置，应该看到 '#1', '#2' 等编号")

if __name__ == "__main__":
    print("Qmsg多配置功能测试\n")
    print("注意：")
    print("- 请先在上面的代码中填写你的真实KEY")
    print("- 确保已经激活了Qmsg机器人")
    print("- 如果不想真实发送，可以设置 enabled=False\n")
    
    input("按回车键开始测试...")
    test_multi_qmsg()
