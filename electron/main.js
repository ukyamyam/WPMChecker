const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const path = require('node:path');

let mainWindow;

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

ipcMain.on('show-context-menu', () => {
  buildMenu().popup({ window: mainWindow });
});

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
