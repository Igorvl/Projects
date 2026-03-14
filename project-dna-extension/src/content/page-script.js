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
    const isGoogleAPI = url.includes('generativelanguage.googleapis') || url.includes('alkali') || url.includes('makersuite') || url.includes('gemini.google.com');
    const isGeneration = url.includes('GenerateContent') || url.includes('streamGenerateContent') || url.includes('batched');
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
    const isGoogleAPI = url.includes('generativelanguage.googleapis') || url.includes('alkali') || url.includes('makersuite') || url.includes('gemini.google.com');
    const isGeneration = url.includes('GenerateContent') || url.includes('streamGenerateContent') || url.includes('batched');

    if (isGoogleAPI && isGeneration) {
      console.log('[Project DNA] 🧬 Intercepted AI Studio XHR call:', url);
      
      let requestBody = null;
      try {
        if (typeof bodyArgs === 'string') {
          requestBody = JSON.parse(bodyArgs);
        } else if (bodyArgs instanceof ArrayBuffer) {
           const str = new TextDecoder().decode(bodyArgs);
           try { requestBody = JSON.parse(str); } catch(e) {}
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
                
                processInterceptedCall(url, requestBody, { text: async () => capturedText });
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
   */
  async function processInterceptedCall(url, requestBody, clonedResp) {
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
      const capturedData = extractGenerationData(url, requestBody, responseData);

      if (capturedData) {
        captureCount++;
        capturedData.captureIndex = captureCount;
        capturedData.timestamp = new Date().toISOString();
        capturedData.sourceUrl = window.location.href;

        window.postMessage({
          type: MESSAGE_TYPE,
          payload: capturedData,
        }, '*');

        console.log(
          `[Project DNA] 🧬 Captured generation #${captureCount}:`,
          capturedData.model,
          `| prompt: ${(capturedData.promptText || '').substring(0, 80)}...`
        );
      } else {
        console.warn(`[Project DNA] ⚠️ Generation data extraction returned null (empty prompt/output) for url: ${url}`);
        console.warn('Raw Request:', JSON.stringify(requestBody).substring(0, 500));
        console.warn('Raw Response:', JSON.stringify(responseData).substring(0, 500));
      }
    } catch (err) {
      console.error('[Project DNA] Error processing intercepted call:', err);
    }
  }

  /**
   * Extract structured generation data from raw API request/response.
   *
   * Google AI Studio sends different payload formats depending on the
   * API version and the type of request (generateContent, streamGenerateContent).
   * This function normalizes all formats into a single clean structure.
   *
   * @param {string} url          - The API URL (used to extract model name)
   * @param {object} requestBody  - Parsed request JSON
   * @param {object} responseData - Parsed response JSON
   * @returns {object|null}       - Normalized capture data, or null if not a generation
   */
  function extractGenerationData(url, requestBody, responseData) {
    if (!requestBody) return null;

    // ----- Extract model name from URL or request body -----
    const modelMatch = url.match(/models\/([^:/?]+)/);
    let model = modelMatch ? modelMatch[1] : (requestBody.model || 'unknown');
    
    // New 2026 format often nests model deep in RPC payload
    if (model === 'unknown' && Array.isArray(requestBody)) {
       // Search for any string starting with "models/"
       const flatStr = JSON.stringify(requestBody);
       const nestedModelMatch = flatStr.match(/"models\/([^"]+)"/);
       if (nestedModelMatch) model = nestedModelMatch[1];
    }

    // ----- Extract prompt text -----
    // AI Studio format: { contents: [{ parts: [{ text: "..." }], role: "user" }] }
    let promptText = '';
    let systemInstruction = '';

    // AI Studio format 1: standard generative language
    if (requestBody.contents && Array.isArray(requestBody.contents)) {
      const userParts = requestBody.contents
        .filter(c => c.role === 'user')
        .flatMap(c => c.parts || [])
        .filter(p => p.text)
        .map(p => p.text);
      promptText = userParts.join('\n\n');
    } 
    // AI Studio format 2: 2026 internal RPC payload (array of nested arrays)
    else if (Array.isArray(requestBody)) {
        // Deep search the JSON array for any readable prompt text from the user
        // This is a robust fallback for undocumented RPC arrays
        try {
            const flatStr = JSON.stringify(requestBody);
            // Search for {"text": "something"} patterns in the nested array map
            // First, try standard "text":"value" matches
            const textMatches = Array.from(flatStr.matchAll(/{"text":"(.*?)"}|"text":"(.*?)"/g));
            if (textMatches.length > 0) {
                const possiblePrompts = textMatches.map(m => m[1] || m[2]).filter(t => t && t.length > 2);
                if (possiblePrompts.length > 0) promptText = possiblePrompts.join('\n\n');
            }
            
            // If that failed, this is an aggressive RPC format (just arrays). Extract all long strings!
            if (!promptText) {
                const allStrings = Array.from(flatStr.matchAll(/"([^"]{10,})"/g))
                   .map(m => m[1])
                   .filter(t => !t.includes("models/") && !t.includes("generatelanguage") && t !== "GenerateContent");
                if (allStrings.length > 0) promptText = allStrings.join('\n\n');
            }
        } catch(e) {}
    }

    // Extract system instruction if present
    if (requestBody.systemInstruction) {
      const sysParts = requestBody.systemInstruction.parts || [];
      systemInstruction = sysParts.map(p => p.text || '').join('\n');
    }

    // ----- Extract generation parameters -----
    const generationConfig = requestBody.generationConfig || {};
    const safetySettings = requestBody.safetySettings || [];

    // ----- Extract generated output -----
    let outputText = '';
    let finishReason = '';

    if (responseData && responseData.candidates) {
      // Standard response format
      const candidate = responseData.candidates[0];
      if (candidate && candidate.content && candidate.content.parts) {
        outputText = candidate.content.parts
          .filter(p => p.text)
          .map(p => p.text)
          .join('');
      }
      finishReason = candidate?.finishReason || '';
    } else if (Array.isArray(responseData) && responseData.length > 0 && Array.isArray(responseData[0])) {
      // New 2026 internal RPC response (deeply nested arrays)
      try {
          const flatStr = JSON.stringify(responseData);
          // Look for text segments in the output response payload
          const outMatches = Array.from(flatStr.matchAll(/"([^"]+)"/g))
               .map(m => m[1])
               .filter(t => t.length > 10 && !t.includes("models/")); // rudimentary filter for actual generated text
           
           if (outMatches.length > 0) {
               // The longest string in the array structure is usually the generated text
               outputText = outMatches.reduce((a, b) => a.length > b.length ? a : b);
           }
      } catch(e) {}
    } else if (responseData && Array.isArray(responseData)) {
      // Streaming response (array of chunks), e.g., standard API stream
      outputText = responseData
        .filter(chunk => chunk && typeof chunk === 'object' && chunk.candidates)
        .flatMap(chunk => chunk.candidates)
        .flatMap(c => (c.content?.parts || []))
        .filter(p => p.text)
        .map(p => p.text)
        .join('');
    } else if (responseData && responseData.rawText) {
      // SSE streaming response — parse newline-delimited JSON
      outputText = parseSSEResponse(responseData.rawText);
    }

    // Ultimate fallback for missing text so we don't lose the generation metric
    if (!promptText && requestBody) promptText = '(RPC Prompt data)';
    if (!outputText && responseData) outputText = '(RPC Generation data)';

    // Only skip if it's literally empty (which shouldn't happen now)
    if (!promptText && !outputText) return null;

    // ----- Build normalized capture object -----
    return {
      model: model,
      promptText: promptText,
      systemInstruction: systemInstruction,
      outputText: outputText,
      finishReason: finishReason,

      // Generation parameters (important for reproducibility!)
      parameters: {
        temperature: generationConfig.temperature ?? null,
        topP: generationConfig.topP ?? null,
        topK: generationConfig.topK ?? null,
        maxOutputTokens: generationConfig.maxOutputTokens ?? null,
        candidateCount: generationConfig.candidateCount ?? null,
        stopSequences: generationConfig.stopSequences ?? null,
        seed: generationConfig.seed ?? null,
      },

      // Safety settings (array of {category, threshold} objects)
      safetySettings: safetySettings,

      // Metadata
      apiUrl: url,
    };
  }

  /**
   * Parse Server-Sent Events (SSE) response format.
   *
   * When AI Studio uses streaming, the response comes as newline-delimited
   * JSON objects, each prefixed with "data: ". We parse each chunk and
   * extract the text parts.
   *
   * SSE Format Example:
   *   data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]...}}]}
   *   data: {"candidates":[{"content":{"parts":[{"text":" world"}]...}}]}
   *
   * @param {string} rawText - Raw SSE response text
   * @returns {string}       - Concatenated output text
   */
  function parseSSEResponse(rawText) {
    const lines = rawText.split('\n');
    const texts = [];

    for (const line of lines) {
      // SSE data lines start with "data: "
      if (line.startsWith('data: ')) {
        try {
          const jsonStr = line.substring(6); // Remove "data: " prefix
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
        } catch {
          // Skip non-JSON lines (like empty lines or "[DONE]")
        }
      }
    }

    return texts.join('');
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
