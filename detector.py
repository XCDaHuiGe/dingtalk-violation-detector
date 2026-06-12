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

    def increment_scanned(self, count: int = 1):
        with self.lock:
            self.scanned_count += count

    def add_found(self, result: DetectionResult):
        with self.lock:
            self.results.append(result)
            self.found_count += 1


class HighPerfScanner:

    KEYWORD = "\u9489\u9489"
    KEYWORD_EN = "dingding"
    KEYWORD_EN2 = "dingtalk"

    # ── PE 版本信息中已知的钉钉厂商特征（大小写不敏感匹配）──
    _DINGTALK_COMPANIES = [
        "dingtalk",
        "alibaba",
        "\u9489\u9489",
        "\u963f\u91cc",
    ]

    # ── 噪声文件扩展名：即使文件名含关键词也不算违规 ──
    # 图标/图片类（WPS 等软件常自带 dingding.svg 图标）
    NOISE_EXTENSIONS = {
        ".svg", ".ico", ".png", ".jpg", ".jpeg", ".gif",
        ".bmp", ".webp", ".tiff", ".tif",
        # 字体、数据库、编译产物
        ".ttf", ".otf", ".woff", ".woff2",
        ".db", ".sqlite", ".pyc", ".pyo", ".class",
    }

    # ── 包含关键词但不属于钉钉的软件/厂商目录（路径级排除）──
    FALSE_POSITIVE_PATH_KEYWORDS = [
        "kingsoft",
        "wps",
    ]

    # ── 跳过扫描的系统/无关目录（提速）──
    DEFAULT_EXCLUDE = {
        "$Recycle.Bin", "System Volume Information", "Package Cache",
        "node_modules", ".git", "__pycache__", "venv", ".venv",
        "Windows", "WinSxS", "Microsoft.NET",
        "ProgramData", "Recovery", "PerfLogs",
        "Intel", "AMD", "NVIDIA",
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

    def _has_keyword(self, name: str) -> bool:
        """名称是否包含钉钉关键词（中/英）"""
        return self.KEYWORD in name or self.KEYWORD_EN in name.lower() or self.KEYWORD_EN2 in name.lower()

    def _is_false_positive_path(self, filepath: str) -> bool:
        """判断文件路径是否属于已知的误报软件（如 WPS/Kingsoft）"""
        fp_lower = filepath.lower()
        return any(kw in fp_lower for kw in self.FALSE_POSITIVE_PATH_KEYWORDS)

    def _is_dingtalk_exe(self, filepath: str) -> bool:
        """
        通过 Windows PE 文件版本信息识别钉钉安装包。
        适用于文件名本身不含关键词（如 8.3.30-Release.260610012.exe）的情况。
        """
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

            # 获取翻译表（语言 + 代码页）
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

            # 依次检查关键字段
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
        """
        通过 Info.plist 识别 macOS 钉钉应用包。
        适用于文件名不含关键词的 .app 目录。
        """
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
        """
        智能判断：文件名含关键词 且 不属于噪声/误报
        排除逻辑：
          1. 噪声扩展名（图标/图片/字体等）→ 不算违规
          2. 误报路径（kingsoft/wps 等目录）→ 不算违规
        额外检测：
          3. Windows: .exe 通过 PE 元数据识别钉钉安装包
          4. macOS:   .app 通过 Info.plist 识别钉钉应用包
        """
        ext = os.path.splitext(filename)[1].lower()
        # 误报路径对所有类型均生效
        if self._is_false_positive_path(filepath):
            return False
        # 路径含关键词的常规检测
        if self._has_keyword(filename):
            if ext in self.NOISE_EXTENSIONS:
                return False
            return True
        # 无关键词补充检测：Windows PE 元数据 / macOS Info.plist
        if ext == ".exe" and self._is_dingtalk_exe(filepath):
            return True
        if ext == ".app" and self._is_dingtalk_app(filepath):
            return True
        return False

    def _classify(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        # 安装程序
        if ext in {".exe", ".msi", ".bat", ".cmd", ".ps1"}:
            return "\u5b89\u88c5\u7a0b\u5e8f"
        if ext in {".dmg", ".pkg", ".app"}:
            return "\u5b89\u88c5\u7a0b\u5e8f"
        # 压缩包
        if ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
            return "\u538b\u7f29\u5305"
        # 文档（钉钉相关的文档文件）
        if ext in {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".wps", ".et"}:
            return "\u6587\u6863"
        # 视频
        if ext in {".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".webm"}:
            return "\u89c6\u9891"
        # 音频
        if ext in {".mp3", ".wav", ".flac", ".aac", ".ogg"}:
            return "\u97f3\u9891"
        # 日志/文本
        if ext in {".log", ".txt", ".md", ".csv"}:
            return "\u65e5\u5fd7/\u6587\u672c"
        # 配置文件
        if ext in {".json", ".xml", ".yaml", ".yml", ".ini", ".cfg", ".plist", ".reg"}:
            return "\u914d\u7f6e\u6587\u4ef6"
        # 临时/缓存
        if ext in {".tmp", ".temp", ".cache", ".bak"}:
            return "\u4e34\u65f6/\u7f13\u5b58"
        # 系统文件
        if ext in {".dll", ".sys", ".dylib", ".so"}:
            return "\u7cfb\u7edf\u6587\u4ef6"
        # 快捷方式
        if ext in {".lnk", ".url"}:
            return "\u5feb\u6377\u65b9\u5f0f"
        # 无扩展名 → 可能是目录名
        if not ext:
            return "\u76ee\u5f55"
        return "\u5176\u4ed6\u6587\u4ef6"

    # ── 注册表扫描 ──────────────────────────────────────────

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
                                        if dn and self._has_keyword(dn):
                                            try:
                                                loc, _ = winreg.QueryValueEx(sk, "InstallLocation")
                                            except FileNotFoundError:
                                                loc = ""
                                            results.append(DetectionResult(
                                                file_type="\u6ce8\u518c\u8868-\u5df2\u5b89\u88c5",
                                                path=loc or f"{sub_path}\\{subkey_name}",
                                                filename=dn,
                                                source="\u6ce8\u518c\u8868",
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

    def clean_registry(self) -> Tuple[int, List[str]]:
        """
        删除钉钉相关注册表项
        Returns: (删除数量, 失败信息列表)
        """
        if not IS_WINDOWS:
            return 0, ["\u975e Windows \u7cfb\u7edf"]
        deleted = 0
        errors: List[str] = []
        for hkey_root, sub_path in self.REGISTRY_ROOTS:
            to_delete: List[str] = []
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
                                        if dn and self._has_keyword(dn):
                                            to_delete.append(subkey_name)
                                    except FileNotFoundError:
                                        pass
                            except (FileNotFoundError, PermissionError):
                                pass
                            i += 1
                        except OSError:
                            break
            except (FileNotFoundError, PermissionError) as e:
                errors.append(f"{sub_path}: {e}")
                continue
            # 删除命中的子键
            for name in to_delete:
                try:
                    with winreg.OpenKey(hkey_root, sub_path, 0, winreg.KEY_ALL_ACCESS) as key:
                        winreg.DeleteKey(key, name)
                        deleted += 1
                except PermissionError:
                    errors.append(f"\u6743\u9650\u4e0d\u8db3: {sub_path}\\{name} (\u9700\u8981\u7ba1\u7406\u5458\u6743\u9650)")
                except Exception as e:
                    errors.append(f"{sub_path}\\{name}: {e}")
        return deleted, errors

    def _scan_dir(self, root: str, max_depth: int = 20) -> List[DetectionResult]:
        results = []
        stack: List[Tuple[str, int]] = [(root, 0)]
        batch = 0                       # 批量进度计数（减少锁竞争）
        last_cb_count = 0               # 上次回调时的累计数量
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
                                batch += 1
                                if self._is_valid_hit(entry.name, entry.path):
                                    try:
                                        stat = entry.stat()
                                        results.append(DetectionResult(
                                            file_type=self._classify(entry.name),
                                            path=os.path.dirname(entry.path),
                                            filename=entry.name,
                                            size=stat.st_size,
                                            source="\u6587\u4ef6\u7cfb\u7edf",
                                        ))
                                        self.progress.add_found(results[-1])
                                    except OSError:
                                        pass
                            elif entry.is_dir(follow_symlinks=False):
                                # macOS: .app 包作为整体检测，不递归内部
                                if IS_MAC and entry.name.endswith(".app"):
                                    if self._is_dingtalk_app(entry.path):
                                        results.append(DetectionResult(
                                            file_type="\u5b89\u88c5\u76ee\u5f55",
                                            path=os.path.dirname(entry.path),
                                            filename=entry.name,
                                            size=0,
                                            source="\u6587\u4ef6\u7cfb\u7edf",
                                        ))
                                        self.progress.add_found(results[-1])
                                    continue
                                if not self._is_excluded_dir(entry.name):
                                    stack.append((entry.path, depth + 1))
                        except (PermissionError, OSError):
                            continue

                # 每 500 个文件刷新一次进度（减少锁竞争）
                if batch >= 500:
                    self.progress.increment_scanned(batch)
                    batch = 0
                    # 定期调用进度回调
                    cb = getattr(self, '_progress_cb', None)
                    if cb and self.progress.scanned_count - last_cb_count >= 1000:
                        elapsed = time.time() - self.progress.start_time
                        self.progress.speed = self.progress.scanned_count / elapsed if elapsed > 0 else 0
                        cb(self.progress)
                        last_cb_count = self.progress.scanned_count
            except (PermissionError, OSError):
                continue
        # 目录扫描完毕，刷新剩余进度
        if batch:
            self.progress.increment_scanned(batch)
        # 最终回调
        cb = getattr(self, '_progress_cb', None)
        if cb:
            elapsed = time.time() - self.progress.start_time
            self.progress.speed = self.progress.scanned_count / elapsed if elapsed > 0 else 0
            cb(self.progress)
        return results

    def scan_all_drives(self, drives: List[str],
                        progress_cb: Optional[Callable] = None) -> List[DetectionResult]:
        self.progress = ScanProgress(start_time=time.time(), is_running=True)
        self._cancel = False
        self._progress_cb = progress_cb  # 存储回调供 _scan_dir 内部使用
        all_results: List[DetectionResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._scan_dir, d): d for d in drives if os.path.isdir(d)}
            for future in as_completed(futures):
                if self._cancel:
                    break
                try:
                    all_results.extend(future.result())
                except Exception:
                    pass

        self.progress.is_running = False
        if progress_cb:
            progress_cb(self.progress)
        self._progress_cb = None
        return all_results

    def scan_fixed_paths(self) -> List[DetectionResult]:
        results = []
        for p in self.INSTALL_PATHS:
            if p.exists():
                try:
                    if p.is_file():
                        # 固定路径下的文件直接视为违规
                        results.append(DetectionResult(
                            file_type="\u5b89\u88c5\u672c\u4f53",
                            path=str(p.parent), filename=p.name,
                            size=p.stat().st_size, source="\u56fa\u5b9a\u8def\u5f84",
                        ))
                    else:
                        # 整个安装目录本身就是违规证据
                        results.append(DetectionResult(
                            file_type="\u5b89\u88c5\u76ee\u5f55",
                            path=str(p.parent), filename=p.name,
                            size=0, source="\u56fa\u5b9a\u8def\u5f84",
                        ))
                        # 递归遍历目录下所有文件（均为违规证据）
                        for item in p.rglob("*"):
                            if item.is_file():
                                results.append(DetectionResult(
                                    file_type=self._classify(item.name),
                                    path=str(item.parent), filename=item.name,
                                    size=item.stat().st_size,
                                    source="\u56fa\u5b9a\u8def\u5f84",
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


def delete_to_recycle_bin(file_path: str) -> tuple:
    """
    将文件/目录移入 Windows 回收站（安全删除，可恢复）。
    Returns: (success: bool, error_message: str)
    """
    if not IS_WINDOWS:
        return False, "仅支持 Windows 系统"
    if not os.path.exists(file_path):
        return False, "文件不存在"
    try:
        from ctypes import wintypes

        FO_DELETE = 0x0003
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd",   wintypes.HWND),
                ("wFunc",  ctypes.c_uint),
                ("pFrom",  ctypes.c_wchar_p),
                ("pTo",    ctypes.c_wchar_p),
                ("fFlags", ctypes.c_ushort),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", ctypes.c_wchar_p),
            ]

        fileop = SHFILEOPSTRUCTW()
        fileop.hwnd = 0
        fileop.wFunc = FO_DELETE
        fileop.pFrom = file_path + "\0"  # c_wchar_p 自动追加 \0
        fileop.pTo = None
        fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT

        result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
        if result == 0 and not fileop.fAnyOperationsAborted:
            return True, ""
        return False, f"操作失败 (错误码: {result})"
    except Exception as e:
        return False, str(e)
