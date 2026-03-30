# 🎯 Project DNA — Goals & Progress Tracker

> **Last Updated:** 2026-03-28  
> **Architecture Version:** 2.2.0  
> **Status:** Active Development  

---

## 🏆 Supergoal

Build a **self-hosted enterprise MLOps ecosystem with "infinite memory"** — so AI tools never forget the designer's working context, automatically manage provider rate limits, and remain completely invisible as infrastructure to the end user.

---

## Goal 1 — Eliminate LLM "Amnesia" (3-Level Memory System)

**Problem:** Every new chat session starts from scratch. The model has no memory of:
- Past decisions, rejected directions, chosen styles
- Nano Banana / Imagen parameters (seeds, steps, style matrix)
- Multi-month project evolution

**Solution:** Auto-compressing RAG Context with 3 levels:
- 📄 **DNA Document** — Manual "project constitution" (tone, palette, typography)
- 📊 **Strategic Context** — Auto-summarized 50 generations every 20 iterations
- ⚡ **Tactical Context** — Auto-summarized 10 generations every 5 iterations

| Milestone | Status |
|-----------|--------|
| PostgreSQL schema (projects, generations, context_summaries) | ✅ Done |
| `auto_summarize.py` background worker | ✅ Done |
| `GET /v1/dna/context/{slug}` — 3-level context assembly | ✅ Done |
| LLM fallback for summarization (Gemini → Qwen3-8B) | ✅ Done |
| `GET/PUT /v1/dna/projects/{slug}/dna-document` — Level 1 DNA Document | ✅ Done |
| `GET /v1/dna/context/{slug}` returns `dna_document` field | ✅ Done |

---

## Goal 2 — Capture Every Generation (Zero Data Loss)

**Problem:** Prompts and AI outputs live only in the browser tab. Close it — lose them forever.

**Solution:** Chrome Extension with dual-layer interceptor + Outbox Pattern:

| Milestone | Status |
|-----------|--------|
| MV3 Extension structure (manifest, popup, service-worker) | ✅ Done |
| `fetch()` monkey-patch interceptor (`page-script.js`) | ✅ Done |
| XHR interceptor for gRPC-Web binary stream | ✅ Done |
| State-Drop Anomaly Fix (readyState 0 → delayed capture) | ✅ Done |
| Path 2B-bis parser (full JSON `[[null,"text"]]`) | ✅ Done |
| Path 2D parser (partial rawText, regex) | ✅ Done |
| Text Fragmentation Fix (incremental token join) | ✅ Done |
| Outbox Pattern (`chrome.alarms`, retry queue) | ✅ Done |
| `POST /v1/dna/capture` backend endpoint | ✅ Done |
| Gemini (gemini.google.com) interception (batchexecute + wrb.fr) | ✅ Done |

---

## Goal 3 — Zero-Downtime LLM Provisioning

**Problem:** Providers have hard quotas. `429 Too Many Requests` stops all work.

**Solution:** LLM Gateway with Circuit Breaker and Tiered Routing:

| Milestone | Status |
|-----------|--------|
| FastAPI Router (`router.py`) + LiteLLM | ✅ Done |
| Tier 1: Gemini Flash (Primary) | ✅ Done |
| Tier 2: DeepSeek-V3 (Code Analysis) | ✅ Done |
| Tier 3: Qwen-3-Coder 480B (DevOps Workhorse) | ✅ Done |
| Multimodal Fallback: Qwen2-VL (Vision) | ✅ Done |
| Circuit Breaker (auto-switch on 429) | ✅ Done |
| Smart tail clipping (context → 32k token window) | ✅ Done |
| Custom SSE Streaming generator | ✅ Done |
| Vision-Aware Routing (auto-detects images in payload) | ✅ Done |
| Region: Split Tunneling via VLESS/Shadowsocks | ✅ Done |

---

## Goal 4 — Semantic Auto-Routing

**Problem:** With 5+ active projects, every captured generation must land in the right one automatically.

**Solution:** Zero-shot classifier (`gemini-2.5-flash-lite`) + Agentic Interceptor:

| Milestone | Status |
|-----------|--------|
| `semantic_router.py` — zero-shot classification | ✅ Done |
| MD5 session-level caching (0ms on repeated messages) | ✅ Done |
| Agentic Interceptor (SSE state machine for `UNKNOWN` routing) | ✅ Done |
| Routing confirmation injected directly into Open WebUI chat | ✅ Done |
| `route_text_capture()` — wrapper for plain-text Extension captures | ✅ Done |
| `POST /v1/dna/route` endpoint (auto-capture + Qdrant + summarize) | ✅ Done |
| Semantic Router for Extension captures (no project selected → auto-route) | ✅ Done |
| Auto-routed fast path image capture to MinIO (Phase 2 URL fallback) | ✅ Done |
| Dashboard batch-correction UI for routing mistakes (via Batch Move) | ✅ Done |

---

## Goal 5 — Media Asset Management (MinIO Pipeline)

**Problem:** AI-generated images live only in the browser cache. No versioning, no search, no cross-tool access.

**Solution:** MinIO (S3-compatible) pipeline with presigned URLs:

| Milestone | Status |
|-----------|--------|
| MinIO Docker integration | ✅ Done |
| `minio_storage.py` — upload / list / presigned URL | ✅ Done |
| Extension: base64 image → MinIO upload | ✅ Done |
| Presigned URL injection into capture record | ✅ Done |
| `POST /v1/dna/upload/{slug}` endpoint | ✅ Done |
| `GET /v1/dna/files/{slug}` endpoint | ✅ Done |
| API latency: 15s → 2-3s (base64 → URL) | ✅ Done |

---

## Goal 6 — Semantic Search Over Generation History

**Problem:** With 1,000+ generations, impossible to find "that dark sci-fi dashboard prompt from last month."

**Solution:** Qdrant Vector DB with FastEmbed:

| Milestone | Status |
|-----------|--------|
| Qdrant Docker integration | ✅ Done |
| `qdrant_db.py` — add / search prompts | ✅ Done |
| Embedding model: `BAAI/bge-small-en-v1.5` | ✅ Done |
| `POST /v1/dna/search` semantic search endpoint | ✅ Done |
| Sidebar semantic search in Dashboard | ✅ Done |
| Race condition fix (4-worker Uvicorn + collection creation) | ✅ Done |

---

## Goal 7 — Style Parameter Logging (Nano Banana / Imagen)

**Problem:** Reproducible image generation requires exact seeds, style matrices, masks, and typography. Without logging, every session starts from zero.

**Solution:** Rich capture schema in PostgreSQL:

| Milestone | Status |
|-----------|--------|
| `seed` field | ✅ Done |
| `model_params` JSONB (steps, guidance, temperature) | ✅ Done |
| `typography` JSONB (font, size, weight) | ✅ Done |
| `mask_source_url` (for inpainting workflows) | ✅ Done |
| `result_urls` + `reference_urls` (style transfer) | ✅ Done |
| `source` field (extension / api / open-webui) | ✅ Done |
| `metadata` JSONB field | ✅ Done |

---

## Goal 8 — Transparent UX for End User

**Problem:** Designer works on macOS. Should never need to know about Docker, API keys, VPN, or PostgreSQL.

**Solution:** Open WebUI + Dashboard + invisible context injection:

| Milestone | Status |
|-----------|--------|
| Open WebUI (PWA) as primary interface | ✅ Done |
| Auto context injection before every LLM request | ✅ Done |
| Dashboard SPA (projects, generations, files, DNA) | ✅ Done |
| Batch Delete / Batch Move in Dashboard | ✅ Done |
| Extension Popup (project selector, capture toggle, queue status) | ✅ Done |
| **Folder System** — colour-coded collapsible folders (Design/MLOps/Other), localStorage persist | ✅ Done |
| **Project Rename** — inline via `PATCH /v1/dna/projects/{slug}` | ✅ Done |
| **Move Project** between folders via modal picker | ✅ Done |
| **Archive/Restore** soft-lifecycle via `POST /archive` / `POST /unarchive` | ✅ Done |
| **Context menu ⋮** — dropdown replaces scattered hover buttons | ✅ Done |
| **Modal sticky header** — title + actions pinned, content scrolls | ✅ Done |
| **Project-wide Lightbox** — navigates ALL images across ALL generations with Gen label | ✅ Done |
| **DNA Context grid** — DNA Document full-width row, Strategic+Tactical side-by-side | ✅ Done |
| Dashboard batch-correction UI for routing mistakes | ✅ Done |

---

## Goal 9 — Security & Disaster Recovery

**Problem:** Self-hosted = full responsibility for data integrity and IP protection.

| Milestone | Status |
|-----------|--------|
| Secrets via `.env` + `.gitignore` | ✅ Done |
| `.env.example` template committed to repo | ✅ Done |
| PostgreSQL + Qdrant cron dumps | ✅ Done |
| MinIO → Physical tarball backups | ✅ Done |
| `restore.sh` — single-command cluster recovery | ✅ Done |
| Monthly DR tests in isolated VLAN | ✅ Done (Game Day via ABB Instant Restore) |
| Active Backup for Business (NAS Integration) | ✅ Done |

---

## Goal 10 — Observability Stack

**Problem:** No visibility into token spend, API latency, quota exhaustion, or container health.

| Milestone | Status |
|-----------|--------|
| Prometheus (metrics scraping) | ✅ Done |
| Grafana (dashboards + Alerting System) | ✅ Done |
| Telegraf (direct Docker API container metrics vs broken cAdvisor) | ✅ Done |
| Loki + Promtail (centralized log aggregation) | 🔴 Planned |

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ Done | Implemented and working in production |
| 🟡 Partial | In progress or partially implemented |
| 🔴 Planned | Designed, not yet implemented |

---

## Goal 11 — Antigravity Context Integration

**Problem:** The most valuable architectural and MLOps discussions happen directly with the AI Assistant ("Google Antigravity"), but this knowledge remains siloed in isolated chat histories and isn't part of the overarching Project DNA database.

**Solution:** Develop a dedicated capture pipeline/sync between Antigravity session outputs and the Project DNA context engine.

| Milestone | Status |
|-----------|--------|
| Design data extraction strategy for Antigravity chats | 🔴 Planned |
| Map chat metadata (tags, goals, code snippets) to DNA Schema | 🔴 Planned |
| Create CLI or automated daemon to push context to `POST /v1/dna/capture` | 🔴 Planned |
| Include Antigravity architectural decisions in 3-level context | 🔴 Planned |

---

## Goal 12 — System Redundancy (High Availability & Failover)

**Problem:** A single container crash, network tunnel ban, or ESXi disk failure could paralyze the entire AI generation pipeline. The system needs proactive redundancy at compute, storage, and networking layers.

**Solution:** Implement Active-Passive and Active-Active high availability strategies suitable for a self-hosted ML environment.

| Milestone | Status |
|-----------|--------|
| **DB Redundancy:** PostgreSQL Primary/Standby replication (Repmgr) | 🔴 Planned |
| **Vector DB Redundancy:** Qdrant Distributed Deployment (Cluster mode) | 🔴 Planned |
| **Compute HA:** Load Balancer (Traefik/Nginx) for `ai-router` scaling (`replicas: 3`) | 🔴 Planned |
| **Storage Sync:** MinIO Active-Active Site Replication | 🔴 Planned |
| **Network Failover:** Multi-Region LLM Tunneling (Auto-switch VLESS/Shadowsocks) | 🔴 Planned |
| **Host Redundancy:** ESXi VM Fault Tolerance (FT) or continuous VCSA replication | 🔴 Planned |

---

## Infrastructure

| Component | Technology | Version |
|-----------|-----------|---------|
| Compute | Intel Xeon E5-2680 v3, 64GB RAM | — |
| Virtualization | VMware ESXi 7.0 | On-Premise |
| Storage | 90TB+ LVM (hot-resize) | — |
| Containers | Docker + Docker Compose | — |
| API Gateway | FastAPI + Uvicorn (4 workers) | Python 3.12 |
| LLM Proxy | LiteLLM | Latest |
| Vector DB | Qdrant + FastEmbed | bge-small-en-v1.5 |
| Relational DB | PostgreSQL + asyncpg | — |
| Object Storage | MinIO (S3-compatible) | — |
| Extension | Chrome MV3 (ES Modules) | v2.1.0 |
| Safari Distribution | Orion Browser (WebKit + Chrome Extensions) | kagi.com/orion |
| Dashboard | Vanilla HTML/JS SPA (no framework, no build step) | v2.2.0 |
| ESXi Lessons | No snapshots on QEMU VMs; blkio limits mandatory; `restart: "no"` for heavy containers | — |
