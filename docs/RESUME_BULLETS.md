# 💼 Выдающиеся профессиональные достижения (Resume Bullets)

Этот документ собирает самые сложные, архитектурно значимые и «вкусные» решённые задачи в рамках Project DNA. Каждую из этих строк можно смело вставлять в резюме MLOps/Fullstack инженера на сеньорские позиции.

## 🧬 Project DNA (AI Design Infrastructure)

*   **AI Payload Interception:** Built an invisible AI payload interception layer inside Google's streaming gRPC-Web React environment using transparent Monkey Patching and Outbox patterns, bypassing strict auth protections and preventing prototype collisions.

*   **Deep RPC Payload Extraction:** Engineered a robust, multi-stage recursive parser to intercept and decode undocumented, deeply-nested "Batched Execute" (`)]}'`) JSON payloads and SSE streams from Google's consumer Gemini interface (`gemini.google.com`), enabling full context capture.

*   **gRPC-Web Stream Timing Fix:** Diagnosed and resolved a critical data-loss bug caused by Google AI Studio's state-drop anomaly, where XHR transitions from `readyState 3` to `0`, aborting mid-stream before the AI's description text arrives after the 2MB base64 image payload. Implemented a **deferred capture pattern** with timer cancellation (state:4 wins, state:0 schedules 3s delay), recovering 100% of streamed content.

*   **Dual-Path gRPC Parser (2B-bis / 2D):** Built a two-path parser for Google AI Studio's `MakerSuiteService/GenerateContent` responses: Path 2B-bis uses a recursive array scanner for complete JSON responses; Path 2D uses a robust regex approach (no closing-quote required) to extract text fragments and base64 image data from partial/truncated gRPC-Web buffers caused by premature stream aborts.

*   **LLM Gateway & Routing:** Architected a custom FastAPI-based LLM Router with a Circuit Breaker pattern (Gemini → DeepSeek → Qwen → GLM), implementing automatic key rotation, context injection, and strict rate limit management.

*   **Resilient Data Capture:** Implemented an Outbox delivery pattern in a Manifest V3 browser extension and a WeakMap-based XHR state management system to ensure 100% data capture reliability during volatile gRPC stream drops without impacting the host application's stability.

*   **Vector Search & RAG:** Integrated Qdrant Vector DB with FastEmbed models to create a "Project DNA" semantic search layer, allowing the system to retroactively auto-inject strategic and tactical context into ongoing AI chat sessions.

*   **Semantic Auto-Routing:** Engineered a zero-shot semantic routing microservice using Gemini 2.5 Flash Lite to automatically classify multi-source AI captures (Chrome Extension + Open WebUI) into the correct project without training data. Implemented MD5-based session caching achieving sub-10ms routing overhead on cache hits, with a graceful UNKNOWN fallback triggering queue-based retry rather than silent misrouting. Designed unified `/v1/dna/route` endpoint absorbing full capture pipeline (PostgreSQL + Qdrant + auto-summarize) behind a single call.

*   **Multi-Engine TTS Pipeline:** Unified 4 distinct Text-to-Speech engines (Chatterbox, Kokoro, SaluteSpeech, Silero v5) behind a single REST API, orchestrating asynchronous audio generation and dynamic speed control via ffmpeg.

*   **Automated Context Compression:** Designed a background LLM-powered summarization worker that automatically condenses thousands of captured designer prompts into a two-level (Strategic/Tactical) "Project DNA" constitution.

*   **Interactive AI Dashboard & Media Management:** Developed a real-time SPA dashboard to visualize complex AI interactions. Engineered an Object Storage (MinIO) integration pipeline for capturing, sanitizing (removing signed auth parameters), and serving generated media (Canvas UI) with full semantic search and generation lifecycle management.

*   **ESXi VMware Storage Triage:** Diagnosed and resolved a critical, multi-layer infrastructure deadlock: QEMU/Docker I/O overload causing ESXi AHCI ABORT→VIRT_RESET loops, rendering a VM unkillable via normal means. Performed live VMDK surgery (ESXi SSH) — manually bypassing a corrupt sesparse snapshot chain by patching `.vmx` descriptor and `.vmsd` metadata without data loss — restoring full service to 11 production Docker containers.

*   **Cross-Platform CI/CD & Browser Extension Distribution:** Replaced a complex, failed 3-day self-hosted macOS runner setup (QEMU inside Docker inside ESXi) with a zero-infrastructure solution: Orion Browser (WebKit, Chrome Extension compatible) for macOS. Technical diagnosis included `LSMinimumSystemVersion` plist patching, Mach-O `LC_BUILD_VERSION` analysis via `otool`, and understanding of xcodebuild's Info.plist regeneration behavior.
