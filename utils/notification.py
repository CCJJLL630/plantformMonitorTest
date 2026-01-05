"""通知模块 - 支持邮件、钉钉、企业微信等通知方式"""
import smtplib
import requests
import hmac
import hashlib
import base64
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
import logging


class Notifier:
    """通知管理类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化通知器
        
        Args:
            config: 通知配置
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def send(self, title: str, content: str, price_list: List[Dict[str, Any]] = None):
        """
        发送通知
        
        Args:
            title: 通知标题
            content: 通知内容
            price_list: 价格列表
        """
        # 构建完整消息
        message = self._build_message(title, content, price_list)
        
        # 邮件通知
        if self.config.get('email', {}).get('enabled'):
            self._send_email(title, message)
        
        # 钉钉通知
        if self.config.get('dingtalk', {}).get('enabled'):
            self._send_dingtalk(title, message)
        
        # 企业微信通知
        if self.config.get('wechat', {}).get('enabled'):
            self._send_wechat(title, message)
        
        # QQ消息通知（Qmsg酱）- 支持多个配置
        qmsg_config = self.config.get('qmsg')
        if qmsg_config:
            # 支持单个配置（字典）或多个配置（列表）
            if isinstance(qmsg_config, list):
                # 多个qmsg配置
                for idx, config in enumerate(qmsg_config):
                    if config.get('enabled'):
                        self._send_qq_qmsg(title, message, config, idx + 1)
            elif isinstance(qmsg_config, dict):
                # 单个qmsg配置（向后兼容）
                if qmsg_config.get('enabled'):
                    self._send_qq_qmsg(title, message, qmsg_config)
    
    def _build_message(self, title: str, content: str, price_list: List[Dict[str, Any]] = None) -> str:
        """
        构建消息内容
        
        Args:
            title: 标题
            content: 内容
            price_list: 价格列表
            
        Returns:
            完整消息
        """
        message = f"{title}\n\n{content}\n\n"
        
        if price_list:
            message += "价格详情：\n"
            for item in price_list:
                message += (
                    f"- 平台: {item.get('platform', '未知')}\n"
                    f"  商品: {item.get('item_name', '未知')}\n"
                    f"  价格: ¥{item.get('price', 0):.2f}\n"
                    f"  磨损: {item.get('wear', 0):.6f}\n"
                    f"  链接: {item.get('url', '无')}\n\n"
                )
        
        return message
    
    def _send_email(self, subject: str, content: str):
        """
        发送邮件通知
        
        Args:
            subject: 邮件主题
            content: 邮件内容
        """
        try:
            email_config = self.config.get('email', {})
            
            msg = MIMEMultipart()
            msg['From'] = email_config.get('sender')
            msg['To'] = ', '.join(email_config.get('receivers', []))
            msg['Subject'] = subject
            
            msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            # 连接SMTP服务器
            server = smtplib.SMTP(
                email_config.get('smtp_server'),
                email_config.get('smtp_port', 587)
            )
            server.starttls()
            server.login(
                email_config.get('sender'),
                email_config.get('password')
            )
            
            # 发送邮件
            server.send_message(msg)
            server.quit()
            
            self.logger.info("邮件通知发送成功")
        
        except Exception as e:
            self.logger.error(f"邮件通知发送失败: {e}")
    
    def _send_dingtalk(self, title: str, content: str):
        """
        发送钉钉通知
        
        Args:
            title: 标题
            content: 内容
        """
        try:
            dingtalk_config = self.config.get('dingtalk', {})
            webhook = dingtalk_config.get('webhook')
            secret = dingtalk_config.get('secret')
            
            # 计算签名
            timestamp = str(round(time.time() * 1000))
            sign = self._calc_dingtalk_sign(timestamp, secret)
            
            # 构建请求URL
            url = f"{webhook}&timestamp={timestamp}&sign={sign}"
            
            # 构建消息
            data = {
                "msgtype": "text",
                "text": {
                    "content": f"{title}\n\n{content}"
                }
            }
            
            # 发送请求
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            
            self.logger.info("钉钉通知发送成功")
        
        except Exception as e:
            self.logger.error(f"钉钉通知发送失败: {e}")
    
    def _calc_dingtalk_sign(self, timestamp: str, secret: str) -> str:
        """
        计算钉钉签名
        
        Args:
            timestamp: 时间戳
            secret: 密钥
            
        Returns:
            签名字符串
        """
        secret_enc = secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        
        hmac_code = hmac.new(
            secret_enc,
            string_to_sign_enc,
            digestmod=hashlib.sha256
        ).digest()
        
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign
    
    def _send_wechat(self, title: str, content: str):
        """
        发送企业微信通知
        
        Args:
            title: 标题
            content: 内容
        """
        try:
            wechat_config = self.config.get('wechat', {})
            webhook = wechat_config.get('webhook')
            
            # 构建消息
            data = {
                "msgtype": "text",
                "text": {
                    "content": f"{title}\n\n{content}"
                }
            }
            
            # 发送请求
            response = requests.post(webhook, json=data, timeout=10)
            response.raise_for_status()
            
            self.logger.info("企业微信通知发送成功")
        
        except Exception as e:
            self.logger.error(f"企业微信通知发送失败: {e}")
    
    def _send_qq_qmsg(self, title: str, content: str, qmsg_config: dict = None, index: int = None):
        """
        通过Qmsg酱发送QQ消息
        
        Args:
            title: 标题
            content: 内容
            qmsg_config: Qmsg配置字典（可选，默认从self.config读取）
            index: 配置索引（用于多配置场景的日志标识）
        """
        try:
            # 使用传入的配置或从self.config读取（向后兼容）
            config = qmsg_config or self.config.get('qmsg', {})
            key = config.get('key')
            msg_type = config.get('msg_type', 'send')  # send=好友, group=群聊
            qq = config.get('qq', '')  # QQ号或群号
            
            if not key:
                prefix = f"#{index} " if index else ""
                self.logger.warning(f"{prefix}Qmsg酱KEY未配置，跳过QQ消息发送")
                return
            
            # 构建消息内容（Qmsg支持换行）
            message = f"{title}\n\n{content}"
            
            # 限制消息长度（Qmsg限制）
            if len(message) > 1000:
                message = message[:997] + "..."
            
            # API地址
            url = f"https://qmsg.zendee.cn/{msg_type}/{key}"
            
            # 请求参数
            params = {
                "msg": message
            }
            if qq:
                params["qq"] = qq
            
            # 发送请求
            response = requests.post(url, data=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('success'):
                success_msg = f"Qmsg酱消息发送成功 #{index}" if index else "Qmsg酱消息发送成功"
                self.logger.info(success_msg)
            else:
                error_prefix = f"#{index} " if index else ""
                self.logger.error(f"{error_prefix}Qmsg酱消息发送失败: {result.get('reason')}")
        
        except Exception as e:
            error_prefix = f"#{index} " if index else ""
            self.logger.error(f"{error_prefix}Qmsg酱消息发送失败: {e}")
