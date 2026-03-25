# 🏗️ Project DNA — Полная Архитектура Системы

## Обзор
Project DNA — enterprise-система управления AI-пайплайнами для графического дизайнера.
"Бесконечная память" + автоматическое управление лимитами LLM.

## Архитектурная схема (5 слоёв):

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: Frontend                         │
│              Open WebUI (PWA) + Safari Extension             │
│              Dashboard (Web UI для проектов)                 │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP API
┌─────────────────────────▼───────────────────────────────────┐
│                Layer 4: LLM Gateway                         │
│            AI-Router (FastAPI + LiteLLM + Uvicorn)          │
│                                                              │
│  Эндпоинты:                                                 │
│  POST /v1/dna/capture     — записать генерацию              │
│  POST /v1/dna/search      — семантический поиск             │
│  POST /v1/dna/upload/{s}  — загрузить файл (MinIO)          │
│  GET  /v1/dna/context/{s} — полный 3-уровневый контекст     │
│  GET  /v1/dna/files/{s}   — файлы проекта                   │
│  GET  /v1/dna/projects    — список проектов                 │
│  POST /v1/chat/completions— LLM gateway (Gemini/DeepSeek)   │
│                                                              │
│  Модули:                                                     │
│  router.py         — LLM маршрутизация, TTS, Circuit Breaker│
│  api_dna.py        — REST API для Project DNA               │
│  db.py             — PostgreSQL менеджер (asyncpg)           │
│  qdrant_db.py      — Qdrant векторный менеджер (fastembed)   │
│  minio_storage.py  — MinIO файловый менеджер                │
│  auto_summarize.py — авто-сжатие контекста через LLM        │
└────────┬──────────────┬──────────────┬──────────────────────┘
         │              │              │
┌────────▼────┐  ┌──────▼──────┐  ┌───▼──────────┐
│ Layer 3a:   │  │ Layer 3b:   │  │ Layer 3c:    │
│ PostgreSQL  │  │ Qdrant      │  │ MinIO        │
│             │  │             │  │              │
│ Текстовые   │  │ Векторные   │  │ Бинарные     │
│ данные:     │  │ данные:     │  │ файлы:       │
│ - проекты   │  │ - embeddings│  │ - изображения│
│ - промпты   │  │ - семант.   │  │ - аудиокниги │
│ - контексты │  │   поиск     │  │ - артефакты  │
│ - аккаунты  │  │             │  │              │
└─────────────┘  └─────────────┘  └──────────────┘

Внешние LLM провайдеры:
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Google Gemini│ │ SiliconFlow  │ │ Sber Cloud   │
│ (3 ключа)   │ │ (DeepSeek,   │ │ (SaluteSpeech│
│ Flash/Pro   │ │  Qwen, GLM)  │ │  TTS)        │
└──────────────┘ └──────────────┘ └──────────────┘

TTS Pipeline (4 движка):
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Chatterbox   │ │ Kokoro       │ │ SaluteSpeech │ │ Silero v5    │
│ EN Premium   │ │ EN Fast      │ │ RU Cloud     │ │ RU Local     │
│ ★10/10      │ │ ★7/10       │ │ ★8/10       │ │ ★5/10       │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

## Потоки данных (Data Flows):

### Flow 1: Захват генерации (Capture)
```
Дизайнер → Safari Extension → POST /v1/dna/capture
  → PostgreSQL (текст промпта, параметры, seed)
  → Qdrant (вектор промпта для семантического поиска)
  → Auto-Summarize (фоновое сжатие контекста через LLM)
```

### Flow 2: Семантический поиск (Search)
```
Дизайнер набирает "dark sci-fi dashboard"
  → POST /v1/dna/search
  → Qdrant: fastembed переводит текст в вектор
  → Qdrant: cosine similarity поиск
  → Результат: "futuristic UI interface, neon green..." (score: 0.81)
```

### Flow 3: Контекст проекта (DNA Assembly)
```
GET /v1/dna/context/my-project
  → PostgreSQL: core_dna (конституция проекта)
  → PostgreSQL: strategic_context (последнее стратегическое сжатие)
  → PostgreSQL: tactical_context (последнее тактическое сжатие)
  → JSON ответ с 3 уровнями контекста для LLM injection
```

## Docker Compose сервисы:
| Сервис | Контейнер | Порты | Назначение |
|--------|-----------|-------|------------|
| llm-router | ai-router | 8000 | API Gateway + LLM Router |
| postgres | ai-postgres | 5432 | Реляционная БД |
| qdrant | ai-qdrant | 6333 | Векторная БД |
| minio | ai-minio | 9000, 9001 | Объектное хранилище |
| tts-chatterbox | tts-chatterbox | 4123 | TTS (EN Premium) |
| tts-sovits | tts-sovits | 9880 | TTS (SoVITS) |
| audio-host | ai-audio-host | 8001 | Статика для аудио |
| open-webui | open-webui | 3000 | Фронтенд (PWA) |

## Технологический стек:
- **Язык:** Python 3.12
- **Фреймворк:** FastAPI + Uvicorn (4 workers)
- **ORM/DB:** asyncpg (async PostgreSQL driver)
- **Вектора:** qdrant-client + fastembed (BAAI/bge-small-en-v1.5)
- **Файлы:** minio (S3-compatible object storage)
- **LLM:** litellm (unified API for multiple LLM providers)
- **TTS:** Chatterbox, Kokoro, SaluteSpeech, Silero
- **Контейнеризация:** Docker + Docker Compose
- **CI/CD:** GitHub Actions (planned)
