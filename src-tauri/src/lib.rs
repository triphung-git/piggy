use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_opener::OpenerExt;
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Serialize)]
pub struct ConnectionInfo {
    base_url: String,
    token: String,
    ready: bool,
    appdata_dir: PathBuf,
    error: Option<String>,
}

pub struct BackendState {
    lifecycle: Mutex<()>,
    child: Mutex<Option<CommandChild>>,
    port: Mutex<u16>,
    token: String,
    ready: AtomicBool,
    terminated: AtomicBool,
    generation: AtomicU64,
    error: Mutex<Option<String>>,
    appdata_dir: PathBuf,
    resource_dir: PathBuf,
}

#[derive(Deserialize)]
struct ServerReadySignal {
    event: String,
    port: Option<u16>,
}

fn spawn_backend(app: &AppHandle, state: Arc<BackendState>) -> Result<(), String> {
    let lifecycle_state = state.clone();
    let _guard = lifecycle_state.lifecycle.lock().map_err(|e| e.to_string())?;
    if !state.terminated.load(Ordering::SeqCst) {
        return Err("Backend is still running".into());
    }
    let command = app.shell().sidecar("tft-backend").map_err(|e| e.to_string())?
        .env("TFT_APPDATA_DIR", &state.appdata_dir)
        .env("TFT_RESOURCE_DIR", &state.resource_dir)
        .env("STUDIO_SESSION_TOKEN", &state.token)
        .set_process_group(true);
    let (mut rx, child) = command.spawn().map_err(|e| e.to_string())?;
    let generation = state.generation.fetch_add(1, Ordering::SeqCst) + 1;
    *state.child.lock().map_err(|e| e.to_string())? = Some(child);
    *state.error.lock().map_err(|e| e.to_string())? = None;
    state.terminated.store(false, Ordering::SeqCst);
    state.ready.store(false, Ordering::SeqCst);
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            if generation != state.generation.load(Ordering::SeqCst) { break; }
            match event {
                CommandEvent::Stdout(bytes) => {
                    if let Ok(signal) = serde_json::from_slice::<ServerReadySignal>(&bytes) {
                        if signal.event == "server_ready" {
                            if let Some(port) = signal.port {
                                if let Ok(mut current) = state.port.lock() { *current = port; }
                            }
                            state.ready.store(true, Ordering::SeqCst);
                            let _ = app.emit("backend-ready", ());
                        }
                    }
                }
                CommandEvent::Stderr(bytes) => eprintln!("[Backend] {}", String::from_utf8_lossy(&bytes)),
                CommandEvent::Terminated(payload) => {
                    state.ready.store(false, Ordering::SeqCst);
                    if let Ok(mut child) = state.child.lock() { *child = None; }
                    if let Ok(mut error) = state.error.lock() { *error = Some(format!("Backend stopped ({:?})", payload.code)); }
                    let _ = app.emit("backend-stopped", ());
                    state.terminated.store(true, Ordering::SeqCst);
                    break;
                }
                _ => {}
            }
        }
    });
    Ok(())
}

#[tauri::command]
pub fn get_backend_connection_info(state: State<Arc<BackendState>>) -> Result<ConnectionInfo, String> {
    let port = *state.port.lock().map_err(|e| e.to_string())?;
    let error = state.error.lock().map_err(|e| e.to_string())?.clone();
    Ok(ConnectionInfo {
        base_url: format!("http://127.0.0.1:{port}"),
        token: state.token.clone(),
        ready: state.ready.load(Ordering::SeqCst),
        appdata_dir: state.appdata_dir.clone(),
        error,
    })
}

#[tauri::command]
pub async fn stop_backend_sidecar(state: State<'_, Arc<BackendState>>) -> Result<(), String> {
    let state = state.inner().clone();
    tauri::async_runtime::spawn_blocking(move || {
        let _guard = state.lifecycle.lock().map_err(|e| e.to_string())?;
        if let Some(child) = state.child.lock().map_err(|e| e.to_string())?.take() {
            child.kill().map_err(|e| e.to_string())?;
        }
        state.ready.store(false, Ordering::SeqCst);
        let deadline = std::time::Instant::now() + std::time::Duration::from_secs(5);
        while !state.terminated.load(Ordering::SeqCst) {
            if std::time::Instant::now() > deadline { return Err("Backend did not exit; installation cancelled".into()); }
            std::thread::sleep(std::time::Duration::from_millis(50));
        }
        Ok(())
    }).await.map_err(|e| e.to_string())?
}

#[tauri::command]
pub fn start_backend_sidecar(app: AppHandle, state: State<Arc<BackendState>>) -> Result<(), String> {
    spawn_backend(&app, state.inner().clone())
}

#[tauri::command]
pub async fn set_preview_visibility(app: AppHandle, state: State<'_, Arc<BackendState>>, visible: bool) -> Result<bool, String> {
    if let Some(window) = app.get_webview_window("preview") {
        (if visible { window.show() } else { window.hide() }).map_err(|e| e.to_string())?;
    } else if visible {
        if !state.ready.load(Ordering::SeqCst) { return Err("Backend is not ready".into()); }
        let url = format!("http://127.0.0.1:{}/overlay", *state.port.lock().map_err(|e| e.to_string())?);
        WebviewWindowBuilder::new(&app, "preview", WebviewUrl::External(tauri::Url::parse(&url).map_err(|e| e.to_string())?))
            .title("TFT Overlay Preview").inner_size(960.0, 540.0).build().map_err(|e| e.to_string())?;
    }
    Ok(visible)
}

#[tauri::command]
pub fn open_browser_panel(app: AppHandle, state: State<Arc<BackendState>>) -> Result<(), String> {
    let port = *state.port.lock().map_err(|e| e.to_string())?;
    app.opener().open_url(format!("http://127.0.0.1:{port}/app/#token={}", state.token), None::<&str>).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn open_app_folder(app: AppHandle, state: State<Arc<BackendState>>, folder_type: String) -> Result<(), String> {
    let folder = match folder_type.as_str() {
        "output" => state.appdata_dir.join("output"),
        "logs" => state.appdata_dir.join("logs"),
        _ => return Err("Unknown folder".into()),
    };
    std::fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    app.opener().open_path(folder.to_string_lossy().to_string(), None::<&str>).map_err(|e| e.to_string())
}

pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let state = Arc::new(BackendState {
                lifecycle: Mutex::new(()),
                child: Mutex::new(None), port: Mutex::new(8080), token: uuid::Uuid::new_v4().to_string(),
                ready: AtomicBool::new(false), terminated: AtomicBool::new(true), generation: AtomicU64::new(0), error: Mutex::new(None),
                appdata_dir: app.path().app_data_dir()?, resource_dir: app.path().resource_dir()?,
            });
            std::fs::create_dir_all(&state.appdata_dir)?;
            app.manage(state.clone());
            if let Err(error) = spawn_backend(app.handle(), state.clone()) {
                *state.error.lock().unwrap() = Some(error);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_backend_connection_info, stop_backend_sidecar, start_backend_sidecar, set_preview_visibility, open_browser_panel, open_app_folder])
        .build(tauri::generate_context!())
        .expect("Failed to build TFT Studio");
    app.run(|handle, event| {
        if let RunEvent::ExitRequested { .. } = event {
            let state = handle.state::<Arc<BackendState>>();
            if let Ok(mut child) = state.child.lock() {
                if let Some(child) = child.take() { let _ = child.kill(); }
            };
        }
    });
}
