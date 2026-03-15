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

  // We don't use a simple array anymore because we want to be more specific.

  /**
   * Message type used for window.postMessage communication.
   * Must match the listener in content-script.js.
   */
  const MESSAGE_TYPE = 'PROJECT_DNA_CAPTURE';

  /**
   * Message type for status/heartbeat messages.
   */
  const STATUS_TYPE = 'PROJECT_DNA_STATUS';

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
    const isGeneration = url.includes('GenerateContent') || url.includes('StreamGenerate') || url.includes('batchexecute');
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
    
    // Check if it's a target internal API
    const isGoogleAPI = url.includes('generativelanguage') || url.includes('alkali') || url.includes('makersuite') || url.includes('BardChatUi') || url.includes('BardFrontendService');
    const isGeneration = url.includes('GenerateContent') || url.includes('StreamGenerate') || url.includes('batchexecute');

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
                  baseUrl = baseUrl.replace(/\/(rd-)?gg-dl\//, '/');
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
        // DEDUPLICATION filtering out the English image string descriptions if we had the same payload earlier
        const dedupStr = (capturedData.promptText || '') + '|||' + (capturedData.outputText || '').substring(0, 100) + '|||' + (capturedData.resultUrls || []).join(',');
        
        let hash = 0;
        for (let i = 0; i < dedupStr.length; i++) hash = ((hash << 5) - hash) + dedupStr.charCodeAt(i);
        const dedupKey = hash.toString();

        const now = Date.now();
        if (recentCaptures.has(dedupKey)) {
            const timeSince = now - recentCaptures.get(dedupKey);
            if (timeSince < DEDUP_WINDOW_MS) {
                console.log(`[Project DNA] 🧬 Skipping duplicate capture: ${capturedData.model}`);
                return; // Skip duplicate
            }
        }
        recentCaptures.set(dedupKey, now);

        // Keep map small
        if (recentCaptures.size > 50) {
            const keysToDelete = Array.from(recentCaptures.keys()).slice(0, 20);
            keysToDelete.forEach(k => recentCaptures.delete(k));
        }

        finalizeAndSendCapture(capturedData);

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
              .filter(t => t.length > 10 && t.includes(' '))
              .filter(t => !t.match(/^[a-zA-Z0-9_\-\/\+\=]{40,}$/)); // Ignore base64 hashes

            if (validTexts.length > 0) {
              promptText = validTexts[validTexts.length - 1]; // Pick the last one which is usually the user's latest prompt
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
      }

      if (requestBody.systemInstruction?.parts) {
        systemInstruction = requestBody.systemInstruction.parts.map(p => p.text || '').join('\n');
      }
    }

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
      } 
      // 2B. AI Studio Streaming Array
      else if (Array.isArray(responseData) && responseData.length > 0 && responseData[0].candidates) {
        outputText = responseData
          .filter(chunk => chunk?.candidates)
          .flatMap(chunk => chunk.candidates)
          .flatMap(c => c.content?.parts || [])
          .filter(p => p.text)
          .map(p => p.text)
          .join('');
      } 
      // 2C. Batched Execute JSON / Text Output
      else if (responseData.rawText) {
        let text = responseData.rawText;
        
        // Handle SSE (Server-Sent Events)
        if (text.startsWith('data: ')) {
          outputText = parseSSEResponse(text);
        } 
        // Handle Google RPC Format, usually starts with )]}'
        else {
          let chunks = [];
          if (text.includes(")]}'")) {
            text = text.replace(/^\)\]\}'\n*/, ''); // Strip prefix
            try {
              // RPC streams are line-delimited arrays
              const lines = text.split('\n');
              for (let line of lines) {
                 if (line.startsWith('[')) {
                    const parsed = JSON.parse(line);
                    // Standard batchexecute response envelopes have 'wrb.fr' followed by a stringified JSON array
                    if (Array.isArray(parsed)) {
                       for (const item of parsed) {
                          if (Array.isArray(item) && item[0] === 'wrb.fr' && typeof item[2] === 'string') {
                             try {
                                const embedded = JSON.parse(item[2]);
                                // Deep recursive extraction from nested arrays
                                const deepStrings = [];
                                const deepUrls = [];
                                
                                function extractDeep(obj, depth) {
                                  if (depth > 15 || !obj) return;
                                  
                                  if (typeof obj === 'string') {
                                    if (obj.startsWith('http') && obj.includes('googleusercontent.com')) {
                                        deepUrls.push(obj);
                                    } else if (obj.length > 30) {
                                        deepStrings.push(obj);
                                    }
                                  } else if (Array.isArray(obj)) {
                                    for (const child of obj) extractDeep(child, depth + 1);
                                  } else if (typeof obj === 'object') {
                                    for (const key in obj) extractDeep(obj[key], depth + 1);
                                  }
                                }
                                extractDeep(embedded, 0);
                                
                                // Process all collected URLs
                                for (let url of deepUrls) {
                                    // Skip avatars and generic icons
                                    if (url.includes('/a/') || url.includes('/a-/') || url.includes('AATXAJ') || url.includes('photo.jpg')) continue;
                                    
                                    // It appears Gemini sometimes ONLY returns the /gg-dl/ version of the URL in the response!
                                    // Bypassing 403 authorization lock requires rewriting /gg-dl/ back to a public URL.
                                    let cleanUrl = url.replace(/\/(rd-)?gg-dl\//, '/');
                                    
                                    if (cleanUrl.length > 60) {
                                        // The base URL without any size query params etc.
                                        let baseUrl = cleanUrl.split('=')[0];
                                        
                                        if (!snapshotUrls.has(baseUrl) && !resultUrls.includes(cleanUrl)) {
                                            snapshotUrls.add(baseUrl);
                                            resultUrls.push(cleanUrl);
                                        }
                                    }
                                }

                                for (let str of deepStrings) {
                                  // Unescape
                                  str = str.replace(/\\n/g, '\n').replace(/\\"/g, '"')
                                           .replace(/\\t/g, '\t').replace(/\\\\/g, '\\');
                                  // Strip Base64/binary tails appended to readable text
                                  str = str.replace(/\n?[!]?[A-Za-z0-9_\-\/\+\.]{80,}[=]*\s*$/, '').trim();
                                  if (str.length < 30) continue;
                                  if (!str.includes(' ')) continue;
                                  const spaceCount = (str.match(/ /g) || []).length;
                                  if (spaceCount / str.length < 0.05) continue;
                                  if (str.includes('models/') || str.includes('data_analysis_tool')) continue;
                                  if (/^https?:\/\//.test(str)) continue;
                                  if (/[a-zA-Z0-9_\-\/\+\=]{60,}/.test(str)) continue;
                                  chunks.push(str);
                                }
                             } catch(err) {}
                          }
                       }
                    }
                 }
              }
            } catch(e) {}
            if (chunks.length > 0) outputText = chunks.join('');
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
         const s = typeof responseData.rawText === 'string' ? responseData.rawText : JSON.stringify(responseData);
         const chunks = Array.from(s.matchAll(/"([^"]{50,})"/g)).map(m=>m[1]).filter(t=>t.includes(' '));
         if (chunks.length) outputText = chunks.join('\n\n');
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

  function finalizeAndSendCapture(capturedData) {
    captureCount++;
    capturedData.captureIndex = captureCount;
    capturedData.timestamp = new Date().toISOString();
    capturedData.sourceUrl = window.location.href;

    window.postMessage({
      type: MESSAGE_TYPE,
      payload: capturedData,
    }, '*');

    const promptSnippet = capturedData.promptText || '';
    
    console.log(
      `[Project DNA] 🧬 Captured generation #${captureCount}:`,
      capturedData.model,
      `| prompt: ${promptSnippet.substring(0, 80)}...`
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
