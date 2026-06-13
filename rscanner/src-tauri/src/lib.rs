use scanner_core::scanner::{get_available_drives, Scanner};
use scanner_core::types::*;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tauri::{AppHandle, Emitter, State};

struct ScannerState {
    cancel_flag: Arc<AtomicBool>,
}

#[tauri::command]
fn start_scan(
    app: AppHandle,
    drives: Vec<String>,
    state: State<'_, ScannerState>,
) -> Result<(), String> {
    eprintln!("[start_scan] called, drives={:?}", drives);
    state.cancel_flag.store(false, Ordering::Relaxed);
    let cancel = state.cancel_flag.clone();

    let (progress_tx, progress_rx) = crossbeam_channel::unbounded::<ProgressEvent>();
    let (phase_tx, phase_rx) = crossbeam_channel::unbounded::<ScanPhase>();

    let app_handle = app.clone();
    let drives_clone = drives.clone();

    // Forward progress events to UI
    let app_h = app_handle.clone();
    std::thread::spawn(move || {
        while let Ok(event) = progress_rx.recv() {
            let _ = app_h.emit("scan-progress", &event);
        }
    });

    let app_h2 = app_handle.clone();
    std::thread::spawn(move || {
        while let Ok(phase) = phase_rx.recv() {
            eprintln!("[phase] {:?}", phase);
            let _ = app_h2.emit("scan-phase", &serde_json::json!({ "phase": phase }));
        }
    });

    // Spawn scan in background thread
    std::thread::spawn(move || {
        let mut scanner = Scanner::with_cancel(cancel);
        scanner.set_channels(progress_tx, phase_tx);

        let config = ScanConfig {
            include_registry: true,
            include_fixed_paths: true,
            include_full_scan: true,
            drives: drives_clone,
        };

        eprintln!("[scan] starting run_scan...");
        let results = scanner.run_scan(&config);
        eprintln!("[scan] done, found {} items", results.len());

        let _ = app_handle.emit(
            "scan-complete",
            &ScanCompleteEvent {
                total_found: results.len() as u32,
                results,
            },
        );
    });

    Ok(())
}

#[tauri::command]
fn cancel_scan(state: State<'_, ScannerState>) -> Result<(), String> {
    eprintln!("[cancel_scan] called");
    state.cancel_flag.store(true, Ordering::Relaxed);
    Ok(())
}

#[tauri::command]
fn get_drives() -> Vec<String> {
    let drives = get_available_drives();
    eprintln!("[get_drives] {:?}", drives);
    drives
}

#[tauri::command]
fn delete_files(paths: Vec<String>) -> Vec<DeleteResult> {
    paths
        .into_iter()
        .map(|path| {
            let (success, error) = scanner_core::scanner::delete_to_recycle_bin(&path);
            DeleteResult {
                path,
                success,
                error,
            }
        })
        .collect()
}

#[tauri::command]
fn clean_registry() -> CleanRegistryResult {
    let scanner = Scanner::new();
    scanner.clean_registry()
}

#[tauri::command]
fn open_in_explorer(path: String) -> Result<(), String> {
    scanner_core::scanner::open_explorer_at(&path);
    Ok(())
}

#[tauri::command]
fn get_city_from_ip() -> String {
    notifier::get_city_from_ip()
}

#[tauri::command]
fn send_report(name: String, results: Vec<DetectionResult>, city: String) -> Result<(), String> {
    // 企业微信通知
    let notify_result = notifier::send_notification(&name, &results, None, &city);
    // 智能表上报（失败不阻断）
    let sheet_result = notifier::push_results_to_smartsheet(&name, &results, None, &city);

    match (notify_result, sheet_result) {
        (Ok(()), Ok(())) => Ok(()),
        (Ok(()), Err(e)) => Err(format!("企业微信通知成功，智能表上报失败: {}", e)),
        (Err(e), Ok(())) => Err(format!("企业微信通知失败: {}，智能表上报成功", e)),
        (Err(e1), Err(e2)) => Err(format!("企业微信: {}; 智能表: {}", e1, e2)),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    eprintln!("[run] starting tauri app...");
    tauri::Builder::default()
        .manage(ScannerState {
            cancel_flag: Arc::new(AtomicBool::new(false)),
        })
        .invoke_handler(tauri::generate_handler![
            start_scan,
            cancel_scan,
            get_drives,
            delete_files,
            clean_registry,
            open_in_explorer,
            get_city_from_ip,
            send_report,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
