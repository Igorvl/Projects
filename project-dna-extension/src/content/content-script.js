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
 * 1. Listen for messages from page-script.js (via window.postMessage)
 * 2. Forward captured data to the service worker (via chrome.runtime.sendMessage)
 *
 * NOTE: page-script.js is now declared directly in manifest.json
 * with "world": "MAIN" — the browser injects it into the page context,
 * bypassing CSP restrictions (which broke dynamic DOM injection in April 2026
 * when Gemini updated its Content-Security-Policy).
 *
 * DATA FLOW:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │  Browser Tab (aistudio.google.com)                              │
 * │                                                                  │
 * │  ┌─── Page Context (MAIN world) ─────────────────────────────┐ │
 * │  │  page-script.js  [injected by manifest: world:MAIN]        │ │
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

  // (page-script.js is injected by manifest.json with world:MAIN — no manual injection needed)

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

      case 'SHOW_PROJECT_PICKER':
        // Semantic Router returned UNKNOWN — ask the user to pick a project
        showProjectToast(message.captureId, message.projects, message.promptPreview);
        sendResponse({ shown: true });
        break;

      default:
        break;
    }

    // Return true to indicate we'll send a response asynchronously
    // (required by Chrome Extension messaging API)
    return true;
  });

  // Notify that content script is loaded
  console.log('[Project DNA] 🧬 Content script loaded on:', window.location.href);
  console.log('[Project DNA] 🧬 page-script.js injected via manifest world:MAIN — fetch interceptor active.');

  // =========================================================================
  // UI: PROJECT PICKER TOAST
  // =========================================================================

  function showProjectToast(captureId, projects, promptPreview) {
    const existing = document.getElementById('dna-project-picker');
    if (existing) existing.remove();

    const AUTO_DISMISS_MS = 30000;
    const toast = document.createElement('div');
    toast.id = 'dna-project-picker';
    Object.assign(toast.style, {
      position: 'fixed', bottom: '24px', right: '24px', zIndex: '2147483647',
      width: '340px', background: 'rgba(18,18,28,0.93)',
      backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)',
      border: '1px solid rgba(139,92,246,0.35)', borderRadius: '16px',
      boxShadow: '0 8px 40px rgba(0,0,0,0.5)', overflow: 'hidden',
      fontFamily: "-apple-system,BlinkMacSystemFont,'Inter',sans-serif",
      fontSize: '13px', color: '#e2e8f0',
    });

    const previewHTML = promptPreview
      ? `<div style="margin:0 16px 12px;padding:8px 10px;background:rgba(255,255,255,0.05);border-radius:8px;font-size:11px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">“${promptPreview}”</div>`
      : '';

    const btnHTML = (projects || []).map(p =>
      `<button class="dna-pb" data-slug="${p.slug}" style="display:block;width:calc(100% - 32px);margin:0 16px 8px;padding:10px 14px;background:rgba(139,92,246,0.12);border:1px solid rgba(139,92,246,0.25);border-radius:10px;color:#c4b5fd;font-size:13px;font-weight:500;text-align:left;cursor:pointer;">📁 ${p.name || p.slug}</button>`
    ).join('');

    toast.innerHTML = `
      <style>
        @keyframes dna-sin{from{transform:translateY(16px);opacity:0}to{transform:translateY(0);opacity:1}}
        @keyframes dna-cd{from{width:100%}to{width:0%}}
        #dna-project-picker .dna-pb:hover{background:rgba(139,92,246,.28)!important;border-color:rgba(139,92,246,.5)!important;color:#ede9fe!important;}
      </style>
      <div style="padding:14px 16px 10px;display:flex;align-items:center;gap:10px;animation:dna-sin .3s ease;">
        <span style="font-size:20px;">🧬</span>
        <div>
          <div style="font-weight:600;color:#f1f5f9;">Project DNA</div>
          <div style="font-size:11px;color:#94a3b8;">Проект не определён авто-роутером</div>
        </div>
        <button id="dna-tc" style="margin-left:auto;background:none;border:none;color:#64748b;font-size:20px;cursor:pointer;line-height:1;">&times;</button>
      </div>
      ${previewHTML}
      <div style="padding:0 0 6px;font-size:11px;color:#64748b;text-align:center;">Выберите проект для сохранения:</div>
      ${btnHTML}
      <div style="margin:4px 16px 14px;text-align:right;">
        <button id="dna-tq" style="background:none;border:none;color:#64748b;font-size:11px;cursor:pointer;text-decoration:underline;">В очередь</button>
      </div>
      <div style="height:2px;background:linear-gradient(90deg,#8b5cf6,#6366f1);animation:dna-cd ${AUTO_DISMISS_MS}ms linear forwards;"></div>
    `;

    document.body.appendChild(toast);
    const timer = setTimeout(() => toast.remove(), AUTO_DISMISS_MS);
    const dismiss = () => { clearTimeout(timer); toast.remove(); };

    toast.querySelector('#dna-tc').addEventListener('click', dismiss);
    toast.querySelector('#dna-tq').addEventListener('click', () => {
      dismiss();
      console.log('[Project DNA] 📬 Queued pending capture', captureId);
    });

    toast.querySelectorAll('.dna-pb').forEach(btn => {
      btn.addEventListener('click', () => {
        const slug = btn.dataset.slug;
        btn.innerHTML = '✔ ' + btn.innerHTML.replace('📁 ', '');
        btn.style.background = 'rgba(139,92,246,0.45)';
        setTimeout(dismiss, 700);
        chrome.runtime.sendMessage(
          { action: 'PROJECT_SELECTED_FROM_TOAST', data: { captureId, projectSlug: slug } },
          (res) => { if (res && res.success) console.log('[Project DNA] ✅ Saved →', slug); }
        );
      });
    });
  }

})();
