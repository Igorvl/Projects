# Вводный контекст для ИИ-Ассистента (Project DNA)

Привет! Я — Игорь, мы разрабатываем **Project DNA** (систему управления знаниями и RAG-окружение для работы с LLM). Ниже приведен полный слепок нашего текущего состояния, чтобы ты сразу влился в работу без лишних вопросов. Ознакомься со сводкой и жди моей первой команды.

---

## 📡 1. Snapshot состояния (Где мы сейчас)
- **✅ G12 ЗАКРЫТ:** Warm Standby Mirror на NAS RS4021xs+ (`172.25.9.147`) работает. `curl http://172.25.9.147:8000/v1/dna/health` → `{"status":"connected"}`.
- **Текущая задача:** G12-next — автоматическая синхронизация данных (pg_dump rsync + qdrant snapshots + minio sync) и G12-slim (Dockerfile без TTS-моделей, 13GB → ~800MB).
- **Инфраструктура:** Ubuntu Primary (`172.25.9.33`) + NAS Mirror (`172.25.9.147`). Local Docker Registry на Ubuntu `:5000`. Образ `ai-router` (13GB) доставлен по LAN.

## 📝 2. Последние 5 изменений в коде/архитектуре
1. **G12 Mirror Stack** (`deploy/docker-compose.mirror.yml`): 5-сервисный стек на NAS (LLM Router + PostgreSQL + Qdrant + MinIO + Nginx `:8080`). Network aliases для прозрачности имён: `ai-minio-mirror` отвечает на `ai-minio` → код роутера не менялся.
2. **Local Docker Registry** (`registry:2` на Ubuntu `:5000`): push через `localhost:5000` (без перезапуска Docker!), pull на NAS через IP.
3. **One-click Failover** (`scripts/failover.sh`): проверяет что primary мёртв → поднимает mirror → ждёт health → инструктирует обновить Open WebUI.
4. **Key Pool Bug Fix** (предыдущая сессия): `docker-compose.yml` переключён с явного `environment:` на `env_file: .env` → все 6 Gemini-ключей загружаются автоматически.
5. **MidStreamFallbackError Fix** (предыдущая сессия): pre-fetch первого SSE-чанка перемещён ВНУТРЬ `call_with_key_rotation` через `_prepend_chunk()` helper → 429 теперь вызывают key rotation, а не model fallback.

## 🐛 3. Подвешенные задачи и Баги (Backlog)
- **G12-next (Active):** rsync cron для синхронизации `pg_dump` + qdrant snapshots + minio data → NAS.
- **G12-slim:** `Dockerfile.router-mirror` без TTS-моделей (13GB → ~800MB). Ускорит обновления зеркала.
- **G12-alerts:** healthcheck watcher на Ubuntu → Telegram/webhook при падении primary.
- **MinIO:** Удалить битые файлы из папки `test-project/` (Ghost-файлы).
- **Frontend Refactoring:** Вынести копипасту логики `uploadImages()` в shared-функцию (v3.0.0).
- **G11:** Antigravity Context Integration.

## 📐 4. Гайдлайны и Ключевые Решения (Отвергнутые варианты)
- ❌ **НЕТ Auto-Failover кластерам (VRRP/Keepalived/Swarm):** Умышленно отказались от автоматического балансировщика. Data Split-Brain недопустим. Только Warm Standby — ручное включение через `failover.sh`.
- ❌ **НЕТ дублированию бэкапов SQL по сети:** ABB бэкапит Ubuntu-ВМ целиком. Ручной rsync только для media/vectors.
- ✅ **API Gateway Pattern:** `router.py` работает через LiteLLM. Все модели через `antigravity.json`. Никаких жёстких привязок к вендорам в коде.
- ✅ **Network Aliases Pattern:** Зеркальные сервисы получают aliases с оригинальными именами → код приложения не меняется при failover.
- ✅ **Резюме-Ориентированность:** При каждом крупном внедрении — фиксировать в `RESUME_BULLETS.md`.

## 🖥️ 5. Топология инфраструктуры
```
Ubuntu 172.25.9.33 (PRIMARY)     NAS 172.25.9.147 (MIRROR — WARM)
├── local-registry  :5000        ├── ai-router-mirror  :8000
├── ai-router       :8000        ├── ai-postgres-mirror:5433 (alias: ai-postgres)
├── ai-postgres     :5432        ├── ai-qdrant-mirror  :6334 (alias: ai-qdrant)
├── ai-qdrant       :6333        ├── ai-minio-mirror   :9002 (alias: ai-minio)
├── ai-minio        :9000        └── nginx-mirror      :8080
└── nginx           :443
```

---
*Ожидаю готовности. Прочитай контекст, загрузи `project_dna_full_context.md` и `PRIVATE_CONTEXT.md`, и ответь одним предложением подтверждая понимание текущего статуса G12 и следующих задач.*


---

