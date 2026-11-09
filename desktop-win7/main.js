/**
 * Electron 22 desktop shell for MM Electricals on Windows 7.
 *
 * Tauri 2 and WebView2 need Windows 10+, so this shell does the same job as
 * desktop/src-tauri/src/lib.rs with the last Electron that runs on Windows 7:
 * show the splash page, start the bundled Django API (`resources/api/`), and
 * point the window at `http://127.0.0.1:<port>/` once it accepts connections.
 * The API is stopped when the app exits (and stops itself if the shell dies).
 *
 * Unpackaged (`npm start`): set MM_API_DIR to a frozen API folder to test the
 * full startup, or leave it unset to load the Vite dev server (MM_DEV_URL)
 * against a Django you start yourself.
 *
 * Delete this folder once the Windows 7 shop PC has been upgraded.
 */

const { app, BrowserWindow, ipcMain, Menu, shell } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const net = require("net");
const os = require("os");
const path = require("path");

/** Fixed port keeps the page origin stable, so browser storage (theme) survives restarts. */
const PREFERRED_PORT = 48620;
/** Upper bound for migrations + integrity checks after an update on a slow PC. */
const STARTUP_TIMEOUT_MS = 180 * 1000;
const API_EXE = process.platform === "win32" ? "mm-electricals-api.exe" : "mm-electricals-api";
const DEV_URL = process.env.MM_DEV_URL || "http://127.0.0.1:5173";

let mainWindow = null;
let apiProcess = null;
let apiExited = false;
let startupStatus = { failed: false, message: "", log_path: "" };

/** Same folder the Python launcher uses: shop data never lives next to the program. */
const dataDir = () =>
  process.platform === "win32"
    ? path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "MMElectricals")
    : path.join(os.homedir(), ".mm_electricals");

const apiDir = () => (app.isPackaged ? path.join(process.resourcesPath, "api") : process.env.MM_API_DIR || null);

const splashPath = () =>
  app.isPackaged
    ? path.join(__dirname, "splash", "index.html")
    : path.join(__dirname, "..", "desktop", "splash", "index.html");

const failStartup = (message) => {
  startupStatus = { failed: true, message, log_path: path.join(dataDir(), "logs", "api.log") };
};

const portIsFree = (port) =>
  new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.listen(port, "127.0.0.1", () => server.close(() => resolve(true)));
  });

const anyFreePort = () =>
  new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });

/** Preferred port when free, otherwise any free loopback port. */
const pickPort = async () => ((await portIsFree(PREFERRED_PORT)) ? PREFERRED_PORT : anyFreePort());

const portAnswers = (port) =>
  new Promise((resolve) => {
    const socket = net.connect({ host: "127.0.0.1", port });
    const done = (ok) => {
      socket.destroy();
      resolve(ok);
    };
    socket.setTimeout(500, () => done(false));
    socket.once("connect", () => done(true));
    socket.once("error", () => done(false));
  });

const spawnApi = (exe, port, data) => {
  const logs = path.join(data, "logs");
  fs.mkdirSync(logs, { recursive: true });
  // Catches errors from before Python's own logging starts (e.g. a broken bundle).
  const consoleLog = fs.openSync(path.join(logs, "api-console.log"), "w");
  const child = spawn(exe, ["--port", String(port), "--data-dir", data], {
    cwd: path.dirname(exe),
    env: { ...process.env, MM_PARENT_PID: String(process.pid) },
    stdio: ["ignore", consoleLog, consoleLog],
    // No black console window next to the app.
    windowsHide: true,
  });
  fs.closeSync(consoleLog);
  child.once("exit", () => {
    apiExited = true;
  });
  return child;
};

/** Poll the port; switch the window to the shop once it answers. */
const openWhenReady = async (port) => {
  const started = Date.now();
  while (true) {
    if (await portAnswers(port)) {
      if (mainWindow) mainWindow.loadURL(`http://127.0.0.1:${port}/`);
      return;
    }
    if (apiExited) return failStartup("The shop service stopped while starting.");
    if (Date.now() - started > STARTUP_TIMEOUT_MS) return failStartup("The shop service took too long to start.");
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
};

const startApi = async (dir) => {
  const exe = path.join(dir, API_EXE);
  if (!fs.existsSync(exe)) return failStartup(`Shop service is missing: ${exe}. Reinstall the app.`);
  try {
    const port = await pickPort();
    apiProcess = spawnApi(exe, port, dataDir());
    apiProcess.once("error", (err) => failStartup(`Could not start the shop service: ${err.message}`));
    await openWhenReady(port);
  } catch (err) {
    failStartup(`Could not start the shop service: ${err.message}`);
  }
};

const stopApi = () => {
  if (apiProcess && !apiExited) apiProcess.kill();
  apiProcess = null;
};

const createWindow = () => {
  mainWindow = new BrowserWindow({
    title: "MM Electricals",
    width: 1280,
    height: 840,
    minWidth: 1024,
    minHeight: 640,
    center: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  // Keep the page title fixed, like the Tauri window.
  mainWindow.on("page-title-updated", (event) => event.preventDefault());
  // Links that would open a new window go to the system browser instead.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
};

// A second launch focuses the open window instead of starting another API.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });

  ipcMain.handle("startup-status", () => startupStatus);

  app.whenReady().then(() => {
    Menu.setApplicationMenu(null);
    createWindow();
    const dir = apiDir();
    if (dir) {
      mainWindow.loadFile(splashPath());
      startApi(dir);
    } else {
      mainWindow.loadURL(DEV_URL);
    }
  });

  app.on("window-all-closed", () => app.quit());
  app.on("will-quit", stopApi);
}
