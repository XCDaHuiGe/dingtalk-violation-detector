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
    --name "违规检测工具-CLI" \
    --hidden-import requests \
    --hidden-import urllib3 \
    --hidden-import charset_normalizer \
    --hidden-import pyperclip \
    --hidden-import struct \
    --clean \
    detector_cli.py

# 生成双击启动脚本（macOS 双击 .command 文件会自动用终端打开）
cat > dist/违规检测工具.command << 'SCRIPT'
#!/bin/bash
cd "$(dirname "$0")"

CLI="./违规检测工具-CLI"

# 若 CLI 二进制已被移入废纸篓，自动恢复
if [ ! -f "$CLI" ]; then
    TRASH_PATH="$HOME/.Trash/违规检测工具-CLI"
    if [ -f "$TRASH_PATH" ]; then
        cp "$TRASH_PATH" "$CLI"
        echo "已从废纸篓恢复 CLI 程序"
    else
        echo "错误: 找不到违规检测工具-CLI，请确认两个文件在同一目录"
        read -p "
按回车键退出..."
        exit 1
    fi
fi

# 清除 macOS 隔离属性 + 修复执行权限
xattr -cr "$CLI" 2>/dev/null
chmod +x "$CLI" 2>/dev/null

"$CLI"
read -p "
按回车键退出..."
SCRIPT
chmod +x dist/违规检测工具.command

echo ""
echo "=============================="
echo "打包完成!"
echo "  CLI程序: dist/违规检测工具-CLI"
echo "  双击启动: dist/违规检测工具.command"
echo "=============================="
