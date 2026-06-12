#!/bin/bash
# macOS 命令行版打包脚本
# 用法: bash build_mac.sh
set -e

cd "$(dirname "$0")"

echo "[1/3] 创建虚拟环境..."
python3 -m venv .venv

echo "[2/3] 安装依赖..."
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install pyinstaller requests pyperclip -q

echo "[3/3] 打包命令行版..."
.venv/bin/python -m PyInstaller \
    --onefile \
    --name "钉钉违规检测工具-CLI" \
    --hidden-import requests \
    --hidden-import urllib3 \
    --hidden-import charset_normalizer \
    --hidden-import pyperclip \
    --hidden-import struct \
    --clean \
    detector_cli.py

echo ""
echo "=============================="
echo "打包完成! 可执行文件在 dist/ 目录下"
echo "使用: ./dist/钉钉违规检测工具-CLI"
echo "=============================="
