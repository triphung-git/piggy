use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ConnectionInfo {
    pub base_url: String,
    pub token: String,
    pub ready: bool,
    pub appdata_dir: String,
}

pub struct BackendState {
    pub child: Mutex<Option<CommandChild>>,
    pub port: Mutex<u16>,
    pub token: String,
    pub ready: AtomicBool,
    pub appdata_dir: PathBuf,
    pub resource_dir: PathBuf,
}

#[derive(Debug, Deserialize)]
struct ServerReadySignal {
    event: String,
    port: Option<u16>,
}

#[tauri::command]
pub fn get_backend_connection_info(state: State<Arc<BackendState>>) -> Result<ConnectionInfo, String> {
    let port = *state.port.lock().map_err(|e| e.to_string())?;
    Ok(ConnectionInfo {
        base_url: format!("http://127.0.0.1:{}", port),
        token: state.token.clone(),
        ready: state.ready.load(Ordering::SeqCst),
        appdata_dir: state.appdata_dir.to_string_lossy().to_string(),
    })
}

#[tauri::command]
pub fn stop_backend_sidecar(state: State<Arc<BackendState>>) -> Result<(), String> {
    let mut child_guard = state.child.lock().map_err(|e| e.to_string())?;
    if let Some(child) = child_guard.take() {
        let _ = child.kill();
    }
    state.ready.store(false, Ordering::SeqCst);
    Ok(())
}

#[tauri::command]
pub fn open_app_folder(
    app: AppHandle,
    state: State<Arc<BackendState>>,
    folder_type: String,
) -> Result<(), String> {
    let target_dir = match folder_type.as_str() {
        "output" => state.appdata_dir.join("output"),
        "logs" => state.appdata_dir.join("logs"),
        _ => state.appdata_dir.clone(),
    };

    if !target_dir.exists() {
        let _ = std::fs::create_dir_all(&target_dir);
    }

    app.opener()
        .open_path(target_dir.to_string_lossy().to_string(), None::<&str>)
        .map_err(|e| e.to_string())
}

pub fn run() {
    let app_builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build());

    let backend_state_holder: Arc<Mutex<Option<Arc<BackendState>>>> = Arc::new(Mutex::new(None));
    let state_holder_clone = backend_state_holder.clone();

    let app = app_builder
        .setup(move |app| {
            let app_handle = app.handle().clone();

            // 1. Xác định thư mục AppData và Resources
            let appdata_dir = app_handle
                .path()
                .app_data_dir()
                .unwrap_or_else(|_| PathBuf::from("./appdata"));
            let resource_dir = app_handle
                .path()
                .resource_dir()
                .unwrap_or_else(|_| PathBuf::from("./"));

            // Đảm bảo thư mục AppData tồn tại
            let _ = std::fs::create_dir_all(&appdata_dir);
            let _ = std::fs::create_dir_all(appdata_dir.join("output"));
            let _ = std::fs::create_dir_all(appdata_dir.join("logs"));

            // 2. Tạo Session Token bí mật
            let session_token = uuid::Uuid::new_v4().to_string();

            let backend_state = Arc::new(BackendState {
                child: Mutex::new(None),
                port: Mutex::new(8080),
                token: session_token.clone(),
                ready: AtomicBool::new(false),
                appdata_dir: appdata_dir.clone(),
                resource_dir: resource_dir.clone(),
            });

            app.manage(backend_state.clone());
            if let Ok(mut holder) = state_holder_clone.lock() {
                *holder = Some(backend_state.clone());
            }

            // 3. Khởi chạy Sidecar tft-backend
            let sidecar_command = match app.shell().sidecar("tft-backend") {
                Ok(cmd) => cmd
                    .env("TFT_APPDATA_DIR", appdata_dir.to_string_lossy().to_string())
                    .env("TFT_RESOURCE_DIR", resource_dir.to_string_lossy().to_string())
                    .env("STUDIO_SESSION_TOKEN", session_token),
                Err(err) => {
                    eprintln!("[Rust] Error preparing sidecar: {:?}", err);
                    return Ok(());
                }
            };

            match sidecar_command.spawn() {
                Ok((mut rx, child)) => {
                    if let Ok(mut child_lock) = backend_state.child.lock() {
                        *child_lock = Some(child);
                    }

                    let state_for_events = backend_state.clone();
                    let handle_for_events = app_handle.clone();

                    tauri::async_runtime::spawn(async move {
                        while let Some(event) = rx.recv().await {
                            match event {
                                CommandEvent::Stdout(line_bytes) => {
                                    let line = String::from_utf8_lossy(&line_bytes);
                                    if let Ok(signal) = serde_json::from_str::<ServerReadySignal>(&line) {
                                        if signal.event == "server_ready" {
                                            if let Some(p) = signal.port {
                                                if let Ok(mut port_lock) = state_for_events.port.lock() {
                                                    *port_lock = p;
                                                }
                                            }
                                            state_for_events.ready.store(true, Ordering::SeqCst);
                                            let _ = handle_for_events.emit("backend-ready", ());
                                        }
                                    }
                                }
                                CommandEvent::Stderr(err_bytes) => {
                                    let err_line = String::from_utf8_lossy(&err_bytes);
                                    eprintln!("[Python Backend] {}", err_line);
                                }
                                CommandEvent::Terminated(term_payload) => {
                                    state_for_events.ready.store(false, Ordering::SeqCst);
                                    eprintln!("[Python Backend] Terminated with code: {:?}", term_payload.code);
                                }
                                _ => {}
                            }
                        }
                    });
                }
                Err(err) => {
                    eprintln!("[Rust] Failed to spawn sidecar: {:?}", err);
                }
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_backend_connection_info,
            stop_backend_sidecar,
            open_app_folder
        ])
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |_app_handle, event| {
        if let RunEvent::ExitRequested { .. } = event {
            if let Ok(holder) = backend_state_holder.lock() {
                if let Some(ref state) = *holder {
                    if let Ok(mut child_guard) = state.child.lock() {
                        if let Some(child) = child_guard.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        }
    });
}
