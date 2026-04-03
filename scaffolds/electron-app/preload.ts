/**
 * Preload script — bridge between Node.js and browser contexts.
 *
 * Uses contextBridge to safely expose IPC methods to the renderer.
 * The renderer calls window.electronAPI.* instead of require('electron').
 */

import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  // App info
  getAppPath: () => ipcRenderer.invoke('get-app-path'),

  // File dialogs
  showOpenDialog: (options: Record<string, unknown>) =>
    ipcRenderer.invoke('show-open-dialog', options),
  showSaveDialog: (options: Record<string, unknown>) =>
    ipcRenderer.invoke('show-save-dialog', options),

  // File I/O
  readFile: (path: string) => ipcRenderer.invoke('read-file', path),
  writeFile: (path: string, content: string) =>
    ipcRenderer.invoke('write-file', path, content),

  // Generic IPC
  send: (channel: string, data: unknown) => ipcRenderer.send(channel, data),
  on: (channel: string, callback: (...args: unknown[]) => void) => {
    const subscription = (_event: unknown, ...args: unknown[]) => callback(...args);
    ipcRenderer.on(channel, subscription);
    return () => ipcRenderer.removeListener(channel, subscription);
  },
});
