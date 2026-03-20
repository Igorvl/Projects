# Project DNA Extension - Context Summary

**Date Range:** March 10 - March 20, 2026
**Primary Goal:** Enable the "Project DNA" Chrome extension to reliably intercept and capture generated outputs from Google AI Studio and Gemini Pro.

## ✅ T-06 & T-07 STATUS: CLOSED (v2.0.34 — 2026-03-20)

**T-06 (AI Studio Text+Image stream capture) & T-07 (AI Studio Binary Imagen Capture via XHR Buffer) are both completed!**
**Both sources confirmed working:**
- **Gemini Pro** (gemini.google.com → batchexecute/wrb.fr): text ✅ + images ✅
- **AI Studio** (MakerSuiteService/GenerateContent): text ✅ + images ✅ (including inline base64 via buffer scan)

### Key fixes that closed T-06

| Fix | Version | What it solved |
|-----|---------|----------------|
| URL-dedup XHR (`processedXhrUrls`) | 2.0.29 | `(prompt not captured)` × N spam records |
| Path 2B-bis (JSON.parse success → Array) | 2.0.30 | AI Studio gRPC nested array text + images |
| Path 2D (JSON.parse fail → rawText) | 2.0.31 | AI Studio partial response at state:0 abort |
| Robust `"data":` regex (no closing `"` needed) | 2.0.32 | AI Studio inline base64 image from partial gRPC |

### AI Studio response architecture (discovered)

AI Studio's `MakerSuiteService/GenerateContent` XHR fires at **readyState 0** (premature state-drop anomaly).
Two possible states at capture time:

1. **JSON.parse succeeds** → `responseData = Array` → **Path 2B-bis** handles it
   - Recursively scans nested array `[[[[null,"text"]],...]]` for natural language strings
   - Also finds `{mimeType, data}` inline images and googleusercontent URLs

2. **JSON.parse fails** (partial data) → `responseData = {rawText}` → **Path 2D** handles it
   - Regex scan of rawText for quoted strings with spaces (any length, not just ≥50)
   - Strategy A: `"data":"<b64>` key match — works WITHOUT closing quote
   - Strategy B: bare `iVBORw0` / `/9j/` header in buffer



## Overview of Challenges & Discoveries

Over the last three days, we engaged in a deep dive into reverse-engineering Google AI Studio's internal network traffic. The platform had recently transitioned to new, undocumented API endpoints and data structures, breaking our previous `fetch` interception methods.

The core of the work focused on `src/content/page-script.js`, which is injected into the isolated page context to perform "monkey-patching" on browser network APIs.

### 1. New API Endpoints & Structured Arrays (Fetch)
*   **Discovery:** Google introduced new endpoints (e.g., `alkalimakersuite-pa.clients6.google.com` using the `GenerateContent` RPC method).
*   **Challenge:** The payloads were no longer standard JSON objects (`{ prompt: "...", response: "..." }`) but deeply nested, nameless arrays (RPC format).
*   **Solution:** We updated `API_PATTERNS` to include the new domains and methods. We rewrote `extractGenerationData` to implement a "tank mode" parser: if standard `{text: "..."}` keys are absent, the parser aggressively scans the entire stringified array payload for any strings longer than 10 characters to extract prompts and outputs, ensuring no generation is dropped.

### 2. Browser Caching 
*   **Challenge:** Updates to `page-script.js` were not reflecting in the browser because Chrome aggressively caches injected page-level scripts.
*   **Solution:** Added a cache-busting timestamp query parameter (`?t=Date.now()`) in `content-script.js` when calling `chrome.runtime.getURL()`.

### 3. State Management Bug (Popup)
*   **Challenge:** The popup failed to save the selected project, immediately resetting to "Select project", which caused captured generations to hang in the Service Worker's retry queue.
*   **Solution:** AI-Router was returning project unique identifiers as `id`, but the popup expected `slug`. Updated `popup.js` to handle `projectId = project.slug || project.id || String(project.name)`.

### 4. The gRPC-Web & XHR Challenge
*   **Discovery:** We found that AI Studio uses `XMLHttpRequest` (XHR) instead of `fetch` for some new models, specifically transmitting binary protobuf data via gRPC-Web streams.
*   **Challenge 1 (Auth Failures):** Initial attempts to override XHR `open` and `send` corrupted Google's custom authentication headers or prototype chains, causing `401 Unauthorized` and `403 Forbidden` errors from Google's servers.
    *   *Fix:* Converted the interceptor to be 100% transparent using `originalXhrOpen.apply(this, arguments)` and stored local variables safely in a JavaScript `Symbol` to prevent prototype collision.
*   **Challenge 2 (Binary Data):** Responses were coming back as `ArrayBuffer` instead of text.
    *   *Fix:* Implemented `TextDecoder('utf-8').decode()` to forcefully extract readable text from binary buffers.

### 5. The State-Drop Streaming Anomaly (Major Breakthrough)
*   **The Final Boss:** XHR requests were being caught starting (`readyState 1, 2`), downloading data (`readyState 3`), but were **never reaching completion (`readyState 4`)**.
*   **Discovery:** Google's frontend framework reads the gRPC-Web stream chunk-by-chunk while the connection is still in `readyState 3`. Once the frontend receives their internal "EOF" signal from the payload, they immediately call `.abort()` on the XHR object to free up memory. This violently drops the `readyState` back to `0` representing an unsent/aborted state, bypassing `4` entirely.
*   **Solution:** We implemented an aggressive state-drop capture strategy:
    1.  Continuously read and accumulate the largest chunk of text seen during `readyState 3`.
    2.  If the state hits `4` (normal completion), trigger capture.
    3.  If the state violently drops to `0` BUT we have accumulated text (Google's abort pattern), **trigger capture**.
    4.  Used flags (`_dnaCaptured`) to ensure the generation is only submitted to the backend once.

## Current Status
The extension is now equipped with a dual-layered, highly resilient interception engine (`fetch` + aggressive `XHR` state-drop scanning). It is capable of bypassing Google's strict auth protections without breaking the UI, reading binary array buffers, rescuing data from aborted streams, and reliably sending data to the AI-Router without 404/403 errors (by using 100% transparent WeakMap state and dynamically resolving project slugs). 

**Result (March 14, 2026):** Full end-to-end functionality confirmed on both `aistudio.google.com` and `gemini.google.com`. The extension successfully captures prompts, params, output, and transmits them cleanly to the Project DNA backend.

For the consumer Gemini interface, we successfully reverse-engineered the Google Batched Execute RPC format (`)]}'`), parsing deeply nested JSON payloads and Server-Sent Events (SSE) to extract prompts and generated responses.

## 🔴 CRITICAL BUG: Long Context Multi-Capture (March 14, 2026)
During testing with long prompts at `gemini.google.com`, a serious regression was found:
- **Issue:** One user interaction triggers 50+ backend capture requests instead of one.
- **Root Cause:** `batchexecute` is an umbrella endpoint for all Google activities (telemetry, drafts, context updates). Filter `url.includes('batchexecute')` was too broad.
- **Impact:** Backend spam, duplicated data, potential rate limiting.

### Fix Applied (March 14, 2026) — 3-Layer Defense:
1. **LAYER 1: Body-based pre-filtering** (`isBatchExecuteGeneration()`):
   - Parses `f.req` from request body before interception
   - Checks payload size (telemetry < 100 chars, generation >> 100 chars)
   - Looks for natural language strings (spaces, length > 20 chars)
   - Filters out telemetry, drafts, UI updates at the earliest stage
   
2. **LAYER 2: Content validation** (in `extractGenerationData()`):
   - Returns `null` when both promptText AND outputText are empty
   - Previously always returned a result with fallback strings, causing noise

3. **LAYER 3: Time+content deduplication** (in `processInterceptedCall()`):
   - djb2 hash of first 300 chars of promptText
   - 10-second dedup window (same prompt hash within 10s = skip)
   - Auto-cleanup of old entries (max 50, TTL 30s)

**Status:** Fix applied, awaiting manual testing on gemini.google.com.

