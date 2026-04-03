/**
 * Content script — injected into web pages.
 *
 * Has access to the page DOM but runs in an isolated world.
 * Communicates with the popup/background via chrome.runtime.
 */

// Listen for messages from popup or background
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'EXTENSION_ACTION') {
    // Example: highlight all links on the page
    const links = document.querySelectorAll('a');
    links.forEach((link) => {
      (link as HTMLElement).style.outline = '2px solid #4a9eff';
    });
    sendResponse({ success: true, count: links.length });
  }
  return true; // keep channel open for async response
});

// Example: inject a badge showing extension is active
const badge = document.createElement('div');
badge.textContent = 'Ext Active';
badge.style.cssText = `
  position: fixed; bottom: 10px; right: 10px; z-index: 999999;
  background: #4a9eff; color: white; padding: 4px 8px;
  border-radius: 4px; font-size: 12px; font-family: sans-serif;
  opacity: 0.8; pointer-events: none;
`;
document.body.appendChild(badge);
setTimeout(() => badge.remove(), 3000);
