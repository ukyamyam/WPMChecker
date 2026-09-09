const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('wpmchecker', {
  showContextMenu: () => ipcRenderer.send('show-context-menu'),
  getAuthToken: () => ipcRenderer.invoke('get-backend-token'),
  onBackendCommand: (callback) => ipcRenderer.on('backend-command', (_event, command) => callback(command))
});
