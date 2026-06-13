"""Flet 版主入口 — 默认启动 flet 深色 GUI。

打包: pyinstaller flet.spec
产物: dist/违规检测_flet.exe
"""
import os
import sys
import time
import socket
from detector import HighPerfScanner, delete_to_recycle_bin, get_available_drives, ScanProgress
from notifier import send_notification
from smartsheet import push_results_to_smartsheet

# 默认走 flet（区别于 main.py 的 tkinter 默认）
from flet_gui import FletGUI as GUI_CLASS


class ScanController:
    """扫描控制器 — 统一管理扫描引擎"""

    def __init__(self):
        self.scanner = HighPerfScanner()

    def do_scan(self, drives, progress_cb, stage_cb=None):
        """执行全量检测：注册表 + 固定路径 + 文件扫描"""
        all_results = []

        def stage1_callback():
            """注册表扫描阶段完成"""
            if stage_cb:
                stage_cb(f"✓ 注册表扫描完成, 找到 {len(all_results)} 个")

        # 阶段 1: 注册表扫描
        if stage_cb:
            stage_cb("→ 阶段 1/3: 扫描注册表...")
        registry_results = self.scanner.scan_registry(
            lambda msg: stage_cb(f"  {msg}") if stage_cb else None
        )
        all_results.extend(registry_results)
        stage1_callback()

        # 阶段 2: 固定路径扫描
        if stage_cb:
            stage_cb(f"→ 阶段 2/3: 扫描固定路径 (累计 {len(all_results)} 个)...")
        fixed_results = self.scanner.scan_fixed_paths()
        all_results.extend(fixed_results)

        # 阶段 3: 全盘文件扫描
        if stage_cb:
            stage_cb(f"→ 阶段 3/3: 全盘文件扫描 (累计 {len(all_results)} 个)...")
        deep_results = self.scanner.scan_drives_deep(
            drives, progress_cb=progress_cb
        )
        all_results.extend(deep_results)

        # 去重
        seen = set()
        unique = []
        for r in all_results:
            key = (r.path.lower(), r.filename.lower())
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique


def main():
    """主入口 - 启动 flet GUI"""
    controller = ScanController()

    def on_scan(drives, progress_cb, stage_cb):
        return controller.do_scan(drives, progress_cb, stage_cb)

    def on_delete(file_paths):
        return controller.scanner.delete_files(file_paths)

    def on_cancel():
        controller.scanner.cancel()

    drives = get_available_drives()
    if not drives:
        # 走 GUI 错误对话框而非 print（exe 模式 console=False 无 stdout）
        import flet as ft
        def _err_dlg(page: ft.Page):
            page.title = "启动失败"
            page.add(ft.Text("未检测到任何驱动器", size=16))
            page.add(ft.Text("请检查磁盘是否连接正常", size=12))
            page.update()
        ft.app(target=_err_dlg)
        sys.exit(1)

    app = GUI_CLASS(
        on_scan=on_scan,
        on_delete=on_delete,
        on_cancel=on_cancel,
    )
    app.run()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # 写 stderr（console=False 时不可见但可重定向到日志文件）
        import traceback
        with open("crash.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {e}\n")
            traceback.print_exc(file=f)
        raise
