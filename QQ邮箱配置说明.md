# QQ邮箱通知配置说明

## 功能说明
系统已添加QQ邮箱通知功能，当监控到符合条件的商品时，会自动发送邮件通知。

## 配置步骤

### 1. 开启QQ邮箱SMTP服务

1. 登录QQ邮箱网页版：https://mail.qq.com
2. 点击顶部的 **设置** → **账户**
3. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务** 部分
4. 开启 **IMAP/SMTP服务** 或 **POP3/SMTP服务**
5. 点击 **生成授权码**，按照提示用手机发送短信验证
6. 记录下生成的 **授权码**（16位字符），这个授权码就是配置中的password

### 2. 修改config.json配置

在 `config.json` 文件中找到 `notification.email` 部分，修改为：

```json
"notification": {
    "email": {
        "enabled": true,
        "smtp_server": "smtp.qq.com",
        "smtp_port": 465,
        "use_ssl": true,
        "sender": "你的QQ邮箱@qq.com",
        "password": "你的QQ邮箱授权码",
        "receivers": ["接收邮件的邮箱@example.com"]
    }
}
```

### 3. 配置说明

- **enabled**: `true` 表示启用邮件通知，`false` 表示禁用
- **smtp_server**: QQ邮箱的SMTP服务器地址，固定为 `smtp.qq.com`
- **smtp_port**: SMTP端口号
  - `465`: SSL加密方式（推荐）
  - `587`: STARTTLS加密方式（如果465不可用时使用）
- **use_ssl**: 是否使用SSL加密，端口465时设为 `true`，端口587时设为 `false`
- **sender**: 发送邮件的QQ邮箱地址
- **password**: QQ邮箱的授权码（不是QQ密码！）
- **receivers**: 接收通知的邮箱列表，可以配置多个

### 4. 配置示例

```json
"notification": {
    "email": {
        "enabled": true,
        "smtp_server": "smtp.qq.com",
        "smtp_port": 465,
        "use_ssl": true,
        "sender": "123456789@qq.com",
        "password": "abcdefghijklmnop",
        "receivers": ["987654321@qq.com", "your-email@gmail.com"]
    }
}
```

## 注意事项

1. **授权码不是QQ密码**：必须使用QQ邮箱生成的授权码，不能使用QQ密码
2. **授权码保密**：不要将授权码泄露给他人，也不要上传到公开的代码仓库
3. **多个接收者**：`receivers` 可以配置多个邮箱，用逗号分隔
4. **测试邮件**：配置完成后建议先测试一下是否能正常发送邮件

## 其他常见邮箱配置

### 163邮箱
```json
{
    "smtp_server": "smtp.163.com",
    "smtp_port": 465,
    "use_ssl": true
}
```

### 126邮箱
```json
{
    "smtp_server": "smtp.126.com",
    "smtp_port": 465,
    "use_ssl": true
}
```

### Gmail (需要科学上网)
```json
{
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "use_ssl": false
}
```

## 故障排查

如果邮件发送失败，请检查：

1. QQ邮箱的SMTP服务是否已开启
2. 授权码是否正确（不是QQ密码）
3. 发送者邮箱地址是否正确
4. 网络连接是否正常
5. 防火墙是否阻止了465或587端口
6. 查看日志文件 `logs/monitor.log` 获取详细错误信息

## 邮件内容示例

当监控到符合条件的商品时，会收到如下格式的邮件：

```
主题：价格监控提醒

内容：
发现低价商品

价格详情：
- 平台: buff
  商品: AK-47 | 红线 (久经沙场)
  价格: ¥99.50
  磨损: 0.150000
  链接: https://buff.163.com/goods/968354
```
