@echo off
chcp 65001 >nul
echo [AionUi] 正在启动自托管后端服务...

REM 检查 Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8 并配置环境变量。
    pause
    exit /b 1
)

REM 初始化数据库（若首次运行）
if not exist "aionui.db" (
    echo [AionUi] 检测到首次运行，正在初始化数据库...
    python app.py --init
)

REM 启动服务
echo [AionUi] 正在启动服务 (http://0.0.0.0:5000)...
echo [AionUi] 默认管理员: admin / admin123
python app.py

pause
