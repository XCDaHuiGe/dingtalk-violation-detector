# 钉钉违规检测工具

企业级钉钉（DingTalk）安装检测工具，用于检查终端设备是否安装了钉钉软件。

## 功能特性

- **三重检测机制**
  - 文件名关键词匹配（钉钉 / dingding / dingtalk）
  - PE 元数据识别（Windows 安装包，通过 VERSION.dll 读取 ProductName / CompanyName）
  - Info.plist 识别（macOS .app 应用包）
- **固定路径扫描** — 已知钉钉安装目录全量递归检测
- **注册表扫描** — Windows 注册表卸载项检测（可选清理）
- **自动上报** — 检测完成后自动发送企业微信报警 + 同步智能表
- **跨平台** — Windows (GUI) / macOS (CLI) / Linux (CLI)

## 版本说明

| 版本 | 入口 | UI | 说明 |
|------|------|-----|------|
| 主力版 | `main.py` | tkinter GUI | Windows 图形界面版 |
| flet 深色版 | `main.py --flet` | flet Material Design 3 | 深色主题现代 UI 版 |
| 命令行版 | `detector_cli.py` | 终端 ANSI UI | 跨平台命令行版，无 tkinter 依赖 |
| V3 封存版 | `V3/` | tkinter GUI | 历史版本，已封存 |

## 快速开始

### Windows（GUI 版）

```bash
# 双击 build.bat 或命令行执行
build.bat
# 产物在 dist/ 目录
```

### flet 深色版（推荐）

```bash
# 直接运行（需安装 flet: pip install flet）
python main.py --flet

# 或使用 -f 参数
python main.py -f
```

### macOS / Linux（命令行版）

```bash
# 方式一：直接运行（需 Python 3.8+）
python3 detector_cli.py

# 方式二：打包为独立可执行文件
bash build_mac.sh
# 产物在 dist/ 目录
```

### GitHub Actions 自动打包

推送 tag 或在 Actions 页面手动触发：

```bash
git tag v4.0
git push origin v4.0
```

打包完成后在 Actions 页面下载 `Windows-GUI` 和 `macOS-CLI` 产物。

## 命令行版界面

```
╔════════════════════════════════════════════════╗
║         钉钉违规检测工具  v4.0                  ║
║            开发者: xc-hjh                       ║
╚════════════════════════════════════════════════╝

请输入被检测人姓名: 张三

▶ 正在扫描...

  注册表检测 ......... 发现 0 项
  固定路径检测 ....... 发现 12 项
  全盘文件扫描 ....... 进行中

  ████████████████░░░░░░░░░░  54%
  已扫描: 128,430  发现: 3  速度: 12,500/s  已用: 10s

✓ 扫描完成，共发现 15 个违规项

▶ 正在上报...
  ✓ 报警已发送
  ✓ 智能表已同步

   1. 安装目录  DingDing
      /Applications/DingDing
   2. 安装程序  DingTalk
      /Applications/DingDing.app/Contents/MacOS/DingTalk
   ...
```

## 项目结构

```
├── detector.py          # 检测引擎（核心）
├── detector_cli.py      # 命令行版入口
├── gui.py               # tkinter GUI 版界面
├── flet_gui.py          # flet 深色 Material Design 3 版界面
├── main.py              # GUI 版入口
├── notifier.py          # 企业微信报警
├── smartsheet.py        # 智能表同步
├── build.bat            # Windows 打包脚本
├── build_mac.sh         # macOS 打包脚本
├── .github/workflows/   # GitHub Actions CI/CD
└── V3/                  # 封存版本
```

## 技术栈

- Python 3.8+
- tkinter（GUI 版）
- flet（深色 Material Design 3 版）
- ANSI 转义码（CLI 版终端 UI）
- PyInstaller（打包）
- Windows VERSION.dll + ctypes（PE 元数据读取）
- plistlib（macOS Info.plist 读取）

## 开发者

xc-hjh (XCDaHuiGe)

## License

MIT
