import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
from typing import List
from detector import DetectionResult, ScanProgress, get_available_drives, open_explorer_at

try:
    import pyperclip
except ImportError:
    pyperclip = None


class ViolationScannerGUI:
    """违规检测工具 V3 — 纯本地版"""

    def __init__(self, on_scan_callable, on_cancel_callable=None):
        self.on_scan = on_scan_callable
        self.on_cancel = on_cancel_callable
        self._results: List[DetectionResult] = []
        self._scanning = False

        self.root = tk.Tk()
        self.root.title("违规检测")
        self.root.geometry("960x720")
        self.root.resizable(True, True)
        self.root.configure(bg="#F0F0F0")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

    def _build_ui(self):
        bg = "#F0F0F0"

        top = tk.Frame(self.root, bg=bg, padx=10, pady=8)
        top.pack(fill="x")

        tk.Label(top, text="姓名:", bg=bg, font=("微软雅黑", 10)).grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(top, textvariable=self.name_var, width=22, font=("微软雅黑", 10))
        self.name_entry.grid(row=0, column=1, sticky="w", padx=5)

        btn_bar = tk.Frame(top, bg=bg)
        btn_bar.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(8, 0))

        btn_color = "#0078D7"
        btn_font_bold = ("微软雅黑", 10, "bold")

        self.start_btn = tk.Button(btn_bar, text="开始检测", command=self._start_scan,
                                   bg=btn_color, fg="white", font=btn_font_bold,
                                   width=14, height=1, cursor="hand2")
        self.start_btn.pack(side="left", padx=3)

        self.cancel_btn = tk.Button(btn_bar, text="取消", command=self._cancel_scan,
                                    state="disabled", bg=btn_color, fg="white",
                                    font=btn_font_bold, width=8, cursor="hand2")
        self.cancel_btn.pack(side="left", padx=3)

        self.copy_btn = tk.Button(btn_bar, text="复制全部路径", command=self._copy_paths,
                                  state="disabled", bg=btn_color, fg="white",
                                  font=btn_font_bold, width=12, cursor="hand2")
        self.copy_btn.pack(side="left", padx=3)

        status_bar = tk.Frame(self.root, bg="#E8E8E8", padx=10, pady=4)
        status_bar.pack(fill="x")

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(status_bar, textvariable=self.status_var, bg="#E8E8E8", font=("微软雅黑", 9)).pack(anchor="w")

        self.detail_var = tk.StringVar(value="")
        tk.Label(status_bar, textvariable=self.detail_var, bg="#E8E8E8", font=("Consolas", 9)).pack(anchor="w")

        self.progress_bar = ttk.Progressbar(status_bar, mode="indeterminate", length=400)
        self.progress_bar.pack(fill="x", pady=2)

        list_area = tk.Frame(self.root, bg=bg, padx=10, pady=5)
        list_area.pack(fill="both", expand=True)

        hdr = tk.Frame(list_area, bg="#D0D0D0")
        hdr.pack(fill="x")
        tk.Label(hdr, text="  操作", width=6, bg="#D0D0D0", font=("微软雅黑", 9, "bold"), anchor="w").pack(side="left")
        tk.Label(hdr, text="类型", width=10, bg="#D0D0D0", font=("微软雅黑", 9, "bold"), anchor="w").pack(side="left")
        tk.Label(hdr, text="文件名", width=30, bg="#D0D0D0", font=("微软雅黑", 9, "bold"), anchor="w").pack(side="left")
        tk.Label(hdr, text="路径", bg="#D0D0D0", font=("微软雅黑", 9, "bold"), anchor="w").pack(side="left", fill="x", expand=True)

        self.canvas = tk.Canvas(list_area, bg="white", height=360)
        vsb = ttk.Scrollbar(list_area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.list_inner = tk.Frame(self.canvas, bg="white")
        self.list_win = self.canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-(e.delta // 120), "units"))

        bottom = tk.Frame(self.root, bg=bg, padx=10, pady=4)
        bottom.pack(fill="x")
        tk.Label(bottom, text="⚠ 本软件只做检测，请自行考虑文件是否需要删除",
                bg=bg, fg="#D83B01", font=("微软雅黑", 9)).pack(side="left")
        tk.Label(bottom, text="开发者: xc-hjh  |  V3",
                bg=bg, fg="#666666", font=("微软雅黑", 8)).pack(side="right")

    def _get_drives(self) -> List[str]:
        return get_available_drives()

    def _start_scan(self):
        name = self.name_var.get().strip()
        if not name:
            self.name_entry.configure(bg="#FFCCCC")
            self.root.after(500, lambda: self.name_entry.configure(bg="white"))
            self.root.after(500, lambda: self.name_entry.configure(bg="#FFCCCC"))
            self.root.after(1000, lambda: self.name_entry.configure(bg="white"))
            self.status_var.set("请输入姓名")
            return
        self.name_entry.configure(bg="white")

        self._scanning = True
        self._results = []
        self._clear_list()

        self.start_btn.config(state="disabled", text="扫描中...")
        self.cancel_btn.config(state="normal")
        self.copy_btn.config(state="disabled")
        self.progress_bar.start(8)
        self.status_var.set("扫描中...")

        drives = self._get_drives()

        def run():
            try:
                results = self.on_scan(drives, self._update_progress)
                self._results = results
                self.root.after(0, lambda: self._show_results(results))
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
        speed = progress.speed
        est = progress.estimated_total
        scanned = progress.scanned_count
        found = progress.found_count
        remaining = max(0, (est - scanned) / speed) if speed > 0 else 0
        self.detail_var.set(
            f"已扫描: {scanned:,} | 发现: {found} 个 | "
            f"速度: {speed:,.0f} 文件/秒 | 已用: {int(elapsed)}秒 | 预估剩余: {int(remaining)}秒"
        )

    def _scan_done(self):
        self._scanning = False
        self.start_btn.config(state="normal", text="开始检测")
        self.cancel_btn.config(state="disabled")
        self.progress_bar.stop()
        total = len(self._results)
        self.status_var.set(f"扫描完成，发现 {total} 个违规文件")
        if total:
            self.copy_btn.config(state="normal")

    def _clear_list(self):
        for w in self.list_inner.winfo_children():
            w.destroy()

    def _show_results(self, results: List[DetectionResult]):
        self._clear_list()
        for i, r in enumerate(results):
            bg_c = "white" if i % 2 == 0 else "#F5F5F5"
            row = tk.Frame(self.list_inner, bg=bg_c)
            row.pack(fill="x")

            full = os.path.join(r.path, r.filename)
            btn = tk.Button(row, text="→", width=2,
                            command=lambda fp=full: open_explorer_at(fp),
                            bg="#0078D7", fg="white", font=("微软雅黑", 9), cursor="hand2")
            btn.pack(side="left", padx=2, pady=1)

            tk.Label(row, text=f"{r.file_type}", width=10, bg=bg_c,
                     font=("微软雅黑", 9), anchor="w").pack(side="left")
            tk.Label(row, text=r.filename[:28], width=30, bg=bg_c,
                     font=("微软雅黑", 9), anchor="w").pack(side="left")
            txt = r.path if len(r.path) < 80 else r.path[:77] + "..."
            tk.Label(row, text=txt, bg=bg_c, font=("Consolas", 8), anchor="w").pack(side="left", fill="x", expand=True)

    def _copy_paths(self):
        if not self._results:
            return
        text = "\n".join(os.path.join(r.path, r.filename) for r in self._results)
        if pyperclip:
            pyperclip.copy(text)
        else:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        self.copy_btn.config(text="已复制 ✓")
        self.root.after(2000, lambda: self.copy_btn.config(text="复制全部路径"))

    def _on_close(self):
        self._scanning = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()
