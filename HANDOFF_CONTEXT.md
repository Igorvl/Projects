# Вводный контекст для ИИ-Ассистента (Project DNA)

Привет! Я — Игорь, мы разрабатываем **Project DNA** (систему управления знаниями и RAG-окружение для работы с LLM). Ниже приведен полный слепок нашего текущего состояния, чтобы ты сразу влился в работу без лишних вопросов. Ознакомься со сводкой и жди моей первой команды.

---

## 📡 1. Snapshot состояния (Где мы сейчас, 2026-04-12)

- **✅ G12 ЗАКРЫТ:** Warm Standby Mirror на NAS RS4021xs+ (`172.25.9.147`) работает.
- **✅ G12-next ЗАКРЫТ:** `scripts/sync_to_nas.sh` — cron `0 */2 * * *`. PostgreSQL (pg_dump gz) + Qdrant (HTTP snapshots) + MinIO (mc mirror, 31 MiB/s).
- **✅ G12-alerts ЗАКРЫТ:** ntfy.sh push-уведомления работают. Grafana contact point настроен.
- **✅ Semantic Router:** работает на `openrouter/openai/gpt-oss-120b:free`.
- **✅ Circuit Breaker v3:** 8 моделей, все живые (8/8 OK — последний watchdog прогон).
- **✅ model_watchdog.py v2 СТАБИЛИЗИРОВАН:** Self-healing LLM gateway с умной аналитикой недоступности.
- **В Бэклоге:**
  - Автоматический бэкап Docker-вольюма `n8n_data` на NAS.
  - `docs/learning/prometheus_grafana.md`.
  - **G11:** Antigravity Context Integration (RAG).
  - Удалить битые файлы из MinIO `test-project/`.

## 📝 2. Последние изменения (2026-04-12)

### model_watchdog.py v2 — Smart Self-Healing

1. **Умная аналитика недоступности** — два режима замены:
   - `PERMANENT_DEATH`: ошибка содержит ключевые слова (`"deprecated"`, `"no longer free"`, `"provider returned error"` и др.) → замена немедленно
   - `CONSECUTIVE_FAILS_BEFORE_REPLACE = 3`: три последовательных провала cron → замена
   - Временные сбои (`RATE_LIMIT daily limit`, `TIMEOUT`, `ERROR`) → `WAIT N/3`, не заменяем
2. **`deploy/model_failures.json`** — история отказов сохраняется между запусками cron. OK/SLOW сбрасывают счётчик.
3. **httpx 0.28+ совместимость** — `proxies={}` → `**_CLIENT_KWARGS` (`proxy="url"`).
4. **`WATCHDOG_PROXY`** — все httpx-клиенты поддерживают прокси через `.env`. На сервере: `WATCHDOG_PROXY=http://127.0.0.1:10809`.
5. **Groq geo-block** — 403 обрабатывается тихо. Groq блокирует datacenter ASN на уровне TLS fingerprint (SSL_ERROR_SYSCALL). Пропускается без шума.
6. **SiliconFlow фильтр** расширен — Reranker, Embedding, Image-Edit, TTS убраны из кандидатов.
7. **ntfy вердикты** — `[⏳ 1/3]` или `[🔄 replace]` для каждой проблемной модели.

### Инфраструктура

- **Xray VPN на хосте перенастроен** — ранее хост подключался напрямую к финскому VDS (РКН блокировал). Добавлен Московский relay. Цепочка: `Хост → Москва (3X-UI VLESS) → Финляндия exit (79.110.48.133) → Интернет`. Конфиг: `/usr/local/etc/xray/config.json`.
- **antigravity.json обновлён:**
  - `GLM_5` → `GLM_5.1` (zai-org/GLM-5.1, SiliconFlow)
  - `deepseek-v3.2` восстановлен (был ошибочно заменён старым watchdog'ом) → `deepseek-ai/DeepSeek-V3.2` на SiliconFlow
  - Алиасы: `"GLM_5": "GLM_5.1"` для обратной совместимости

## 📐 3. Гайдлайны и Ключевые Решения

- ❌ **НЕТ Auto-Failover кластерам (VRRP/Keepalived/Swarm):** Data Split-Brain недопустим. Только Warm Standby — ручное включение через `failover.sh`.
- ❌ **НЕТ Tailscale для ntfy:** Батарея + безопасность. ntfy.sh — приемлемый компромисс.
- ✅ **ntfy.sh для мобильных push:** телефон подписан на ntfy.sh, НЕ на локальный IP.
- ✅ **API Gateway Pattern:** Все модели через `antigravity.json`. Никаких жёстких привязок в коде.
- ✅ **Watchdog = self-healing, не upgrade:** заменяет только сломанные модели, не обновляет версии автоматически.
- ✅ **Резюме-Ориентированность:** При каждом крупном внедрении — фиксировать в `RESUME_BULLETS.md`.
- ⚠️ **Groq недоступен с инфраструктуры:** finland VDS — datacenter ASN, Groq блокирует по TLS fingerprint. Через OpenRouter работает.
- ⚠️ **Репо на хосте отдельное** — синхронизация вручную через vim (не git pull). Учитывать при обновлениях скриптов.

## 🖥️ 4. Топология инфраструктуры

```
Ubuntu 172.25.9.33 (PRIMARY)          NAS 172.25.9.147 (MIRROR — WARM)
├── local-registry  :5000              ├── ai-router-mirror  :8000
├── ai-router       :8000              ├── ai-postgres-mirror:5433
├── ai-postgres     :5432              ├── ai-qdrant-mirror  :6334
├── ai-qdrant       :6333              ├── ai-minio-mirror   :9002
├── ai-minio        :9000              └── nginx-mirror      :8080
├── nginx           :443
├── grafana         :3030
├── n8n             :5678
├── ntfy            :9080
├── open-webui      :3000
├── xray (systemd)  :10808 socks5, :10809 http  ← VPN: Москва→Финляндия
└── tts services
```

## 📱 5. Мониторинг и Алёртинг

```
Хостовые скрипты → https://ntfy.sh/dna-alerts-igorvl777 → 📱 телефон
Grafana alerts   → https://ntfy.sh/dna-alerts-igorvl777 → 📱 телефон
model_watchdog   → https://ntfy.sh/dna-alerts-igorvl777 → 📱 телефон (cron каждые 6ч)
local ntfy :9080 (relay upstream → ntfy.sh)

Тема ntfy: dna-alerts-igorvl777
Grafana CP UID: bfi0v1rcnao74c
Grafana credentials: admin / K5/9E-3ZFGTB
```

## 📁 6. Ключевые файлы

```
deploy/docker-compose.yml        ← основной стек + ntfy сервис
deploy/.env                      ← секреты (WATCHDOG_PROXY, NTFY_TOPIC, GROQ_API_KEY, и т.д.)
deploy/antigravity.json          ← Circuit Breaker v3 (8 моделей + алиасы)
deploy/model_failures.json       ← история отказов watchdog (NEW)
scripts/model_watchdog.py        ← Self-Healing Gateway v2 (UPDATED)
scripts/sync_to_nas.sh           ← cron 0 */2 * * *
scripts/healthcheck_nas.sh       ← cron */30 * * * *
scripts/failover.sh              ← one-click failover на NAS mirror
routing/semantic_router.py       ← Semantic Router: gpt-oss-120b, ROUTING_FAILED_CACHE 5min TTL
/usr/local/etc/xray/config.json  ← Xray VPN: Хост→Москва relay→Финляндия exit
docs/RESUME_BULLETS.md           ← резюме-достижения
```

### ⏳ Current Working Status (2026-04-12):
- **✅ model_watchdog.py v2 (04-12-2026):** N consecutive fails до замены, PERMANENT_DEATH_KEYWORDS, model_failures.json, httpx 0.28+ compat, WATCHDOG_PROXY.
- **✅ Xray VPN Fix (04-12-2026):** Хост переключён на Москва→Финляндия. Весь watchdog-трафик через `http://127.0.0.1:10809`.
- **✅ antigravity.json Cleanup (04-12-2026):** GLM_5.1, deepseek-v3.2 восстановлен, алиасы.
- **⏸️ Groq:** datacenter ASN TLS block. Пропускается тихо. Через OpenRouter — ок.
- **⏸️ Gemini Discovery:** 400 на `/v1beta/models`. OpenRouter+SiliconFlow достаточно.

### ⏱ Next Steps:
1. Запустить `python3 scripts/model_watchdog.py --auto-replace` (боевой прогон после всех фиксов).
2. Настроить cron watchdog на сервере: `0 */6 * * * cd /home/igorvl/ai-design-workspace && python3 scripts/model_watchdog.py --auto-replace`.
3. Следующий приоритет: n8n_data бэкапы на NAS или G11 (Antigravity RAG).

---
*Ознакомься с контекстом и PRIVATE_CONTEXT.md. Подтверди одним предложением: статус watchdog и почему Groq недоступен.*
