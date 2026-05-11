# Project DNA: ⚡ Antigravity Handoff Context (2026-05-11)

**Критически важно:** Этот файл содержит инъекцию контекста для нового ИИ-ассистента при смене сессии. Внимательно изучи текущее состояние, чтобы не предлагать отвергнутые решения и понимать архитектурные особенности данного окружения. Обязательно прочитай `project_dna_full_context.md` и `PRIVATE_CONTEXT.md` в рабочей директории, прежде чем приступать к коду.

---

## 📸 1. Snapshot состояния (State Snapshot)

**Текущая задача:** Завершён релиз **Strips Pro Gen V59** — инструмента генерации Midjourney-промптов для Ксении Артман. Инструмент работает как standalone-страница `/strips` FastAPI-дашборда Behance Scout на сервере `172.25.9.33:7788`.

**Последние 5 архитектурных изменений:**
1. **Strips Pro Gen V59 (strips.html):** Обновлён генератор промптов до V59. Добавлено 9 новых форматов, 10 интерьерных протоколов, обновлено 6 существующих форматов.
2. **Оптимизация размера (strips_db.js):** База данных `CATEGORIES` вынесена из `strips.html` в отдельный файл `dashboard/static/strips_db.js`. Это сократило размер `strips.html` с 881 KB до 374 KB, значительно ускорив разработку. `strips.html` использует маркеры `[[CATEGORIES_START]]` и загружает базу через тег `<script>`.
3. **PDF Export Patch:** Настроен корректный экспорт в PDF. Формат страниц А4, промпт всегда начинается с отдельной страницы, шрифт промпта уменьшен до 6pt Helvetica, добавлена textarea для заметок клиента.
4. **URL Hash State Extended:** В URL hash добавлены поля `bh` (behanceMode), `pt` (projectTitle), `ct` (customText) для полного восстановления состояния между сессиями.
5. **Deploy Flow зафиксирован:** Сервер живёт на Linux Ubuntu (`linux-job`, `172.25.9.33`). Папка: `/home/igorvl/ai-design-workspace/behance_scout/`. Запуск: `venv/bin/python run.py --dashboard`. Деплой: ручной перенос через `scp` (теперь нужно переносить и `strips.html`, и `static/strips_db.js`). После замены `strips.html` — перезапуск сервера НЕ нужен. После замены `app.py` — перезапуск нужен (`sudo pkill -f uvicorn` → `venv/bin/python run.py --dashboard`).

**Список активных (переходящих) задач и багов:**
*   [Task] **Strips V47:** Возможные будущие улучшения — поле для Brief (краткое описание проекта), история последних N промптов, экспорт пресетов в JSON.
*   [Bug] **Разбор пустой ошибки "HTTP ?:"** Ожидание вывода логов с production-сервера с детальным трейсом `repr(e)` от `httpx` при вызове `api.siliconflow.com`.
*   [Task] **Observability/Monitoring:** Внедрение Loki + Promtail для агрегации логов в Grafana.
*   [Task] **Backup Automation:** Автоматическое резервное копирование Docker-вольюма `n8n_data` на Synology NAS.

---

## 🗂️ Архитектура Strips Pro Gen

**Файловая структура:**
```
behance_scout/
├── run.py                          # Точка входа, uvicorn запуск
├── config.py                       # DASHBOARD_PORT=7788, DASHBOARD_HOST=0.0.0.0
└── dashboard/
    ├── app.py                      # FastAPI: GET /strips → читает strips.html с диска
    │                               # POST /api/strips/ai → LLM каскад (OpenRouter → SiliconFlow)
    └── templates/
        └── strips.html             # V59 — standalone React app (Babel CDN)
```

**Маршруты:**
- `GET /strips` → читает `templates/strips.html` с диска при каждом запросе (без кэша)
- `POST /api/strips/ai` → LLM-генерация параметров по текстовому концепту, каскад провайдеров

**Стек front-end (strips.html):**
- React 18 (CDN, UMD build)
- Babel Standalone (JSX в браузере)
- Tailwind CSS (CDN)
- Vanilla CSS переменные + кастомные классы
- Состояние в URL hash (`#%7B...%7D`) — полное восстановление по ссылке
- Custom protocols в `localStorage` (ключ `ksar_custom_protocols`)

**Категории V59 (11 категорий, вынесены в `dashboard/static/strips_db.js`):**
| # | Название | Размер |
|---|---|---|
| C1 | Школа Дизайна | 123 элемента |
| C2 | Эстетика ДНК | 120 элементов |
| C3 | 3 Цвета | 60 палитр |
| C4 | Ротация Цвета | 20 схем |
| C5 | Структура | 60 элементов |
| C6 | Графика и Маркировка | 60 элементов |
| C7 | Супер-Графика | 30 заголовков |
| C8 | Материал и Печать | 20 техник |
| C9 | Оптика и Камера | 20 линз |
| C10 | Триггер-Фокус | 60 дисрупторов |
| C11 | Свет и Атмосфера | 20 схем |

**Форматы (TARGET_FORMATS - 23 формата):**
`strips` · `poster` · `identity` · `packaging` · `cosmetics` · `space` · `product` · `merch` · `editorial` · `ui` · `wayfinding` · `aero` · `installation` · `motion` · `ui2` · `popup` · `furniture` · `hard_luxury` · `exterior` · `robotics` · `typeface` · `scientific_viz` · `procedural_art`

**Протоколы (встроенные пресеты - 14 штук):**
- `ABYSSAL` — глубоководный ресёрч, каустика
- `CLINICAL` — стерильная мед-инженерия
- `TECTONIC` — тяжёлый бетон, разрушение
- `STEALTH $` — тихая роскошь, идеальная сборка
- + 10 элитных интерьерных концептов (interior_subsurface, interior_acoustic, interior_cryogenic и т.д.)
- + пользовательские (localStorage)

---

## ⚖️ 2. Гайдлайны и Code Style (Строгие правила!)

1. **Защита существующей архитектуры:** Никогда не предлагайте "переписать систему с нуля" на другой фреймворк или "заменить SQLite на PostgreSQL для Behance Scout". Работайте в рамках существующих технологий и файловых структур (Vanilla JS для фронта, FastAPI + asyncpg для роутера).
2. **Решение проблем без изменения чужого кода:** Как показал Bypass с `DNA_PICKER`, мы предпочитаем решать проблемы на стороне клиента (хитрая инъекция в API), а не переписывать код стабильно работающего бэкенд-роутера.
3. **Fail Fast Pattern:** В браузерных расширениях и API-запросах всегда используйте жесткие таймауты (`AbortSignal.timeout(5000)` в JS / `asyncio.sleep` или `timeout=60` в httpx), чтобы не вешать потоки.
4. **Резюме-Ориентированность:** Любое значимое внедрение новой технологии должно автоматически сопровождаться записью в `docs/RESUME_BULLETS.md` (на англ. и русском) в формате достижения старшего инженера (Senior MLOps/DevOps).
5. **Теория и Обучение (Learning Blocks):** При введении новых технологий (Promtail, Loki, VLANs), всегда предваряй техническое объяснение секцией `**📚 Learning Block — [Topic]**`. Пользователь активно обучается во время интеграций.
6. **Осторожность с Терминалом (Escaping):** Помни, что скрипты выполняются через Windows (локально) поверх файлов Linux (SSH/Samba). Осторожнее со строгими bash-операторами, кавычками в `sqlite3` и `echo >>` в PowerShell. Для сложных баз данных лучше запускать inline Python скрипт.

---

## 🚫 3. Summary диалога (Отвергнутые и принятые пути)

**Что МЫ УЖЕ ПРОБОВАЛИ И ОТВЕРГЛИ:**
*   *Отвергнуто:* Выполнение парсинга Behance Scout (в частности, первичный логин с обходом капчи) headlessly на Ubuntu-сервере. (Причина: Google Auth блокирует безголовые браузеры. Принятое решение: скрипт `login_local.py` генерирует `session.json` на локальном ПК с UI, затем ключ копируется на сервер).
*   *Отвергнуто:* Изменение логики самого роутера `routing/router.py`, чтобы он не вызывал `DNA_PICKER`. (Причина: Угроза стабильности Open WebUI).
*   *Отвергнуто:* Установка библиотек глобально на Ubuntu 24.04 (Причина: Блокировка `EXTERNALLY-MANAGED`. Принято: Строгая изоляция через `python3 -m venv venv`).
*   *Отвергнуто:* Self-hosted macOS runner для Safari. (Причина: Провал виртуализации).
*   *Отвергнуто:* Полный рефайл strips.html в одном tool-call (лимит токенов). Принято: точечные `multi_replace_file_content` по секциям.

**Что УСПЕШНО ИСПОЛЬЗУЕТСЯ:**
*   **Strips Pro Gen (standalone React в HTML):** Babel CDN + React UMD в одном HTML-файле — максимальная простота деплоя, нет build-шага.
*   **Hash-based State:** Весь стейт кодируется в URL hash → шаринг сессий, восстановление без БД.
*   **localStorage Protocols:** Пользовательские пресеты без бэкенда.
*   **Fallback Sequence:** В случае падения LLM провайдера скрипт автоматически обходит список запасных моделей без остановки процесса.
*   **Manual Synchronization Pattern:** Раздельные Git-репозитории на Windows-ПК и Ubuntu-сервере; точечный перенос важных изменений и ключей.
*   Synology NAS (Active Backup for Business + Docker Registry) как центральный хаб хранения и Disaster Recovery.

**Следующий шаг ассистента:**
Прочитать этот файл, подтвердить понимание и уточнить у Пользователя текущую задачу. Последнее состояние: Strips Pro Gen V46 задеплоен на `172.25.9.33:7788/strips`.
