# AionUi 自托管账号与分发后端 (Windows 7 兼容)

适用于 Windows 7 / Windows 10+ / Linux 的 AionUi 自托管鉴权与配置分发服务。

## 特性
- **用户登录鉴权**: JWT 无状态 Token，密码安全加盐哈希存储（`werkzeug.security`）
- **模型配置下发与同步**: 支持用户 API 密钥（Fernet 对称加密存储）、Base URL、默认模型同步
- **市场分发系统**: 管理员上传 ZIP 资源包（助手/插件/Skill），客户端在线获取与下载安装
- **客户端日志收集**: 自动收集并集中查看桌面客户端上报日志
- **管理后台**: 内置基于 Flask-Admin 的 Web 管理界面（访问 `/admin`）
- **Windows 7 完全兼容**: 基于 Python 3.8 + SQLite，无需复杂依赖

## 运行要求
- Python 3.8+ (Windows 7 请安装 Python 3.8.10 64-bit)
- 依赖包见 `requirements.txt`

## 快速安装与运行

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 首次初始化数据库（创建管理员及数据表）：
   ```bash
   python app.py --init
   ```
   默认管理员账号：
   - 用户名: `admin`
   - 密码: `admin123`

3. 启动服务：
   ```bash
   python app.py
   ```
   或直接在 Windows 7 下双击运行 `start.bat`。

4. 访问管理后台：
   - 浏览器打开：`http://127.0.0.1:5000/admin`
