import os
import sys
import socket
from detector import HighPerfScanner, delete_to_recycle_bin
from notifier import send_notification
from smartsheet import push_results_to_smartsheet

# 根据参数选择 GUI
USE_FLET = '--flet' in sys.argv or '-f' in sys.argv

if USE_FLET:
    from flet_gui import FletGUI as GUI_CLASS
else:
    from gui import DingTalkScannerGUI as GUI_CLASS


class ScanController:
    """扫描控制器 — 统一管理扫描引擎"""

    def __init__(self):
        self.scanner = HighPerfScanner()

    def do_scan(self, drives, progress_cb):
        """执行全量检测：注册表 + 固定路径 + 文件扫描"""
        all_results = []

        # 1. 注册表预检（毫秒级）
        all_results.extend(self.scanner.scan_registry())

        # 2. 固定路径探测
        all_results.extend(self.scanner.scan_fixed_paths())

        # 3. 全盘文件扫描
        if drives:
            all_results.extend(self.scanner.scan_all_drives(drives, progress_cb))

        # 去重 + 排序
        seen = set()
        unique = []
        for r in all_results:
            key = (r.path, r.filename)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        unique.sort(key=lambda x: x.path + x.filename)
        return unique

    def clean_registry(self):
        """删除钉钉相关注册表项，返回 (删除数量, 错误列表)"""
        return self.scanner.clean_registry()

    def cancel(self):
        self.scanner.cancel()

    def delete_files(self, file_paths: list) -> list:
        """
        批量删除文件（移入回收站）。
        Returns: 失败信息列表，空列表表示全部成功。
        """
        errors = []
        for fp in file_paths:
            ok, msg = delete_to_recycle_bin(fp)
            if not ok:
                errors.append(f"{fp}: {msg}")
        return errors


def main():
    ctrl = ScanController()

    def do_notify(username, results, webhook_url):
        return send_notification(username, results, webhook_url, source_name="")

    gui = GUI_CLASS(
        on_scan_callable=ctrl.do_scan,
        on_cancel_callable=ctrl.cancel,
        on_notify_callable=do_notify,
        on_smartsheet_callable=push_results_to_smartsheet,
        on_clean_registry_callable=ctrl.clean_registry,
        on_delete_callable=ctrl.delete_files,
    )
    gui.run()


if __name__ == "__main__":
    main()
