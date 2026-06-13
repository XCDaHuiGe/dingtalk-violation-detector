# -*- mode: python ; coding: utf-8 -*-
# 违规检测工具 — PyInstaller spec (适配 flet 0.85.x)
# 打包: pyinstaller 违规检测.spec
#
# 产物: dist/违规检测.exe

import sys
from pathlib import Path

block_cipher = None

# 定位 venv site-packages 下的 flet 资源
# spec 解析时 sys.executable = venv/Scripts/python.exe
sp = Path(sys.executable).parent.parent / 'Lib' / 'site-packages' / 'flet'

datas = [
    # flet 包内所有资源（assets、js、native dll 等）
    (str(sp), 'flet'),
]

hiddenimports = [
    # HTTP
    'requests', 'urllib3', 'charset_normalizer', 'certifi', 'idna',
    # 剪贴板
    'pyperclip',
    # Windows 平台
    'winreg', 'ctypes',
    # flet 核心
    'flet', 'flet_runtime', 'flet_desktop', 'flet.core',
    'flet.app', 'flet.page', 'flet.controls',
    'flet.utils', 'flet.cli',
    # 第三方打包易漏
    'oauthlib', 'msgpack', 'repath', 'six', 'anyio', 'h11', 'httpcore', 'httpx',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 不要排除 tkinter — main.py 通过 `from gui import` 引入，PyInstaller
    # 会静态分析 gui.py 的 import tkinter（即便走 --flet 模式也会跟踪）
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
    name='违规检测',
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
