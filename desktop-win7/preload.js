// The splash page's only window into the shell: read-only startup status.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("mmShell", {
  startupStatus: () => ipcRenderer.invoke("startup-status"),
});
