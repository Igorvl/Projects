# Project DNA Extension - Context Summary (Last 3 Days)

**Date Range:** ~March 10 - March 13, 2026
**Primary Goal:** Enable the "Project DNA" Chrome extension to reliably intercept and capture generated outputs directly from the Google AI Studio web interface and forward them to a local AI-Router backend.

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

**Result (March 14, 2026):** Full end-to-end functionality confirmed on `aistudio.google.com`. The extension successfully captures prompts, params, output, and transmits them cleanly to the Project DNA backend.

*Next steps:* Expand the interception logic to cover the consumer interface (`gemini.google.com`) by reverse-engineering the Google Batched Execute RPC format.
