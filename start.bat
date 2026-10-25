@echo off
chcp 936 >nul
cd /d "%~dp0"
title 云游 · 文旅智能助手

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 首次运行，正在创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请确认已安装 Python 3.10 及以上版本
        pause
        exit /b 1
    )
    echo [2/3] 安装依赖，请稍候（约 2-3 分钟）...
    .venv\Scripts\python.exe -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --disable-pip-version-check
)

echo.
echo [3/3] 启动服务  http://127.0.0.1:8000
echo       按 Ctrl+C 停止服务
echo.
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
