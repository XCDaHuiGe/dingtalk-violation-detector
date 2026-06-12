import os
import socket
from detector import HighPerfScanner
from notifier import send_notification
from smartsheet import push_results_to_smartsheet
from gui import DingTalkScannerGUI


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


def main():
    ctrl = ScanController()

    def do_notify(username, results, webhook_url):
        return send_notification(username, results, webhook_url, source_name="")

    gui = DingTalkScannerGUI(
        on_scan_callable=ctrl.do_scan,
        on_cancel_callable=ctrl.cancel,
        on_notify_callable=do_notify,
        on_smartsheet_callable=push_results_to_smartsheet,
        on_clean_registry_callable=ctrl.clean_registry,
    )
    gui.run()


if __name__ == "__main__":
    main()
