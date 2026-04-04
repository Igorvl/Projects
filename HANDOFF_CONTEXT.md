# Вводный контекст для ИИ-Ассистента (Project DNA)

Привет! Я — Игорь, мы разрабатываем **Project DNA** (систему управления знаниями и RAG-окружение для работы с LLM). Ниже приведен полный слепок нашего текущего состояния, чтобы ты сразу влился в работу без лишних вопросов. Ознакомься со сводкой и жди моей первой команды.

---

## 📡 1. Snapshot состояния (Где мы сейчас, 2026-04-04)

- **✅ G12 ЗАКРЫТ:** Warm Standby Mirror на NAS RS4021xs+ (`172.25.9.147`) работает.
- **✅ G12-next ЗАКРЫТ:** `scripts/sync_to_nas.sh` — cron `0 */2 * * *`. Синхронизирует: PostgreSQL (pg_dump gz) + Qdrant (HTTP snapshots) + MinIO (mc mirror, 31 MiB/s). Первый запуск успешен: 140K + 593M + 369M + 135MB → NAS.
- ✅ **G12-alerts ЗАКРЫТ:** ntfy.sh push-уведомления работают. Grafana contact point настроен → уведомления приходят на телефон. Сырые JSON-алерты от Grafana переведены в человекочитаемый вид через n8n Webhook Bridge.
- **✅ Semantic Router:** переключён на `openrouter/qwen/qwen3.6-plus:free`. Gemini-квота на классификацию не тратится.
- **✅ Circuit Breaker v2:** 7 моделей в цепочке, двойное покрытие Qwen3 Coder 480B (OpenRouter + SiliconFlow).
- **Текущая задача:** G12-slim — `Dockerfile.router-mirror` без TTS-моделей (13GB → ~800MB).
- **Инфраструктура:** Ubuntu Primary (`172.25.9.33`) + NAS Mirror (`172.25.9.147`). Local Docker Registry на Ubuntu `:5000`.

## 📝 2. Последние изменения в коде/архитектуре (апрель 2026)

1. **sync_to_nas.sh** (`scripts/sync_to_nas.sh`): автоматическая синхронизация 3 слоёв данных → NAS каждые 2 часа. PostgreSQL `pg_dump` gz, Qdrant HTTP snapshots + rsync, MinIO `mc mirror`. ntfy.sh push при ошибке (urgent) и ежедневный ОК в 02:00.
2. **healthcheck_nas.sh** (`scripts/healthcheck_nas.sh`): cron `*/30 * * * *`. Проверка NAS-зеркала (ai-router, qdrant, minio), anti-spam lock 1 alert/час, автоматический RECOVERED alert.
3. **ntfy self-hosted** (`deploy/docker-compose.yml`): добавлен сервис `ntfy` (port 9080). Конфиг: `serve --base-url http://172.25.9.33:9080 --cache-file /var/cache/ntfy/cache.db --upstream-base-url https://ntfy.sh`. volume `ntfy_cache`. Upstream forwarding работает.
4. **Grafana contact point** (API provisioned): `ntfy-dna-alerts`, type=webhook, URL=`https://ntfy.sh/dna-alerts-igorvl777`. Grafana → ntfy.sh прямо (MinIO исключён). Работает, но сообщение — сырой JSON.
5. **ntfy.sh для скриптов**: хостовые скрипты пишут в `https://ntfy.sh/dna-alerts-igorvl777` напрямую. local ntfy используется только как relay для Grafana.
6. **NTFY_TOPIC** добавлен в `deploy/.env`.
7. **Grafana credentials**: `admin` / `K5/9E-3ZFGTB` (сменён через grafana-cli).

- ✅ **G12-slim ЗАКРЫТ:** Создан `Dockerfile.router-mirror` без тяжелых TTS-кэшей и PyTorch. Размер контейнера уменьшен с 13 ГБ до 1.6 ГБ (в пуле — меньше 400 МБ).
- **🆕 G13-llm-radar:** n8n workflow — ежедневный мониторинг новых бесплатных LLM моделей на OpenRouter/SiliconFlow/Groq. Фильтр: free + >30B params + известные org. Алёрт в ntfy. ~2-3ч работы.
- **MinIO:** Удалить битые файлы из папки `test-project/` (Ghost-файлы).
- **Frontend Refactoring:** Вынести копипасту логики `uploadImages()` в shared-функцию (v3.0.0).
- **G11:** Antigravity Context Integration.
- **Prometheus + Grafana docs:** Создать `docs/learning/prometheus_grafana.md` (planned).
- **Loki + Promtail** централизованный сбор логов (planned).

## 📐 4. Гайдлайны и Ключевые Решения

- ❌ **НЕТ Auto-Failover кластерам (VRRP/Keepalived/Swarm):** Data Split-Brain недопустим. Только Warm Standby — ручное включение через `failover.sh`.
- ❌ **НЕТ Tailscale для ntfy:** Батарея (постоянный VPN) + безопасность (прямой туннель в сеть с телефона). ntfy.sh — приемлемый компромисс приватности.
- ✅ **ntfy.sh для мобильных push:** телефон подписан на ntfy.sh, НЕ на локальный IP. Работает в любой сети (4G/5G/роуминг).
- ✅ **API Gateway Pattern:** Все модели через `antigravity.json`. Никаких жёстких привязок в коде.
- ✅ **Network Aliases Pattern:** Зеркальные сервисы получают aliases с оригинальными именами → код не меняется при failover.
- ✅ **Резюме-Ориентированность:** При каждом крупном внедрении — фиксировать в `RESUME_BULLETS.md`.
- ✅ **Правило cross-network доступа:** перед self-hosted с мобильным клиентом — всегда спрашивать "как работает вне домашней сети?" (задокументировано в MEMORY.md).

## 🖥️ 5. Топология инфраструктуры

```
Ubuntu 172.25.9.33 (PRIMARY)          NAS 172.25.9.147 (MIRROR — WARM)
├── local-registry  :5000              ├── ai-router-mirror  :8000
├── ai-router       :8000              ├── ai-postgres-mirror:5433 (alias: ai-postgres)
├── ai-postgres     :5432              ├── ai-qdrant-mirror  :6334 (alias: ai-qdrant)
├── ai-qdrant       :6333              ├── ai-minio-mirror   :9002 (alias: ai-minio)
├── ai-minio        :9000              └── nginx-mirror      :8080
├── nginx           :443
├── grafana         :3030
├── telegraf        (metrics)
├── n8n             :5678
├── ntfy            :9080  ← NEW
├── open-webui      :3000
└── tts services
```

## 📱 6. Мониторинг и Алёртинг

```
Хостовые скрипты → https://ntfy.sh/dna-alerts-igorvl777 → 📱 телефон
Grafana alerts   → https://ntfy.sh/dna-alerts-igorvl777 → 📱 телефон
local ntfy :9080 (relay, upstream → ntfy.sh, используется Grafana Docker-internally)

Тема ntfy: dna-alerts-igorvl777
Grafana CP UID: bfi0v1rcnao74c
```

## 📁 7. Ключевые файлы

```
deploy/docker-compose.yml        ← основной стек + ntfy сервис
deploy/.env                      ← все секреты (NTFY_TOPIC, NAS_*, GEMINI_*, и т.д.)
deploy/antigravity.json          ← Circuit Breaker v2 (7 моделей), горячая перезагрузка
routing/semantic_router.py       ← Semantic Router на Qwen3.6 (OpenRouter)
scripts/sync_to_nas.sh           ← cron 0 */2 * * * (pg+qdrant+minio → NAS)
scripts/healthcheck_nas.sh       ← cron */30 * * * * (NAS mirror health)
scripts/failover.sh              ← one-click failover на NAS mirror
docs/learning/ntfy_push_notifications.md  ← полная инструкция по ntfy setup
docs/RESUME_BULLETS.md           ← резюме-достижения
```

---
*Ожидаю готовности. Прочитай контекст, PRIVATE_CONTEXT.md, MEMORY.md и ответь одним предложением подтверждая понимание: какой статус G12-alerts и какая ближайшая нерешённая задача.*
