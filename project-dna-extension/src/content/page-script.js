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
   * URL patterns that indicate an AI Studio generation API call.
   * These are the endpoints where AI Studio sends prompts to Gemini.
   *
   * We match against these patterns to decide which fetch() calls to intercept.
   * Non-matching calls pass through untouched for zero performance impact.
   */
  const API_PATTERNS = [
    'generativelanguage.googleapis.com',       // Main Gemini API
    'generativelanguage.googleapis.com/v1beta', // Beta API (common in AI Studio)
    'generativelanguage.googleapis.com/v1',     // Stable API
    'alkali-abstractedai-pa.googleapis.com',     // Internal AI Studio endpoint
  ];

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
  window.fetch = async function (resource, init) {
    // Extract URL string from either a string or a Request object
    const url = typeof resource === 'string' ? resource : resource.url;

    // -----------------------------------------------------------------------
    // Fast path: if URL doesn't match our patterns, skip interception entirely.
    // This ensures ZERO performance impact on all other page requests
    // (stylesheets, images, tracking, etc.)
    // -----------------------------------------------------------------------
    const isTargetAPI = API_PATTERNS.some(pattern => url.includes(pattern));
    if (!isTargetAPI) {
      return originalFetch.call(this, resource, init);
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
      response = await originalFetch.call(this, resource, init);
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

        // ---------------------------------------------------------------
        // RELAY TO CONTENT SCRIPT via window.postMessage
        // ---------------------------------------------------------------
        // window.postMessage sends a message to the window itself.
        // Our content script listens for this message type.
        // The second argument ('*') is the target origin — we use '*'
        // because both sender (page) and receiver (content script)
        // are on the same page (aistudio.google.com).
        // ---------------------------------------------------------------
        window.postMessage({
          type: MESSAGE_TYPE,
          payload: capturedData,
        }, '*');

        console.log(
          `[Project DNA] 🧬 Captured generation #${captureCount}:`,
          capturedData.model,
          `| prompt: ${(capturedData.promptText || '').substring(0, 80)}...`
        );
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
    // URL pattern: .../models/gemini-2.0-flash:generateContent
    const modelMatch = url.match(/models\/([^:/?]+)/);
    const model = modelMatch ? modelMatch[1] : (requestBody.model || 'unknown');

    // ----- Extract prompt text -----
    // AI Studio format: { contents: [{ parts: [{ text: "..." }], role: "user" }] }
    let promptText = '';
    let systemInstruction = '';

    if (requestBody.contents && Array.isArray(requestBody.contents)) {
      // Collect all user messages as the prompt
      const userParts = requestBody.contents
        .filter(c => c.role === 'user')
        .flatMap(c => c.parts || [])
        .filter(p => p.text)
        .map(p => p.text);
      promptText = userParts.join('\n\n');
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
    } else if (responseData && Array.isArray(responseData)) {
      // Streaming response (array of chunks)
      outputText = responseData
        .filter(chunk => chunk.candidates)
        .flatMap(chunk => chunk.candidates)
        .flatMap(c => (c.content?.parts || []))
        .filter(p => p.text)
        .map(p => p.text)
        .join('');
    } else if (responseData && responseData.rawText) {
      // SSE streaming response — parse newline-delimited JSON
      outputText = parseSSEResponse(responseData.rawText);
    }

    // Don't capture empty generations
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
