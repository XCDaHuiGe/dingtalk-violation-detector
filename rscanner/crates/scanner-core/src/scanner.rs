use crate::types::*;
use crossbeam_channel::Sender;
use rayon::prelude::*;
use std::path::Path;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Instant;
use walkdir::WalkDir;

// ─── 常量 ───

pub const KEYWORD: &str = "钉钉";
pub const KEYWORD_EN: &str = "dingding";
pub const KEYWORD_EN2: &str = "dingtalk";

const DINGTALK_COMPANIES: &[&str] = &["dingtalk", "alibaba", "钉钉", "阿里"];

const NOISE_EXTENSIONS: &[&str] = &[
    ".svg", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".db", ".sqlite", ".sqlite3",
    ".pyc", ".pyo", ".class",
];

const FALSE_POSITIVE_PATH_KEYWORDS: &[&str] = &["kingsoft", "wps"];

const DEFAULT_EXCLUDE: &[&str] = &[
    "$Recycle.Bin", "System Volume Information", "Recovery",
    "Windows", "WinSxS", "System32", "SysWOW64",
    "ProgramData\\Package Cache", "MSOCache",
    "node_modules", ".git", "__pycache__", ".venv", "venv",
];

const INSTALL_PATHS_WINDOWS: &[&str] = &[
    "C:\\Program Files\\DingDing",
    "C:\\Program Files (x86)\\DingDing",
    "C:\\Program Files\\DingTalk",
    "C:\\Program Files (x86)\\DingTalk",
    "C:\\Users\\%USERNAME%\\AppData\\Local\\DingDing",
    "C:\\Users\\%USERNAME%\\AppData\\Local\\Programs\\DingTalk",
    "C:\\Users\\%USERNAME%\\AppData\\Roaming\\DingTalk",
    "C:\\Users\\%USERNAME%\\AppData\\Local\\com.alibabainc.dingtalk",
];

const INSTALL_PATHS_MACOS: &[&str] = &[
    "/Applications/DingDing.app",
    "/Applications/DingTalk.app",
    "/Applications/钉钉.app",
];

const REGISTRY_ROOTS: &[&str] = &[
    "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
    "SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall",
];

// ─── Windows FFI ───

#[cfg(target_os = "windows")]
mod ffi {
    use std::ffi::c_void;

    pub type DWORD = u32;
    pub type LPVOID = *mut c_void;
    pub type LPCWSTR = *const u16;
    pub type LPDWORD = *mut u32;
    pub type UINT = u32;
    pub type BOOL = i32;

    pub const ERROR_SUCCESS: DWORD = 0;

    #[link(name = "version")]
    extern "system" {
        pub fn GetFileVersionInfoSizeW(
            lptstrFilename: LPCWSTR,
            lpdwHandle: LPDWORD,
        ) -> DWORD;

        pub fn GetFileVersionInfoW(
            lptstrFilename: LPCWSTR,
            dwHandle: DWORD,
            dwLen: DWORD,
            lpData: LPVOID,
        ) -> BOOL;

        pub fn VerQueryValueW(
            pBlock: LPVOID,
            lpSubBlock: LPCWSTR,
            lplpBuffer: *mut LPVOID,
            puLen: LPDWORD,
        ) -> BOOL;
    }

    #[link(name = "kernel32")]
    extern "system" {
        pub fn GetLogicalDrives() -> DWORD;
    }

    #[link(name = "shell32")]
    extern "system" {
        pub fn SHFileOperationW(
            lpFileOp: *mut SHFILEOPSTRUCTW,
        ) -> i32;
    }

    #[repr(C)]
    pub struct SHFILEOPSTRUCTW {
        pub hwnd: *mut c_void,
        pub wFunc: UINT,
        pub pFrom: LPCWSTR,
        pub pTo: LPCWSTR,
        pub fFlags: UINT,
        pub fAnyOperationsAborted: BOOL,
        pub hNameMappings: LPVOID,
        pub lpszProgressTitle: LPCWSTR,
    }

    pub const FO_DELETE: UINT = 3;
    pub const FOF_ALLOWUNDO: UINT = 0x0040;
    pub const FOF_NOCONFIRMATION: UINT = 0x0010;
    pub const FOF_SILENT: UINT = 0x0004;
}

// ─── Scanner ───

pub struct Scanner {
    cancel_flag: Arc<AtomicBool>,
    progress_tx: Option<Sender<ProgressEvent>>,
    phase_tx: Option<Sender<ScanPhase>>,
}

impl Scanner {
    pub fn new() -> Self {
        Self {
            cancel_flag: Arc::new(AtomicBool::new(false)),
            progress_tx: None,
            phase_tx: None,
        }
    }

    pub fn with_cancel(cancel_flag: Arc<AtomicBool>) -> Self {
        Self {
            cancel_flag,
            progress_tx: None,
            phase_tx: None,
        }
    }

    pub fn set_channels(
        &mut self,
        progress_tx: Sender<ProgressEvent>,
        phase_tx: Sender<ScanPhase>,
    ) {
        self.progress_tx = Some(progress_tx);
        self.phase_tx = Some(phase_tx);
    }

    pub fn cancel(&self) {
        self.cancel_flag.store(true, Ordering::Relaxed);
    }

    pub fn cancel_flag(&self) -> Arc<AtomicBool> {
        self.cancel_flag.clone()
    }

    fn send_phase(&self, phase: ScanPhase) {
        if let Some(ref tx) = self.phase_tx {
            let _ = tx.send(phase);
        }
    }

    fn send_progress(&self, scanned: u64, found: u64, elapsed: u64, speed: f64, phase: ScanPhase) {
        if let Some(ref tx) = self.progress_tx {
            let _ = tx.send(ProgressEvent {
                scanned,
                found: found as u32,
                speed,
                elapsed_secs: elapsed,
                phase,
            });
        }
    }

    // ─── 关键词匹配 ───

    fn has_keyword(name: &str) -> bool {
        let lower = name.to_lowercase();
        lower.contains(KEYWORD)
            || lower.contains(KEYWORD_EN)
            || lower.contains(KEYWORD_EN2)
    }

    fn is_false_positive_path(filepath: &str) -> bool {
        let lower = filepath.to_lowercase();
        FALSE_POSITIVE_PATH_KEYWORDS
            .iter()
            .any(|&kw| lower.contains(kw))
    }

    fn is_noise_extension(path: &Path) -> bool {
        path.extension()
            .and_then(|e| e.to_str())
            .map(|e| {
                let ext = format!(".{}", e.to_lowercase());
                NOISE_EXTENSIONS.contains(&ext.as_str())
            })
            .unwrap_or(false)
    }

    fn is_valid_hit(_filename: &str, filepath: &str) -> bool {
        if Self::is_false_positive_path(filepath) {
            return false;
        }
        let path = Path::new(filepath);
        if path.is_file() && Self::is_noise_extension(path) {
            return false;
        }
        if cfg!(target_os = "windows")
            && path.is_file()
            && path.extension().map(|e| e.to_ascii_lowercase()) == Some(std::ffi::OsString::from("exe"))
        {
            return Self::is_dingtalk_exe(filepath);
        }
        true
    }

    #[cfg(target_os = "windows")]
    fn is_dingtalk_exe(filepath: &str) -> bool {
        use std::ffi::OsStr;
        use std::os::windows::ffi::OsStrExt;
        use std::ptr;

        let wide: Vec<u16> = OsStr::new(filepath)
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();

        unsafe {
            let mut dummy: u32 = 0;
            let size = ffi::GetFileVersionInfoSizeW(wide.as_ptr(), &mut dummy);
            if size == 0 {
                return false;
            }

            let mut buf = vec![0u8; size as usize];
            if ffi::GetFileVersionInfoW(
                wide.as_ptr(),
                0,
                size,
                buf.as_mut_ptr() as *mut std::ffi::c_void,
            ) == 0
            {
                return false;
            }

            // Read language ID
            let subblock = "\\VarFileInfo\\Translation\0".encode_utf16().collect::<Vec<_>>();
            let mut lang_ptr: *mut std::ffi::c_void = ptr::null_mut();
            let mut lang_len: u32 = 0;

            if ffi::VerQueryValueW(
                buf.as_mut_ptr() as *mut std::ffi::c_void,
                subblock.as_ptr(),
                &mut lang_ptr,
                &mut lang_len,
            ) == 0
            {
                return false;
            }

            let lang_id = *(lang_ptr as *const u16);
            let lang = lang_id & 0xFF;
            let charset = (lang_id >> 8) & 0xFF;

            let strings_to_check = ["ProductName", "CompanyName", "FileDescription", "InternalName"];

            for &key in &strings_to_check {
                let sub_path = format!(
                    "\\StringFileInfo\\{:02X}{:02X}\\{}\0",
                    charset, lang, key
                );
                let sub_wide: Vec<u16> = sub_path.encode_utf16().collect();

                let mut value_ptr: *mut std::ffi::c_void = ptr::null_mut();
                let mut value_len: u32 = 0;

                if ffi::VerQueryValueW(
                    buf.as_mut_ptr() as *mut std::ffi::c_void,
                    sub_wide.as_ptr(),
                    &mut value_ptr,
                    &mut value_len,
                ) != 0
                    && !value_ptr.is_null()
                {
                    let s = String::from_utf16_lossy(
                        std::slice::from_raw_parts(value_ptr as *const u16, value_len as usize),
                    );
                    let s = s.trim_end_matches('\0').to_lowercase();
                    if DINGTALK_COMPANIES.iter().any(|&c| s.contains(c)) {
                        return true;
                    }
                }

                // Try reversed lang/charset
                let sub_path2 = format!(
                    "\\StringFileInfo\\{:02X}{:02X}\\{}\0",
                    lang, charset, key
                );
                let sub_wide2: Vec<u16> = sub_path2.encode_utf16().collect();

                let mut value_ptr2: *mut std::ffi::c_void = ptr::null_mut();
                let mut value_len2: u32 = 0;

                if ffi::VerQueryValueW(
                    buf.as_mut_ptr() as *mut std::ffi::c_void,
                    sub_wide2.as_ptr(),
                    &mut value_ptr2,
                    &mut value_len2,
                ) != 0
                    && !value_ptr2.is_null()
                {
                    let s = String::from_utf16_lossy(
                        std::slice::from_raw_parts(value_ptr2 as *const u16, value_len2 as usize),
                    );
                    let s = s.trim_end_matches('\0').to_lowercase();
                    if DINGTALK_COMPANIES.iter().any(|&c| s.contains(c)) {
                        return true;
                    }
                }
            }
            false
        }
    }

    #[cfg(not(target_os = "windows"))]
    fn is_dingtalk_exe(_filepath: &str) -> bool {
        false
    }

    fn classify(filename: &str) -> &'static str {
        let lower = filename.to_lowercase();
        if lower.ends_with(".exe") || lower.ends_with(".msi") {
            "安装程序"
        } else if lower.ends_with(".zip")
            || lower.ends_with(".rar")
            || lower.ends_with(".7z")
            || lower.ends_with(".tar.gz")
            || lower.ends_with(".tar")
        {
            "压缩包"
        } else if lower.ends_with(".doc")
            || lower.ends_with(".docx")
            || lower.ends_with(".pdf")
            || lower.ends_with(".xls")
            || lower.ends_with(".xlsx")
            || lower.ends_with(".ppt")
            || lower.ends_with(".pptx")
        {
            "文档"
        } else if lower.ends_with(".mp4")
            || lower.ends_with(".avi")
            || lower.ends_with(".mov")
            || lower.ends_with(".mkv")
            || lower.ends_with(".flv")
        {
            "视频"
        } else if lower.ends_with(".mp3")
            || lower.ends_with(".wav")
            || lower.ends_with(".flac")
            || lower.ends_with(".aac")
        {
            "音频"
        } else if lower.ends_with(".log")
            || lower.ends_with(".txt")
            || lower.ends_with(".md")
            || lower.ends_with(".csv")
        {
            "日志/文本"
        } else if lower.ends_with(".cfg")
            || lower.ends_with(".conf")
            || lower.ends_with(".ini")
            || lower.ends_with(".json")
            || lower.ends_with(".xml")
            || lower.ends_with(".yaml")
            || lower.ends_with(".yml")
        {
            "配置文件"
        } else if lower.ends_with(".tmp")
            || lower.ends_with(".temp")
            || lower.ends_with(".bak")
            || lower.ends_with(".dat")
        {
            "临时/缓存"
        } else if lower.ends_with(".dll")
            || lower.ends_with(".sys")
            || lower.ends_with(".drv")
            || lower.ends_with(".ocx")
        {
            "系统文件"
        } else if lower.ends_with(".lnk") || lower.ends_with(".url") {
            "快捷方式"
        } else if lower.ends_with(".app") || Path::new(filename).is_dir() {
            "目录"
        } else {
            "其他"
        }
    }

    // ─── 注册表扫描 ───

    #[cfg(target_os = "windows")]
    pub fn scan_registry(&self) -> Vec<DetectionResult> {
        use winreg::enums::*;
        use winreg::RegKey;

        let mut results = Vec::new();
        let hklm = RegKey::predef(HKEY_LOCAL_MACHINE);
        let hkcu = RegKey::predef(HKEY_CURRENT_USER);

        for root_key in REGISTRY_ROOTS {
            for hkey in &[&hklm, &hkcu] {
                let root = match hkey.open_subkey_with_flags(root_key, KEY_READ) {
                    Ok(key) => key,
                    Err(_) => continue,
                };

                for entry in root.enum_keys().flatten() {
                    if let Ok(sub_key) =
                        root.open_subkey_with_flags(&entry, KEY_READ)
                    {
                        if let Ok(display_name) = sub_key.get_value::<String, _>("DisplayName") {
                            if Self::has_keyword(&display_name) {
                                results.push(DetectionResult {
                                    file_type: "注册表项".to_string(),
                                    path: format!("{}\\{}", root_key, entry),
                                    filename: display_name,
                                    size: 0,
                                    source: "注册表扫描".to_string(),
                                });
                            }
                        }
                    }
                }
            }
        }
        results
    }

    #[cfg(not(target_os = "windows"))]
    pub fn scan_registry(&self) -> Vec<DetectionResult> {
        Vec::new()
    }

    #[cfg(target_os = "windows")]
    pub fn clean_registry(&self) -> CleanRegistryResult {
        use winreg::enums::*;
        use winreg::RegKey;

        let mut deleted = 0u32;
        let mut errors = Vec::new();

        let hklm = RegKey::predef(HKEY_LOCAL_MACHINE);
        let hkcu = RegKey::predef(HKEY_CURRENT_USER);

        for root_key in REGISTRY_ROOTS {
            for hkey in &[&hklm, &hkcu] {
                let root = match hkey.open_subkey_with_flags(root_key, KEY_READ | KEY_WRITE) {
                    Ok(key) => key,
                    Err(_) => continue,
                };

                let keys_to_delete: Vec<String> = root
                    .enum_keys()
                    .flatten()
                    .filter(|entry| {
                        if let Ok(sub_key) =
                            root.open_subkey_with_flags(entry, KEY_READ)
                        {
                            if let Ok(display_name) =
                                sub_key.get_value::<String, _>("DisplayName")
                            {
                                return Self::has_keyword(&display_name);
                            }
                        }
                        false
                    })
                    .collect();

                for key_name in keys_to_delete {
                    let full_path = format!("{}\\{}", root_key, key_name);
                    match root.delete_subkey(&key_name) {
                        Ok(_) => deleted += 1,
                        Err(e) => errors.push(format!("删除失败: {} ({})", full_path, e)),
                    }
                }
            }
        }
        CleanRegistryResult { deleted, errors }
    }

    #[cfg(not(target_os = "windows"))]
    pub fn clean_registry(&self) -> CleanRegistryResult {
        CleanRegistryResult {
            deleted: 0,
            errors: vec!["不支持在当前平台清理注册表".to_string()],
        }
    }

    // ─── 固定路径扫描 ───

    pub fn scan_fixed_paths(&self) -> Vec<DetectionResult> {
        let mut results = Vec::new();
        let paths = if cfg!(target_os = "windows") {
            INSTALL_PATHS_WINDOWS.to_vec()
        } else if cfg!(target_os = "macos") {
            INSTALL_PATHS_MACOS.to_vec()
        } else {
            return results;
        };

        for raw_path in paths {
            let resolved = resolve_user_profile(&raw_path);
            let path = Path::new(&resolved);
            if path.exists() {
                results.push(DetectionResult {
                    file_type: "目录".to_string(),
                    path: resolved.clone(),
                    filename: path
                        .file_name()
                        .map(|n| n.to_string_lossy().to_string())
                        .unwrap_or_default(),
                    size: 0,
                    source: "固定路径扫描".to_string(),
                });
                if let Ok(entries) = path.read_dir() {
                    for entry in entries.flatten() {
                        let p = entry.path();
                        if let Ok(meta) = p.metadata() {
                            results.push(DetectionResult {
                                file_type: Self::classify(
                                    p.file_name().unwrap().to_str().unwrap_or(""),
                                )
                                .to_string(),
                                path: p.to_string_lossy().to_string(),
                                filename: p
                                    .file_name()
                                    .map(|n| n.to_string_lossy().to_string())
                                    .unwrap_or_default(),
                                size: meta.len(),
                                source: "固定路径扫描".to_string(),
                            });
                        }
                    }
                }
            }
        }
        results
    }

    // ─── 多阶段扫描（编排） ───

    pub fn run_scan(
        &self,
        config: &ScanConfig,
    ) -> Vec<DetectionResult> {
        let mut all_results = Vec::new();
        let start = Instant::now();

        // Phase 1: 注册表
        if config.include_registry {
            self.send_phase(ScanPhase::Registry);
            for r in self.scan_registry() {
                all_results.push(r);
            }
        }

        if self.cancel_flag.load(Ordering::Relaxed) {
            return all_results;
        }

        // Phase 2: 固定路径
        if config.include_fixed_paths {
            self.send_phase(ScanPhase::FixedPaths);
            for r in self.scan_fixed_paths() {
                all_results.push(r);
            }
        }

        if self.cancel_flag.load(Ordering::Relaxed) {
            return all_results;
        }

        // Phase 3: 全盘扫描
        if config.include_full_scan && !config.drives.is_empty() {
            self.send_phase(ScanPhase::FullScan);
            let cancel = self.cancel_flag.clone();
            let progress = ScanProgress::new(cancel);

            let results: Vec<Vec<DetectionResult>> = config
                .drives
                .par_iter()
                .map(|drive| {
                    let mut local_results = Vec::new();
                    let mut last_report = Instant::now();

                    for entry in WalkDir::new(drive)
                        .max_depth(20)
                        .into_iter()
                        .filter_entry(|e| {
                            let name = e.file_name().to_string_lossy();
                            !DEFAULT_EXCLUDE.iter().any(|ex| name == *ex)
                                && !name.starts_with('.')
                        })
                    {
                        if progress.is_cancelled() {
                            break;
                        }

                        if let Ok(entry) = entry {
                            let path = entry.path();
                            let path_str = path.to_string_lossy().to_string();
                            let filename = path
                                .file_name()
                                .map(|n| n.to_string_lossy().to_string())
                                .unwrap_or_default();

                            progress.increment_scanned();

                            if Self::has_keyword(&filename)
                                && Self::is_valid_hit(&filename, &path_str)
                            {
                                let meta = entry.metadata().ok();
                                local_results.push(DetectionResult {
                                    file_type: Self::classify(&filename).to_string(),
                                    path: path_str,
                                    filename,
                                    size: meta.map(|m| m.len()).unwrap_or(0),
                                    source: "全盘扫描".to_string(),
                                });
                                progress.add_found();
                            }

                            if last_report.elapsed().as_millis() > 200 {
                                let elapsed = start.elapsed().as_secs();
                                let scanned = progress
                                    .scanned
                                    .load(std::sync::atomic::Ordering::Relaxed);
                                let found = progress
                                    .found
                                    .load(std::sync::atomic::Ordering::Relaxed);
                                let speed = if elapsed > 0 {
                                    scanned as f64 / elapsed as f64
                                } else {
                                    scanned as f64
                                };
                                self.send_progress(
                                    scanned, found, elapsed, speed, ScanPhase::FullScan,
                                );
                                last_report = Instant::now();
                            }
                        }
                    }
                    local_results
                })
                .collect();

            for mut r in results {
                all_results.append(&mut r);
            }
        }

        self.send_phase(ScanPhase::Complete);
        all_results
    }
}

// ─── 工具函数 ───

fn resolve_user_profile(raw: &str) -> String {
    if let Some(username) = std::env::var("USERNAME").ok() {
        raw.replace("%USERNAME%", &username)
    } else {
        raw.replace("%USERNAME%", "default")
    }
}

pub fn get_available_drives() -> Vec<String> {
    #[cfg(target_os = "windows")]
    {
        unsafe {
            let bits = ffi::GetLogicalDrives();
            let mut drives = Vec::new();
            for i in 0..26 {
                if (bits & (1 << i)) != 0 {
                    let letter = char::from_u32(b'A' as u32 + i).unwrap();
                    drives.push(format!("{}:\\", letter));
                }
            }
            drives
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        vec!["/".to_string()]
    }
}

#[cfg(target_os = "windows")]
pub fn open_explorer_at(file_path: &str) {
    let _ = std::process::Command::new("explorer")
        .args(["/select,", file_path])
        .spawn();
}

#[cfg(target_os = "macos")]
pub fn open_explorer_at(file_path: &str) {
    let _ = std::process::Command::new("open")
        .args(["-R", file_path])
        .spawn();
}

#[cfg(target_os = "linux")]
pub fn open_explorer_at(file_path: &str) {
    if let Some(parent) = std::path::Path::new(file_path).parent() {
        let _ = std::process::Command::new("xdg-open")
            .arg(parent)
            .spawn();
    }
}

#[cfg(target_os = "windows")]
pub fn delete_to_recycle_bin(file_path: &str) -> (bool, Option<String>) {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;

    let wide: Vec<u16> = OsStr::new(file_path)
        .encode_wide()
        .chain(std::iter::once(0))
        .chain(std::iter::once(0))
        .collect();

    let mut op = ffi::SHFILEOPSTRUCTW {
        hwnd: std::ptr::null_mut(),
        wFunc: ffi::FO_DELETE,
        pFrom: wide.as_ptr(),
        pTo: std::ptr::null(),
        fFlags: ffi::FOF_ALLOWUNDO | ffi::FOF_NOCONFIRMATION | ffi::FOF_SILENT,
        fAnyOperationsAborted: 0,
        hNameMappings: std::ptr::null_mut(),
        lpszProgressTitle: std::ptr::null(),
    };

    unsafe {
        let result = ffi::SHFileOperationW(&mut op);
        if result == 0 {
            (true, None)
        } else {
            (false, Some(format!("SHFileOperation 失败: code={}", result)))
        }
    }
}

#[cfg(not(target_os = "windows"))]
pub fn delete_to_recycle_bin(file_path: &str) -> (bool, Option<String>) {
    match trash::delete(file_path) {
        Ok(()) => (true, None),
        Err(e) => (false, Some(e.to_string())),
    }
}

// ─── ScanProgress ───

pub struct ScanProgress {
    pub scanned: AtomicU64,
    pub found: AtomicU64,
    pub start_time: Instant,
    pub cancel_flag: Arc<AtomicBool>,
}

impl ScanProgress {
    pub fn new(cancel_flag: Arc<AtomicBool>) -> Self {
        Self {
            scanned: AtomicU64::new(0),
            found: AtomicU64::new(0),
            start_time: Instant::now(),
            cancel_flag,
        }
    }

    pub fn increment_scanned(&self) {
        self.scanned.fetch_add(1, Ordering::Relaxed);
    }

    pub fn add_found(&self) {
        self.found.fetch_add(1, Ordering::Relaxed);
    }

    pub fn is_cancelled(&self) -> bool {
        self.cancel_flag.load(Ordering::Relaxed)
    }
}

// ─── 测试 ───

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_has_keyword_chinese() {
        assert!(Scanner::has_keyword("钉钉.exe"));
        assert!(!Scanner::has_keyword("微信.exe"));
    }

    #[test]
    fn test_has_keyword_english() {
        assert!(Scanner::has_keyword("DingTalk.exe"));
        assert!(Scanner::has_keyword("DingDing.msi"));
        assert!(!Scanner::has_keyword("WeChat.exe"));
    }

    #[test]
    fn test_has_keyword_case_insensitive() {
        assert!(Scanner::has_keyword("DINGTALK.exe"));
        assert!(Scanner::has_keyword("dingtalk_setup.exe"));
    }

    #[test]
    fn test_is_false_positive_path() {
        assert!(Scanner::is_false_positive_path(
            "C:\\Program Files\\kingsoft\\wps\\dingding.ico"
        ));
        assert!(!Scanner::is_false_positive_path(
            "C:\\Program Files\\DingTalk\\DingTalk.exe"
        ));
    }

    #[test]
    fn test_noise_extensions_filtered() {
        assert!(Scanner::is_noise_extension(Path::new("钉钉.svg")));
        assert!(!Scanner::is_noise_extension(Path::new("钉钉.exe")));
    }

    #[test]
    fn test_is_valid_hit_false_positive() {
        assert!(!Scanner::is_valid_hit(
            "dingding.ico",
            "C:\\kingsoft\\wps\\dingding.ico",
        ));
    }

    #[test]
    fn test_classify_installer() {
        assert_eq!(Scanner::classify("setup.exe"), "安装程序");
        assert_eq!(Scanner::classify("dingtalk.msi"), "安装程序");
    }

    #[test]
    fn test_classify_document() {
        assert_eq!(Scanner::classify("report.pdf"), "文档");
        assert_eq!(Scanner::classify("data.xlsx"), "文档");
    }

    #[test]
    fn test_classify_archive() {
        assert_eq!(Scanner::classify("archive.zip"), "压缩包");
        assert_eq!(Scanner::classify("backup.rar"), "压缩包");
    }

    #[test]
    fn test_scan_fixed_paths_no_crash() {
        let scanner = Scanner::new();
        let results = scanner.scan_fixed_paths();
        // 不崩溃即可；结果可能因环境是否有钉钉安装而异
        assert!(results.len() < 1000);
    }
}
