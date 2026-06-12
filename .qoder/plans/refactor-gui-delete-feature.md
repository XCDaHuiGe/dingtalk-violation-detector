# 钉钉违规检测工具重构方案

## Context

用户需要 Windows GUI 版具备"方便删除违规文件"的能力，当前 GUI 只能查看不能删除。同时去掉不需要的 CSV 导出功能。Mac CLI 版保持稳定，仅新增删除选项。

## 改动概览

| 文件 | 改动幅度 | 说明 |
|------|----------|------|
| `detector.py` | **小** +40行 | 末尾追加 `delete_to_recycle_bin()` |
| `main.py` | **小** +17行 | 新增 `delete_files()` + 传入回调 |
| `gui.py` | **大** 净+135行 | 删CSV、加删除/右键菜单/双击/全选 |
| `detector_cli.py` | **中** +79行 | 菜单新增删除指定/删除全部 |
| 其他文件 | 不动 | notifier/smartsheet/build/CI |

---

## Task 1: detector.py — 恢复回收站删除功能

文件末尾 `open_explorer_at()` 之后追加 `delete_to_recycle_bin(file_path)` 函数：

- 使用 `ctypes.windll.shell32.SHFileOperationW` + `FOF_ALLOWUNDO` 移入回收站
- 参数: 单个文件路径
- 返回: `(success: bool, error_msg: str)`
- 失败处理: 文件不存在、权限不足、非Windows

---

## Task 2: main.py — 新增删除回调

1. `ScanController` 新增 `delete_files(file_paths: list) -> list` 方法
   - 遍历路径列表调用 `delete_to_recycle_bin()`
   - 返回失败信息列表
2. `main()` 中 GUI 构造新增 `on_delete_callable=ctrl.delete_files`

---

## Task 3: gui.py — 核心重构

### 3a: 删除不需要的功能
- 移除 `import csv`, `from tkinter import filedialog`
- 移除 "导出CSV" 按钮（第98-100行）
- 移除 `_export_csv()` 方法（第338-358行）

### 3b: 新增 import
- `import sys, subprocess`（双击定位用）

### 3c: 构造函数新增参数
```python
on_delete_callable=None  # 新增，默认None，向后兼容
```

### 3d: 工具栏改造
按钮顺序: `[开始检测] [取消] [复制路径] [删除所选] [全选] [取消全选]    [清理注册表]`

- "删除所选" 红色背景，调用 `_delete_selected()`
- "全选"/"取消全选" 灰色背景

### 3e: 右键上下文菜单
菜单项: `打开文件位置 | 删除所选文件 | --- | 复制路径`

- `<Button-3>` Windows右键 / `<Button-2>` macOS右键
- 右键时自动选中点击行

### 3f: 双击定位
- `<Double-1>` 绑定 `_on_double_click`
- 叶子节点 → `open_explorer_at()` 打开资源管理器
- 目录组节点 → 不拦截，让Treeview处理展开/折叠

### 3g: 删除核心逻辑
`_delete_selected()`:
1. 收集选中节点的文件路径（目录组节点展开收集子文件）
2. 确认对话框："确定将 N 个文件移入回收站？"
3. 后台线程执行删除（避免UI卡顿）
4. `_delete_done()` 回调：从Treeview移除 + 从`_results`列表移除 + 更新状态栏

### 3h: 全选/取消全选
- `_select_all()`: `self.tree.selection_set(self.tree.get_children(""))`
- `_deselect_all()`: `self.tree.selection_remove(...)`

---

## Task 4: detector_cli.py — 菜单新增删除

### 菜单变更
```
[1] 复制所有违规路径
[2] 在文件管理器中定位文件
[3] 删除指定序号文件（移入回收站）  ← 新增
[4] 删除全部违规文件（移入回收站）  ← 新增
[5] 导出全部结果到 CSV
[6] 重新扫描
[0] 退出
```

### 新增方法
- `_delete_by_index()`: 输入序号（逗号分隔）→ 二次确认 → 逐个删除 → 从列表移除
- `_delete_all()`: 二次确认 → 删除全部 → 保留失败项

CLI版保留CSV导出（管理员可能需要）。

---

## Task 5: 提交 + 推送 + 验证

1. `git add -A && git commit && git push`
2. 验证 Actions 打包通过
3. 功能测试矩阵:

| 测试项 | 预期 |
|--------|------|
| 删除单文件 | 移入回收站，从列表消失 |
| 批量删除 | Ctrl多选后一键删除 |
| 删除目录组 | 整组文件全部删除 |
| 右键→打开位置 | 资源管理器定位 |
| 右键→删除 | 确认后删除 |
| 双击文件 | 资源管理器定位 |
| 双击目录组 | 展开/折叠 |
| CSV按钮已移除 | 工具栏无该按钮 |
| CLI菜单3/4 | 删除功能正常 |

---

## 注意事项

1. 删除操作使用回收站（`FOF_ALLOWUNDO`），用户可从回收站恢复
2. 目录组节点删除时，确认框显示实际文件数量
3. 权限不足的文件（如 `C:\Program Files\` 下）删除会失败，给出明确提示
4. macOS CLI 删除功能运行时检查平台，非Windows提示不支持
5. PyInstaller 打包无需改动（`shell32.dll` 通过 ctypes 自动收集）
