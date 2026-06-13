use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::Arc;
use std::time::Instant;

// ─── 检测结果 ───

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectionResult {
    pub file_type: String,
    pub path: String,
    pub filename: String,
    pub size: u64,
    pub source: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeleteResult {
    pub path: String,
    pub success: bool,
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CleanRegistryResult {
    pub deleted: u32,
    pub errors: Vec<String>,
}

// ─── 扫描阶段 ───

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ScanPhase {
    Idle,
    Registry,
    FixedPaths,
    FullScan,
    Complete,
}

impl ScanPhase {
    pub fn label(&self) -> &'static str {
        match self {
            ScanPhase::Idle => "等待开始",
            ScanPhase::Registry => "注册表检测",
            ScanPhase::FixedPaths => "固定路径检测",
            ScanPhase::FullScan => "全盘文件扫描",
            ScanPhase::Complete => "扫描完成",
        }
    }
}

// ─── 进度事件 ───

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProgressEvent {
    pub scanned: u64,
    pub found: u32,
    pub speed: f64,
    pub elapsed_secs: u64,
    pub phase: ScanPhase,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseEvent {
    pub phase: ScanPhase,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanCompleteEvent {
    pub total_found: u32,
    pub results: Vec<DetectionResult>,
}

// ─── 扫描进度跟踪器 ───

pub struct ScanProgress {
    pub scanned: AtomicU64,
    pub found: AtomicU64,
    pub start_time: Instant,
    pub is_running: AtomicBool,
    pub cancel_flag: Arc<AtomicBool>,
}

impl ScanProgress {
    pub fn new(cancel_flag: Arc<AtomicBool>) -> Self {
        Self {
            scanned: AtomicU64::new(0),
            found: AtomicU64::new(0),
            start_time: Instant::now(),
            is_running: AtomicBool::new(true),
            cancel_flag,
        }
    }

    pub fn increment_scanned(&self) {
        self.scanned.fetch_add(1, Ordering::Relaxed);
    }

    pub fn add_found(&self) {
        self.found.fetch_add(1, Ordering::Relaxed);
    }

    pub fn snapshot(&self) -> ProgressEvent {
        let elapsed = self.start_time.elapsed();
        let scanned = self.scanned.load(Ordering::Relaxed);
        let speed = if elapsed.as_secs() > 0 {
            scanned as f64 / elapsed.as_secs_f64()
        } else {
            scanned as f64
        };
        ProgressEvent {
            scanned,
            found: self.found.load(Ordering::Relaxed) as u32,
            speed,
            elapsed_secs: elapsed.as_secs(),
            phase: ScanPhase::Idle,
        }
    }

    pub fn is_cancelled(&self) -> bool {
        self.cancel_flag.load(Ordering::Relaxed)
    }
}

// ─── 配置 ───

#[derive(Debug, Clone)]
pub struct ScanConfig {
    pub include_registry: bool,
    pub include_fixed_paths: bool,
    pub include_full_scan: bool,
    pub drives: Vec<String>,
}

impl Default for ScanConfig {
    fn default() -> Self {
        Self {
            include_registry: true,
            include_fixed_paths: true,
            include_full_scan: true,
            drives: Vec::new(),
        }
    }
}
