# ntfy: Production Setup Guide — Self-Hosted + External Delivery

> Дата: 2026-04-04 | Project DNA | G12-alerts  
> Статус: ✅ Production

---

## Проблема, которую решаем

ntfy self-hosted работает отлично — пока ты в домашней сети.  
Как только телефон уходит в мобильную сеть — уведомления перестают приходить.  
Потому что ntfy app держит **постоянное SSE/WebSocket соединение** с сервером,  
а `http://192.168.x.x:9080` недоступен из интернета.

```
✅ Телефон (Wi-Fi дома) → 172.25.9.33:9080 → ntfy → push
❌ Телефон (4G/5G)      → 172.25.9.33:9080 → НЕДОСТУПЕН
```

---

## Матрица решений

| Вариант | Доступность | Батарея | Безопасность | Сложность |
|---------|-------------|---------|--------------|-----------|
| **ntfy.sh relay** ← выбрано | ✅ везде | ✅ нет влияния | ✅ приемлемо | ⭐ |
| Tailscale VPN | ✅ везде | ⚠️ постоянный VPN | ⚠️ прямой доступ в сеть | ⭐⭐ |
| Cloudflare Tunnel | ✅ везде | ✅ нет влияния | ✅ хорошо | ⭐⭐⭐ |
| Port forwarding | ✅ везде | ✅ нет влияния | ⚠️ открытый порт | ⭐⭐ |
| Без self-hosted | ✅ везде | ✅ нет влияния | ⚠️ всё через ntfy.sh | ⭐ |

### Почему Tailscale не подошёл:
1. **Батарея:** WireGuard процесс работает постоянно в фоне
2. **Безопасность:** телефон получает прямой туннель в домашнюю сеть  
   — при потере/взломе телефона вся инфраструктура под угрозой
3. **Избыточность:** для push-нотификаций это overkill

### Почему ntfy.sh — наименьшее зло:
- ntfy.sh видит только: **тему** + **текст алёрта** + **IP сервера**
- Текст алёрта — технический ("PostgreSQL sync failed"), не чувствительный
- Тема (`dna-alerts-igorvl777`) не идентифицирует личность
- Компромисс: **низкая чувствительность данных vs. удобство**

---

## Финальная архитектура

```
┌─────────────────────────────────────────────────────────┐
│                  Ubuntu Server (172.25.9.33)             │
│                                                          │
│  scripts (хост)                                          │
│  sync_to_nas.sh ──────────────────────────────────┐      │
│  healthcheck_nas.sh ──────────────────────────────┤      │
│                                                   │      │
│  Docker Network                                   │      │
│  ┌─────────────────┐                              │      │
│  │  Grafana :3030  │                              ▼      │
│  │  Contact Point  │──→ ntfy:80 ──→ upstream ──→ ntfy.sh │
│  └─────────────────┘   (Docker)    forward     (https)   │
└─────────────────────────────────────────────────────────┘
                                           │
                                           ▼
                                    📱 Телефон
                                    (LAN + 4G/5G)
```

**Правило:** 
- Скрипты на хосте → напрямую в `https://ntfy.sh/`
- Сервисы внутри Docker → в локальный `ntfy:80` → он проксирует → `ntfy.sh`

---

## Пошаговая установка

### Шаг 1: ntfy в docker-compose.yml

```yaml
services:
  ntfy:
    image: binwiederhier/ntfy
    container_name: ntfy
    restart: unless-stopped
    # --upstream-base-url = ключевой параметр!
    # Все сообщения автоматически пересылаются на ntfy.sh
    command: serve --cache-file /var/cache/ntfy/cache.db --upstream-base-url https://ntfy.sh
    ports:
      - "9080:80"       # локальный доступ в LAN
    volumes:
      - ntfy_cache:/var/cache/ntfy
    networks:
      - ai-net          # одна сеть с Grafana!
    healthcheck:
      test: ["CMD-SHELL", "wget -q --tries=1 http://localhost:80/v1/health -O - || exit 1"]
      interval: 60s
      timeout: 10s
      retries: 3

volumes:
  ntfy_cache:     # ← не забыть добавить в секцию volumes!
```

```bash
# Запуск
docker compose up -d ntfy

# Проверка здоровья
curl http://localhost:9080/v1/health
# Ожидаем: {"healthy":true}
```

### Шаг 2: Настройка .env

```bash
# В deploy/.env добавить:
NTFY_TOPIC=dna-alerts-igorvl777    # имя топика (уникальная строка)
# NTFY_URL не нужна отдельно — скрипты используют https://ntfy.sh напрямую
```

### Шаг 3: Функция notify в скриптах

```bash
# Скрипты на ХОСТЕ → ntfy.sh напрямую (не через Docker)
notify() {
    local title="$1"
    local msg="$2"
    local priority="${3:-default}"
    local tags="${4:-floppy_disk}"

    curl -s --max-time 8 \
        -H "Title: $title" \
        -H "Priority: $priority" \
        -H "Tags: $tags" \
        -d "$msg" \
        "https://ntfy.sh/$NTFY_TOPIC" > /dev/null || true
        # ^ || true важно: не ломаем скрипт если ntfy.sh недоступен!
}

# Вызов при ошибке:
notify "❌ Sync FAILED" "PostgreSQL backup failed. $(date '+%d.%m %H:%M')" "urgent" "rotating_light"

# Вызов при успехе (только раз в сутки в 02:00 — антиспам):
if [ "$(date +%H)" = "02" ]; then
    notify "✅ DNA Sync OK" "Ежедневный отчёт: всё синхронизировано" "low" "white_check_mark"
fi
```

### Шаг 4: Grafana Contact Point

В Grafana UI (http://server:3030):
1. **Alerting → Contact Points → + Add contact point**
2. Заполняем:
   ```
   Name:    ntfy
   Type:    Webhook
   URL:     http://ntfy:80/dna-alerts-igorvl777
              ^^^^^
              Docker internal hostname! (не localhost, не IP)
   Method:  POST
   ```
3. **Optional HTTP headers:**
   ```
   Title:    Grafana Alert
   Priority: high
   Tags:     warning,grafana
   ```
4. **Test** → сообщение должно прийти через цепочку:  
   `Grafana → ntfy контейнер → upstream → ntfy.sh → телефон`

> **Почему Grafana title/message работают с ntfy без адаптера:**  
> Grafana webhook payload содержит поля `title` и `message` в корне JSON.  
> ntfy при получении JSON ищет именно эти поля — идеальное совпадение,  
> никакого промежуточного кода не нужно!

### Шаг 5: Настройка телефона

**Установка:**
- Android: [Google Play — ntfy](https://play.google.com/store/apps/details?id=io.hnuma.ntfy)
- iOS: [App Store — ntfy](https://apps.apple.com/app/ntfy/id1625396347)

**Подписка:**
1. Открыть ntfy app
2. `+` → Subscribe to topic
3. Server: **оставить ntfy.sh** (https://ntfy.sh) — не менять на локальный!
4. Topic: `dna-alerts-igorvl777`
5. Готово ✅

> Телефон подписан на **ntfy.sh**, а не на домашний сервер.  
> Поэтому работает в любой сети — Wi-Fi, 4G, 5G, роуминг.

---

## Проверка всей цепочки

```bash
# 1. Тест: скрипт → ntfy.sh → телефон
curl -s -H "Title: 🧪 Test from script" \
     -H "Priority: high" \
     -H "Tags: test_tube" \
     -d "Тест прямой отправки через ntfy.sh" \
     https://ntfy.sh/dna-alerts-igorvl777
# Через 1-2 сек должен прийти push на телефон

# 2. Тест: локальный ntfy → upstream → ntfy.sh → телефон
curl -s -H "Title: 🧪 Test via local ntfy" \
     -d "Тест через upstream forwarding" \
     http://localhost:9080/dna-alerts-igorvl777
# Тоже должен прийти push (может быть небольшая задержка ~2-3 сек)

# 3. Проверка что Telegram заблокирован (для истории):
timeout 5 curl -s --max-time 5 https://api.telegram.org \
  && echo "✅ Telegram доступен" || echo "❌ Telegram заблокирован (РКН?)"
```

---

## Антиспам паттерны

```bash
# Паттерн 1: Ежедневный summary вместо постоянных OK
if [ "$(date +%H)" = "02" ]; then  # только в 02:00
    notify "✅ Daily OK" "Всё работает" "low"
fi

# Паттерн 2: Lock-файл (антиспам для healthcheck)
ALERT_LOCK="/tmp/nas_down_alerted"

send_once_per_hour() {
    local msg="$1"
    if [ ! -f "$ALERT_LOCK" ] || \
       [ $(($(date +%s) - $(stat -c %Y "$ALERT_LOCK" 2>/dev/null || echo 0))) -gt 3600 ]; then
        touch "$ALERT_LOCK"
        notify "⚠️ DOWN" "$msg" "urgent"
    fi
}

# Очистка когда recovered:
rm -f "$ALERT_LOCK"
notify "✅ RECOVERED" "Сервис восстановлен" "default"
```

---

## Приоритеты и тэги — шпаргалка

```bash
# Priority
-H "Priority: min"      # тихо, без вибрации
-H "Priority: low"      # без вибрации
-H "Priority: default"  # стандартное уведомление
-H "Priority: high"     # с вибрацией
-H "Priority: urgent"   # максимум, прорывается через DND

# Популярные Tags (emoji)
white_check_mark   → ✅   rotating_light → 🚨
warning            → ⚠️   computer       → 💻
floppy_disk        → 💾   test_tube      → 🧪
robot              → 🤖   fire           → 🔥
```

---

## Известные проблемы и решения

| Проблема | Причина | Решение |
|----------|---------|---------|
| Push не приходит вне LAN | Подписан на локальный сервер | Подписаться на `ntfy.sh`, не на `172.25.x.x` |
| Grafana webhook не работает | Неверный URL | Использовать `http://ntfy:80/...` (Docker hostname), не `localhost` |
| curl зависает 3-5 мин | РКН блокирует Telegram API | Это нормально, Telegram заблокирован. Используем ntfy.sh |
| `syntax error near unexpected token ')'` | `source <(...)` на .env со спецсимволами | Читать через `grep "^VAR=" .env \| cut -d= -f2-` |
| ntfy в docker-compose не запускается | Блок добавлен в `volumes:` вместо `services:` | Проверить уровень вложенности YAML |

---

## Итог — файлы проекта

```
deploy/docker-compose.yml     ← ntfy сервис с --upstream-base-url
deploy/.env                   ← NTFY_TOPIC=dna-alerts-igorvl777
scripts/sync_to_nas.sh        ← notify() → https://ntfy.sh напрямую
scripts/healthcheck_nas.sh    ← healthcheck + антиспам lock
```

---

## ⚠️ Правило для будущих self-hosted сервисов

> **Перед установкой любого self-hosted сервиса с мобильным клиентом —  
> первый вопрос: "Как работает вне домашней сети?"**  
> Если нет ответа → остаёмся на облачном сервисе или добавляем публичный доступ.
