# Docker Registry & Warm Standby (High Availability)

> **Контекст:** G12 — Развёртывание зеркальной инфраструктуры Project DNA на Synology NAS RS4021xs+.

---

## 1. Типы HA-архитектур: выбор правильного подхода

| Тип | Как | Переключение | Риск | Когда |
|-----|-----|-------------|------|-------|
| **Hot Standby** | Оба узла активны, трафик балансируется | Автоматически, мгновенно | Data Split-Brain (оба пишут) | Критично для uptime, ~$$$  |
| **Warm Standby** | Зеркало поднято, но не принимает трафик | Вручную (один скрипт) | Минимальный | SMB/HomeOps — наш выбор ✅ |
| **Cold Standby** | Зеркало выключено, запускается только при аварии | Вручную, долго | RTO > 30 мин | Бюджетный DR |

**Почему Warm, а не Hot для Project DNA:**
- Нет корпоративного load balancer
- Одновременная запись в PostgreSQL/Qdrant → `Data Split-Brain` (данные рассинхронизируются навсегда)
- Warm Standby: зеркало idle, включается только командой `failover.sh` когда primary мёртв

---

## 2. Private Docker Registry (registry:2)

### Зачем свой registry?

```
Docker Hub (публичный)   — медленно, данные в облаке, зависимость от сети
docker save | ssh        — 13GB файл каждый раз при обновлении (10-30 мин)
Local Registry (:5000)   — быстро по LAN, полный контроль, бесплатно ✅
```

### Запуск registry на Ubuntu:

```bash
docker run -d \
  --name local-registry \
  --restart=unless-stopped \
  -p 5000:5000 \
  -v registry_data:/var/lib/registry \
  registry:2

# Проверка
curl http://localhost:5000/v2/_catalog
# {"repositories":[]}
```

### Ключевой трюк: localhost vs IP

Docker по умолчанию требует HTTPS для registry **кроме localhost** (hardcoded исключение):

```
localhost:5000  → ВСЕГДА доверенный (HTTP), без изменений daemon.json
172.25.9.33:5000 → НЕ доверенный → нужен insecure-registries
```

**Пуш с Ubuntu (без изменений daemon.json и перезапуска!):**
```bash
# Тег через localhost (не IP)
docker tag my-image:latest localhost:5000/my-image:latest
# Пуш — Docker не проверяет TLS для localhost
docker push localhost:5000/my-image:latest
```

**Pull на NAS (только NAS нужна конфигурация):**
```bash
# /var/packages/Docker/etc/dockerd.json на Synology
{
  "insecure-registries": ["172.25.9.33:5000"]
}
# Рестарт Docker через веб-консоль DSM (не systemctl!)
```

---

## 3. Docker Network Aliases — прозрачное зеркалирование

**Проблема:** router.py обращается к сервисам по именам (`ai-minio`, `ai-postgres`). В mirror-стеке сервисы называются `ai-minio-mirror`, `ai-postgres-mirror`. Менять код нельзя.

**Решение: Network Aliases** — контейнер отвечает на несколько DNS-имён в рамках одной Docker-сети:

```yaml
# docker-compose.mirror.yml
services:
  minio-mirror:
    image: minio/minio:latest
    networks:
      mirror-net:
        aliases:
          - ai-minio     # ← router.py резолвит это имя и попадает сюда

  postgres-mirror:
    image: postgres:15-alpine
    networks:
      mirror-net:
        aliases:
          - ai-postgres  # ← то же самое

  qdrant-mirror:
    networks:
      mirror-net:
        aliases:
          - ai-qdrant

networks:
  mirror-net:
    driver: bridge
```

**Результат:** `router.py` не изменён ни на строчку. При failover на NAS он «думает» что работает с теми же сервисами.

---

## 4. NAS-специфика (Synology Docker package)

### docker compose vs docker-compose

Synology Docker package (v20.10.x) поставляется БЕЗ compose-plugin (V2):

```bash
docker compose -f ...    # ❌ unknown shorthand flag: 'f'
docker-compose -f ...    # ✅ работает (нужно установить отдельно)
```

Установка docker-compose standalone:
```bash
sudo curl -L \
  "https://github.com/docker/compose/releases/download/v2.24.7/docker-compose-linux-x86_64" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Порты занятые DSM:
- `:80` → DSM Web UI (HTTP)
- `:443` → DSM Web UI (HTTPS)
- `:5000` → DSM QuickConnect

Nginx для зеркала → `:8080`

### Перезапуск Docker на Synology:
```bash
# НЕ работает:
sudo systemctl restart Docker.service  # unit not found

# Работает:
# Веб-консоль DSM → Package Center → Docker → Stop/Start
```

---

## 5. sudo по SSH без TTY

**Проблема:** `ssh user@host "sudo docker ..."` падает с:
```
sudo: a terminal is required to read the password
```

**Решения:**

```bash
# 1. Аллоцировать TTY (-t флаг):
ssh -t adminDS@172.25.9.147 "sudo docker ps"

# 2. Разрешить конкретную команду без пароля (sudoers):
echo "adminDS ALL=(ALL) NOPASSWD: /usr/bin/docker" \
  | sudo tee /etc/sudoers.d/docker-nopasswd

# 3. Двухшаговый подход (копируем файл, потом запускаем интерактивно):
cat file | ssh user@host "cat > /remote/path/file"  # без sudo
# Потом на NAS напрямую:
sudo docker exec ...  # интерактивно, sudo спрашивает пароль нормально
```

---

## 6. pg_dump — частые ошибки

### `$VAR` пустой на хост-шелле:
```bash
# ❌ Неправильно — $PG_USER пустой в хост-оболочке:
docker exec ai-postgres pg_dump -U $PG_USER project_dna

# ✅ Правильно — выполнить внутри контейнера где POSTGRES_USER установлен:
docker exec ai-postgres bash -c 'pg_dump -U $POSTGRES_USER --schema-only $POSTGRES_DB' \
  > /tmp/schema.sql
```

### Права при `sudo docker exec ... psql`:
```bash
# ❌ sudo запускает psql от root → PostgreSQL ищет роль "root":
sudo docker exec -i ai-postgres-mirror psql -d project_dna < schema.sql
# FATAL: role "root" does not exist

# ✅ Явно указывать -U:
sudo docker exec -i ai-postgres-mirror psql -U igorvl -d project_dna < schema.sql
```

### Узнать POSTGRES_USER из контейнера:
```bash
docker exec ai-postgres env | grep POSTGRES_USER
# или изнутри:
docker exec ai-postgres bash -c 'echo $POSTGRES_USER'
```

---

## 7. env_file vs --env-file в Docker Compose

```yaml
# Это попадает только В КОНТЕЙНЕР (runtime env):
services:
  app:
    env_file: .env.mirror

# Это ТАКЖЕ используется для ${VAR} подстановки в самом compose.yml:
# docker-compose --env-file .env.mirror -f compose.yml up
```

| Режим | Когда работает |
|-------|---------------|
| `.env` (авто) | Compose ищет `.env` в текущей папке — для `${VAR}` в compose.yml |
| `env_file: file` | Только для передачи vars В контейнер |
| `--env-file file` | И для `${VAR}` в compose.yml, И в контейнер |

**Правило:** Если `${VAR}` в compose.yml выдаёт WARN — нужен `--env-file`.

---

## 8. Финальная архитектура G12 (Что работает)

```
Ubuntu 172.25.9.33 (PRIMARY — ACTIVE)
├── local-registry    :5000   → хранит Docker образы
├── ai-router         :8000
├── ai-postgres       :5432
├── ai-qdrant         :6333
├── ai-minio          :9000
└── nginx             :443

NAS 172.25.9.147 (MIRROR — WARM/IDLE)
├── ai-router-mirror  :8000   (alias: —)
├── ai-postgres-mirror:5433   (alias: ai-postgres)
├── ai-qdrant-mirror  :6334   (alias: ai-qdrant)
├── ai-minio-mirror   :9002   (alias: ai-minio)
└── nginx-mirror      :8080

Failover: ./failover.sh → проверяет primary → up -d → curl /health
```

**Health check результат:** `{"status":"connected","projects_count":0}` ✅
