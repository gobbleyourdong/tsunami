/**
 * useIPC — React hook for Electron IPC communication.
 *
 * Wraps window.electronAPI with type safety and React state.
 * Falls back gracefully when running in a regular browser (vite dev).
 */

import { useState, useEffect, useCallback } from 'react';

interface ElectronAPI {
  getAppPath: () => Promise<string>;
  showOpenDialog: (options: Record<string, unknown>) => Promise<{
    canceled: boolean;
    filePaths: string[];
  }>;
  showSaveDialog: (options: Record<string, unknown>) => Promise<{
    canceled: boolean;
    filePath: string;
  }>;
  readFile: (path: string) => Promise<string>;
  writeFile: (path: string, content: string) => Promise<boolean>;
  send: (channel: string, data: unknown) => void;
  on: (channel: string, callback: (...args: unknown[]) => void) => () => void;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

const isElectron = typeof window !== 'undefined' && !!window.electronAPI;

export function useIPC() {
  const [appPath, setAppPath] = useState<string>('');

  useEffect(() => {
    if (isElectron) {
      window.electronAPI!.getAppPath().then(setAppPath);
    }
  }, []);

  const invoke = useCallback(async (channel: string, ...args: unknown[]) => {
    if (!isElectron) {
      console.warn(`[useIPC] Not in Electron — ${channel} ignored`);
      return { canceled: true, filePaths: [], filePath: '' };
    }
    const api = window.electronAPI!;
    switch (channel) {
      case 'show-open-dialog': return api.showOpenDialog(args[0] as Record<string, unknown>);
      case 'show-save-dialog': return api.showSaveDialog(args[0] as Record<string, unknown>);
      case 'read-file': return api.readFile(args[0] as string);
      case 'write-file': return api.writeFile(args[0] as string, args[1] as string);
      default: return null;
    }
  }, []);

  const subscribe = useCallback((channel: string, callback: (...args: unknown[]) => void) => {
    if (!isElectron) return () => {};
    return window.electronAPI!.on(channel, callback);
  }, []);

  return { invoke, subscribe, appPath, isElectron };
}
