# 🧬 Projects — Igor Viktorovich

> Personal R&D monorepo: MLOps infrastructure, AI integrations, browser extensions and web projects.

---

## 🚀 Active Projects (Production / In Development)

### 🧠 Project DNA — AI Knowledge Management System
**Stack:** `Python` `FastAPI` `PostgreSQL` `Qdrant` `MinIO` `Docker` `LiteLLM`

An intelligent middleware layer between LLM interfaces and vector databases.
Automatically captures, categorizes and stores AI-generated knowledge for RAG retrieval.

| Component | Description |
|---|---|
| [`routing/`](./routing/) | FastAPI API Gateway — LLM routing, key pool rotation, SSE streaming resilience, semantic auto-routing |
| [`dashboard/`](./dashboard/) | Admin SPA — project management, batch operations, DNA document editor, lightbox gallery |
| [`project-dna-extension/`](./project-dna-extension/) | Chrome Extension MV3 — intercepts Gemini / AI Studio / Open WebUI, sends captures to backend |
| [`scripts/`](./scripts/) | Backup & restore scripts — `backup.sh` / `restore.sh` with zero-downtime `pg_dump` |
| [`docs/`](./docs/) | Architecture decisions, learning notes, resume bullets |

**Key engineering achievements:**
- 🔄 **Vendor-agnostic LLM routing** with seamless fallback chain (Gemini → DeepSeek → Qwen) and API key pool rotation (6 keys)
- 🌊 **SSE streaming resilience** — pre-fetch first chunk inside key rotation loop prevents `400 TransferEncodingError` on dead-on-arrival providers
- 🧩 **Agentic Interceptor** — state machine over SSE streams that intercepts ambiguous intents and injects interactive prompts directly into Open WebUI
- ⚡ **Zero-latency semantic caching** — MD5 hash of root message caches project slug, 0ms on all subsequent turns
- 📦 **Enterprise DR pipeline** — `pg_dump` + volume tar + Synology Active Backup for Business (full VM incremental backup)

---

### 📊 Observability Stack
**Stack:** `Prometheus` `Grafana` `Telegraf` `Docker`

**Location:** [`observability/`](./observability/)

Infrastructure monitoring for the Docker-based MLOps stack.
Telegraf reads directly from `docker.sock` (bypassing cgroups v2 limitations that broke cAdvisor on Ubuntu 24.04).
Grafana dashboards visualize CPU/RAM/Network per container with SMTP alerting.

---

### 🌐 ksar.me Design Portfolio Site
**Stack:** `Next.js` `React` `CSS Modules`

**Location:** [`ksar.me/`](./ksar.me/)

Commercial portfolio site for a designer client. Built and maintained as a submodule.

---

## 📚 Learning Archive (Historical)

These folders contain coursework and training exercises. Kept for reference.

| Folder | Topic | Age |
|---|---|---|
| `barbershop/` `cat-energy/` `technomart/` | HTML/CSS layout practice (Pixel Perfect) | ~6 years |
| `Witcher/` `GLO_portfolio/` | JavaScript / animation projects | ~6 years |
| `AntD/` `components/` | React + Redux course (Samurai) | ~6 years |
| `*.ipynb` | ML/AI course notebooks (PyTorch, CNNs, time series) | ~3 years |

---

## 🛠 Tech Stack (Active)

```
Backend:    Python 3.12 · FastAPI · asyncpg · LiteLLM · aiohttp
Databases:  PostgreSQL · Qdrant (Vector DB) · MinIO (S3-compatible)
DevOps:     Docker Compose · Prometheus · Grafana · Telegraf
Platform:   VMware ESXi · Ubuntu 24.04 · XPenology NAS
Extensions: Chrome MV3 · Service Workers · WebSockets
LLMs:       Gemini 2.5 · DeepSeek V3 · Qwen · Silero TTS
```

---

## 📄 Documentation

- [`docs/RESUME_BULLETS.md`](./docs/RESUME_BULLETS.md) — Key engineering achievements formatted for CV
- [`docs/PROJECT_GOALS.md`](./docs/PROJECT_GOALS.md) — Roadmap and milestone tracker
- [`docs/learning/`](./docs/learning/) — Deep-dive technical notes on implemented technologies

---

*Built and maintained by Igor Viktorovich — Infrastructure & AI Integration Engineer*
