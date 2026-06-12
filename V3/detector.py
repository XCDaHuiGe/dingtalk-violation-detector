import os
import sys
import time
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Tuple, Callable, Optional
from dataclasses import dataclass, field
from threading import Lock

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

if IS_WINDOWS:
    import winreg
    import ctypes


@dataclass
class DetectionResult:
    file_type: str
    path: str
    filename: str
    size: int = 0
    source: str = ""


@dataclass
class ScanProgress:
    scanned_count: int = 0
    found_count: int = 0
    start_time: float = 0.0
    speed: float = 0.0
    estimated_total: int = 0
    is_running: bool = False
    results: List[DetectionResult] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)

    def increment_scanned(self):
        with self.lock:
            self.scanned_count += 1

    def add_found(self, result: DetectionResult):
        with self.lock:
            self.results.append(result)
            self.found_count += 1


class HighPerfScanner:

    KEYWORD = "钉钉"
    KEYWORD_EN = "dingding"
    KEYWORD_EN2 = "dingtalk"

    # PE 版本信息中已知的钉钉厂商特征
    _DINGTALK_COMPANIES = [
        "dingtalk",
        "alibaba",
        "钉钉",
        "阿里",
    ]

    # 包含 dingding 关键字但不属于钉钉的软件目录（误报排除）
    FALSE_POSITIVE_PATH_KEYWORDS = [
        "kingsoft",
        "wps",
    ]

    DEFAULT_EXCLUDE = {
        "$Recycle.Bin", "System Volume Information", "Package Cache",
        "node_modules", ".git", "__pycache__", "venv", ".venv", "Windows",
        ".Trash", ".fseventsd", ".Spotlight-V100",
    }

    if IS_WINDOWS:
        INSTALL_PATHS = [
            Path("C:\\Program Files\\DingDing"),
            Path("C:\\Program Files (x86)\\DingDing"),
            Path(os.path.expandvars("%LOCALAPPDATA%\\Programs\\DingDing")),
            Path(os.path.expandvars("%APPDATA%\\DingDing")),
        ]
        REGISTRY_ROOTS = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
    elif IS_MAC:
        INSTALL_PATHS = [
            Path("/Applications/DingDing.app"),
            Path(os.path.expanduser("~/Applications/DingDing.app")),
            Path(os.path.expanduser("~/Library/Application Support/DingDing")),
        ]
    else:
        INSTALL_PATHS = [
            Path(os.path.expanduser("~/.local/share/DingDing")),
            Path("/opt/DingDing"),
        ]

    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or min(8, (os.cpu_count() or 4))
        self.progress = ScanProgress()
        self._cancel = False

    def _is_excluded_dir(self, dirname: str) -> bool:
        dn = dirname.lower()
        for excl in self.DEFAULT_EXCLUDE:
            if excl.lower() == dn:
                return True
        return False

    def _match(self, filename: str) -> bool:
        return self.KEYWORD in filename or self.KEYWORD_EN in filename.lower() or self.KEYWORD_EN2 in filename.lower()

    def _is_false_positive_path(self, filepath: str) -> bool:
        """判断文件路径是否属于已知的误报软件（如 WPS/Kingsoft）"""
        fp_lower = filepath.lower()
        return any(kw in fp_lower for kw in self.FALSE_POSITIVE_PATH_KEYWORDS)

    def _is_dingtalk_exe(self, filepath: str) -> bool:
        """通过 Windows PE 文件版本信息识别钉钉安装包"""
        if not IS_WINDOWS:
            return False
        try:
            version_dll = ctypes.windll.version

            size = version_dll.GetFileVersionInfoSizeW(filepath, None)
            if size == 0:
                return False

            buf = ctypes.create_string_buffer(size)
            if not version_dll.GetFileVersionInfoW(filepath, 0, size, buf):
                return False

            p_trans = ctypes.c_void_p()
            trans_len = ctypes.c_uint()
            if not version_dll.VerQueryValueW(
                ctypes.cast(buf, ctypes.c_void_p),
                "\\",
                ctypes.byref(p_trans),
                ctypes.byref(trans_len),
            ):
                return False

            lang, codepage = struct.unpack_from("HH", p_trans.value)

            for field_name in ("ProductName", "CompanyName", "FileDescription", "InternalName"):
                query = f"\\StringFileInfo\\{lang:04x}{codepage:04x}\\{field_name}"
                p_val = ctypes.c_wchar_p()
                val_len = ctypes.c_uint()
                if version_dll.VerQueryValueW(
                    ctypes.cast(buf, ctypes.c_void_p),
                    query,
                    ctypes.byref(p_val),
                    ctypes.byref(val_len),
                ):
                    v = p_val.value.lower() if p_val.value else ""
                    if any(kw in v for kw in self._DINGTALK_COMPANIES):
                        return True
        except Exception:
            pass
        return False

    def _is_dingtalk_app(self, app_path: str) -> bool:
        """通过 Info.plist 识别 macOS 钉钉应用包"""
        if not IS_MAC:
            return False
        try:
            import plistlib
            plist_path = os.path.join(app_path, "Contents", "Info.plist")
            if not os.path.isfile(plist_path):
                return False
            with open(plist_path, "rb") as f:
                info = plistlib.load(f)
            for key in ("CFBundleName", "CFBundleDisplayName",
                        "CFBundleIdentifier", "CFBundleExecutable"):
                v = (info.get(key) or "").lower()
                if any(kw in v for kw in self._DINGTALK_COMPANIES):
                    return True
        except Exception:
            pass
        return False

    def _is_valid_hit(self, filename: str, filepath: str) -> bool:
        """文件名含关键词，或通过元数据识别钉钉安装包，且不属于误报"""
        if self._is_false_positive_path(filepath):
            return False
        if self._match(filename):
            return True
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".exe" and self._is_dingtalk_exe(filepath):
            return True
        if ext == ".app" and self._is_dingtalk_app(filepath):
            return True
        return False

    def _classify(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext in {".exe", ".msi", ".bat", ".cmd", ".ps1"}:
            return "安装程序"
        if ext in {".dmg", ".pkg", ".app"}:
            return "安装程序"
        if ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
            return "压缩包"
        if ext in {".log", ".txt"}:
            return "日志/文本"
        if ext in {".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".plist"}:
            return "配置文件"
        if ext in {".tmp", ".temp", ".cache"}:
            return "临时/缓存"
        if ext in {".dll", ".sys", ".dylib", ".so"}:
            return "系统文件"
        return "其他文件"

    def scan_registry(self) -> List[DetectionResult]:
        if not IS_WINDOWS:
            return []
        results = []
        for hkey_root, sub_path in self.REGISTRY_ROOTS:
            try:
                with winreg.OpenKey(hkey_root, sub_path, 0, winreg.KEY_READ) as key:
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            try:
                                with winreg.OpenKey(key, subkey_name, 0, winreg.KEY_READ) as sk:
                                    try:
                                        dn, _ = winreg.QueryValueEx(sk, "DisplayName")
                                        if dn and self._match(dn):
                                            try:
                                                loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                                            except FileNotFoundError:
                                                loc = ""
                                            results.append(DetectionResult(
                                                file_type="注册表-已安装",
                                                path=loc or f"{sub_path}\\{subkey_name}",
                                                filename=dn,
                                                source="注册表",
                                            ))
                                    except FileNotFoundError:
                                        pass
                            except (FileNotFoundError, PermissionError):
                                pass
                            i += 1
                        except OSError:
                            break
            except (FileNotFoundError, PermissionError):
                continue
        return results

    def _scan_dir(self, root: str, max_depth: int = 20) -> List[DetectionResult]:
        results = []
        stack: List[Tuple[str, int]] = [(root, 0)]
        while stack:
            dirpath, depth = stack.pop()
            if self._cancel or depth > max_depth:
                continue
            try:
                with os.scandir(dirpath) as entries:
                    for entry in entries:
                        if self._cancel:
                            break
                        try:
                            if entry.is_file(follow_symlinks=False):
                                self.progress.increment_scanned()
                                if self._is_valid_hit(entry.name, entry.path):
                                    try:
                                        stat = entry.stat()
                                        results.append(DetectionResult(
                                            file_type=self._classify(entry.name),
                                            path=os.path.dirname(entry.path),
                                            filename=entry.name,
                                            size=stat.st_size,
                                            source="文件系统",
                                        ))
                                        self.progress.add_found(results[-1])
                                    except OSError:
                                        pass
                            elif entry.is_dir(follow_symlinks=False):
                                # macOS: .app 包作为整体检测，不递归内部
                                if IS_MAC and entry.name.endswith(".app"):
                                    if self._is_dingtalk_app(entry.path):
                                        results.append(DetectionResult(
                                            file_type="安装目录",
                                            path=os.path.dirname(entry.path),
                                            filename=entry.name,
                                            size=0,
                                            source="文件系统",
                                        ))
                                        self.progress.add_found(results[-1])
                                    continue
                                if not self._is_excluded_dir(entry.name):
                                    stack.append((entry.path, depth + 1))
                        except (PermissionError, OSError):
                            continue
            except (PermissionError, OSError):
                continue
        return results

    def scan_all_drives(self, drives: List[str],
                        progress_cb: Optional[Callable] = None) -> List[DetectionResult]:
        self.progress = ScanProgress(start_time=time.time(), is_running=True)
        self._cancel = False
        all_results: List[DetectionResult] = []
        last_update = 0.0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._scan_dir, d): d for d in drives if os.path.isdir(d)}
            for future in as_completed(futures):
                if self._cancel:
                    break
                try:
                    all_results.extend(future.result())
                except Exception:
                    pass
                if progress_cb:
                    now = time.time()
                    if now - last_update >= 0.2:
                        elapsed = now - self.progress.start_time
                        scanned = self.progress.scanned_count
                        self.progress.speed = scanned / elapsed if elapsed > 0 else 0
                        self.progress.estimated_total = int(scanned * 1.5 if elapsed < 3 else scanned * 1.25)
                        progress_cb(self.progress)
                        last_update = now

        self.progress.is_running = False
        if progress_cb:
            progress_cb(self.progress)
        return all_results

    def scan_fixed_paths(self) -> List[DetectionResult]:
        results = []
        for p in self.INSTALL_PATHS:
            if p.exists():
                try:
                    if p.is_file():
                        results.append(DetectionResult(
                            file_type="安装本体",
                            path=str(p.parent), filename=p.name,
                            size=p.stat().st_size, source="固定路径",
                        ))
                    else:
                        # 安装目录本身就是违规证据
                        results.append(DetectionResult(
                            file_type="安装目录",
                            path=str(p.parent), filename=p.name,
                            size=0, source="固定路径",
                        ))
                        # 递归遍历目录下所有文件
                        for item in p.rglob("*"):
                            if item.is_file():
                                results.append(DetectionResult(
                                    file_type=self._classify(item.name),
                                    path=str(item.parent), filename=item.name,
                                    size=item.stat().st_size,
                                    source="固定路径",
                                ))
                except PermissionError:
                    continue
        return results

    def cancel(self):
        self._cancel = True


def get_available_drives() -> List[str]:
    if IS_WINDOWS:
        drives = []
        bitmask = 0
        try:
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        except Exception:
            pass
        if not bitmask:
            for letter in "CDEFGH":
                p = f"{letter}:\\"
                if os.path.exists(p):
                    drives.append(p)
            return drives
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
        return drives
    elif IS_MAC:
        return ["/"]
    else:
        return ["/"]


def open_explorer_at(file_path: str):
    if IS_WINDOWS:
        subprocess.run(f'explorer /select,"{file_path}"', shell=True)
    elif IS_MAC:
        subprocess.run(["open", "-R", file_path])
    else:
        subprocess.run(["xdg-open", os.path.dirname(file_path)])
