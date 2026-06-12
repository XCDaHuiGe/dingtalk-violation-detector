import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import sys
import subprocess
from typing import List, Dict
from collections import defaultdict
from detector import DetectionResult, ScanProgress, get_available_drives, open_explorer_at

try:
    import pyperclip
except ImportError:
    pyperclip = None


class DingTalkScannerGUI:
    """钉钉违规检测工具 v4.0 - GUI"""

    COLORS = {
        "bg":       "#F5F6FA",
        "card":     "#FFFFFF",
        "primary":  "#2563EB",
        "danger":   "#DC2626",
        "success":  "#16A34A",
        "border":   "#E2E8F0",
        "text":     "#1E293B",
        "text_sec": "#64748B",
        "stripe":   "#F8FAFC",
        "header":   "#1E293B",
    }

    TREE_COLS = ("type", "name", "path", "size")

    def __init__(self, on_scan_callable, on_notify_callable,
                 on_cancel_callable=None, on_smartsheet_callable=None,
                 on_clean_registry_callable=None,
                 on_delete_callable=None):
        self.on_scan = on_scan_callable
        self.on_notify = on_notify_callable
        self.on_cancel = on_cancel_callable
        self.on_smartsheet = on_smartsheet_callable
        self.on_clean_registry = on_clean_registry_callable
        self.on_delete = on_delete_callable
        self._results: List[DetectionResult] = []
        self._scanning = False

        self.root = tk.Tk()
        self.root.title("钉钉违规检测工具 v4.0")
        self.root.geometry("1020x720")
        self.root.minsize(800, 500)
        self.root.configure(bg=self.COLORS["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._create_context_menu()

    def _build_ui(self):
        c = self.COLORS

        # ── 顶部区域 ──────────────────────────────────────────────
        top = tk.Frame(self.root, bg=c["card"], padx=16, pady=12)
        top.pack(fill="x")

        # 标题行
        title_frame = tk.Frame(top, bg=c["card"])
        title_frame.pack(fill="x", pady=(0, 8))
        tk.Label(title_frame, text="钉钉违规检测工具", bg=c["card"],
                 fg=c["text"], font=("微软雅黑", 14, "bold")).pack(side="left")
        tk.Label(title_frame, text="v4.0  xc-hjh", bg=c["card"],
                 fg=c["text_sec"], font=("微软雅黑", 9)).pack(side="left", padx=(8, 0))

        # 输入 + 按钮行
        ctrl = tk.Frame(top, bg=c["card"])
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="姓名", bg=c["card"], fg=c["text"],
                 font=("微软雅黑", 10)).pack(side="left")
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(ctrl, textvariable=self.name_var, width=18,
                                   font=("微软雅黑", 10), relief="solid", bd=1)
        self.name_entry.pack(side="left", padx=(4, 12))

        btn_font = ("微软雅黑", 9, "bold")

        self.start_btn = tk.Button(ctrl, text="开始检测", command=self._start_scan,
                                   bg=c["primary"], fg="white", font=btn_font,
                                   relief="flat", padx=12, pady=3, cursor="hand2")
        self.start_btn.pack(side="left", padx=2)

        self.cancel_btn = tk.Button(ctrl, text="取消", command=self._cancel_scan,
                                    state="disabled", bg="#94A3B8", fg="white",
                                    font=btn_font, relief="flat", padx=8, pady=3,
                                    cursor="hand2")
        self.cancel_btn.pack(side="left", padx=2)

        tk.Button(ctrl, text="复制路径", command=self._copy_paths,
                  bg="#6366F1", fg="white", font=btn_font, relief="flat",
                  padx=8, pady=3, cursor="hand2").pack(side="left", padx=2)

        tk.Button(ctrl, text="删除所选", command=self._delete_selected,
                  bg=c["danger"], fg="white", font=btn_font, relief="flat",
                  padx=8, pady=3, cursor="hand2").pack(side="left", padx=2)

        tk.Button(ctrl, text="全选", command=self._select_all,
                  bg="#64748B", fg="white", font=btn_font, relief="flat",
                  padx=6, pady=3, cursor="hand2").pack(side="left", padx=1)

        tk.Button(ctrl, text="取消全选", command=self._deselect_all,
                  bg="#94A3B8", fg="white", font=btn_font, relief="flat",
                  padx=6, pady=3, cursor="hand2").pack(side="left", padx=1)

        tk.Button(ctrl, text="清理注册表", command=self._clean_registry,
                  bg=c["danger"], fg="white", font=btn_font, relief="flat",
                  padx=8, pady=3, cursor="hand2").pack(side="right")

        # ── 状态栏 ────────────────────────────────────────────────
        status_bar = tk.Frame(self.root, bg="#EFF6FF", padx=16, pady=6)
        status_bar.pack(fill="x")

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(status_bar, textvariable=self.status_var, bg="#EFF6FF",
                 fg=c["text"], font=("微软雅黑", 9)).pack(side="left")

        self.detail_var = tk.StringVar(value="")
        tk.Label(status_bar, textvariable=self.detail_var, bg="#EFF6FF",
                 fg=c["text_sec"], font=("Consolas", 9)).pack(side="right")

        self.progress = ttk.Progressbar(self.root, mode="indeterminate", length=300)
        self.progress.pack(fill="x")

        # ── Treeview 主区域 ────────────────────────────────────────
        tree_frame = tk.Frame(self.root, bg=c["card"], padx=8, pady=8)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        # Treeview 样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="white", foreground=c["text"],
                        fieldbackground="white", font=("微软雅黑", 9), rowheight=26)
        style.configure("Treeview.Heading", background=c["header"], foreground="white",
                        font=("微软雅黑", 9, "bold"))
        style.map("Treeview", background=[("selected", c["primary"])],
                  foreground=[("selected", "white")])

        self.tree = ttk.Treeview(tree_frame, columns=self.TREE_COLS, show="tree headings",
                                 selectmode="extended")

        self.tree.heading("#0",   text="展开", anchor="w")
        self.tree.heading("type", text="类型",   anchor="w")
        self.tree.heading("name", text="文件名", anchor="w")
        self.tree.heading("path", text="路径",   anchor="w")
        self.tree.heading("size", text="大小",   anchor="e")

        self.tree.column("#0",   width=30,  minwidth=30,  stretch=False)
        self.tree.column("type", width=80,  minwidth=60,  stretch=False)
        self.tree.column("name", width=260, minwidth=120, stretch=True)
        self.tree.column("path", width=380, minwidth=100, stretch=True)
        self.tree.column("size", width=80,  minwidth=60,  stretch=False)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # ── 底部 ──────────────────────────────────────────────────
        bottom = tk.Frame(self.root, bg=c["bg"], padx=16, pady=6)
        bottom.pack(fill="x")
        tk.Label(bottom, text="删除操作移入回收站，可从回收站恢复",
                 bg=c["bg"], fg=c["text_sec"], font=("微软雅黑", 9)).pack(side="left")
        tk.Label(bottom, text="开发者: xc-hjh",
                 bg=c["bg"], fg=c["text_sec"], font=("微软雅黑", 8)).pack(side="right")

        # ── 事件绑定 ──────────────────────────────────────────────
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<Double-1>", self._on_double_click)

    # ── 右键上下文菜单 ─────────────────────────────────────────────

    def _create_context_menu(self):
        self.ctx_menu = tk.Menu(self.root, tearoff=0)
        self.ctx_menu.add_command(label="打开文件位置", command=self._open_selected_location)
        self.ctx_menu.add_command(label="删除所选文件", command=self._delete_selected)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="复制路径", command=self._copy_selected_paths)

        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Button-2>", self._show_context_menu)

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item and item not in self.tree.selection():
            self.tree.selection_set(item)
        if self.tree.selection():
            self.ctx_menu.post(event.x_root, event.y_root)

    # ── 工具方法 ───────────────────────────────────────────────────

    def _format_size(self, size: int) -> str:
        if size == 0:
            return "-"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def _get_drives(self) -> List[str]:
        return get_available_drives()

    def _get_selected_full_paths(self) -> list:
        """获取当前选中项的完整文件路径列表"""
        paths = []
        for item in self.tree.selection():
            values = self.tree.item(item, "values")
            if not values:
                continue
            _, name, path, _ = values
            items_str = self.tree.set(item, "_items")
            if items_str:
                for r in eval(items_str):
                    fp = os.path.join(r.path, r.filename)
                    if fp not in paths:
                        paths.append(fp)
            else:
                fp = os.path.join(path, name)
                if fp not in paths:
                    paths.append(fp)
        return paths

    # ── 按目录分组 ─────────────────────────────────────────────────

    def _group_results(self, results: List[DetectionResult]) -> Dict[str, List[DetectionResult]]:
        groups: Dict[str, List[DetectionResult]] = defaultdict(list)
        for r in results:
            groups[r.path].append(r)
        return groups

    def _populate_tree(self, results: List[DetectionResult]):
        """按目录分组填充 Treeview，同一目录的文件归为子节点"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        groups = self._group_results(results)

        for dir_path, items in sorted(groups.items()):
            if len(items) == 1:
                r = items[0]
                self.tree.insert("", "end", text="",
                                 values=(r.file_type, r.filename, r.path,
                                         self._format_size(r.size)),
                                 tags=("single",))
            else:
                types = set(i.file_type for i in items)
                type_label = "/".join(sorted(types))
                total_size = sum(i.size for i in items)
                dir_node = self.tree.insert(
                    "", "end", text=f"▸ {len(items)} 个文件",
                    values=(type_label, os.path.basename(dir_path) or dir_path,
                            dir_path, self._format_size(total_size)),
                    tags=("dir",))
                self.tree.set(dir_node, "_items", repr(items))

        self.tree.tag_configure("dir", background="#FEFCE8")
        self.tree.tag_configure("single", background="white")

    def _on_tree_open(self, event):
        """目录节点展开时，动态加载子文件"""
        node = self.tree.focus()
        if not node:
            return
        if self.tree.get_children(node):
            return
        items_str = self.tree.set(node, "_items")
        if not items_str:
            return
        items = eval(items_str)
        for r in items:
            self.tree.insert(node, "end", text="",
                             values=(r.file_type, r.filename, r.path,
                                     self._format_size(r.size)),
                             tags=("file",))
        self.tree.tag_configure("file", background="white")

    # ── 双击定位 ───────────────────────────────────────────────────

    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        # 目录组节点：不拦截，让 Treeview 处理展开/折叠
        if self.tree.set(item, "_items"):
            return
        values = self.tree.item(item, "values")
        if not values:
            return
        _, name, path, _ = values
        full_path = os.path.join(path, name)
        if os.path.exists(full_path):
            open_explorer_at(full_path)
        elif os.path.isdir(path):
            if sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.Popen(f'explorer "{path}"', shell=True)

    # ── 扫描流程 ───────────────────────────────────────────────────

    def _start_scan(self):
        name = self.name_var.get().strip()
        if not name:
            self.name_entry.configure(bg="#FEE2E2")
            self.root.after(600, lambda: self.name_entry.configure(bg="white"))
            self.status_var.set("请输入姓名")
            return
        self.name_entry.configure(bg="white")

        self._scanning = True
        self._results = []
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.start_btn.config(state="disabled", text="扫描中...")
        self.cancel_btn.config(state="normal")
        self.progress.start(8)
        self.status_var.set("扫描中...")

        drives = self._get_drives()

        def run():
            try:
                results = self.on_scan(drives, self._update_progress)
                self._results = results
                self.root.after(0, lambda: self._populate_tree(results))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"扫描失败: {e}"))
            finally:
                self.root.after(0, self._scan_done)

        threading.Thread(target=run, daemon=True).start()

    def _cancel_scan(self):
        self._scanning = False
        if self.on_cancel:
            self.on_cancel()
        self.status_var.set("已取消")

    def _update_progress(self, progress: ScanProgress):
        if not self._scanning:
            return
        elapsed = time.time() - progress.start_time
        scanned = progress.scanned_count
        found = progress.found_count
        self.detail_var.set(
            f"已扫描: {scanned:,} | 发现: {found} | "
            f"速度: {progress.speed:,.0f}/s | 已用: {int(elapsed)}s"
        )

    def _scan_done(self):
        self._scanning = False
        self.start_btn.config(state="normal", text="开始检测")
        self.cancel_btn.config(state="disabled")
        self.progress.stop()
        total = len(self._results)
        groups = len(self._group_results(self._results))
        self.status_var.set(f"扫描完成，发现 {total} 个违规文件（{groups} 个目录）")
        if total:
            self._auto_notify()

    # ── 自动上报 ───────────────────────────────────────────────────

    def _auto_notify(self):
        name = self.name_var.get().strip()
        self.status_var.set(f"扫描完成，发现 {len(self._results)} 个违规文件 — 正在上报...")

        def _send():
            result = self.on_notify(name, self._results, "")
            self.root.after(0, self._notify_done, result)

        def _push():
            result = self.on_smartsheet(name, self._results, "") if self.on_smartsheet else {"success": True}
            self.root.after(0, self._sheet_done, result)

        threading.Thread(target=_send, daemon=True).start()
        threading.Thread(target=_push, daemon=True).start()

    def _notify_done(self, r):
        tag = "报警已发送 ✓" if r.get("success") else f"报警失败: {r.get('message','')}"
        self.status_var.set(f"{self.status_var.get().split('—')[0].strip()} — {tag}")

    def _sheet_done(self, r):
        tag = "智能表已同步 ✓" if r.get("success") else f"智能表失败: {r.get('message','')}"
        self.status_var.set(f"{self.status_var.get()} ; {tag}")

    # ── 删除功能 ───────────────────────────────────────────────────

    def _delete_selected(self):
        if not self.on_delete:
            messagebox.showwarning("提示", "删除功能未启用")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选中要删除的文件")
            return

        files_to_delete = []
        nodes_to_remove = []

        for item in selected:
            values = self.tree.item(item, "values")
            if not values:
                continue
            _, name, path, _ = values

            items_str = self.tree.set(item, "_items")
            if items_str:
                items = eval(items_str)
                for r in items:
                    fp = os.path.join(r.path, r.filename)
                    if fp not in files_to_delete:
                        files_to_delete.append(fp)
                nodes_to_remove.append(item)
            else:
                fp = os.path.join(path, name)
                if fp not in files_to_delete:
                    files_to_delete.append(fp)
                nodes_to_remove.append(item)

        if not files_to_delete:
            return

        count = len(files_to_delete)
        if not messagebox.askyesno("确认删除",
                f"确定要将 {count} 个文件移入回收站吗？\n\n此操作可从回收站恢复。"):
            return

        def _do():
            errors = self.on_delete(files_to_delete)
            self.root.after(0, self._delete_done, files_to_delete, errors, nodes_to_remove)

        threading.Thread(target=_do, daemon=True).start()

    def _delete_done(self, file_paths, errors, nodes_to_remove):
        for node in nodes_to_remove:
            try:
                self.tree.delete(node)
            except tk.TclError:
                pass

        deleted_set = set(file_paths)
        self._results = [r for r in self._results
                         if os.path.join(r.path, r.filename) not in deleted_set]

        total = len(self._results)
        success_count = len(file_paths) - len(errors)

        if errors:
            msg = f"已删除 {success_count} 个文件，{len(errors)} 个失败"
            if len(errors) <= 3:
                msg += "\n\n" + "\n".join(errors)
            messagebox.showwarning("删除完成", msg)
            self.status_var.set(f"删除完成: 成功 {success_count}, 失败 {len(errors)}, 剩余 {total}")
        else:
            self.status_var.set(f"已成功删除 {success_count} 个文件，剩余 {total} 个违规项")

    # ── 全选 / 取消全选 ────────────────────────────────────────────

    def _select_all(self):
        all_items = self.tree.get_children("")
        if all_items:
            self.tree.selection_set(all_items)

    def _deselect_all(self):
        self.tree.selection_remove(*self.tree.selection())

    # ── 右键菜单动作 ───────────────────────────────────────────────

    def _open_selected_location(self):
        paths = self._get_selected_full_paths()
        for fp in paths[:5]:  # 最多打开5个
            if os.path.exists(fp):
                open_explorer_at(fp)

    def _copy_selected_paths(self):
        paths = self._get_selected_full_paths()
        if not paths:
            return
        text = "\n".join(paths)
        if pyperclip:
            pyperclip.copy(text)
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        self.status_var.set(f"已复制 {len(paths)} 条路径到剪贴板")

    # ── 复制全部路径 ───────────────────────────────────────────────

    def _copy_paths(self):
        if not self._results:
            return
        text = "\n".join(os.path.join(r.path, r.filename) for r in self._results)
        if pyperclip:
            pyperclip.copy(text)
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        messagebox.showinfo("已复制", f"已复制 {len(self._results)} 条路径到剪贴板")

    # ── 清理注册表 ─────────────────────────────────────────────────

    def _clean_registry(self):
        if not self.on_clean_registry:
            messagebox.showwarning("提示", "该功能未启用")
            return
        if not messagebox.askyesno("确认", "将删除注册表中所有钉钉相关安装记录，不可撤销。\n是否继续？"):
            return

        def _do():
            deleted, errors = self.on_clean_registry()
            self.root.after(0, self._clean_done, deleted, errors)

        threading.Thread(target=_do, daemon=True).start()

    def _clean_done(self, deleted, errors):
        msg = f"已删除 {deleted} 个钉钉相关注册表项。"
        if errors:
            msg += "\n\n失败项:\n" + "\n".join(errors)
        messagebox.showinfo("清理完成", msg)

    def _on_close(self):
        self._scanning = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()
