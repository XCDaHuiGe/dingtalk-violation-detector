@echo off
cd /d "%~dp0"
call :main
echo.
pause
exit /b

:main
echo [1/3] 创建虚拟环境...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [错误] 创建虚拟环境失败，请确认已安装 Python 并加入 PATH
    exit /b 1
)

echo [2/3] 安装依赖...
.venv\Scripts\python.exe -m pip install pyinstaller requests pyperclip -q
if %errorlevel% neq 0 (
    echo [错误] 安装依赖失败
    exit /b 1
)

echo [3/3] 打包单文件 GUI 程序...
.venv\Scripts\python.exe -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "钉钉违规检测工具" ^
    --hidden-import requests ^
    --hidden-import urllib3 ^
    --hidden-import charset_normalizer ^
    --hidden-import pyperclip ^
    --hidden-import winreg ^
    --hidden-import ctypes ^
    --hidden-import struct ^
    --clean ^
    main.py

if %errorlevel% neq 0 (
    echo [错误] 打包失败
    exit /b 1
)

echo.
echo ==============================
echo 打包完成! exe 在 dist\ 目录下
echo ==============================
exit /b 0
