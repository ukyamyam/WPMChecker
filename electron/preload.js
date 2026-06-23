const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('wpmchecker', {
  showContextMenu: () => ipcRenderer.send('show-context-menu'),
  onBackendCommand: (callback) => ipcRenderer.on('backend-command', (_event, command) => callback(command))
});
