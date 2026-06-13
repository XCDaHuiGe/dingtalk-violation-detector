# -*- mode: python ; coding: utf-8 -*-
# 违规检测工具 — flet 版 PyInstaller spec
# 打包: pyinstaller --noconfirm --clean flet.spec
# 产物: dist/违规检测_flet.exe
# 入口: main_flet.py (默认启动 flet GUI)
#
# 关键依赖：
#   - flet 0.85.x
#   - flet-desktop 0.85.x (独立 pip 包)
#   - flet-windows.zip (从 GitHub Releases 下载，放到 flet_desktop/app/)

import sys
from pathlib import Path

block_cipher = None

# 定位 venv site-packages
sp = Path(sys.executable).parent.parent / 'Lib' / 'site-packages'

datas = [
    # flet 包内所有资源（assets、js、native dll 等）
    (str(sp / 'flet'), 'flet'),
    # flet-desktop 包 + 预打包的 flet-windows.zip（关键！）
    (str(sp / 'flet_desktop'), 'flet_desktop'),
]

hiddenimports = [
    # HTTP
    'requests', 'urllib3', 'charset_normalizer', 'certifi', 'idna',
    # 剪贴板
    'pyperclip',
    # Windows 平台
    'winreg', 'ctypes',
    # flet 核心
    'flet', 'flet.app', 'flet.page', 'flet.utils', 'flet.cli',
    'flet.controls', 'flet.messaging', 'flet.security', 'flet.auth',
    'flet.canvas', 'flet.components', 'flet.fastapi', 'flet.pubsub',
    'flet.testing',
    # flet-desktop（独立包）
    'flet_desktop', 'flet_desktop.version',
    # 第三方打包易漏
    'oauthlib', 'msgpack', 'repath', 'six', 'anyio', 'h11', 'httpcore', 'httpx',
]

a = Analysis(
    ['main_flet.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 不排除 tkinter（虽然 flet 不用，但安全起见保留）
    excludes=['matplotlib', 'numpy', 'pandas',
              'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='违规检测_flet',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 模式
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)