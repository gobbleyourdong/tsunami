/**
 * Electron main process — creates the BrowserWindow and handles IPC.
 *
 * This runs in Node.js, not the browser. It manages:
 * - Window creation and lifecycle
 * - Native OS integration (menus, dialogs, notifications)
 * - IPC communication with the renderer (React app)
 */

import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import path from 'path';

const isDev = !app.isPackaged;

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0a0e17',
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App lifecycle
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// IPC handlers — the bridge between renderer and main
ipcMain.handle('get-app-path', () => app.getPath('userData'));

ipcMain.handle('show-open-dialog', async (_event, options) => {
  if (!mainWindow) return { canceled: true, filePaths: [] };
  return dialog.showOpenDialog(mainWindow, options);
});

ipcMain.handle('show-save-dialog', async (_event, options) => {
  if (!mainWindow) return { canceled: true, filePath: '' };
  return dialog.showSaveDialog(mainWindow, options);
});

ipcMain.handle('read-file', async (_event, filePath: string) => {
  const fs = await import('fs/promises');
  return fs.readFile(filePath, 'utf-8');
});

ipcMain.handle('write-file', async (_event, filePath: string, content: string) => {
  const fs = await import('fs/promises');
  await fs.writeFile(filePath, content, 'utf-8');
  return true;
});
