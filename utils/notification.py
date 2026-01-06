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
            
            smtp_server = email_config.get('smtp_server')
            smtp_port = email_config.get('smtp_port', 465)
            use_ssl = email_config.get('use_ssl', True)
            
            # 根据配置选择SSL或STARTTLS连接方式
            if use_ssl and smtp_port == 465:
                # 使用SSL加密连接（QQ邮箱推荐方式）
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                # 使用STARTTLS方式
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
            
            # 登录邮箱
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
