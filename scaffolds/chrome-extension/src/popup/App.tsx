import { useState, useEffect } from 'react';

export default function App() {
  const [status, setStatus] = useState('Ready');

  useEffect(() => {
    // Example: get data from storage on popup open
    chrome.storage.local.get(['extensionData'], (result) => {
      if (result.extensionData) {
        setStatus(`Data: ${JSON.stringify(result.extensionData)}`);
      }
    });
  }, []);

  const handleAction = () => {
    // Send message to content script on active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'EXTENSION_ACTION' });
        setStatus('Action sent to page');
      }
    });
  };

  return (
    <div className="popup-container">
      <h1>My Extension</h1>
      <p className="status">{status}</p>
      <button onClick={handleAction}>Run Action</button>
    </div>
  );
}
