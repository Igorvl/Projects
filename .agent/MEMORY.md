# 🧠 AI INFRASTRUCTURE LAB — GLOBAL MEMORY

> ⚠️ **ОБЯЗАТЕЛЬНО К ПРОЧТЕНИЮ ПЕРЕД ЛЮБОЙ РАБОТОЙ!**
> Эти правила действуют ВСЕГДА. Без исключений.

---

## 🎯 ГЛАВНАЯ ЦЕЛЬ (PORTFOLIO)

**Всё, что мы делаем — это портфолио на GitHub.**

Каждый проект, каждый скрипт, каждая инфраструктурная задача должны быть:
1. **Задокументированы** (README, docs/, архитектурные схемы)
2. **На GitHub** с чистой историей коммитов
3. **Презентабельны** для рекрутера/техлида

### Целевые позиции (по приоритету):
1. 🥇 **MLOps Engineer** — предпочтительно
2. 🥈 **DevOps Engineer** — как вариант
3. 🥉 **SysAdmin** — крайний случай, для разгона в сторону Dev/ML-Ops

### Что ценится в портфолио:
- Docker, Docker Compose, оркестрация
- CI/CD (GitHub Actions)
- Мониторинг (Prometheus, Grafana)
- IaC (Ansible, Terraform)
- LLM/AI пайплайны — **главный дифференциатор!**
- RAG, Vector DB, embeddings
- API Gateway, маршрутизация, Circuit Breaker
- Безопасность (секреты, бэкапы, DR)
- Документация (Mermaid, README, Architecture Decision Records)

### Правило коммитов:
- Conventional Commits: `feat:`, `fix:`, `docs:`, `infra:`, `ci:`
- Развернутые описания (не "fix stuff")
- Каждый коммит = демонстрация компетенции

---

## 🏗️ ПРОЕКТ: AI Design Infrastructure Lab (Project DNA)

### Назначение
Enterprise-система управления ИИ-пайплайнами для графического дизайнера.
"Бесконечная память" + автоматическое управление лимитами LLM.

### Ключевые задачи:
1. Автоматическое логирование промптов и результатов генерации
2. Поддержание DNA проекта (стиль, контекст) на протяжении месяцев
3. Переиспользование истории для автоматизации новых проектов
4. Cross-account перенос контекста (одному проекту = несколько аккаунтов)

### Архитектура (5 Layers):
- **Layer 1:** Frontend — Open WebUI (PWA)
- **Layer 2:** RAG Engine — Custom (в роутере) + Safari Extension
- **Layer 3:** Storage — PostgreSQL + Qdrant + MinIO
- **Layer 4:** LLM Gateway — Custom Python Router (FastAPI + LiteLLM)
- **Layer 5:** Observability — Prometheus + Grafana (планируется)

### Инфраструктура:
- **Сервер:** Xeon E5-2680 v3, 64GB RAM, ESXi 7.0
- **OS:** Ubuntu 24.04 LTS
- **Сеть:** Split Tunneling (VLESS/Xray для Google, direct для SiliconFlow/Sber)

---

## 📋 ТЕКУЩИЙ БЭКЛОГ (RAG PIPELINE)

| # | Этап | Статус |
|---|------|--------|
| 1 | PostgreSQL: схема, миграции, API | ✅ |
| 2 | MinIO: поднять, API для изображений | ✅ |
| 3 | Qdrant: embeddings, семантический поиск | ✅ |
| 4 | Router API: /capture, /projects, /search, /dna | ✅ |
| 5 | Safari Web/Chrome Extension: перехват AI Studio | ✅ |
| 5.1 | Safari Web/Chrome Extension: перехват gemini.google.com | ✅ |
| 6 | Auto-Summarize: Dual context (Strategic 50 + Tactical 10) | ✅ |
| 7 | Dashboard: Web UI для просмотра проекта | ✅ |

---

## 🔧 РЕАЛИЗОВАННЫЕ КОМПОНЕНТЫ

### TTS Pipeline (4 движка):
| Движок | Язык | Качество | Статус |
|--------|------|----------|--------|
| SaluteSpeech (Sber Cloud) | RU | ★8/10 | ✅ |
| Silero v5 (Local CPU) | RU | ★5/10 | ✅ |
| Chatterbox (Premium) | EN | ★10/10 | ✅ |
| Kokoro (Fast) | EN | ★7/10 | ✅ |

### LLM Router:
- Circuit Breaker: Gemini → DeepSeek → Qwen → GLM
- Key Rotation (3 ключа Gemini)
- Audiobook Pipeline + ffmpeg speed control

---

## 🗣️ КОММУНИКАЦИЯ
- Общаемся на русском языке
- Комментарии в коде — на английском
- Быть честным и прямым
- Шутить можно, легкость приветствуется
- Предложения по улучшению приветствуются. Работай как незашоренный умудренный опытом программист-профессионал и не бойся предлагать свои решения.
- **ВСЕГДА подробно объяснять CLI-команды:** каждый флаг, ключ, pipe, что делает каждая часть команды. Пользователь набивает руку для MLOps — не просто копипастит, а учится понимать.
- **ВСЕГДА все объяснения подробно документируем в `~/ai-design-workspace/docs/learning/` для дальнейшего изучения и прокачки навыков пользователя. Роль делает это сама, не спрашивая разрешения, автоматически через `write_to_file`.

---

*Последнее обновление: 2026-03-12*
