# Project Memory & Critical Rules

## Deployment & Server Sync
- **CRITICAL**: Репозитории на сервере (Behance Scout) и на локальном ноутбуке **РАЗНЫЕ**.
- **НЕ ИСПОЛЬЗОВАТЬ `git pull`** для обновления кода на сервере напрямую из локального репозитория.
- **Метод переноса**: Перенос изменений осуществляется исключительно через **`scp`** или вручную через **буфер обмена и `vim`**.
- **Внимание (V59+)**: Файл `strips.html` оптимизирован. База данных `CATEGORIES` вынесена в отдельный статический файл `dashboard/static/strips_db.js`. При деплое **необходимо переносить оба файла**:
  1. `dashboard/templates/strips.html`
  2. `dashboard/static/strips_db.js`
