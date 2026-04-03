/**
 * Background service worker — runs persistently (MV3).
 *
 * Handles events: install, tab updates, alarms, messages.
 * No DOM access — communicate with content scripts via messaging.
 */

// On install — set default storage
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ extensionData: { installed: Date.now() } });
  console.log('Extension installed');
});

// Listen for messages from content scripts or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_TAB_INFO') {
    sendResponse({
      tabId: sender.tab?.id,
      url: sender.tab?.url,
    });
  }
  return true;
});

// Example: badge text update on tab change
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab.url) {
      const hostname = new URL(tab.url).hostname;
      chrome.action.setBadgeText({ text: hostname.slice(0, 3) });
      chrome.action.setBadgeBackgroundColor({ color: '#4a9eff' });
    }
  } catch {
    // Tab may have been closed
  }
});
