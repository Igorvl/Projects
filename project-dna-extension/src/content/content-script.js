/**
 * CONTENT-SCRIPT.JS — Bridge between Page and Extension
 * ======================================================
 *
 * This script runs in the extension's ISOLATED WORLD — it shares
 * the DOM with the page but has a separate JavaScript context.
 * It can access Chrome Extension APIs (chrome.runtime, chrome.storage)
 * but CANNOT access the page's JavaScript variables (window.fetch, etc.)
 *
 * PURPOSE:
 * 1. Inject page-script.js into the page's own JavaScript context
 * 2. Listen for messages from page-script.js (via window.postMessage)
 * 3. Forward captured data to the service worker (via chrome.runtime.sendMessage)
 *
 * DATA FLOW:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │  Browser Tab (aistudio.google.com)                              │
 * │                                                                  │
 * │  ┌─── Page Context ───────────────────────────────────────────┐ │
 * │  │  page-script.js                                            │ │
 * │  │  → Intercepts fetch() calls to Gemini API                  │ │
 * │  │  → Posts data via: window.postMessage({type, payload}, '*')│ │
 * │  └────────────────────────────┬───────────────────────────────┘ │
 * │                               │ window.postMessage               │
 * │  ┌─── Extension Context ──────▼──────────────────────────────┐ │
 * │  │  content-script.js (THIS FILE)                             │ │
 * │  │  → Listens for postMessage events                          │ │
 * │  │  → Validates message type and origin                       │ │
 * │  │  → Forwards to service worker via chrome.runtime           │ │
 * │  └────────────────────────────┬───────────────────────────────┘ │
 * └───────────────────────────────┼──────────────────────────────────┘
 *                                 │ chrome.runtime.sendMessage
 * ┌───────────────────────────────▼──────────────────────────────────┐
 * │  Service Worker (service-worker.js)                              │
 * │  → Processes captured data                                       │
 * │  → Sends to Project DNA API (POST /v1/dna/capture)              │
 * └──────────────────────────────────────────────────────────────────┘
 *
 * ISOLATED WORLD EXPLAINED:
 * Chrome/Safari run content scripts in a separate JavaScript "world"
 * from the page. Think of it as two people in the same room (DOM),
 * but each wearing noise-canceling headphones (isolated JS context).
 * They can both see and touch the furniture (DOM elements), but they
 * can't hear each other's conversations (JS variables/functions).
 * window.postMessage is like passing a written note between them.
 *
 * @see https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts
 */

(function () {
  'use strict';

  // =========================================================================
  // CONSTANTS
  // =========================================================================

  /** Must match the MESSAGE_TYPE in page-script.js */
  const MESSAGE_TYPE = 'PROJECT_DNA_CAPTURE';

  /** Must match the STATUS_TYPE in page-script.js */
  const STATUS_TYPE = 'PROJECT_DNA_STATUS';

  /** Expected origins for messages */
  const EXPECTED_ORIGINS = ['https://aistudio.google.com', 'https://gemini.google.com'];

  // =========================================================================
  // STEP 1: INJECT PAGE-SCRIPT INTO THE PAGE CONTEXT
  // =========================================================================

  /**
   * Inject our page-script.js into the page's own JavaScript context.
   *
   * HOW IT WORKS:
   * 1. We create a <script> element in the DOM
   * 2. Set its `src` to our page-script.js file (via chrome.runtime.getURL)
   * 3. The browser downloads and executes it in the PAGE's context
   * 4. Once loaded, we remove the <script> tag (it's already executed)
   *
   * WHY chrome.runtime.getURL?
   * Extension files are not accessible by default from the page.
   * We declared page-script.js in manifest.json's "web_accessible_resources"
   * which allows the page to load it. chrome.runtime.getURL converts
   * a relative extension path to a full chrome-extension:// URL.
   */
  async function injectPageScript() {
    try {
      const url = chrome.runtime.getURL('src/content/page-script.js');
      console.log('[Project DNA] 🧬 Attempting to inject:', url);
      
      const response = await fetch(url);
      if (!response.ok) throw new Error('Network response was not ok');
      const code = await response.text();
      
      const script = document.createElement('script');
      
      // Try inline text injection (works around some Safari CSP restrictions)
      script.text = code;
      
      script.onload = function() {
        console.log('[Project DNA] 🧬 Page interceptor injected successfully via text');
        this.remove();
      };
      
      script.onerror = function() {
        console.error('[Project DNA] ❌ Failed to inject via text, trying Blob...');
        
        // Fallback: Blob URL
        const blob = new Blob([code], { type: 'application/javascript' });
        const blobUrl = URL.createObjectURL(blob);
        const fbScript = document.createElement('script');
        fbScript.src = blobUrl;
        fbScript.onload = () => {
          console.log('[Project DNA] 🧬 Page interceptor injected via Blob');
          fbScript.remove();
          URL.revokeObjectURL(blobUrl);
        };
        fbScript.onerror = () => {
           console.error('[Project DNA] ❌ Failed to inject via Blob. CSP is completely blocking it.');
        };
        (document.head || document.documentElement).appendChild(fbScript);
        this.remove();
      };

      (document.head || document.documentElement).appendChild(script);
      
      // For inline scripts, onload might not fire. Just assume success if no error.
      setTimeout(() => {
        if (script.parentNode) script.remove();
      }, 100);

    } catch (err) {
      console.error('[Project DNA] ❌ Critical failure loading page-script:', err);
    }
  }

  // =========================================================================
  // STEP 2: LISTEN FOR MESSAGES FROM PAGE-SCRIPT
  // =========================================================================

  /**
   * Handle messages from page-script.js.
   *
   * SECURITY CONSIDERATIONS:
   * - We check event.origin to ensure the message comes from AI Studio
   * - We check the message type to filter out unrelated postMessage traffic
   * - We never trust the data blindly — the service worker validates it
   *
   * @param {MessageEvent} event - The postMessage event
   */
  function handlePageMessage(event) {
    // SECURITY: Verify the message origin
    // Only accept messages from allowed domains
    if (!EXPECTED_ORIGINS.includes(event.origin)) return;

    // Ignore messages without our data structure
    if (!event.data || !event.data.type) return;

    // ----- Handle capture messages -----
    if (event.data.type === MESSAGE_TYPE) {
      const capturedData = event.data.payload;
      console.log(
        '[Project DNA] 📨 Received capture from page-script:',
        `#${capturedData.captureIndex}`,
        capturedData.model
      );

      // Forward to service worker via Chrome Extension messaging API
      // chrome.runtime.sendMessage sends a message to the extension's
      // service worker (background script). Unlike postMessage, this
      // uses Chrome's internal messaging channel — secure and fast.
      try {
        chrome.runtime.sendMessage({
          action: 'CAPTURE_GENERATION',
          data: capturedData,
        }, (response) => {
          // Handle response from service worker (optional)
          if (chrome.runtime.lastError) {
            console.warn(
              '[Project DNA] Service worker unavailable:',
              chrome.runtime.lastError.message
            );
            return;
          }
          if (response && response.success) {
            console.log(
              `[Project DNA] ✅ Generation #${capturedData.captureIndex} sent to Project DNA API`
            );
          }
        });
      } catch (err) {
        if (err.message && err.message.includes('Extension context invalidated')) {
          console.error('[Project DNA] ❌ Extension was updated. The page must be refreshed.');
          alert('[Project DNA AI Capture] Расширение было обновлено!\n\nПожалуйста, обновите страницу (F5), чтобы продолжить перехват генераций.');
        } else {
          console.error('[Project DNA] ❌ Error sending message to service worker:', err);
        }
      }
    }

    // ----- Handle status messages -----
    if (event.data.type === STATUS_TYPE) {
      console.log(
        '[Project DNA] 📡 Interceptor status:',
        event.data.payload.status
      );

      // Notify service worker about interceptor status
      chrome.runtime.sendMessage({
        action: 'INTERCEPTOR_STATUS',
        data: event.data.payload,
      });
    }
  }

  // Register the message listener
  window.addEventListener('message', handlePageMessage, false);

  // =========================================================================
  // STEP 3: LISTEN FOR MESSAGES FROM SERVICE WORKER
  // =========================================================================

  /**
   * Handle messages from the service worker (e.g., config updates).
   *
   * The service worker can send messages to content scripts for:
   * - Configuration changes (new API URL, active project, etc.)
   * - Capture confirmations
   * - Status queries
   */
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Only handle messages from our own extension
    if (sender.id !== chrome.runtime.id) return;

    switch (message.action) {
      case 'PING':
        // Service worker wants to know if content script is alive
        sendResponse({ alive: true, url: window.location.href });
        break;

      case 'GET_PAGE_INFO':
        // Service worker wants info about the current AI Studio session
        sendResponse({
          url: window.location.href,
          title: document.title,
          timestamp: new Date().toISOString(),
        });
        break;

      default:
        break;
    }

    // Return true to indicate we'll send a response asynchronously
    // (required by Chrome Extension messaging API)
    return true;
  });

  // =========================================================================
  // INITIALIZATION
  // =========================================================================

  // Inject the page script
  injectPageScript();

  // Notify that content script is loaded
  console.log('[Project DNA] 🧬 Content script loaded on:', window.location.href);

})();
