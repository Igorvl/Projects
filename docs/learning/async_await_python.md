# async/await в Python: Полное Руководство

> Изучено при разборе FastAPI endpoint в Project DNA (2026-03-25)

---

## Проблема: синхронный код блокирует сервер

Представь: у тебя ресторан с одним официантом.

```
Синхронный официант (обычная функция):
  1. Принял заказ у стола 1
  2. Пошёл на кухню — ЖДЁТ пока готовят (3 мин.)
  3. Отнёс блюдо → принял заказ у стола 2
  Стол 2 ждёт 3+ минуты!

Асинхронный официант (async функция):
  1. Принял заказ у стола 1 → передал на кухню
  2. Пока готовят → принял заказ у стола 2
  3. Пока готовят оба → принял заказ у стола 3
  4. Кухня: "Стол 1 готово!" → отнёс
  Все столы обслужены параллельно!
```

---

## async def: создаём корутину

```python
# Обычная функция — выполняется синхронно:
def compute_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

# Корутина — может "приостанавливаться":
async def fetch_from_db(slug: str) -> dict:
    # await = "я жду, займись другим пока жду"
    result = await conn.fetchrow("SELECT * FROM projects WHERE slug = $1", slug)
    return dict(result)
```

**Ключевое:** `async def` функцию нельзя вызвать как обычную.
Нужно либо `await`, либо создать Task.

```python
# ❌ Не работает:
data = fetch_from_db("ksar-me")      # возвращает корутину, не результат!

# ✅ Правильно:
data = await fetch_from_db("ksar-me")   # ← только внутри async def

# ✅ Или создать задачу:
task = asyncio.create_task(fetch_from_db("ksar-me"))
```

---

## Разбор нашего endpoint построчно

```python
# ① Декоратор — регистрирует маршрут в FastAPI роутере
# @router.patch = HTTP PATCH метод
# "/generations/{generation_id}" = URL шаблон, {generation_id} = переменная
@router.patch("/generations/{generation_id}")

# ② async def — функция-корутина:
# - generation_id: str = из URL (FastAPI парсит автоматически)
# - data: dict = тело JSON запроса
async def patch_generation(generation_id: str, data: dict):

    # ③ Проверяем что БД подключена:
    # db.pool — async connection pool к PostgreSQL
    if not db.pool:
        raise HTTPException(503, "Database not connected")

    try:
        # ④ async with = асинхронный контекстный менеджер
        # pool.acquire() = "взять" соединение из пула
        # Когда блок with завершится → соединение вернётся в пул
        async with db.pool.acquire() as conn:

            # ⑤ await = "жди ответа от PostgreSQL"
            # Пока база обрабатывает — FastAPI обслуживает ДРУГИЕ запросы!
            await conn.execute(
                "UPDATE generations SET result_urls = $1 WHERE id = $2",
                data.get('result_urls', []),   # $1 — Python list → TEXT[]
                generation_id                   # $2 — UUID строка
            )

        # ⑥ FastAPI автоматически конвертирует dict → JSON ответ
        return {"ok": True, "generation_id": generation_id}

    # ⑦ Любое исключение → логируем + 500 клиенту
    except Exception as e:
        logger.error(f"[PATCH gen] {e}")
        raise HTTPException(500, str(e))
```

---

## Когда нужен async?

### ✅ НУЖЕН async:

```python
# 1. Работа с БД
async def get_project(slug: str):
    return await db.pool.fetchrow("SELECT * FROM projects WHERE slug = $1", slug)

# 2. HTTP запросы к внешним API
async def call_gemini(prompt: str) -> str:
    return await litellm.acompletion(model="gemini-2.5-flash-lite", ...)

# 3. Работа с файлами (в async контексте)
async def upload_to_minio(file_bytes: bytes):
    await minio_client.put_object(...)

# 4. Ожидание нескольких операций параллельно
async def fetch_all():
    # asyncio.gather = запустить параллельно, ждать всех
    projects, accounts = await asyncio.gather(
        db.list_projects(),
        db.list_accounts()
    )
    return projects, accounts
```

### ❌ НЕ нужен async:

```python
# Чистые вычисления (CPU, без ожидания):
def compute_md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def build_prompt(projects: list) -> str:
    return "\n".join(f"- {p['slug']}" for p in projects)

def parse_json(raw: str) -> dict:
    return json.loads(raw)
```

**Правило:** Если функция делает I/O (сеть, диск, БД) — `async def` + `await`.

---

## Event Loop: как это работает внутри

```
FastAPI запущен → Event Loop работает

   Request 1: "GET /projects"
       → await db.fetch("SELECT...")
       ↓ (жду БД, ухожу)
       
   Request 2: "POST /route"  ← обрабатывается пока ждём БД для Request 1!
       → await litellm.completion(...)
       ↓ (жду LLM)
       
   БД ответила Request 1 → возобновляем
   LLM ответил Request 2 → возобновляем
   
   Оба запроса завершены!
```

**Один поток, но параллельная обработка** — вот магия async/await.

В отличие от `threading` (несколько потоков), async работает в ОДНОМ потоке.
Это эффективнее для I/O-bound задач (сеть, БД).

---

## asyncio.gather: параллельные запросы

```python
# Последовательно (медленно):
project = await db.get_project(slug)     # ← ждём
context = await db.get_context(slug)     # ← ждём
# Итого = T1 + T2

# Параллельно (быстро):
project, context = await asyncio.gather(
    db.get_project(slug),
    db.get_context(slug)
)
# Итого = max(T1, T2)
```

В Project DNA мы могли бы оптимизировать endpoints используя gather.

---

## В контексте карьеры

- **FastAPI с async** — стандарт для ML inference API в 2025-2026
- **asyncpg** — упоминается в вакансиях MLOps как требование
- **Event Loop** — понимание необходимо для debugging production систем

Слова для резюме: *"async/await Python, FastAPI, asyncpg, event-driven architecture"*
