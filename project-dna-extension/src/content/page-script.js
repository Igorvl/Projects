/**
 * PAGE-SCRIPT.JS — Fetch Interceptor (injected into page context)
 * ================================================================
 *
 * THIS FILE RUNS IN THE PAGE'S OWN JAVASCRIPT CONTEXT.
 * It is NOT a content script — it has access to the page's `window.fetch`,
 * `XMLHttpRequest`, and all other page-level APIs.
 *
 * PURPOSE:
 * Google AI Studio uses `fetch()` to send prompts to the Gemini API.
 * We monkey-patch `window.fetch` to intercept these API calls,
 * extract prompt text, model parameters, and generated output,
 * then relay this data back to our content script via `window.postMessage`.
 *
 * DATA FLOW:
 * ┌──────────────────────────────────────────────────┐
 * │  AI Studio Page                                   │
 * │  └── fetch("generativelanguage.googleapis.com")   │
 * │        ↓ (intercepted by our patched fetch)       │
 * │  ┌─────────────────────────────────────────────┐  │
 * │  │  page-script.js (THIS FILE)                 │  │
 * │  │  - Clones request body (prompt, params)     │  │
 * │  │  - Waits for response (generated text)      │  │
 * │  │  - Posts data via window.postMessage        │  │
 * │  └─────────────────────────────────────────────┘  │
 * │        ↓ (window.postMessage)                     │
 * │  ┌─────────────────────────────────────────────┐  │
 * │  │  content-script.js (extension context)      │  │
 * │  │  - Receives message from page               │  │
 * │  │  - Forwards to service worker               │  │
 * │  └─────────────────────────────────────────────┘  │
 * └──────────────────────────────────────────────────┘
 *
 * SECURITY NOTE:
 * We use a unique message type identifier ("PROJECT_DNA_CAPTURE")
 * to distinguish our messages from any other postMessage traffic.
 *
 * WHY MONKEY-PATCHING?
 * Content scripts run in an "isolated world" — they share the DOM
 * with the page but NOT the JavaScript context. So a content script
 * cannot access `window.fetch` as used by AI Studio. The only way
 * to intercept the page's own network calls is to inject a script
 * that runs in the page's world and overrides `fetch`.
 *
 * @see https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts#isolated_world
 */

(function () {
  'use strict';

  // =========================================================================
  // CONFIGURATION
  // =========================================================================

  /**
   * Message type used for window.postMessage communication.
   * Must match the listener in content-script.js.
   */
  const MESSAGE_TYPE = 'PROJECT_DNA_CAPTURE';

  /**
   * Message type for status/heartbeat messages.
   */
  const STATUS_TYPE = 'PROJECT_DNA_STATUS';

  /**
   * Known rpcids used by Gemini's batchexecute endpoint for actual AI generation.
   * Every other rpcid is telemetry / drafts / UI metadata — we must ignore those.
   *
   * HOW TO FIND NEW IDs:
   *   DevTools → Network → filter "batchexecute" → look at the URL query param
   *   "rpcids=" right after sending a prompt. Update this list if Google rotates them.
   *
   * Currently confirmed generation rpcids for gemini.google.com:
   *   ESY5D  — standard text generation
   *   MBAWBf — image generation (Imagen 3 / image-3)
   *   dpMR6b — continuation / multi-turn
   *   CZS3Bc — image+text multi-modal generation
   */
  const GEMINI_GENERATION_RPCIDS = new Set([
    'ESY5D',   // text generation
    'MBAWBf',  // image generation (Imagen 3)
    'dpMR6b',  // continuation / multi-turn
    'CZS3Bc',  // image+text generation
    'BiSymb',  // alt text generation rpcid (observed in some regions)
    'GNzX8b',  // streaming text alt
  ]);

  // =========================================================================
  // FETCH INTERCEPTOR (Monkey-Patching)
  // =========================================================================

  /**
   * Store the original, unmodified fetch function.
   * We'll call this for the actual network request — our job is only to
   * OBSERVE, not to MODIFY the requests.
   *
   * Think of it as a security camera on a highway: cars (requests) pass
   * through normally, but we record their license plates (data).
   */
  const originalFetch = window.fetch;

  /**
   * Counter for captured generations (resets on page reload).
   * Used for sequential numbering in the popup UI.
   */
  let captureCount = 0;

  const recentCaptures = new Map();
  const DEDUP_WINDOW_MS = 6000;

  /**
   * Overridden fetch function.
   *
   * This replaces the native `window.fetch` with our version that:
   * 1. Checks if the request URL matches an AI Studio API pattern
   * 2. If YES — intercepts, clones, extracts data, then lets it through
   * 3. If NO  — passes through to original fetch immediately (zero overhead)
   *
   * @param {string|Request} resource - The URL or Request object
   * @param {object} [init]           - Optional fetch init options (method, body, headers)
   * @returns {Promise<Response>}     - The original fetch response (unmodified)
   */
  window.fetch = async function () {
    const resource = arguments[0];
    const init = arguments[1];
    const url = typeof resource === 'string' ? resource : (resource ? resource.url : '');

    // -----------------------------------------------------------------------
    // Fast path: if URL doesn't match our patterns, skip interception entirely.
    // This ensures ZERO performance impact on all other page requests
    // (stylesheets, images, tracking, etc.)
    // -----------------------------------------------------------------------
    const isGoogleAPI = url.includes('generativelanguage') || url.includes('alkali') || url.includes('makersuite') || url.includes('BardChatUi') || url.includes('BardFrontendService');

    // For batchexecute (Gemini web consumer) we ONLY intercept if the URL
    // contains a known generation rpcid. This prevents capturing the dozens
    // of telemetry/draft/UI-metadata requests that also hit batchexecute.
    let isGeneration = url.includes('GenerateContent') || url.includes('StreamGenerate');
    if (!isGeneration && url.includes('batchexecute')) {
      // Extract rpcids param from URL: ...&rpcids=ESY5D,other,...
      try {
        const rpcidsMatch = url.match(/[?&]rpcids=([^&]+)/);
        if (rpcidsMatch) {
          const rpcids = rpcidsMatch[1].split(',');
          isGeneration = rpcids.some(id => GEMINI_GENERATION_RPCIDS.has(id));
        }
      } catch (e) { /* ignore */ }
    }

    const isTargetAPI = isGoogleAPI && isGeneration;

    if (!isTargetAPI) {
      return originalFetch.apply(this, arguments);
    }

    // -----------------------------------------------------------------------
    // Slow path: this IS an AI Studio generation request. Intercept it!
    // -----------------------------------------------------------------------
    console.log('[Project DNA] 🧬 Intercepted AI Studio API call:', url);

    // Clone the request body BEFORE fetch consumes it.
    // fetch() body is a ReadableStream — once read, it's gone forever.
    // We must clone it now or lose the data.
    let requestBody = null;
    try {
      if (init && init.body) {
        // init.body can be a string, Blob, FormData, etc.
        // For AI Studio, it's typically a JSON string
        requestBody = typeof init.body === 'string'
          ? JSON.parse(init.body)
          : init.body;
      } else if (resource instanceof Request) {
        // If fetch was called with a Request object, clone and read its body
        const clonedRequest = resource.clone();
        const bodyText = await clonedRequest.text();
        requestBody = JSON.parse(bodyText);
      }
    } catch (err) {
      console.warn('[Project DNA] Could not parse request body:', err.message);
    }

    // -----------------------------------------------------------------------
    // Execute the ORIGINAL fetch (don't break AI Studio!)
    // We are just observers — the actual request must go through unchanged.
    // -----------------------------------------------------------------------
    let response;
    try {
      response = await originalFetch.apply(this, arguments);
    } catch (fetchError) {
      // If the original fetch fails, we don't interfere — just re-throw
      console.warn('[Project DNA] Original fetch failed:', fetchError.message);
      throw fetchError;
    }

    // -----------------------------------------------------------------------
    // Clone the response to read its body without consuming the original.
    // The page code will read the original response; we read the clone.
    // -----------------------------------------------------------------------
    try {
      const clonedResponse = response.clone();

      // Process response asynchronously (don't block the page!)
      processInterceptedCall(url, requestBody, clonedResponse);
    } catch (cloneError) {
      console.warn('[Project DNA] Could not clone response:', cloneError.message);
    }

    // Return the ORIGINAL response to AI Studio — completely unmodified
    return response;
  };

  // =========================================================================
  // XHR INTERCEPTOR (Monkey-Patching)
  // =========================================================================
  
  const originalXhrOpen = XMLHttpRequest.prototype.open;
  const originalXhrSend = XMLHttpRequest.prototype.send;

  // Use WeakMap to store state completely invisibly from the XHR object itself
  // This prevents ANY interference with Google's framework and prevents 403 errors
  const xhrStateMap = new WeakMap();

  XMLHttpRequest.prototype.open = function() {
    xhrStateMap.set(this, { 
      url: arguments[1] ? arguments[1].toString() : '',
      text: '',
      captured: false
    });
    return originalXhrOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function() {
    const defaultState = { url: '' };
    const state = xhrStateMap.get(this) || defaultState;
    const url = state.url || '';
    const bodyArgs = arguments[0];
    
    // Check if it's a target internal API (same rpcids whitelist as fetch interceptor)
    const isGoogleAPI = url.includes('generativelanguage') || url.includes('alkali') || url.includes('makersuite') || url.includes('BardChatUi') || url.includes('BardFrontendService');
    let isGeneration = url.includes('GenerateContent') || url.includes('StreamGenerate');
    if (!isGeneration && url.includes('batchexecute')) {
      try {
        const rpcidsMatch = url.match(/[?&]rpcids=([^&]+)/);
        if (rpcidsMatch) {
          const rpcids = rpcidsMatch[1].split(',');
          isGeneration = rpcids.some(id => GEMINI_GENERATION_RPCIDS.has(id));
        }
      } catch (e) { /* ignore */ }
    }

    if (isGoogleAPI && isGeneration) {
      console.log('[Project DNA] 🧬 Intercepted AI Studio / Gemini XHR call:', url);
      
      let requestBody = null;
      try {
        if (typeof bodyArgs === 'string') {
          try { requestBody = JSON.parse(bodyArgs); } catch(e) { requestBody = { _rawStr: bodyArgs }; }
        } else if (window.FormData && bodyArgs instanceof FormData) {
           let obj = {};
           for (let key of bodyArgs.keys()) obj[key] = bodyArgs.get(key);
           requestBody = obj;
        } else if (window.URLSearchParams && bodyArgs instanceof URLSearchParams) {
           requestBody = { _rawStr: bodyArgs.toString() };
        } else if (bodyArgs instanceof ArrayBuffer) {
           const str = new TextDecoder().decode(bodyArgs);
           try { requestBody = JSON.parse(str); } catch(e) { requestBody = { _rawStr: str }; }
        } else {
           requestBody = { _type: typeof bodyArgs, stringified: String(bodyArgs) };
        }
      } catch (e) {}

      // Ensure state exists
      let state = xhrStateMap.get(this);
      if (!state) {
        state = { url: url, text: '', captured: false };
        xhrStateMap.set(this, state);
      }

      // We log ALL states to diagnose gRPC-Web streaming lifecycle
      this.addEventListener('readystatechange', function() {
        let currentState = xhrStateMap.get(this) || { text: '', captured: false };
        if (currentState.captured) return; // Already processed this request
        
        let currentText = '';
        try {
          if (!this.responseType || this.responseType === 'text' || this.responseType === '') {
               currentText = this.responseText;
          } else if (this.responseType === 'arraybuffer' && this.response instanceof ArrayBuffer) {
               currentText = new TextDecoder('utf-8').decode(this.response);
          }
        } catch(err) {}

        // Accumulate the largest chunk of text (streaming builds it up)
        if (currentText && currentText.length > currentState.text.length) {
            currentState.text = currentText;
            xhrStateMap.set(this, currentState);
        }

        if (this.readyState === 4 || (this.readyState === 0 && currentState.text.length > 0)) {
            console.log(`[Project DNA] 🧬 Triggering capture! Final text length: ${currentState.text.length}, Triggered on state: ${this.readyState}`);
            currentState.captured = true; // Mark as done
            xhrStateMap.set(this, currentState);
            
            const capturedText = currentState.text;
            setTimeout(() => {
                let responseData = null;
                try {
                    responseData = JSON.parse(capturedText);
                } catch {
                    responseData = { rawText: capturedText };
                }
                processInterceptedCall(url, requestBody, { text: async () => capturedText }, currentState.snapshotUrls || new Set());
            }, 10);
        }
      });

      this.addEventListener('error', () => { 
        const s = xhrStateMap.get(this);
        if (!s || !s.captured) console.warn(`[Project DNA] ⚠️ XHR Error on: ${url}`);
      });
      this.addEventListener('abort', () => { 
        const s = xhrStateMap.get(this);
        if (!s || !s.captured) console.warn(`[Project DNA] ⚠️ XHR Aborted on: ${url}`);
      });
      
      // Scrape DOM BEFORE request finishes to memorize historical images for THIS request
      let localSnapshotUrls = new Set();
      try {
          document.querySelectorAll('img[src*="googleusercontent.com"]').forEach(img => {
              if (img.src) {
                  let baseUrl = img.src.split('=')[0]; 
                  localSnapshotUrls.add(baseUrl);
              }
          });
      } catch(e) {}
      
      const currentState = xhrStateMap.get(this) || { text: '', captured: false };
      currentState.snapshotUrls = localSnapshotUrls;
      xhrStateMap.set(this, currentState);
    }

    return originalXhrSend.apply(this, arguments);
  };




  // =========================================================================
  // DATA EXTRACTION
  // =========================================================================

  /**
   * Process an intercepted API call: extract prompt, model, params, output.
   *
   * This function runs ASYNCHRONOUSLY and does NOT block the page.
   * Even if it fails, AI Studio continues working normally.
   *
   * @param {string} url           - The API endpoint URL
   * @param {object} requestBody   - The parsed JSON request body
   * @param {Response} clonedResp  - A cloned Response object to read
   * @param {Set} snapshotUrls     - A Set of Google image URLs that were present on the page BEFORE the request was sent
   */
  async function processInterceptedCall(url, requestBody, clonedResp, snapshotUrls) {
    try {
      // Read the response body as text
      const responseText = await clonedResp.text();
      let responseData = null;

      try {
        responseData = JSON.parse(responseText);
      } catch {
        // Some responses might be streaming (SSE). Handle gracefully.
        responseData = { rawText: responseText };
      }

      // Extract structured data from the request and response
      const capturedData = extractGenerationData(url, requestBody, responseData, snapshotUrls);

      if (capturedData) {
        // DEDUPLICATION: key is based only on the first 300 chars of the prompt
        // (plus any result image URLs). This ensures that the same prompt sent
        // from multiple batchexecute sub-requests collapses into one capture,
        // while genuinely different prompts still get through.
        const promptKey = (capturedData.promptText || '').substring(0, 300);
        const imagesKey = (capturedData.resultUrls || []).join(',').substring(0, 200);
        const dedupStr = promptKey + '|||' + imagesKey;

        let hash = 0;
        for (let i = 0; i < dedupStr.length; i++) hash = ((hash << 5) - hash) + dedupStr.charCodeAt(i);
        const dedupKey = hash.toString();

        const now = Date.now();
        if (recentCaptures.has(dedupKey)) {
            const timeSince = now - recentCaptures.get(dedupKey);
            if (timeSince < DEDUP_WINDOW_MS) {
                console.log(`[Project DNA] 🔁 Skipping duplicate capture (same prompt within ${DEDUP_WINDOW_MS}ms)`);
                return; // Skip duplicate
            }
        }
        recentCaptures.set(dedupKey, now);

        // Keep map small
        if (recentCaptures.size > 50) {
            const keysToDelete = Array.from(recentCaptures.keys()).slice(0, 20);
            keysToDelete.forEach(k => recentCaptures.delete(k));
        }

        finalizeAndSendCapture(capturedData, snapshotUrls);

      } else {
        // Suppress warning spam for normal background syncs
        // console.warn(`[Project DNA] ⚠️ Generation data extraction returned null (empty prompt/output) for url: ${url}`);
      }
    } catch (err) {
      console.error('[Project DNA] Error processing intercepted call:', err);
    }
  }

  /**
   * Extract structured generation data from raw API request/response.
   */
  function extractGenerationData(url, requestBody, responseData, snapshotUrls = new Set()) {
    if (!requestBody && !responseData) return null;

    let model = 'gemini-web-consumer'; // Default for gemini.google.com
    const modelMatch = url.match(/models\/([^:\/?]+)/);
    if (modelMatch) model = modelMatch[1];
    
    if (requestBody && requestBody.model) model = requestBody.model;

    let promptText = '';
    let systemInstruction = '';
    let outputText = '';
    let finishReason = 'SUCCESS';
    let generationConfig = requestBody?.generationConfig || {};
    let safetySettings = requestBody?.safetySettings || [];
    let resultUrls = [];
    let resultBase64Images = [];

    // ==========================================================
    // 1. EXTRACT PROMPT
    // ==========================================================
    if (requestBody) {
      // 1A. Standard AI Studio JSON Format
      if (requestBody.contents && Array.isArray(requestBody.contents)) {
        const userParts = requestBody.contents
          .filter(c => c.role === 'user')
          .flatMap(c => c.parts || [])
          .filter(p => typeof p.text === 'string')
          .map(p => p.text);
        if (userParts.length > 0) promptText = userParts.join('\n\n');
      } 
      // 1B. Gemini Web Consumer Format (batchexecute / f.req)
      else {
        let rawStr = requestBody._rawStr || '';
        let fReq = requestBody['f.req'];

        if (!fReq && typeof rawStr === 'string' && rawStr.includes('f.req=')) {
          try { fReq = new URLSearchParams(rawStr).get('f.req'); } catch(e) {}
        }

        if (fReq) {
          try {
            const reqArr = JSON.parse(fReq);
            const potentialPrompts = [];
            function findPrompts(obj) {
              if (typeof obj === 'string') {
                if (obj.length > 5) {
                  try {
                    const parsed = JSON.parse(obj);
                    findPrompts(parsed);
                  } catch (e) {
                    if (!obj.startsWith('http') && !obj.includes('googleusercontent.com')) {
                      potentialPrompts.push(obj);
                    }
                  }
                }
              } else if (Array.isArray(obj)) {
                for (const item of obj) findPrompts(item);
              } else if (typeof obj === 'object' && obj !== null) {
                for (const key in obj) findPrompts(obj[key]);
              }
            }
            findPrompts(reqArr);

            function cleanupPrompt(s) {
              return s.replace(/\["data_analysis_tool"[\s\S]*$/, '')
                      .replace(/\u0000/g, '')
                      .trim();
            }

            const validTexts = potentialPrompts
              .map(cleanupPrompt)
              // Must have at least one space (= at least 2 words)
              // Minimum length 3 to allow short prompts like "OK", "Hi"
              // but skip empty / single-char strings from telemetry
              .filter(t => t.length > 3 && t.includes(' '))
              // Reject pure base64 / token strings (long, no spaces, alphanumeric)
              .filter(t => !t.match(/^[a-zA-Z0-9_\-\/\+\=]{40,}$/))
              // Reject JSON-like strings (start with { or [)
              .filter(t => !t.startsWith('{') && !t.startsWith('['))
              // Require at least 2 words (redundant with space check, but explicit)
              .filter(t => t.split(' ').length >= 2);

            if (validTexts.length > 0) {
              // Join all found texts while avoiding contiguous duplicates.
              // In large Gemini requests, the prompt is often nested multiple times.
              // We want to capture the FULL user text even if it's split.
              const uniqueTexts = validTexts.filter((t, i, arr) => i === 0 || !arr[i - 1].includes(t));
              
              // 1. Find the longest single entry (usually the full text)
              const sortedByLength = [...uniqueTexts].sort((a, b) => b.length - a.length);
              const longest = sortedByLength[0];

              // 2. If the longest entry is significantly large (>50% of sum), use it.
              // Otherwise join all unique pieces.
              const totalLen = uniqueTexts.join(' ').length;
              if (longest.length > totalLen * 0.7) {
                promptText = longest;
              } else {
                promptText = uniqueTexts.join('\n\n');
              }
              
              // Capping prompt to avoid DB overflow (max 20k)
              if (promptText.length > 20000) promptText = promptText.substring(0, 20000) + '...[truncated]';
            }
          } catch(e) {}
        }
        
        // 1C. Unknown Nested Array API
        if (!promptText && Array.isArray(requestBody)) {
            try {
                const flatStr = JSON.stringify(requestBody);
                const textMatches = Array.from(flatStr.matchAll(/{"text":"(.*?)"}|"text":"(.*?)"/g));
                if (textMatches.length > 0) {
                    promptText = textMatches.map(m => m[1] || m[2]).filter(t => t && t.length > 2).join('\n\n');
                }
            } catch(e) {}
        }
      } // Closes else block from line 454

      // 1D. System Instruction
      if (requestBody.systemInstruction?.parts) {
        systemInstruction = requestBody.systemInstruction.parts.map(p => p.text || '').join('\n');
      }
    } // Closes if (requestBody)

    // ==========================================================
    // 2. EXTRACT OUTPUT
    // ==========================================================
    if (responseData) {
      // 2A. Standard AI Studio Format
      if (responseData.candidates) {
        const candidate = responseData.candidates[0];
        if (candidate?.content?.parts) {
          outputText = candidate.content.parts.filter(p => p.text).map(p => p.text).join('');
        }
        finishReason = candidate?.finishReason || 'SUCCESS';

      // 2B. AI Studio Streaming Array
      } else if (Array.isArray(responseData) && responseData.length > 0 && responseData[0].candidates) {
        outputText = responseData
          .filter(chunk => chunk?.candidates)
          .flatMap(chunk => chunk.candidates)
          .flatMap(c => c.content?.parts || [])
          .filter(p => p.text)
          .map(p => p.text)
          .join('');

      // 2C. Batched Execute / Google RPC Format (Gemini web batchexecute?rpcids=ESY5D)
      } else if (responseData.rawText) {
        let text = responseData.rawText;

        if (text.startsWith('data: ')) {
          // SSE format
          outputText = parseSSEResponse(text);

        } else if (text.includes(")]}'")) {
          // Google batchexecute streaming format.
          // Gemini streams multiple wrb.fr blocks:
          //   - Early blocks: cumulative AI response (each contains the full text so far)
          //   - Final block:  metadata marker [[null,null,null,null,true]] — NO text
          //
          // Strategy: scan ALL blocks, take the LONGEST valid text per block, collect in chunks[].
          // Then substring-dedup removes progressive partial states, leaving the longest complete response.
          text = text.replace(/^\)\]\}'\n*/, '');
          const lines = text.split('\n');
          const chunks = [];

          for (const line of lines) {
            if (!line.startsWith('[')) continue;
            let parsedLine;
            try { parsedLine = JSON.parse(line); } catch(e) { continue; }
            if (!Array.isArray(parsedLine)) continue;

            for (const item of parsedLine) {
              if (!Array.isArray(item) || item[0] !== 'wrb.fr' || typeof item[2] !== 'string') continue;

              let embedded;
              try { embedded = JSON.parse(item[2]); } catch(e) { continue; }
              const deepStrings = [];
              const deepUrls = [];
              (function ext(obj, depth) {
                if (depth > 12 || !obj) return;
                if (typeof obj === 'string') {
                  if (obj.startsWith('http') && (obj.includes('googleusercontent.com') || obj.includes('aistudio.google.com/u/') || obj.includes('/image/'))) {
                    deepUrls.push(obj);
                  } else if (obj.length > 4) {
                    deepStrings.push(obj);
                  }
                } else if (Array.isArray(obj)) {
                  for (const child of obj) ext(child, depth + 1);
                } else if (typeof obj === 'object') {
                  for (const key in obj) ext(obj[key], depth + 1);
                }
              })(embedded, 0);

              // Collect image URLs
              for (const url of deepUrls) {
                if (url.includes('/a/') || url.includes('/a-/') || url.includes('AATXAJ') || url.includes('photo.jpg')) continue;
                const cleanUrl = url.replace(/\/(rd-)?gg-dl\//, '/');
                if (cleanUrl.length > 60) {
                  const baseUrl = cleanUrl.split('=')[0];
                  if (!snapshotUrls.has(baseUrl) && !resultUrls.includes(cleanUrl)) {
                    snapshotUrls.add(baseUrl);
                    resultUrls.push(cleanUrl);
                  }
                }
              }

                for (let str of deepStrings) {
                  str = str.replace(/\\n/g, '\n').replace(/\\"/g, '"')
                           .replace(/\\t/g, '\t').replace(/\\\\/g, '\\');
                  // Remove technical base64 debris at end of strings
                  str = str.replace(/\n?[!]?[A-Za-z0-9_\-\/\+\.]{80,}[=]*\s*$/, '').trim();

                  if (str.length < 5) continue;
                  
                  // Reject long technical tokens/IDs (long strings with no spaces)
                  if (str.length > 15 && !str.includes(' ')) continue;
                  if (str.length > 50 && !str.includes(' ')) continue;

                  const spaceCount = (str.match(/ /g) || []).length;
                  if (str.length > 50 && spaceCount / str.length < 0.05) continue; 
                  
                  if (str.includes('models/') || str.includes('data_analysis_tool')) continue;
                  if (/^https?:\/\//.test(str)) continue;
                  if (/[a-zA-Z0-9_\-\/\+\=]{100,}/.test(str)) continue; // Was 60, increased to avoid killing Russian text
                  
                  chunks.push(str);
                }
            }
          }

          console.log(`[DNA 2C] ${chunks.length} candidate(s) from all blocks`);
          chunks.slice(0, 3).forEach((c, i) =>
            console.log(`  #${i} len=${c.length}: "${c.substring(0, 70).replace(/\n/g, '↵')}"`)
          );

          if (chunks.length > 0) {
            // Substring dedup + prefix dedup: remove progressive partial states and duplicate artifacts.
            const unique = [];
            for (const c of chunks) {
               const existingIdx = unique.findIndex(u => 
                 u.includes(c) || c.includes(u) || 
                 (u.length > 20 && c.length > 20 && u.substring(0, 20) === c.substring(0, 20)) ||
                 (u.length > 20 && c.length > 20 && u.slice(-20) === c.slice(-20))
               );
               if (existingIdx !== -1) {
                  if (c.length > unique[existingIdx].length) unique[existingIdx] = c;
               } else {
                  unique.push(c);
               }
            }
            const candidates = unique.length > 0 ? unique : chunks;
            // Sort by length but try to maintain a cohesive output.
            candidates.sort((a, b) => b.length - a.length);
            const validCandidates = candidates.filter(c => c.length > 40 && !c.includes('Nano Banana'));
            // Remove the explicit "---" separator as it fragments the text too much.
            // Use just double newlines for a cleaner integrated look.
            const best = validCandidates.join('\n\n');
            
            // Beauty cleanup: remove Google's internal safety placeholders
            // and technical artifacts like "Chicago, IL, USA"
            let cleaned = best
                .replace(/(?:^|\n)(?:[*#\s]*)?\[[^\]]*(?:удален|removed)\][ \t]*(?:\r?\n[ \t]*[-*=_]{3,}[ \t]*)?\s*/gi, '\n')
                .replace(/^Chicago, IL, USA[ \t]*\n*/i, '') // Remove location artifact
                .replace(/^\s*[-*=_]{3,}\s*\n/gm, '') // Remove orphaned dividers
                .replace(/\n{3,}/g, '\n\n') // Fix spacing
                .trim();
                
            outputText = cleaned.length > 4000 ? cleaned.substring(0, 4000) + '…[truncated]' : cleaned;
            console.log(`[DNA 2C] ✅ response_text len=${outputText.length}: "${outputText.substring(0, 80).replace(/\n/g, '↵')}"`);
          }
        }
      }
    }
    // Ultimate fallback algorithm
    if (!promptText && requestBody) {
       try {
         const potentialPrompts = [];
         function findPromptsFB(obj) {
             if (typeof obj === 'string') {
                 if (obj.length > 5) {
                     try {
                         const parsed = JSON.parse(obj);
                         findPromptsFB(parsed);
                     } catch(e) {
                         if (!obj.startsWith('http') && !obj.includes('googleusercontent')) potentialPrompts.push(obj);
                     }
                 }
             } else if (Array.isArray(obj)) {
                 for (const item of obj) findPromptsFB(item);
             } else if (typeof obj === 'object' && obj !== null) {
                 for (const key in obj) findPromptsFB(obj[key]);
             }
         }
         findPromptsFB(requestBody);
         const validTexts = potentialPrompts
             .map(s => s.replace(/\["data_analysis_tool"[\s\S]*$/, '').replace(/\u0000/g, '').trim())
             .filter(t => t.length > 10 && t.includes(' '))
             .filter(t => !t.match(/^[a-zA-Z0-9_\-\/\+\=]{40,}$/));
         if (validTexts.length > 0) promptText = validTexts[validTexts.length - 1];
       } catch(e) {}
    }
    
    if (!outputText && responseData) {
      try {
        const raw = typeof responseData.rawText === 'string' ? responseData.rawText : JSON.stringify(responseData);

        // DO NOT scan entire rawText — it contains ALL streaming chunks (progressive states).
        // Find the LAST wrb.fr block (same logic as above), then pick the LONGEST quoted string
        // from it. That string is the final complete AI response.
        const stripped = raw.replace(/^\)\]\}'\n*/, '');
        const lines = stripped.split('\n');
        let lastWrbRaw = null;

        for (const line of lines) {
          if (!line.startsWith('[')) continue;
          try {
            const parsed = JSON.parse(line);
            if (!Array.isArray(parsed)) continue;
            for (const item of parsed) {
              if (Array.isArray(item) && item[0] === 'wrb.fr' && typeof item[2] === 'string') {
                lastWrbRaw = item[2]; // Keep overwriting — want the LAST one
              }
            }
          } catch(e) {}
        }

        const searchTarget = lastWrbRaw || raw;
        // Extract all quoted strings ≥ 50 chars with spaces (natural language)
        const candidates = Array.from(searchTarget.matchAll(/"([^"]{50,})"/g))
          .map(m => m[1].replace(/\\n/g, '\n').replace(/\\"/g, '"').trim())
          .filter(t => t.includes(' ') && !t.startsWith('http'));

        if (candidates.length > 0) {
          const unique = [];
          for (const c of candidates) {
             const existingIdx = unique.findIndex(u => 
               u.includes(c) || c.includes(u) || 
               (u.length > 20 && c.length > 20 && u.substring(0, 20) === c.substring(0, 20)) ||
               (u.length > 20 && c.length > 20 && u.slice(-20) === c.slice(-20))
             );
             if (existingIdx !== -1) {
                if (c.length > unique[existingIdx].length) unique[existingIdx] = c;
             } else {
                unique.push(c);
             }
          }
          const survived = (unique.length > 0 ? unique : candidates).sort((a, b) => b.length - a.length);
          const validCandidates = survived.filter(c => c.length > 40 && !c.includes('Nano Banana'));
          const best = validCandidates.join('\n\n');
          outputText = best.length > 4000 ? best.substring(0, 4000) + '…[truncated]' : best;
          console.log(`[Project DNA] 📝 Fallback response extraction: ${candidates.length} candidates → kept 1 (len=${outputText.length})`);
        }
      } catch(e) {}
    }

    // Force values to string if nothing was found
    if (!promptText) promptText = '(Unable to parse prompt from RPC)';
    if (!outputText) outputText = '(Unable to parse payload from RPC response)';

    // DO NOT return parasite telemetry or historical scroll loads
    if (promptText.includes('Unable to parse prompt from RPC')) {
        return null; 
    }

    return {
      model: model || 'gemini',
      promptText: promptText,
      systemInstruction: systemInstruction,
      outputText: outputText,
      finishReason: finishReason,
      parameters: {
        temperature: generationConfig.temperature ?? null,
        topP: generationConfig.topP ?? null,
        topK: generationConfig.topK ?? null,
        maxOutputTokens: generationConfig.maxOutputTokens ?? null,
        candidateCount: generationConfig.candidateCount ?? null,
        stopSequences: generationConfig.stopSequences ?? null,
        seed: generationConfig.seed ?? null,
      },
      safetySettings: safetySettings,
      resultUrls: resultUrls,
      resultBase64Images: resultBase64Images,
      apiUrl: url,
    };
  }

  function parseSSEResponse(rawText) {
    const lines = rawText.split('\n');
    const texts = [];

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const jsonStr = line.substring(6);
          const data = JSON.parse(jsonStr);
          if (data.candidates) {
            for (const candidate of data.candidates) {
              if (candidate.content?.parts) {
                for (const part of candidate.content.parts) {
                  if (part.text) texts.push(part.text);
                }
              }
            }
          }
        } catch {}
      }
    }

    return texts.join('');
  }

  /**
   * Fetch a Google image URL and convert it to a base64 data URL.
   *
   * lh3.googleusercontent.com URL format: /[token]=[size_param]
   * WITHOUT a size param (e.g. URL ends in bare token like "xxx-") → server returns 400.
   * We try up to 3 URL variants to handle this.
   *
   * @param {string} url - Google CDN image URL (may or may not have size param)
   * @returns {Promise<string|null>} base64 data URL or null on failure
   */
  async function fetchImageAsBase64(url) {
    // Build URL variants to try in order:
    // 1. URL with =s4096 appended (highest quality, works when no size param present)
    // 2. Original URL as-is
    // 3. URL with =s0 (original size alias)
    const hasEqualParam = /=[a-zA-Z0-9\-]+$/.test(url);
    const urlVariants = hasEqualParam
      ? [url]  // Already has param — use as-is
      : [`${url}=s4096`, url, `${url}=s0`]; // No param — try with size first

    for (const fetchUrl of urlVariants) {
      try {
        const response = await originalFetch(fetchUrl, {
          credentials: 'include',
          redirect: 'follow',
        });

        if (!response.ok) {
          console.warn(`[Project DNA] 🖼️ ${response.status} for: ${fetchUrl.substring(0, 80)}`);
          continue; // Try next variant
        }

        const blob = await response.blob();
        if (!blob || blob.size < 1000) {
          console.warn(`[Project DNA] 🖼️ Suspiciously small blob (${blob?.size}b), skipping`);
          continue;
        }

        return new Promise((resolve) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result);
          reader.onerror = () => resolve(null);
          reader.readAsDataURL(blob);
        });
      } catch (e) {
        console.warn(`[Project DNA] 🖼️ fetch error for variant: ${e.message}`);
      }
    }
    return null; // All variants failed
  }

  /**
   * Wait for new images to appear in the DOM (rendered by Gemini after generation).
   * This is the MOST RELIABLE source of image URLs — the browser already has them loaded.
   *
   * @param {Set} knownBaseUrls - Already-known base URLs to exclude
   * @param {number} expectedCount - How many new images to wait for
   * @param {number} timeoutMs - Max time to wait
   * @returns {Promise<string[]>} Fresh img.src URLs from the DOM
   */
  function waitForDOMImages(knownBaseUrls, expectedCount, timeoutMs) {
    return new Promise((resolve) => {
      const found = new Set();

      function scanDOM() {
        document.querySelectorAll('img[src*="googleusercontent.com"]').forEach((img) => {
          if (!img.src) return;
          const base = img.src.split('=')[0];
          if (!knownBaseUrls.has(base) && !found.has(img.src)) {
            found.add(img.src);
          }
        });
      }

      // Immediate scan (image may already be in DOM)
      scanDOM();
      if (found.size >= expectedCount) {
        resolve([...found]);
        return;
      }

      const observer = new MutationObserver(() => {
        scanDOM();
        if (found.size >= expectedCount) {
          observer.disconnect();
          clearTimeout(timer);
          resolve([...found]);
        }
      });
      observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['src'] });

      const timer = setTimeout(() => {
        observer.disconnect();
        resolve([...found]);
      }, timeoutMs);
    });
  }

  /**
   * Finalize captured data, download any images in page context, and post to content-script.
   * Made async so we can await image downloads before sending.
   */
  async function finalizeAndSendCapture(capturedData, knownBaseUrls = new Set()) {
    captureCount++;
    capturedData.captureIndex = captureCount;
    capturedData.timestamp = new Date().toISOString();
    capturedData.sourceUrl = window.location.href;

    // -----------------------------------------------------------------------
    // Image capture strategy (in priority order):
    // 1. Try fetching API response URLs with size param fix (fast, ~1s)
    // 2. Wait for DOM MutationObserver to get live img.src URLs (reliable, ~3s)
    // 3. Fallback: keep original URL for service worker to attempt later
    // -----------------------------------------------------------------------
    if (capturedData.resultUrls && capturedData.resultUrls.length > 0) {
      console.log(`[Project DNA] 🖼️ Fetching ${capturedData.resultUrls.length} image(s)...`);
      const base64Images = [];

      // --- Strategy 1: fetch from API response URLs (with size param fix) ---
      for (const imageUrl of capturedData.resultUrls) {
        const b64 = await fetchImageAsBase64(imageUrl);
        if (b64) {
          base64Images.push(b64);
          console.log(`[Project DNA] 🖼️ ✅ Strategy 1 OK (${Math.round(b64.length / 1024)}KB)`);
        }
      }

      // --- Strategy 2: DOM MutationObserver (if Strategy 1 got nothing) ---
      if (base64Images.length === 0) {
        console.log(`[Project DNA] 🖼️ Strategy 1 failed, waiting for DOM images (up to 6s)...`);
        const domUrls = await waitForDOMImages(knownBaseUrls, capturedData.resultUrls.length, 6000);

        if (domUrls.length > 0) {
          console.log(`[Project DNA] 🖼️ DOM observer found ${domUrls.length} live URL(s)`);
          for (const domUrl of domUrls) {
            const b64 = await fetchImageAsBase64(domUrl);
            if (b64) {
              base64Images.push(b64);
              console.log(`[Project DNA] 🖼️ ✅ Strategy 2 OK — DOM src fetched (${Math.round(b64.length / 1024)}KB)`);
            }
          }
          // Even if fetch failed, use the live DOM URL (it'll work for a few hours)
          if (base64Images.length === 0) {
            capturedData.resultUrls = domUrls;
            console.warn(`[Project DNA] 🖼️ Using raw DOM URLs as fallback`);
          }
        }
      }

      if (base64Images.length > 0) {
        capturedData.resultBase64Images = (capturedData.resultBase64Images || []).concat(base64Images);
      }
    }

    window.postMessage({
      type: MESSAGE_TYPE,
      payload: capturedData,
    }, '*');

    const promptSnippet = capturedData.promptText || '';
    const imgInfo = capturedData.resultBase64Images
      ? ` | 🖼️ ${capturedData.resultBase64Images.length} image(s) pre-fetched`
      : '';

    console.log(
      `[Project DNA] 🧬 Captured generation #${captureCount}:`,
      capturedData.model,
      `| prompt: ${promptSnippet.substring(0, 80)}...${imgInfo}`
    );
  }

  // =========================================================================
  // INITIALIZATION
  // =========================================================================

  // Notify content script that page-script is loaded and active
  window.postMessage({
    type: STATUS_TYPE,
    payload: {
      status: 'initialized',
      message: 'Project DNA fetch interceptor is active',
      timestamp: new Date().toISOString(),
    },
  }, '*');

  console.log('[Project DNA] 🧬 Fetch interceptor initialized. Monitoring AI Studio API calls...');

})();
