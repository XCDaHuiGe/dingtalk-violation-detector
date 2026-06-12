#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钉钉违规检测工具 - 命令行版 (跨平台，无 tkinter 依赖)"""
import os, sys, time, subprocess, threading
from typing import List
from detector import HighPerfScanner, DetectionResult, ScanProgress, get_available_drives
from notifier import send_notification
from smartsheet import push_results_to_smartsheet

IS_WIN = sys.platform == "win32"

# ── 启用 Windows ANSI + 修复编码 ──────────────────────────────────
if IS_WIN:
    try:
        import ctypes as _ct
        _ct.windll.kernel32.SetConsoleMode(_ct.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── ANSI 颜色 ──────────────────────────────────────────────────────
R = "\033[0m"; B = "\033[1m"; D = "\033[2m"
RED = "\033[91m"; GRN = "\033[92m"; YEL = "\033[93m"; CYN = "\033[96m"

def _clear():
    os.system("cls" if IS_WIN else "clear")

def _trunc(s, n):
    return s if len(s) <= n else s[:n-1] + "…"

def _copy_clipboard(text):
    try:
        if sys.platform == "darwin":
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(text.encode())
        elif IS_WIN:
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-16-le"))
        else:
            subprocess.run(["xclip","-selection","clipboard"], input=text.encode(), check=True)
        return True
    except Exception:
        return False

def _open_location(path):
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", path])
        elif IS_WIN:
            subprocess.run(f'explorer /select,"{path}"', shell=True)
        else:
            subprocess.run(["xdg-open", os.path.dirname(path)])
    except Exception:
        pass

# ── 主程序 ─────────────────────────────────────────────────────────
class CLIApp:
    def __init__(self):
        self.scanner = HighPerfScanner()
        self.results: List[DetectionResult] = []
        self.name = ""

    def run(self):
        _clear()
        print(f"{CYN}╔{'═'*48}╗{R}")
        print(f"{CYN}║{R}{B}     钉钉违规检测工具  v4.0{R}                 {CYN}║{R}")
        print(f"{CYN}║{R}{D}        开发者: xc-hjh{R}                       {CYN}║{R}")
        print(f"{CYN}╚{'═'*48}╝{R}\n")

        while True:
            try:
                self.name = input(f"{B}请输入被检测人姓名:{R} ").strip()
            except (EOFError, KeyboardInterrupt):
                print(); return
            if self.name:
                break
            print(f"  {RED}姓名不能为空，请重新输入{R}")

        self._scan()

    # ── 扫描 ───────────────────────────────────────────────────────
    def _scan(self):
        print(f"\n{B}▶ 正在扫描...{R}\n")
        all_res: List[DetectionResult] = []

        # 注册表
        if IS_WIN:
            print(f"  注册表检测 ......... ", end="", flush=True)
            r = self.scanner.scan_registry()
            all_res.extend(r)
            print(f"发现 {YEL}{len(r)}{R} 项")
        else:
            print(f"  注册表检测 ......... {D}跳过 (非Windows){R}")

        # 固定路径
        print(f"  固定路径检测 ....... ", end="", flush=True)
        r = self.scanner.scan_fixed_paths()
        all_res.extend(r)
        print(f"发现 {YEL}{len(r)}{R} 项")

        # 全盘
        print(f"  全盘文件扫描 ....... 进行中\n")
        drives = get_available_drives()
        self._done = False

        def _prog(p: ScanProgress):
            if self._done: return
            el = time.time() - p.start_time
            sp = p.speed; sc = p.scanned_count; fc = p.found_count
            est = p.estimated_total
            pct = min(99, sc/est*100) if est > 0 else 0
            rem = max(0, (est-sc)/sp) if sp > 0 else 0
            filled = int(30*pct/100)
            bar = f"{GRN}{'█'*filled}{'░'*(30-filled)}{R}"
            sys.stdout.write(
                f"\r  {bar}  {pct:.0f}%"
                f"  已扫描:{sc:,} 发现:{YEL}{fc}{R}"
                f" 速度:{sp:,.0f}/s 已用:{int(el)}s 剩余:~{int(rem)}s\033[K"
            ); sys.stdout.flush()

        def _work():
            try:
                res = self.scanner.scan_all_drives(drives, _prog)
                all_res.extend(res)
            except Exception as e:
                print(f"\n  {RED}扫描出错: {e}{R}")
            finally:
                self._done = True

        t = threading.Thread(target=_work, daemon=True)
        t.start()
        try:
            while not self._done:
                time.sleep(0.3)
        except KeyboardInterrupt:
            self.scanner.cancel()
            print(f"\n  {YEL}已取消扫描{R}")
            return

        t.join()
        print(f"\r  {'█'*30}  100%  扫描完成{' '*50}")

        # 去重
        seen = set()
        unique = []
        for r in all_res:
            k = (r.path, r.filename)
            if k not in seen:
                seen.add(k); unique.append(r)
        unique.sort(key=lambda x: x.path + x.filename)
        self.results = unique

        total = len(self.results)
        print(f"\n{B}{'✓' if total else '✓'} 扫描完成，共发现 {YEL}{total}{R} 个违规项{R}")

        if total == 0:
            print(f"\n  {GRN}未发现违规软件，该设备安全。{R}")
            # 无违规也上报
            self._auto_report()
            return

        # ── 有违规：立即上报 ────────────────────────────────────
        self._auto_report()

        # ── 展示结果 ────────────────────────────────────────────
        self._show_results()
        self._menu()

    # ── 自动上报 ───────────────────────────────────────────────────
    def _auto_report(self):
        print(f"\n{B}▶ 正在上报...{R}")

        def _notify():
            r = send_notification(self.name, self.results, source_name="CLI")
            tag = f"{GRN}✓ 报警已发送{R}" if r.get("success") else f"{RED}✗ 报警发送失败: {r.get('message','')}{R}"
            print(f"  {tag}")

        def _sheet():
            r = push_results_to_smartsheet(self.name, self.results)
            tag = f"{GRN}✓ 智能表已同步{R}" if r.get("success") else f"{RED}✗ 智能表失败: {r.get('message','')}{R}"
            print(f"  {tag}")

        t1 = threading.Thread(target=_notify, daemon=True)
        t2 = threading.Thread(target=_sheet, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=15); t2.join(timeout=15)

    # ── 结果表格 ───────────────────────────────────────────────────
    def _show_results(self):
        if not self.results:
            return
        print()
        for i, r in enumerate(self.results, 1):
            full = os.path.join(r.path, r.filename)
            print(f"  {YEL}{i:>2}.{R} {B}{r.file_type:<8}{R} {_trunc(r.filename, 35)}")
            print(f"      {D}{full}{R}")

    # ── 操作菜单 ───────────────────────────────────────────────────
    def _menu(self):
        while True:
            print(f"\n{B}┌─ 操作菜单 ─────────────────────┐{R}")
            print(f"│  {CYN}[1]{R} 复制所有违规路径            │")
            print(f"│  {CYN}[2]{R} 在文件管理器中定位文件      │")
            print(f"│  {CYN}[3]{R} 重新扫描                    │")
            print(f"│  {CYN}[0]{R} 退出                        │")
            print(f"{B}└─────────────────────────────────┘{R}")
            try:
                ch = input(f"请选择 [0-3]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print(); return

            if ch == "1":
                txt = "\n".join(os.path.join(r.path, r.filename) for r in self.results)
                if _copy_clipboard(txt):
                    print(f"  {GRN}✓ 已复制 {len(self.results)} 条路径到剪贴板{R}")
                else:
                    print(f"  {RED}✗ 复制失败，路径如下:{R}")
                    print(txt)
            elif ch == "2":
                try:
                    idx = int(input(f"  输入序号 [1-{len(self.results)}]: ")) - 1
                    if 0 <= idx < len(self.results):
                        r = self.results[idx]
                        _open_location(os.path.join(r.path, r.filename))
                        print(f"  {GRN}✓ 已定位: {r.filename}{R}")
                    else:
                        print(f"  {RED}序号无效{R}")
                except (ValueError, EOFError):
                    print(f"  {RED}输入无效{R}")
            elif ch == "3":
                self._scan()
                return
            elif ch == "0":
                print(f"\n{D}检测完毕，再见。{R}\n")
                return

if __name__ == "__main__":
    CLIApp().run()
