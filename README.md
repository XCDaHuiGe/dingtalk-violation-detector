# 钉钉违规检测工具

企业级终端违规软件安装检测工具，用于检查设备是否安装了钉钉等违规软件，检测完成后自动上报至企业微信和智能表。

## 🚀 功能特性

- **三重检测机制**
  - 文件名关键词匹配（钉钉 / dingding / dingtalk）
  - Windows PE 元数据识别（读取 ProductName / CompanyName）
  - macOS Info.plist 识别
- **智能扫描** — 注册表 + 固定路径 + 全盘递归（支持并行扫描）
- **自动上报** — 检测到违规后自动通过 IP 定位城市，上报企业微信 Webhook + 智能表
- **误报过滤** — 排除 kingsoft/wps 目录、图片/日志等噪声文件
- **回收站删除** — 可恢复的文件清理

## 📦 版本说明

| 版本 | 技术栈 | 入口 | 说明 |
|------|--------|------|------|
| **V6 Rust 版** ⭐ | Rust + Tauri 2 + React + TypeScript | `rscanner/target/release/*.exe` | **推荐**。高性能桌面应用，单 exe 无依赖 |
| flet 深色版 | Python + flet | `main_flet.py` | Material Design 3 风格 GUI |
| tkinter GUI 版 | Python + tkinter | `main.py` | 经典 Windows 图形界面 |
| 命令行版 | Python | `detector_cli.py` | 跨平台 CLI，无 GUI 依赖 |

## ⚡ 快速开始

### V6 Rust 版（推荐）

```bash
# 环境要求：Rust 1.70+、Node.js 18+
cd rscanner
npm install
cargo tauri build          # 产物在 target/release/*.exe

# 开发模式（热重载）
cargo tauri dev
```

**单文件部署：** 编译产物可直接双击运行，无需安装任何运行时。

### Python flet 版

```bash
pip install flet
python main_flet.py
```

### Python 命令行版

```bash
python detector_cli.py
```

## 🖥️ V6 Rust 版操作流程

```
输入姓名 → 点击开始 → 三阶段自动扫描 → 查看结果 → 自动上报
```

### 扫描阶段

| 阶段 | 说明 | 耗时 |
|------|------|------|
| 🔍 注册表扫描 | 检查 Windows 安装记录 | < 1s |
| 📁 固定路径扫描 | Program Files、AppData 等 | 1-3s |
| 💽 全盘扫描 | 所有磁盘分区递归检测 | 视磁盘大小 |

### 自动上报

检测到违规后自动执行：

1. 通过 IP 获取当前城市位置
2. 发送 Markdown 格式企业微信报告
3. 同步智能表记录（含人员、主机、位置、时间、数量）

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+A` | 全选结果 |
| `Delete` | 移至回收站 |
| 右键菜单 | 资源管理器打开 / 复制路径 |

## 📁 项目结构

```
违规检测/
├── rscanner/                    # ⭐ V6 Rust + Tauri 版
│   ├── src-tauri/               # Rust 后端
│   │   ├── src/lib.rs           # 8 个 Tauri IPC 命令
│   │   └── Cargo.toml
│   ├── crates/
│   │   ├── scanner-core/        # 检测引擎（879 行 Rust）
│   │   │   ├── src/scanner.rs   # 注册表 + 路径 + 全盘扫描
│   │   │   └── src/types.rs     # 类型定义
│   │   └── notifier/            # 上报模块
│   │       └── src/lib.rs       # 企业微信 + 智能表 + IP 定位
│   ├── src/                     # React 前端
│   │   ├── App.tsx              # 主界面（自动上报逻辑）
│   │   └── components/          # 8 个 UI 组件
│   ├── docs/                    # 📖 使用说明书
│   ├── tauri.conf.json
│   └── package.json
├── detector.py                  # Python 检测引擎
├── detector_cli.py              # Python CLI 版
├── gui.py                       # tkinter GUI
├── flet_gui.py                  # flet 深色版 v6.0
├── main.py                      # Python 主入口
├── main_flet.py                 # flet 版主入口
├── notifier.py                  # 企业微信报警
├── smartsheet.py                # 智能表同步
├── build.bat                    # Windows 打包
├── build_mac.sh                 # macOS 打包
├── .github/workflows/build.yml  # GitHub Actions CI
└── V3/                          # 历史版本（已封存）
```

## 🏗️ 技术栈

### V6 Rust 版

| 层级 | 技术 |
|------|------|
| 后端引擎 | Rust + rayon（并行扫描）+ walkdir |
| 桌面框架 | Tauri 2.11 |
| 前端 UI | React 18 + TypeScript + Vite + Tailwind CSS |
| 网络请求 | ureq（企业微信/智能表/IP 定位） |
| 打包 | `cargo tauri build` → 单 exe（约 11MB） |

### Python 版

| 层级 | 技术 |
|------|------|
| 后端引擎 | Python 3.8+ + ctypes + ThreadPoolExecutor |
| GUI | tkinter / flet 0.85 |
| 打包 | PyInstaller |
| 跨平台 | Windows (GUI) / macOS / Linux (CLI) |

## 🔧 Tauri IPC 命令列表

| 命令 | 功能 |
|------|------|
| `start_scan` | 启动后台三阶段扫描 |
| `cancel_scan` | 取消扫描 |
| `get_drives` | 获取可用磁盘分区 |
| `delete_files` | 删除文件至回收站 |
| `clean_registry` | 清理注册表 |
| `open_in_explorer` | 在资源管理器中打开 |
| `get_city_from_ip` | 通过 IP 获取城市（5s 超时） |
| `send_report` | 上报结果（微信 + 智能表独立执行） |

## 📖 文档

- `rscanner/docs/使用说明书.html` — 完整图文使用说明（浏览器打开）
- `rscanner/docs/使用说明.md` — Markdown 版说明
- `rscanner/docs/图片生成提示词.md` — 配套图片生成提示词
- `rscanner/PROGRESS.md` — Rust 重构进度报告

## 🚢 GitHub Actions 自动打包

```bash
git tag v6.0
git push origin v6.0
```

Actions 自动构建并在 Releases 页面生成产物。

## 👨‍💻 开发者

xc-hjh (XCDaHuiGe)

## 📄 License

MIT
