# 🔌 API Endpoints (Эндпоинты) — Подробное Объяснение

## Что такое Endpoint?
**Endpoint (Эндпоинт)** — это конкретный "адрес" (URL) на сервере, по которому клиент (браузер, приложение, скрипт) может отправить запрос и получить ответ. 

Представьте отель:
- **Сервер** (наш AI-Router) — это здание отеля.
- **Endpoint** — это конкретная дверь в здании. У каждой двери своя табличка и своя функция:
  - `/v1/dna/projects` — вход в отдел "Проекты" (показать все проекты)
  - `/v1/dna/capture` — вход в отдел "Регистрация" (записать новую генерацию)
  - `/v1/dna/search` — вход в отдел "Поиск" (найти похожие промпты)
  - `/v1/dna/upload/{slug}` — вход в отдел "Хранилище" (загрузить картинку)

## HTTP Методы (Глаголы)
Каждый эндпоинт знает, какие "глаголы" (методы) он принимает:
- **GET** — "Покажи мне" (получить данные, ничего не меняя)
- **POST** — "Сохрани это" (создать новую запись, загрузить файл)
- **PUT** — "Обнови это" (изменить существующую запись)
- **DELETE** — "Удали это" (удалить запись)

## Как это выглядит в коде (`api_dna.py`):
```python
@router.get("/projects")          # GET /v1/dna/projects — список проектов
async def list_projects():
    ...

@router.post("/capture")          # POST /v1/dna/capture — сохранить генерацию
async def capture_generation():
    ...

@router.post("/search")           # POST /v1/dna/search — семантический поиск
async def search_prompts():
    ...

@router.post("/upload/{slug}")    # POST /v1/dna/upload/my-project — загрузить файл
async def upload_image():
    ...
```

## Декоратор `@router.get(...)` / `@router.post(...)`
Эта "волшебная строчка" над функцией называется **декоратор**. Она говорит FastAPI:
*"Когда кто-то отправит GET-запрос по адресу /projects, вызови функцию `list_projects()`."*

## Как тестировать эндпоинты из терминала:
```bash
# GET-запрос (получить данные)
curl -s http://localhost:8000/v1/dna/projects | python3 -m json.tool

# POST-запрос (отправить данные)
curl -s -X POST http://localhost:8000/v1/dna/search \
  -H "Content-Type: application/json" \
  -d '{"query": "futuristic dashboard"}'
```

## Наши текущие эндпоинты в AI Router:

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/v1/dna/projects` | Список всех проектов |
| POST | `/v1/dna/projects` | Создать новый проект |
| PUT | `/v1/dna/projects/{slug}/dna` | Обновить DNA проекта |
| POST | `/v1/dna/capture` | Записать генерацию (промпт + параметры) |
| GET | `/v1/dna/generations/{slug}` | История генераций проекта |
| GET | `/v1/dna/context/{slug}` | Получить полный контекст проекта |
| POST | `/v1/dna/search` | Семантический поиск по промптам |
| POST | `/v1/dna/upload/{slug}` | Загрузить файл в хранилище |
| GET | `/v1/dna/files/{slug}` | Список файлов проекта |
| GET | `/v1/dna/accounts` | Список аккаунтов |
| GET | `/v1/dna/health` | Проверка здоровья системы |
