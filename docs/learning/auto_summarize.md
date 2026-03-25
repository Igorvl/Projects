# 🧠 Auto-Summarize: Двойной Контекст (Strategic + Tactical)

## Что это и зачем?
Auto-Summarize — это система "бесконечной памяти" для AI-проектов. 
Проблема: LLM не помнит, что ты делал вчера. Каждый новый запрос — как разговор с человеком с амнезией.
Решение: после каждых N генераций система автоматически отправляет историю промптов в LLM, получает сжатый контекст и сохраняет его в PostgreSQL.

## Два уровня контекста

### 1. Тактический (Tactical) — "Что мы делаем сейчас?"
- Сжимает последние 10 генераций
- Обновляется каждые 5 генераций
- Содержит: текущий стиль, над чем работает дизайнер, активные элементы

**Пример вывода:**
> "The designer is refining a mobile app UI with bottom navigation and card layouts. 
> Recent emphasis is on smooth animations and gradient backgrounds."

### 2. Стратегический (Strategic) — "Что этот проект из себя представляет?"
- Сжимает последние 50 генераций
- Обновляется каждые 20 генераций
- Содержит: бренд-идентичность, палитру, типографику, эволюцию стиля

**Пример вывода:**
> "The project's DNA is rooted in modern, premium, tech-forward aesthetic
> with dark themes, neon accents, and glassmorphism..."

## Как это работает (Pipeline):

```
Дизайнер отправляет промпт (#20)
    ↓
api_dna.py: capture_generation() сохраняет в PostgreSQL + Qdrant
    ↓
asyncio.create_task(maybe_summarize())  ← Запускается В ФОНЕ (не блокирует ответ!)
    ↓
auto_summarize.py: Проверяет: seq_num % 5 == 0?
    ↓ Да!
db.get_recent_prompts(limit=10) → Получает последние промпты
    ↓
litellm.acompletion(model="gemini-flash") → Отправляет в LLM
    ↓ Если RateLimit...
litellm.acompletion(model="Qwen3-8B", api_base="siliconflow") → Фоллбэк!
    ↓
db.save_context_summary(type="tactical", text="...") → Сохраняет в PostgreSQL
```

## Ключевые архитектурные решения:

### 1. Фоновое выполнение (`asyncio.create_task`)
Суммаризация запускается В ФОНЕ и НЕ блокирует ответ пользователю.
Пользователь получает ответ `{"seq_num": 20}` мгновенно, а LLM работает 5-15 секунд в фоне.

### 2. Фоллбэк-цепочка (Circuit Breaker)
Gemini Flash (основной) → SiliconFlow Qwen3 (запасной).
Если основная модель исчерпала квоту, система автоматически переключается на запасную.

### 3. Идемпотентность
Можно безопасно вызвать суммаризацию 100 раз — каждый раз создаётся новая запись
в таблице `context_summaries`, а endpoint `/context/{slug}` всегда берёт ПОСЛЕДНЮЮ.

## Файлы:
- `routing/auto_summarize.py` — основная логика суммаризации
- `routing/db.py` — методы `save_context_summary()`, `get_recent_prompts()`, `get_latest_contexts()`
- `routing/api_dna.py` — вызов `maybe_summarize()` из `capture_generation()`

## Параметры настройки (в auto_summarize.py):
```python
TACTICAL_EVERY = 5      # Каждые 5 генераций
STRATEGIC_EVERY = 20    # Каждые 20 генераций
SUMMARY_MODEL = "gemini/gemini-2.0-flash"   # Основная модель
FALLBACK_MODEL = "openai/Qwen/Qwen3-8B"    # Запасная модель
```
