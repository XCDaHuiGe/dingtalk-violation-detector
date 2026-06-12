from detector import HighPerfScanner
from gui import ViolationScannerGUI


class ScanController:
    """扫描控制器"""

    def __init__(self):
        self.scanner = HighPerfScanner()

    def do_scan(self, drives, progress_cb):
        """执行全量检测：注册表 + 固定路径 + 文件扫描"""
        all_results = []
        all_results.extend(self.scanner.scan_registry())
        all_results.extend(self.scanner.scan_fixed_paths())
        if drives:
            all_results.extend(self.scanner.scan_all_drives(drives, progress_cb))

        seen = set()
        unique = []
        for r in all_results:
            key = (r.path, r.filename)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        unique.sort(key=lambda x: x.path + x.filename)
        return unique

    def cancel(self):
        self.scanner.cancel()


def main():
    ctrl = ScanController()

    gui = ViolationScannerGUI(
        on_scan_callable=ctrl.do_scan,
        on_cancel_callable=ctrl.cancel,
    )
    gui.run()


if __name__ == "__main__":
    main()
