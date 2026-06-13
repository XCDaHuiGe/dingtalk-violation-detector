# Rust 重构进度报告

## 完成状态

| 模块 | 状态 | 说明 |
|------|------|------|
| **scanner-core** | ✅ **完成** | 编译通过，10/10 单元测试通过 |
| **notifier** | ✅ **完成** | 编译通过 |
| **前端 (React + Vite + TS)** | ✅ **完成** | TypeScript 编译通过，Vite build 成功 |
| **Tauri 集成** | ❌ 阻塞 | 网络问题无法下载 tauri 依赖 |
| **Windows 本地打包** | ❌ 待办 | 需先解决 Tauri 编译 |

## 项目结构

```
rscanner/
├── Cargo.toml                     # 工作区
├── Cargo.lock
├── package.json                   # 前端依赖
├── vite.config.ts                 # Vite 配置
├── tsconfig.json / tsconfig.node.json
├── tailwind.config.js / postcss.config.js
├── index.html                     # 入口 HTML
│
├── crates/
│   ├── scanner-core/              # 检测引擎
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs             # 模块导出
│   │       ├── types.rs           # DetectionResult, ScanProgress, ScanPhase, 事件类型
│   │       └── scanner.rs         # Scanner 结构体 + 全部检测逻辑
│   │
│   └── notifier/                  # 企业微信上报
│       ├── Cargo.toml
│       └── src/lib.rs             # send_notification, push_results_to_smartsheet
│
├── src-tauri/                     # Tauri 桌面壳
│   ├── Cargo.toml
│   ├── tauri.conf.json            # 窗口配置 1200x780
│   ├── build.rs
│   └── src/
│       ├── main.rs                # 入口 (windows_subsystem)
│       └── lib.rs                 # Tauri commands: start_scan, cancel_scan, get_drives, delete_files, clean_registry, open_in_explorer, send_report
│
└── src/                           # React 前端
    ├── main.tsx / index.css / vite-env.d.ts
    ├── App.tsx                    # 主应用 (状态管理 + 事件监听)
    └── components/
        ├── NameInput.tsx          # 被检测人姓名输入
        ├── ActionBar.tsx          # 工具栏 (开始/取消/删除/全选/复制/清理注册表/上报)
        ├── StatsPanel.tsx         # 扫描统计数据 (已扫描/发现数/速度/用时)
        ├── PhaseProgress.tsx      # 三阶段进度条 (注册表→固定路径→全盘)
        ├── ResultTree.tsx         # 结果树视图 (目录分组+复选框+路径双击打开)
        ├── Sidebar.tsx            # 侧边栏 (统计数据+运行日志+快捷键提示)
        ├── StatusBar.tsx          # 底部状态栏
        └── ContextMenu.tsx        # 右键菜单

dist/                              # Vite 构建产物
```

## scanner-core 检测能力

| 功能 | 实现方式 | 平台 |
|------|---------|------|
| 关键词匹配 | 包含"钉钉"/"dingding"/"dingtalk" | 跨平台 |
| 误报过滤 | kingsoft/wps 路径 + 噪声扩展名 (.svg/.ico/.png 等) | 跨平台 |
| PE 元数据识别 | 通过 `GetFileVersionInfoW` + `VerQueryValueW` 读取 ProductName/CompanyName | Windows |
| 注册表扫描 | `winreg` crate 读取 HKLM/HKCU 卸载路径 DisplayName | Windows |
| 注册表清理 | `winreg::RegKey::delete_subkey` | Windows |
| 固定路径扫描 | 检查已知安装目录 + 递归子文件 | Windows/macOS |
| 全盘扫描 | `walkdir` + `rayon` 并行多驱动器 | 跨平台 |
| 文件分类 | 按扩展名分为安装程序/文档/视频/音频等 12 类 | 跨平台 |
| 回车站删除 | `SHFileOperationW` (FFI) | Windows |
| 资源管理器打开 | `explorer /select,` (FFI) | Windows |
| 并行扫描 | `rayon::par_iter` 多驱动器并行 | 跨平台 |
| 进度回调 | `crossbeam_channel` 异步进度推送 | 跨平台 |
| 取消机制 | `Arc<AtomicBool>` 共享取消标志 | 跨平台 |

## 已知问题

1. **网络阻塞**: 无法在本地下载 `tauri` / `tauri-build` 等大型 crate (crates.io API 被限)
   - **解决方案**: 在有梯子的环境执行 `cargo check -p rscanner`
   - 或使用 `cargo vendor` 提前下载依赖
2. **Tauri 调试**: Tauri 的 DevTools 需在运行时打开 (F12)
3. **Windows 打包**: `cargo tauri build` 会产出 MSI 安装包

## 下一步 (交接清单)

### 给接手人的命令

```bash
# 1. 编译检测引擎和测试
cd rscanner
cargo test -p scanner-core          # 应 10/10 通过

# 2. 编译前端
npm install && npx vite build       # 应成功

# 3. 安装 Tauri CLI 并编译桌面应用
cargo install tauri-cli --version "^2"
cargo tauri build                   # 产出去 dist/ 和 src-tauri/target/release/

# 4. 运行开发模式
cargo tauri dev                     # 自动启动前端 dev server + 后端
```

### 代码关键位置

| 文件 | 作用 |
|------|------|
| `crates/scanner-core/src/scanner.rs:131` | `Scanner` 结构体，核心检测逻辑入口 |
| `crates/scanner-core/src/scanner.rs:213` | `is_dingtalk_exe` — PE 元数据解析 (Windows FFI) |
| `crates/scanner-core/src/scanner.rs:332` | `scan_registry` — 注册表扫描 |
| `crates/scanner-core/src/scanner.rs:408` | `scan_fixed_paths` — 固定路径扫描 |
| `crates/scanner-core/src/scanner.rs:444` | `run_scan` — 三阶段扫描编排 |
| `src-tauri/src/lib.rs:20` | `start_scan` — 后台扫描线程 + Tauri 事件推送 |
| `src/App.tsx:50` | 前端事件监听 (progress/phase/complete) |
| `src/components/ResultTree.tsx` | 结果树视图渲染 |
