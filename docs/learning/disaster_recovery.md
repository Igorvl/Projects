# Disaster Recovery & System Redundancy (Goal 9 + Goal 12)

> **Дата:** 2026-03-29  
> **Место в стеке MLOps:** Инфраструктура / Disaster Recovery (DR)  
> **Уровень:** Advanced  

---

## 🧐 Архитектурная идея: "Бессерверная" база как идеальный Backup-Target

У нас есть **XPenology** в той же LAN (свитч 1 Гбит/с) с большим объемом дисков и поддержкой Docker.
Отличное железо для резервных копий! Даже со слабым CPU XPenology идеально подходит для роли **"Пассивного хранилища объектов" (S3 / NFS)**. 

### Стратегия бэкапа (Push-модель)
Раз в сутки (или чаще) боевой сервер ESXi будет:
1. Делать "горячий" дамп базы PostgreSQL (`pg_dump`).
2. Создавать snapshot базы Qdrant (через API: `POST /collections/{name}/snapshots`).
3. Собирать все медиафайлы MinIO (или зеркалировать их через утилиту `mc`).
4. Упаковывать всё это в единый `tar.gz` архив и отправлять на XPenology.

### Как перекидывать файлы на XPenology?
Так как там крутится Docker, у нас есть 3 роскошных варианта (не требующих мощного CPU):
1. **MinIO Server (Рекомендуется):** Поднять на XPenology второй инстанс MinIO. Тогда наша Ubuntu будет пушить бэкапы по S3-протоколу (магически удобно и надежно).
2. **NFS Share:** Расшарить папку на XPenology и примонтировать её в Ubuntu. Бэкап будет писаться "как на локальный диск".
3. **SSH / SCP:** Настроить ключи и кидать архив по SSH (RSYNC). Самый простой, но медленный способ.

---

## 🛠 План на сегодня: 3 шага к DR (Disaster Recovery)

Перед тем как гнаться за высокой доступностью (Goal 12), мы обязаны научиться **восстанавливать систему из пепла** на том же самом оборудовании (Testing Recovery).

### Шаг 1: Написать скрипт бэкапа (`backup.sh`)
Скрипт будет:
- Делать `pg_dump` Postgres.
- Архиватором паковать конфигурацию (папка с `docker-compose.yml`, `.env`).
- Делать копию папки данных MinIO (если она примонтирована на хост).
- Складывать всё в папку `/opt/backups/`.

### Шаг 2: Симуляция катастрофы (Disaster Simulation)
Мы специально:
1. Запустим скрипт `backup.sh`.
2. Остановим Docker-контейнеры.
3. **Беспощадно удалим** папки (volumes) с базой данных Postgres и MinIO `rm -rf /var/lib/postgresql/data`.
4. Запустим систему пустой (чтобы убедиться, что все проекты и генерации исчезли).

### Шаг 3: Написать и выполнить `restore.sh`
Скрипт возьмет наш архив из `/opt/backups/`, развернет файлы по местам и выполнит `pg_restore`.
Если после этого дашборд откроется и все проекты будут на месте — тест пройден! Мы сможем настроить автоматическую отправку архивов на XPenology (Cron) и перейти к оттачиванию Goal 0 - Goal 11.

---

## 💼 Ценность для резюме (Disaster Recovery)

**Formulation:**
*   **Disaster Recovery & Business Continuity:** Engineered a zero-downtime backup and recovery pipeline for a highly-available MLOps ecosystem. Integrated automated S3-based (MinIO) and Postgres (`pg_dump`) logical backups with off-site retention to a secondary NAS. Successfully mandated and executed GameDay recovery drills (simulated complete data loss and restore) directly on production metadata, proving RTO/RPO objectives.*
