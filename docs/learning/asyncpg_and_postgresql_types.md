# asyncpg и типы PostgreSQL

> Изучено в ходе отладки PATCH endpoint в Project DNA (2026-03-25)

---

## Что такое asyncpg?

**asyncpg** — самый быстрый async-драйвер для PostgreSQL в Python.
В отличие от psycopg2 (синхронный), asyncpg использует `async/await` —
это значит, сервер не блокируется пока ждёт ответ от БД.

```python
# psycopg2 (старый, синхронный):
conn = psycopg2.connect(...)
cursor.execute("SELECT ...")   # ← блокирует поток на время запроса

# asyncpg (современный, async):
async with pool.acquire() as conn:
    await conn.fetch("SELECT ...")   # ← "притормаживает" только эту корутину
```

В стеке Project DNA: FastAPI + asyncpg + asyncpg connection pool.

---

## Ключевое правило: Python types → PostgreSQL types

asyncpg **автоматически** конвертирует Python-типы в PostgreSQL-типы.
Передавай native Python — asyncpg всё сделает сам.

| Python тип | PostgreSQL тип | Пример |
|-----------|---------------|--------|
| `str` | `TEXT`, `VARCHAR` | `'hello'` |
| `int` | `INTEGER`, `BIGINT` | `42` |
| `float` | `FLOAT`, `NUMERIC` | `3.14` |
| `list` | `TEXT[]`, `INTEGER[]` | `['a', 'b']` |
| `dict` | `JSONB` | `{'key': 'val'}` |
| `bool` | `BOOLEAN` | `True` |
| `None` | `NULL` | `None` |
| `datetime` | `TIMESTAMPTZ` | `datetime.now()` |

---

## Наш баг: json.dumps для TEXT[] колонки

```python
# ❌ НЕПРАВИЛЬНО — result_urls это TEXT[], не TEXT/JSONB:
await conn.execute(
    "UPDATE generations SET result_urls = $1 WHERE id = $2",
    json.dumps(['http://minio/img.png']),   # → строка '["http://..."]'
    generation_id
)
# PostgreSQL: "invalid input for query argument $1: '[\"http://...\"'"
# Он получил TEXT, но ожидал TEXT[]

# ✅ ПРАВИЛЬНО — передаём list напрямую:
await conn.execute(
    "UPDATE generations SET result_urls = $1 WHERE id = $2",
    ['http://minio/img.png'],              # → asyncpg → PostgreSQL TEXT[]
    generation_id
)
```

### Когда использовать json.dumps?

Только если колонка имеет тип `JSONB` или `TEXT`:

```python
# Колонка model_params = JSONB:
await conn.execute(
    "UPDATE generations SET model_params = $1 WHERE id = $2",
    json.dumps({'temperature': 0.7}),   # ✅ для JSONB TEXT нужна строка
    generation_id
)

# ИЛИ лучше использовать json модуль asyncpg:
import asyncpg
# asyncpg сам умеет: dict → JSONB (версии >= 0.27)
```

---

## Параметры в asyncpg: $1, $2...

PostgreSQL использует `$n` для параметров (не `?` как SQLite/MySQL):

```python
await conn.execute(
    """
    UPDATE generations
    SET result_urls = $1, status = $2
    WHERE id = $3
    """,
    ['http://...'],    # $1
    'generated',       # $2
    generation_id      # $3
)
```

**Зачем параметры вместо f-strings?**

```python
# ❌ SQL-инъекция! Никогда так:
await conn.execute(f"SELECT * FROM users WHERE name = '{user_input}'")
# Если user_input = "'; DROP TABLE users; --"  → катастрофа!

# ✅ Параметризованный запрос — безопасно:
await conn.execute("SELECT * FROM users WHERE name = $1", user_input)
# asyncpg экранирует специальные символы автоматически
```

---

## Connection Pool: зачем нужен

```python
# БЕЗ пула — каждый HTTP запрос открывает новое соединение:
async with await asyncpg.connect(dsn) as conn:  # ← открыть
    await conn.execute(...)
# ← закрыть

# При 100 одновременных запросах → 100 соединений → PostgreSQL падает

# С пулом — заранее открытые соединения переиспользуются:
pool = await asyncpg.create_pool(dsn, min_size=5, max_size=20)

async with pool.acquire() as conn:   # ← взять из пула
    await conn.execute(...)
# ← вернуть в пул (НЕ закрыть)
```

В Project DNA: `db.pool = await asyncpg.create_pool(...)` — инициализируется при старте FastAPI.

---

## В контексте MLOps

Понимание типов данных и пулов соединений — критический навык для:
- **Data Engineering**: правильная типизация данных в пайплайнах
- **Backend ML API**: высокопроизводительные endpoints для inference
- **MLOps**: мониторинг здоровья БД-соединений в production

В резюме: *"asyncpg + PostgreSQL для async ML inference API с connection pooling"*
