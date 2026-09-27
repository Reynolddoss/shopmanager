//! Tauri desktop shell for MM Electricals.
//!
//! Release builds start the bundled Django API (`resources/api/`), show the
//! splash page until it accepts connections, then point the window at
//! `http://127.0.0.1:<port>/`, where Django serves the UI, API, and photos.
//! The API is stopped when the app exits (and stops itself if the shell dies).
//!
//! Debug builds (`tauri dev`) use the Vite dev server and a Django you start
//! yourself, so nothing is spawned.

use std::fs::{self, File};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager, RunEvent, Url};

/// Fixed port keeps the page origin stable, so browser storage (theme) survives restarts.
const PREFERRED_PORT: u16 = 48620;
/// Upper bound for migrations + integrity checks after an update on a slow PC.
const STARTUP_TIMEOUT: Duration = Duration::from_secs(180);
const MAIN_WINDOW: &str = "main";
#[cfg(windows)]
const API_EXE: &str = "mm-electricals-api.exe";
#[cfg(not(windows))]
const API_EXE: &str = "mm-electricals-api";

/// Running API process, killed on exit.
struct ApiProcess(Mutex<Option<Child>>);

/// What the splash page shows; polled through the `startup_status` command.
#[derive(Clone, Default, serde::Serialize)]
struct StartupStatus {
    failed: bool,
    message: String,
    log_path: String,
}

struct Startup(Mutex<StartupStatus>);

#[tauri::command]
fn startup_status(state: tauri::State<'_, Startup>) -> StartupStatus {
    state.0.lock().map(|status| status.clone()).unwrap_or_default()
}

/// Same folder the Python launcher uses: shop data never lives in Program Files.
fn data_dir() -> PathBuf {
    #[cfg(windows)]
    {
        let base = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from(std::env::var_os("USERPROFILE").unwrap_or_default()).join("AppData").join("Local"));
        base.join("MMElectricals")
    }
    #[cfg(not(windows))]
    {
        PathBuf::from(std::env::var_os("HOME").unwrap_or_default()).join(".mm_electricals")
    }
}

/// Preferred port when free, otherwise any free loopback port.
fn pick_port() -> u16 {
    if TcpListener::bind(("127.0.0.1", PREFERRED_PORT)).is_ok() {
        return PREFERRED_PORT;
    }
    TcpListener::bind(("127.0.0.1", 0))
        .and_then(|listener| listener.local_addr())
        .map(|addr| addr.port())
        .unwrap_or(PREFERRED_PORT)
}

fn spawn_api(exe: &Path, port: u16, data: &Path) -> std::io::Result<Child> {
    let logs = data.join("logs");
    fs::create_dir_all(&logs)?;
    // Catches errors from before Python's own logging starts (e.g. a broken bundle).
    let console_log = File::create(logs.join("api-console.log"))?;
    let mut command = Command::new(exe);
    command
        .arg("--port")
        .arg(port.to_string())
        .arg("--data-dir")
        .arg(data)
        .env("MM_PARENT_PID", std::process::id().to_string())
        .stdin(Stdio::null())
        .stdout(console_log.try_clone()?)
        .stderr(console_log);
    if let Some(dir) = exe.parent() {
        command.current_dir(dir);
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW: no black console window next to the app.
        command.creation_flags(0x0800_0000);
    }
    command.spawn()
}

fn fail_startup(app: &AppHandle, message: impl Into<String>) {
    let log_path = data_dir().join("logs").join("api.log").display().to_string();
    if let Ok(mut status) = app.state::<Startup>().0.lock() {
        *status = StartupStatus { failed: true, message: message.into(), log_path };
    }
}

fn api_has_exited(app: &AppHandle) -> bool {
    let state = app.state::<ApiProcess>();
    let mut guard = match state.0.lock() {
        Ok(guard) => guard,
        Err(_) => return false,
    };
    match guard.as_mut() {
        Some(child) => matches!(child.try_wait(), Ok(Some(_))),
        None => true,
    }
}

/// Poll the port in the background; switch the window to the shop once it answers.
fn open_when_ready(app: AppHandle, port: u16) {
    std::thread::spawn(move || {
        let addr = SocketAddr::from(([127, 0, 0, 1], port));
        let started = Instant::now();
        loop {
            if TcpStream::connect_timeout(&addr, Duration::from_millis(500)).is_ok() {
                let url = Url::parse(&format!("http://127.0.0.1:{port}/")).expect("valid loopback URL");
                match app.get_webview_window(MAIN_WINDOW) {
                    Some(window) => {
                        if let Err(err) = window.navigate(url) {
                            fail_startup(&app, format!("Could not open the shop window: {err}"));
                        }
                    }
                    None => fail_startup(&app, "The main window is missing."),
                }
                return;
            }
            if api_has_exited(&app) {
                fail_startup(&app, "The shop service stopped while starting.");
                return;
            }
            if started.elapsed() > STARTUP_TIMEOUT {
                fail_startup(&app, "The shop service took too long to start.");
                return;
            }
            std::thread::sleep(Duration::from_millis(250));
        }
    });
}

/// Tauri refuses exe paths that pass through a symlink on macOS; fall back to the resolved real path.
fn resource_dir(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(dir) = app.path().resource_dir() {
        return Ok(dir);
    }
    let exe = std::env::current_exe().and_then(|path| path.canonicalize()).map_err(|err| err.to_string())?;
    let exe_dir = exe.parent().ok_or("executable has no parent folder")?;
    if cfg!(target_os = "macos") {
        exe_dir.join("../Resources").canonicalize().map_err(|err| err.to_string())
    } else {
        Ok(exe_dir.to_path_buf())
    }
}

fn start_api(app: &AppHandle) {
    let exe = match resource_dir(app) {
        Ok(dir) => dir.join("api").join(API_EXE),
        Err(err) => return fail_startup(app, format!("Install folder not found: {err}")),
    };
    if !exe.is_file() {
        return fail_startup(app, format!("Shop service is missing: {}. Reinstall the app.", exe.display()));
    }
    let port = pick_port();
    match spawn_api(&exe, port, &data_dir()) {
        Ok(child) => {
            if let Ok(mut slot) = app.state::<ApiProcess>().0.lock() {
                *slot = Some(child);
            }
            open_when_ready(app.clone(), port);
        }
        Err(err) => fail_startup(app, format!("Could not start the shop service: {err}")),
    }
}

fn stop_api(app: &AppHandle) {
    if let Ok(mut slot) = app.state::<ApiProcess>().0.lock() {
        if let Some(mut child) = slot.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // Must be first: a second launch focuses the open window instead of starting another API.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window(MAIN_WINDOW) {
                let _ = window.unminimize();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .manage(ApiProcess(Mutex::new(None)))
        .manage(Startup(Mutex::new(StartupStatus::default())))
        .invoke_handler(tauri::generate_handler![startup_status])
        .setup(|app| {
            if !cfg!(debug_assertions) {
                start_api(app.handle());
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building MM Electricals")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                stop_api(app);
            }
        });
}
