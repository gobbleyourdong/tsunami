import { useState } from 'react';
import { useIPC } from './hooks/useIPC';

export default function App() {
  const { invoke, appPath } = useIPC();
  const [content, setContent] = useState('');
  const [filePath, setFilePath] = useState('');

  const handleOpen = async () => {
    const result = await invoke('show-open-dialog', {
      properties: ['openFile'],
      filters: [{ name: 'Text', extensions: ['txt', 'md', 'json'] }],
    });
    if (!result.canceled && result.filePaths[0]) {
      const path = result.filePaths[0];
      const text = await invoke('read-file', path);
      setFilePath(path);
      setContent(text);
    }
  };

  const handleSave = async () => {
    if (!filePath) {
      const result = await invoke('show-save-dialog', {
        filters: [{ name: 'Text', extensions: ['txt', 'md'] }],
      });
      if (result.canceled) return;
      setFilePath(result.filePath);
    }
    await invoke('write-file', filePath, content);
  };

  return (
    <div className="app-container">
      <header className="toolbar">
        <h1>My Desktop App</h1>
        <div className="toolbar-actions">
          <button onClick={handleOpen}>Open</button>
          <button onClick={handleSave}>Save</button>
        </div>
      </header>
      <main className="editor">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Open a file or start typing..."
          spellCheck={false}
        />
      </main>
      <footer className="statusbar">
        <span>{filePath || 'No file open'}</span>
        <span>{content.length} chars</span>
        {appPath && <span>{appPath}</span>}
      </footer>
    </div>
  );
}
