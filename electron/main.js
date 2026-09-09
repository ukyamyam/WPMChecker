const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const crypto = require('node:crypto');
const path = require('node:path');
const { createBackendSpec, startBackend, stopBackend } = require('./backend-process');

let mainWindow;
let backendProcess;
let backendAuthToken;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 220,
    height: 120,
    minWidth: 180,
    minHeight: 95,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: true,
    skipTaskbar: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  mainWindow.setAlwaysOnTop(true, 'screen-saver');
  mainWindow.loadFile(path.join(__dirname, 'renderer.html'));
}

function sendCommand(command) {
  if (mainWindow) mainWindow.webContents.send('backend-command', command);
}

function buildMenu() {
  return Menu.buildFromTemplate([
    {
      label: 'Input Source',
      submenu: [
        { label: 'System audio', type: 'radio', checked: true, click: () => sendCommand({ type: 'setSource', source: 'system' }) },
        { label: 'Microphone', type: 'radio', click: () => sendCommand({ type: 'setSource', source: 'mic' }) }
      ]
    },
    {
      label: 'WPM Mode',
      submenu: [
        { label: 'Effective speech WPM', type: 'radio', checked: true, click: () => sendCommand({ type: 'setMode', mode: 'effective' }) },
        { label: 'Elapsed-time WPM', type: 'radio', click: () => sendCommand({ type: 'setMode', mode: 'elapsed' }) }
      ]
    },
    {
      label: 'Window Seconds',
      submenu: [3, 5, 7, 10].map((seconds) => ({
        label: `${seconds}s`,
        type: 'radio',
        checked: seconds === 5,
        click: () => sendCommand({ type: 'setWindow', seconds })
      }))
    },
    { type: 'separator' },
    { label: 'Quit', role: 'quit' }
  ]);
}

const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  app.quit();
} else {
  ipcMain.on('show-context-menu', () => {
    buildMenu().popup({ window: mainWindow });
  });

  ipcMain.handle('get-backend-token', () => backendAuthToken);

  app.whenReady().then(() => {
    backendAuthToken = crypto.randomBytes(32).toString('hex');
    const spec = createBackendSpec({
      isPackaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      appPath: app.getAppPath(),
      authToken: backendAuthToken
    });
    backendProcess = startBackend(spec, {
      onError: (error) => console.error('Failed to start WPMChecker backend:', error)
    });
    createWindow();
  });

  app.on('second-instance', () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });
  app.on('before-quit', () => stopBackend(backendProcess));
  app.on('window-all-closed', () => app.quit());
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
}
