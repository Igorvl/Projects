/**
 * SERVICE-WORKER.JS — Extension Background Service Worker
 * =========================================================
 *
 * The service worker is the "brain" of the extension. It runs in the
 * background (no visible UI) and handles:
 * 1. Receiving captured generation data from content scripts
 * 2. Sending data to Project DNA API (POST /v1/dna/capture)
 * 3. Managing extension state (active project, API URL, capture queue)
 * 4. Updating the extension badge (capture count indicator)
 * 5. Error handling and retry logic
 *
 * SERVICE WORKER vs BACKGROUND PAGE:
 * In Manifest V3, "background pages" were replaced by "service workers".
 * Key difference: service workers are EVENT-DRIVEN and can be terminated
 * by the browser when idle (to save memory). They wake up when events
 * (messages, alarms, etc.) occur. This means:
 * - ❌ No persistent state in variables (worker can restart at any time)
 * - ✅ Use chrome.storage.local for persistent data
 * - ✅ Use chrome.storage.session for session-scoped data
 *
 * DATA FLOW:
 * content-script.js → (chrome.runtime.sendMessage) → THIS FILE
 *   → (fetch) → Project DNA API (POST /v1/dna/capture)
 *   → (chrome.storage) → Persist state
 *   → (chrome.action.setBadgeText) → Update badge
 *
 * @see https://developer.chrome.com/docs/extensions/develop/migrate/to-service-workers
 */

// =========================================================================
// DEFAULT CONFIGURATION
// =========================================================================

/**
 * Default settings for the extension.
 * These are overridden by values in chrome.storage.local.
 *
 * API_URL: The base URL of the Project DNA Router API.
 * Our server runs on a dedicated Xeon E5 machine at this IP.
 * In production, this would be configurable through the popup UI.
 */
const DEFAULTS = {
  API_URL: 'http://172.25.9.33:8000',
  activeProject: null,     // Currently selected project slug
  captureEnabled: true,    // Auto-capture toggle
  totalCaptures: 0,        // Lifetime capture counter
  captureQueue: [],        // Queue of pending captures (for retry)
};

// =========================================================================
// STATE MANAGEMENT (chrome.storage)
// =========================================================================

/**
 * Get a value from chrome.storage.local with a fallback default.
 *
 * chrome.storage.local is the extension's persistent key-value store.
 * Unlike localStorage (which is per-origin), chrome.storage.local
 * is shared across all parts of the extension and survives restarts.
 *
 * @param {string} key - Storage key
 * @returns {Promise<any>} - The stored value or default
 */
async function getConfig(key) {
  const result = await chrome.storage.local.get(key);
  return result[key] !== undefined ? result[key] : DEFAULTS[key];
}

/**
 * Set a value in chrome.storage.local.
 *
 * @param {string} key   - Storage key
 * @param {any}    value - Value to store (must be JSON-serializable)
 * @returns {Promise<void>}
 */
async function setConfig(key, value) {
  return chrome.storage.local.set({ [key]: value });
}

/**
 * Get multiple config values at once (more efficient than multiple calls).
 *
 * @param {string[]} keys - Array of storage keys
 * @returns {Promise<object>} - Object with key-value pairs
 */
async function getConfigs(keys) {
  const result = await chrome.storage.local.get(keys);
  const merged = {};
  for (const key of keys) {
    merged[key] = result[key] !== undefined ? result[key] : DEFAULTS[key];
  }
  return merged;
}

// =========================================================================
// PROJECT DNA API CLIENT
// =========================================================================

/**
 * Send capture via Semantic Auto-Router when no project is manually selected.
 *
 * Calls POST /v1/dna/route — the server determines the project automatically
 * using the Semantic Router (Gemini 2.5 Flash Lite zero-shot classification).
 *
 * WHY THIS APPROACH:
 * The classic problem: "Where does this capture belong?" requires human judgment
 * OR a smart classifier. We use an LLM as a zero-shot classifier:
 *   - Input: raw prompt text
 *   - Output: project slug ("ksar-me") or "UNKNOWN"
 * The server caches classification by MD5 hash of the text (0ms on repeat).
 *
 * DATA FLOW:
 * Extension (no project) → POST /v1/dna/route → semantic_router.py
 *   → Gemini 2.5 Flash Lite classifies → capture_generation() in DB
 *   → Returns { project_slug, seq_num } to extension
 *
 * @param {object} capturedData - Data from interceptor
 * @param {object} config       - { API_URL, activeProject }
 * @returns {Promise<object>}   - { success, seqNum, method }
 */
async function sendViaSemanticRoute(capturedData, config, tabId) {
  const routePayload = {
    prompt_text: capturedData.promptText || '',
    output_text: capturedData.outputText || '',
    model_name: capturedData.model || 'unknown',
    source: 'ai-studio-extension',
    // NOTE: MinIO images not uploaded here (no project slug known yet).
    // result_urls will contain original Google URLs as fallback.
    result_urls: capturedData.resultUrls || [],
    parameters: capturedData.parameters || {},
    page_title: capturedData.pageTitle || '',  // Top-level field for server classification
    metadata: {
      sourceUrl: capturedData.sourceUrl,
      capturedAt: capturedData.timestamp,
      finishReason: capturedData.finishReason,
      pageTitle: capturedData.pageTitle || '',  // aids semantic classification
    },
  };

  try {
    const response = await fetch(`${config.API_URL}/v1/dna/route`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(routePayload),
      signal: AbortSignal.timeout(8000),
    });

    if (!response.ok) {
      throw new Error(`Route API returned ${response.status}`);
    }

    const result = await response.json();

    if (result.project_slug) {
      // ✅ Semantic Router identified the project — capture done server-side
      console.log(`[Project DNA] 🧭 Auto-routed → "${result.project_slug}" (seq #${result.seq_num})`);

      // -----------------------------------------------------------------------
      // Phase 2: Upload images to MinIO now that we know the project slug.
      //
      // WHY HERE: When sendViaSemanticRoute is called, we don't know the project
      // slug yet (that's what the route endpoint determines). Only after the route
      // call do we have a slug to use for MinIO storage path.
      //
      // After uploading, we PATCH the generation record with the MinIO URLs.
      // The PATCH endpoint (PATCH /v1/dna/generations/{id}) updates result_urls.
      // -----------------------------------------------------------------------
      const base64Images = capturedData.resultBase64Images || [];
      const sourceUrls   = capturedData.resultUrls || [];
      // DEBUG: log what we have to work with
      console.log(`[Project DNA] 🔍 Phase2: base64=${base64Images.length}, urls=${sourceUrls.length}`);

      const hasImages = (base64Images.length > 0 || sourceUrls.length > 0) && result.generation_id;

      if (hasImages) {
        const minioUrls = [];
        const uploadUrl = `${config.API_URL}/v1/dna/upload/${result.project_slug}`;

        if (base64Images.length > 0) {
          // ✅ Fast path: page-script pre-fetched images as base64 data URLs
          console.log(`[Project DNA] 🖼️ Phase2 fast path: uploading ${base64Images.length} base64 image(s) → ${result.project_slug}`);
          for (let i = 0; i < base64Images.length; i++) {
            try {
              const dataRes = await fetch(base64Images[i]);
              const blob = await dataRes.blob();
              const isJpeg = base64Images[i].startsWith('data:image/jpeg');
              const ext = isJpeg ? 'jpg' : 'png';
              const formData = new FormData();
              formData.append('file', blob, `gemini_image_${Date.now()}_${i}.${ext}`);
              const uploadRes = await fetch(uploadUrl, { method: 'POST', body: formData });
              if (uploadRes.ok) {
                const ud = await uploadRes.json();
                if (ud && ud.url) {
                  const apiHost = new URL(config.API_URL).hostname;
                  minioUrls.push(ud.url.split('?')[0].replace('ai-minio:9000', `${apiHost}:9000`));
                  console.log(`[Project DNA] ✅ Phase2 base64 image ${i + 1} uploaded`);
                }
              } else {
                console.warn(`[Project DNA] ⚠️ Phase2 base64 image ${i + 1} upload failed: ${uploadRes.status}`);
              }
            } catch (e) {
              console.error(`[Project DNA] ❌ Phase2 base64 image ${i + 1} error:`, e.message);
            }
          }

        } else if (sourceUrls.length > 0) {
          // ⚠️ Fallback: download from Google CDN URL and re-upload to MinIO.
          // Mirrors the same logic as sendToProjectDNA (lines ~321-378).
          // Works for signed Gemini CDN URLs that don't require cookie auth.
          console.log(`[Project DNA] 🖼️ Phase2 URL fallback: fetching ${sourceUrls.length} image(s) from source → ${result.project_slug}`);
          for (let i = 0; i < sourceUrls.length; i++) {
            const sourceUrl = sourceUrls[i];
            try {
              let imgRes;
              if (sourceUrl.startsWith('data:image/')) {
                imgRes = await fetch(sourceUrl);
              } else {
                // Try with size param first, then with credentials
                let directUrl = sourceUrl.includes('=')
                  ? sourceUrl.replace(/=[a-zA-Z0-9\-]+/, '=w2048-h2048') : sourceUrl;
                try {
                  imgRes = await fetch(directUrl);
                  if (!imgRes.ok) throw new Error(`${imgRes.status}`);
                } catch {
                  imgRes = await fetch(sourceUrl, { credentials: 'include', redirect: 'follow' });
                }
              }
              if (!imgRes || !imgRes.ok) throw new Error(`Fetch failed: ${imgRes?.status}`);

              const arrayBuffer = await imgRes.arrayBuffer();
              const blob = new Blob([arrayBuffer], { type: 'image/png' });
              const formData = new FormData();
              formData.append('file', blob, `gemini_image_${Date.now()}_${i}.png`);
              const uploadRes = await fetch(uploadUrl, { method: 'POST', body: formData });
              if (uploadRes.ok) {
                const ud = await uploadRes.json();
                if (ud && ud.url) {
                  const apiHost = new URL(config.API_URL).hostname;
                  minioUrls.push(ud.url.split('?')[0].replace('ai-minio:9000', `${apiHost}:9000`));
                  console.log(`[Project DNA] ✅ Phase2 URL image ${i + 1} uploaded`);
                }
              } else {
                console.warn(`[Project DNA] ⚠️ Phase2 URL image ${i + 1} upload failed: ${uploadRes.status}`);
              }
            } catch (e) {
              console.error(`[Project DNA] ❌ Phase2 URL image ${i + 1} error (${sourceUrl.substring(0, 50)}):`, e.message);
            }
          }
        }

        // PATCH generation record with MinIO URLs
        if (minioUrls.length > 0) {
          try {
            const patchRes = await fetch(`${config.API_URL}/v1/dna/generations/${result.generation_id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ result_urls: minioUrls }),
            });
            if (patchRes.ok) {
              console.log(`[Project DNA] ✅ Generation ${result.generation_id} patched with ${minioUrls.length} MinIO URL(s)`);
            } else {
              const errText = await patchRes.text().catch(() => '');
              console.error(`[Project DNA] ❌ PATCH failed ${patchRes.status}: ${errText.substring(0, 100)}`);
            }
          } catch (e) {
            console.error('[Project DNA] ❌ PATCH generation URLs failed:', e.message);
          }
        }
      }

      const totalCaptures = await getConfig('totalCaptures');
      await setConfig('totalCaptures', totalCaptures + 1);
      await updateBadge(totalCaptures + 1);

      // Show in popup with 🧭 marker so user knows it was auto-routed
      await addToRecentCaptures({
        model: capturedData.model,
        promptPreview: (capturedData.promptText || '').substring(0, 100),
        project: `${result.project_slug} 🧭`,
        timestamp: capturedData.timestamp,
        seqNum: result.seq_num,
      });

      return { success: true, seqNum: result.seq_num, method: 'semantic' };
    } else {
      // UNKNOWN — offer project picker in the Gemini tab (with tabId), or queue as fallback
      console.warn('[Project DNA] 🧭 Semantic router: UNKNOWN. Showing project picker or queuing...');
      if (tabId) {
        await showProjectPicker(capturedData, tabId);
      } else {
        await queueCapture(capturedData);
      }
      return { success: false, error: 'Semantic router: UNKNOWN project' };
    }
  } catch (err) {
    console.error('[Project DNA] ❌ Route endpoint failed:', err.message);
    // Fallback: queue the capture, don't lose data
    await queueCapture(capturedData);
    return { success: false, error: err.message };
  }
}

/**
 * Send captured generation data to the Project DNA API.
 *
 * ROUTING LOGIC:
 * 1. If user manually selected a project in popup → POST /v1/dna/capture
 * 2. If no project selected → sendViaSemanticRoute() → POST /v1/dna/route
 *    The Semantic Router (Gemini 2.5 Flash Lite) classifies the capture
 *    and assigns it to the right project automatically.
 *
 * @param {object} capturedData - Data from page-script.js interceptor
 * @returns {Promise<object>}   - API response or error object
 */
async function sendToProjectDNA(capturedData, tabId) {
  const config = await getConfigs(['API_URL', 'activeProject']);

  // No manual project selection → try Semantic Auto-Router
  if (!config.activeProject) {
    console.log('[Project DNA] 🧭 No active project — trying Semantic Auto-Router...');
    return await sendViaSemanticRoute(capturedData, config, tabId);
  }

  // -----------------------------------------------------------------------
  // Upload images to MinIO
  // Priority: resultBase64Images (pre-fetched in page context with Google auth)
  //           → fallback to resultUrls (may fail if expired or no auth)
  // -----------------------------------------------------------------------
  let finalResultUrls = [];

  const base64Images = capturedData.resultBase64Images || [];
  const sourceUrls   = capturedData.resultUrls || [];

  if (base64Images.length > 0) {
    // ✅ Fast path: page-script already downloaded the images as base64
    console.log(`[Project DNA] 🖼️ Uploading ${base64Images.length} pre-fetched image(s) to MinIO...`);

    for (let i = 0; i < base64Images.length; i++) {
      try {
        // Fetch the data: URL to get a Blob — supported in service workers
        const dataRes = await fetch(base64Images[i]);
        const blob    = await dataRes.blob();

        const formData = new FormData();
        formData.append('file', blob, `gemini_image_${Date.now()}_${i}.png`);

        const uploadRes = await fetch(`${config.API_URL}/v1/dna/upload/${config.activeProject}`, {
          method: 'POST',
          body: formData,
        });

        if (uploadRes.ok) {
          const uploadData = await uploadRes.json();
          if (uploadData && uploadData.url) {
            const apiHost = new URL(config.API_URL).hostname;
            // Strip signatures and map to external API host
            const finalUrl = uploadData.url.split('?')[0].replace('ai-minio:9000', `${apiHost}:9000`);
            finalResultUrls.push(finalUrl);
            console.log(`[Project DNA] ✅ Clean MinIO URL: ${finalUrl}`);
          }
        } else {
          const errText = await uploadRes.text().catch(() => '');
          console.warn(`[Project DNA] ⚠️ MinIO upload failed (${uploadRes.status}): ${errText.substring(0, 60)}`);
          // Keep the original Google URL as a fallback reference
          if (sourceUrls[i]) finalResultUrls.push(sourceUrls[i] + `#ERROR=MinIO_${uploadRes.status}`);
        }
      } catch (e) {
        console.error(`[Project DNA] ❌ Image ${i + 1} upload error:`, e.message);
        if (sourceUrls[i]) finalResultUrls.push(sourceUrls[i] + `#ERROR_UPLOAD=${e.message}`);
      }
    }

  } else if (sourceUrls.length > 0) {
    // ⚠️ Fallback path: try to download from Google URL directly
    // This often fails (400/403) because service worker has no Google auth cookies.
    // Only works for public or non-auth-required URLs.
    console.log(`[Project DNA] ⚠️ No pre-fetched images — attempting URL download (may fail for Google auth URLs)...`);

    for (let i = 0; i < sourceUrls.length; i++) {
        const sourceUrl = sourceUrls[i];
        try {
            let imgRes;
            if (sourceUrl.startsWith('data:image/')) {
                imgRes = await fetch(sourceUrl);
                if (!imgRes.ok) throw new Error(`HTTP Base64 ${imgRes.status}`);
            } else {
                let directUrl = sourceUrl;
                if (directUrl.includes('=')) {
                    directUrl = directUrl.replace(/=[a-zA-Z0-9\-]+/, '=w2048-h2048');
                }
                try {
                    imgRes = await fetch(directUrl);
                    if (!imgRes.ok) throw new Error(`Fetch failed: ${imgRes.status}`);
                } catch(e1) {
                    imgRes = await fetch(sourceUrl, { credentials: 'include', redirect: 'follow' });
                }
                if (!imgRes || !imgRes.ok) throw new Error(`HTTP/fetch failed: ${imgRes?.status}`);
            }

            const arrayBuffer = await imgRes.arrayBuffer();
            const blob = new Blob([arrayBuffer], { type: 'image/png' });
            const formData = new FormData();
            formData.append('file', blob, `gemini_image_${Date.now()}_${i}.png`);

            const uploadRes = await fetch(`${config.API_URL}/v1/dna/upload/${config.activeProject}`, {
                method: 'POST',
                body: formData
            });

            if (uploadRes.ok) {
                const uploadData = await uploadRes.json();
                if (uploadData && uploadData.url) {
                    const apiHost = new URL(config.API_URL).hostname;
                    // Strip signatures and map
                    const finalUrl = uploadData.url.split('?')[0].replace('ai-minio:9000', `${apiHost}:9000`);
                    finalResultUrls.push(finalUrl);
                    console.log(`[Project DNA] ✅ Clean MinIO URL: ${finalUrl}`);
                } else {
                    finalResultUrls.push(sourceUrl + '#ERROR=No_URL_in_UploadRes');
                }
            } else {
                const errText = await uploadRes.text().catch(()=>'');
                finalResultUrls.push(sourceUrl + `#ERROR=Upload_${uploadRes.status}_${errText.substring(0,20)}`);
            }
        } catch (e) {
            console.error(`[Project DNA] ❌ Failed to process image URL: ${sourceUrl.substring(0,60)}`, e.message);
            finalResultUrls.push(sourceUrl + `#ERROR_FETCH=${e.message}`);
        }
    }
  }

  // Transform intercepted data to our API format
  const apiPayload = {
    project_slug: config.activeProject,
    prompt: capturedData.promptText || '',
    prompt_text: capturedData.promptText || '',
    model_name: capturedData.model || 'unknown',
    parameters: capturedData.parameters || {},
    output: capturedData.outputText || '',
    output_text: capturedData.outputText || '',
    response_text: capturedData.outputText || '',
    system_instruction: capturedData.systemInstruction || '',
    result_urls: finalResultUrls,
    source: 'ai-studio-extension',
    metadata: {
      captureIndex: capturedData.captureIndex,
      sourceUrl: capturedData.sourceUrl,
      apiUrl: capturedData.apiUrl,
      finishReason: capturedData.finishReason,
      safetySettings: capturedData.safetySettings,
      capturedAt: capturedData.timestamp,
    },
  };

  try {
    const response = await fetch(`${config.API_URL}/v1/dna/capture`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(apiPayload),
      signal: AbortSignal.timeout(10000),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API returned ${response.status}: ${errorText}`);
    }

    const result = await response.json();

    // Update capture counter
    const totalCaptures = await getConfig('totalCaptures');
    await setConfig('totalCaptures', totalCaptures + 1);

    // Update badge to show capture count
    await updateBadge(totalCaptures + 1);

    // Store in recent captures list
    await addToRecentCaptures({
      model: capturedData.model,
      promptPreview: (capturedData.promptText || '').substring(0, 100),
      project: config.activeProject,
      timestamp: capturedData.timestamp,
      seqNum: result.seq_num,
    });

    console.log(
      `[Project DNA] ✅ Capture sent successfully! seq_num: ${result.seq_num}`
    );

    return { success: true, seqNum: result.seq_num };

  } catch (err) {
    console.error('[Project DNA] ❌ Failed to send capture:', err.message);

    // Queue failed captures for retry
    await queueCapture(capturedData);

    return { success: false, error: err.message };
  }
}

/**
 * Fetch the list of projects from Project DNA API.
 *
 * Used by the popup to display available projects for selection.
 * Calls GET /v1/dna/projects on the AI Router.
 *
 * @returns {Promise<object[]>} - Array of project objects
 */
async function fetchProjects() {
  const apiUrl = await getConfig('API_URL');

  try {
    const response = await fetch(`${apiUrl}/v1/dna/projects`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });

    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }

    const data = await response.json();
    // Handle both formats: {projects: [...]} and [...]
    return data.projects || data || [];

  } catch (err) {
    console.error('[Project DNA] Failed to fetch projects:', err.message);
    return [];
  }
}

/**
 * Check API health status.
 *
 * Calls GET /v1/dna/health to verify the Project DNA API is online.
 * Used by the popup to show connection status indicator.
 *
 * @returns {Promise<object>} - { online: boolean, latency: number }
 */
async function checkAPIHealth() {
  const apiUrl = await getConfig('API_URL');
  const startTime = Date.now();

  try {
    const response = await fetch(`${apiUrl}/v1/dna/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000), // 5-second timeout
    });

    const latency = Date.now() - startTime;
    return {
      online: response.ok,
      latency: latency,
      status: response.status,
    };

  } catch (err) {
    return {
      online: false,
      latency: Date.now() - startTime,
      error: err.message,
    };
  }
}

// =========================================================================
// CAPTURE QUEUE (Retry Logic)
// =========================================================================

/**
 * Add a failed capture to the retry queue.
 *
 * When the API is unreachable (server down, network issues, etc.),
 * we don't lose the captured data. Instead, we queue it in
 * chrome.storage.local and retry later.
 *
 * This is a simple implementation of the "outbox pattern" — a common
 * resilience pattern in distributed systems where you persist messages
 * locally before sending them to a remote service.
 *
 * @param {object} capturedData - The captured generation data
 */
async function queueCapture(capturedData) {
  const queue = await getConfig('captureQueue');
  queue.push({
    data: capturedData,
    queuedAt: new Date().toISOString(),
    retryCount: 0,
  });

  // Keep queue bounded (max 100 items) to prevent storage bloat
  if (queue.length > 100) {
    queue.shift(); // Remove oldest item (FIFO)
  }

  await setConfig('captureQueue', queue);
  console.log(`[Project DNA] 📋 Capture queued. Queue size: ${queue.length}`);
}

/**
 * Process the capture queue: retry sending failed captures.
 *
 * Called periodically or when the API becomes available.
 * Attempts to send each queued capture to the API.
 * Successfully sent captures are removed from the queue.
 */
async function processQueue() {
  const queue = await getConfig('captureQueue');
  if (queue.length === 0) return;

  console.log(`[Project DNA] 🔄 Processing capture queue (${queue.length} items)...`);

  const remaining = [];

  for (const item of queue) {
    const result = await sendToProjectDNA(item.data);
    if (!result.success) {
      item.retryCount++;
      // Keep items for up to 60 retries (approx 2 hours if retried every 2 minutes)
      if (item.retryCount < 60) {
        remaining.push(item);
      } else {
        console.warn(
          '[Project DNA] Dropping capture after 60 retries:',
          item.data.captureIndex
        );
      }
    }
  }

  await setConfig('captureQueue', remaining);
}

// =========================================================================
// PROJECT PICKER (UNKNOWN fallback — toast in Gemini tab)
// =========================================================================

/**
 * When Semantic Router returns UNKNOWN, show a project-selection toast
 * in the Gemini browser tab via a message to the content script.
 *
 * The pending capture is persisted in chrome.storage.local under a UUID key
 * so it survives service-worker sleep/wake cycles.
 *
 * @param {object} capturedData - Full capture payload
 * @param {number} tabId        - Chrome tab ID to send the picker to
 */
async function showProjectPicker(capturedData, tabId) {
  try {
    const projects = await fetchProjects();
    if (!projects || projects.length === 0) {
      console.warn('[Project DNA] ⚠️ No projects to pick from — queuing.');
      await queueCapture(capturedData);
      return;
    }

    // Store the pending capture with a unique ID
    const captureId = `pending_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const pendingResult = await chrome.storage.local.get('pendingCaptures');
    const pending = pendingResult.pendingCaptures || {};
    pending[captureId] = capturedData;
    // Prune old pending captures older than 5 minutes
    const now = Date.now();
    for (const [key, val] of Object.entries(pending)) {
      if (now - parseInt(key.split('_')[1] || '0') > 300000) delete pending[key];
    }
    await chrome.storage.local.set({ pendingCaptures: pending });

    // Send picker message to the Gemini content script
    chrome.tabs.sendMessage(tabId, {
      action: 'SHOW_PROJECT_PICKER',
      captureId,
      promptPreview: (capturedData.promptText || '').substring(0, 120),
      projects: projects.map(p => ({ slug: p.slug, name: p.name || p.slug })),
    }, (response) => {
      if (chrome.runtime.lastError) {
        // Content script not reachable (tab navigated away) — fall back to queue
        console.warn('[Project DNA] ⚠️ Could not reach content script for picker — queuing.');
        queueCapture(capturedData);
      } else {
        console.log('[Project DNA] 🧭 Project picker shown in tab', tabId);
      }
    });
  } catch (err) {
    console.error('[Project DNA] ❌ showProjectPicker error:', err.message);
    await queueCapture(capturedData);
  }
}

/**
 * Handle user's project selection from the Gemini page toast.
 * Saves the chosen project as activeProject and sends the pending capture.
 */
async function handleProjectSelectedFromToast(data, sendResponse) {
  const { captureId, projectSlug } = data;

  const pendingResult = await chrome.storage.local.get('pendingCaptures');
  const pending = pendingResult.pendingCaptures || {};
  const capturedData = pending[captureId];

  if (!capturedData) {
    console.warn('[Project DNA] ⚠️ Pending capture not found:', captureId);
    sendResponse({ success: false, error: 'Capture not found — may have expired' });
    return;
  }

  // Remove from pending
  delete pending[captureId];
  await chrome.storage.local.set({ pendingCaptures: pending });

  // Persist the chosen project as activeProject
  await setConfig('activeProject', projectSlug);
  console.log(`[Project DNA] 🧭 User selected project: ${projectSlug}`);

  // Now send the capture with the known project
  const result = await sendToProjectDNA(capturedData);
  sendResponse(result);
}


/**
 * Listen for the auto-retry alarm.
 * This ensures the Outbox is processed automatically even if the user
 * doesn't restart the browser or open the popup.
 */
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'retryCaptureQueue') {
    const queue = await getConfig('captureQueue');
    if (queue && queue.length > 0) {
      console.log(`[Project DNA] ⏰ Auto-retry alarm triggered: processing ${queue.length} queued items`);
      await processQueue();
    }
  }
});

// =========================================================================
// RECENT CAPTURES (for popup display)
// =========================================================================

/**
 * Add a capture to the "recent captures" list (displayed in popup).
 * Keeps only the last 20 captures.
 *
 * @param {object} captureInfo - Summary of the capture
 */
async function addToRecentCaptures(captureInfo) {
  const result = await chrome.storage.local.get('recentCaptures');
  const recent = result.recentCaptures || [];

  recent.unshift(captureInfo); // Add to beginning (newest first)

  // Keep only last 20
  if (recent.length > 20) {
    recent.pop();
  }

  await chrome.storage.local.set({ recentCaptures: recent });
}

// =========================================================================
// BADGE MANAGEMENT
// =========================================================================

/**
 * Update the extension icon badge with capture count.
 *
 * The badge is a small text overlay on the extension icon, commonly
 * used to show notification counts (like email count in Gmail extension).
 *
 * We use it to show how many generations have been captured in this session.
 *
 * @param {number} count - Number to display on badge
 */
async function updateBadge(count) {
  const text = count > 0 ? String(count) : '';
  await chrome.action.setBadgeText({ text });
  await chrome.action.setBadgeBackgroundColor({
    color: count > 0 ? '#00d4ff' : '#666666',
  });
}

// =========================================================================
// MESSAGE HANDLERS
// =========================================================================

/**
 * Main message router for the service worker.
 *
 * All messages from content scripts and popup are handled here.
 * This is the central nervous system of the extension.
 *
 * @param {object}  message    - The message payload
 * @param {object}  sender     - Info about the sender (tab, extension, etc.)
 * @param {Function} sendResponse - Callback to send a response back
 * @returns {boolean} - true to indicate async response
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Route messages based on action type
  switch (message.action) {

    // ----- Content Script: New generation captured -----
    case 'CAPTURE_GENERATION':
      handleCapture(message.data, sendResponse, sender.tab?.id);
      return true; // async response

    // ----- Content Script: Interceptor status update -----
    case 'INTERCEPTOR_STATUS':
      console.log('[Project DNA] Interceptor status:', message.data.status);
      sendResponse({ received: true });
      return false;

    // ----- Popup: Get extension state -----
    case 'GET_STATE':
      handleGetState(sendResponse);
      return true; // async response

    // ----- Popup: Set active project -----
    case 'SET_PROJECT':
      handleSetProject(message.data, sendResponse);
      return true; // async response

    // ----- Popup: Set API URL -----
    case 'SET_API_URL':
      handleSetApiUrl(message.data, sendResponse);
      return true; // async response

    // ----- Popup: Toggle capture on/off -----
    case 'TOGGLE_CAPTURE':
      handleToggleCapture(sendResponse);
      return true; // async response

    // ----- Popup: Check API health -----
    case 'CHECK_HEALTH':
      checkAPIHealth().then(sendResponse);
      return true; // async response

    // ----- Popup: Get projects list -----
    case 'GET_PROJECTS':
      fetchProjects().then(sendResponse);
      return true; // async response

    // ----- Popup: Retry queue -----
    case 'RETRY_QUEUE':
      processQueue().then(() => sendResponse({ done: true }));
      return true; // async response

    // ----- Content Script: Project selected from Gemini page picker -----
    case 'PROJECT_SELECTED_FROM_TOAST':
      handleProjectSelectedFromToast(message.data, sendResponse);
      return true; // async response

    default:
      console.warn('[Project DNA] Unknown message action:', message.action);
      return false;
  }
});

/**
 * Handle a captured generation from content script.
 */
async function handleCapture(capturedData, sendResponse, tabId) {
  const captureEnabled = await getConfig('captureEnabled');

  if (!captureEnabled) {
    console.log('[Project DNA] Capture disabled. Ignoring generation.');
    sendResponse({ success: false, reason: 'capture_disabled' });
    return;
  }

  const result = await sendToProjectDNA(capturedData, tabId);
  sendResponse(result);
}

/**
 * Handle GET_STATE request from popup — return all extension state.
 */
async function handleGetState(sendResponse) {
  const config = await getConfigs([
    'API_URL', 'activeProject', 'captureEnabled', 'totalCaptures',
  ]);
  const result = await chrome.storage.local.get(['recentCaptures', 'captureQueue']);

  sendResponse({
    ...config,
    recentCaptures: result.recentCaptures || [],
    queueSize: (result.captureQueue || []).length,
  });
}

/**
 * Handle SET_PROJECT request from popup.
 */
async function handleSetProject(data, sendResponse) {
  await setConfig('activeProject', data.slug);
  console.log(`[Project DNA] Active project set to: ${data.slug}`);
  sendResponse({ success: true, activeProject: data.slug });
}

/**
 * Handle SET_API_URL request from popup.
 */
async function handleSetApiUrl(data, sendResponse) {
  // Remove trailing slash
  const url = data.url.replace(/\/+$/, '');
  await setConfig('API_URL', url);
  console.log(`[Project DNA] API URL set to: ${url}`);
  sendResponse({ success: true, apiUrl: url });
}

/**
 * Handle TOGGLE_CAPTURE request from popup.
 */
async function handleToggleCapture(sendResponse) {
  const current = await getConfig('captureEnabled');
  const newValue = !current;
  await setConfig('captureEnabled', newValue);

  // Update badge to reflect state
  if (!newValue) {
    await chrome.action.setBadgeText({ text: 'OFF' });
    await chrome.action.setBadgeBackgroundColor({ color: '#ff4444' });
  } else {
    const total = await getConfig('totalCaptures');
    await updateBadge(total);
  }

  console.log(`[Project DNA] Capture ${newValue ? 'ENABLED' : 'DISABLED'}`);
  sendResponse({ success: true, captureEnabled: newValue });
}

// =========================================================================
// EXTENSION LIFECYCLE EVENTS
// =========================================================================

/**
 * Setup background alarms for periodic tasks (like queue retry).
 */
function setupAlarms() {
  chrome.alarms.create('retryCaptureQueue', { periodInMinutes: 2 });
  console.log('[Project DNA] ⏰ Auto-retry alarm configured (2m interval)');
}

/**
 * Extension installed or updated.
 * Initialize default settings if this is a fresh install.
 */
chrome.runtime.onInstalled.addListener(async (details) => {
  setupAlarms();

  if (details.reason === 'install') {
    console.log('[Project DNA] 🧬 Extension installed! Setting defaults...');
    await chrome.storage.local.set({
      API_URL: DEFAULTS.API_URL,
      activeProject: DEFAULTS.activeProject,
      captureEnabled: DEFAULTS.captureEnabled,
      totalCaptures: 0,
      recentCaptures: [],
      captureQueue: [],
    });

    // Set initial badge
    await chrome.action.setBadgeText({ text: '' });
    await chrome.action.setBadgeBackgroundColor({ color: '#00d4ff' });
  }

  if (details.reason === 'update') {
    console.log(`[Project DNA] Extension updated to v${chrome.runtime.getManifest().version}`);
  }
});

/**
 * Extension startup (browser launched or extension re-enabled).
 * Restore badge state from storage.
 */
chrome.runtime.onStartup.addListener(async () => {
  setupAlarms();

  const config = await getConfigs(['captureEnabled', 'totalCaptures']);

  if (!config.captureEnabled) {
    await chrome.action.setBadgeText({ text: 'OFF' });
    await chrome.action.setBadgeBackgroundColor({ color: '#ff4444' });
  } else {
    await updateBadge(config.totalCaptures);
  }

  // Try to process any queued captures
  await processQueue();
});

console.log('[Project DNA] 🧬 Service worker initialized');
