# LLM Gateway Resilience & SSE Streaming Failover

**Тема:** Обеспечение отказоустойчивости LLM-роутера при потоковой передаче данных (Server-Sent Events) и умная ротация ключей/провайдеров.
**Связанные концепции:** Circuit Breaker, Fallback Pattern, Generator Functions, Dependency Injection.

## Проблема 1: Уязвимость семантического роутера к лимитам (Rate Limits)
Семантический классификатор (`semantic_router.py`) изначально вызывал модель напрямую через `litellm.acompletion`. Из-за этого при исчерпании квоты (429 RateLimitError) у первичного ключа API, весь конвейер рушился, и новые проекты не распознавались.

**Решение (Dependency Injection):**
Вместо дублирования логики ротации или хардкодинга ключей во множестве файлов, мы внедрили инъекцию зависимости. Главная мощная функция ротации из `router.py` (`call_with_key_rotation`) передается как аргумент (`call_llm_func`) внутрь `semantic_auto_detect`. 
Это паттерн из SOLID-принципов (Dependency Inversion), который позволяет изолировать бизнес-логику классификатора от технической реализации общения с API.

## Проблема 2: Разрыв стриминга (SSE) при падении модели
Open WebUI запрашивает ответ в режиме Stream (`text/event-stream`). Когда стрим начинается, FastAPI сразу отдает заголовок `HTTP 200 OK`. 
Если модель "падает" (например, отбраковывает аккаунт или падает по тайм-ауту) на первой же попытке генерации слова *сразу после* открытия сокета, возникает критическая ситуация: мы уже не можем вернуть клиенту `HTTP 500`, так как HTTP-статус уже отправлен. Отвал сокета вызывает на клиенте ошибку `400 TransferEncodingError` или `MidStreamFallbackError`.

**Решение (Pre-fetching the First Chunk):**
Мы применили хирургический трюк с генераторами (async generators).
До того как отдавать объект `StreamingResponse(gen())` обратно в Starlette/FastAPI, мы вручную заказываем самый первый кусок текста функцией `await resp.__anext__()`.
```python
# Пытаемся получить первый чанк до старта стрима
first_chunk = await resp.__anext__()
```
Если LLM мертва или квоты кончились, ошибка вылетит **здесь**, до отправки HTTP-заголовков. Мы пробрасываем (`raise e`) эту ошибку во внешний цикл `for current in queue:`, который ловит её и бесшовно переключается на запасную модель (Fallback) — например, с Gemini переходит на DeepSeek.

## Проблема 3: Прозрачность Fallback-событий
Если система переключилась на другую модель в фоне, пользователь Open WebUI не узнает, что общается уже с DeepSeek, а не с Gemini. Это вредит аналитике и UX.

**Решение (Сигнатуры внутри потока):**
Если итоговая модель (`mid`) не совпадает с изначально запрошенной (`target.get("model")`), алгоритм инъектирует в конец потока дополнительный JSON-чанк.
```python
sign_txt = f"\n\n> 🔄 *Fallback-модель:* `{mid}`"
# ... упаковка в JSON chat.completion.chunk ...
yield f"data: {signature_chunk}\n\n"
```
Форматирование ответа остается консистентным, клиентский интерфейс отображает красивую цитату с указанием резервной модели, а сама смена провайдера происходит с нулевым даунтаймом.

## Проблема 4: Ключи в `.env` не попадают в контейнер (Docker env_file vs environment)

**Симптом:** В `.env` прописано 6 ключей `GEMINI_API_KEY`, но роутер видит только 3. Контейнерный лог при старте: `Key pool [GEMINI_API_KEY]: 3 key(s) loaded`. После рестарта — всё равно 3.

**Root Cause — разница между `env_file:` и `environment:` в Docker Compose:**

| Механизм | Что делает |
|---|---|
| `env_file: .env` | Передаёт **все** переменные из файла в контейнер автоматически |
| `environment: - KEY=${KEY}` | Передаёт **только явно перечисленные** переменные |

В `docker-compose.yml` была секция `environment:`, в которой вручную были перечислены только 3 ключа:
```yaml
environment:
  - GEMINI_API_KEY=${GEMINI_API_KEY}
  - GEMINI_API_KEY_2=${GEMINI_API_KEY_2}
  - GEMINI_API_KEY_3=${GEMINI_API_KEY_3}
  # KEY_4, KEY_5, KEY_6 в .env есть, но здесь их нет → в контейнер не попадают!
```

**Решение:** Заменить `environment: - GEMINI_API_KEY_N=...` на `env_file: .env`.
Тогда новые ключи достаточно добавить только в `.env` — `docker-compose.yml` трогать не нужно.

```yaml
services:
  llm-router:
    env_file:
      - .env          # все переменные из .env попадают в контейнер автоматически
    environment:
      - PYTHONUNBUFFERED=1  # не-секретные runtime-переменные оставляем здесь
      - HF_HOME=/app/models
      - CONFIG_PATH=deploy/antigravity.json
```

**Важный нюанс:** Когда используются оба блока одновременно, `environment:` имеет **приоритет** над `env_file:` для одинаковых ключей — конфликтов нет.

**Диагностика:** `docker logs $(docker ps -q -f name=router) 2>&1 | grep "Key pool"` — сразу видно сколько ключей загрузилось при старте. Незаменимо при отладке.

## Проблема 5: `MidStreamFallbackError` обходит ротацию ключей

**Симптом:** При 429-ошибке роутер сразу переключается на следующую **модель** (DeepSeek), не перебирая оставшиеся **ключи** текущей модели.

**Root Cause — Pre-fetch вне цикла ротации:**

`call_with_key_rotation` вызывает `acompletion(stream=True)`, который возвращает объект-генератор **не читая данные** (просто открывает HTTP-соединение). Реальный 429 возникает при первом чтении данных — `await resp.__anext__()`. Это чтение происходило в CALLER'е, **уже вне** цикла `for attempt in range(len(keys))`.

```
# БЫЛО (баг):
call_with_key_rotation:
  acompletion() → HTTP OK (соединение открыто, 429 ещё не пришёл) → return resp

CALLER:
  resp.__anext__() → 💥 RateLimitError  ← здесь нет key rotation!
  except → "Fail on gemini-2.5-flash-lite" → switch MODEL → DeepSeek
```

**Решение — `_prepend_chunk` паттерн:**

Перенести pre-fetch **внутрь** цикла ротации. Но тогда первый чанк уже считан — нужно вернуть его CALLER'у. Решение: async generator, который сначала отдаёт сохранённый `first_chunk`, потом стримит остаток.

```python
async def _prepend_chunk(first_chunk, stream):
    """Восстанавливает стрим: сначала уже прочитанный чанк, потом остаток."""
    yield first_chunk
    async for chunk in stream:
        yield chunk

# Внутри call_with_key_rotation, в блоке try:
if stream:
    first_chunk = await resp.__anext__()  # ← pre-fetch ЗДЕСЬ, 429 поймается below
    KEY_INDEX[api_key_env] = idx + 1
    return _prepend_chunk(first_chunk, resp)   # ← CALLER получает прозрачный генератор
```

Для CALLER'а ничего не меняется: он делает `await resp.__anext__()` — получает реплицированный `first_chunk`, гарантированно без исключений. Тип возврата (async generator) не изменился.

```
# СТАЛО (фикс):
call_with_key_rotation:
  attempt=0: acompletion() → OK
  attempt=0: resp.__anext__() → 💥 RateLimitError → _is_rate_limit_ → rotate!
  attempt=1: acompletion(key_2) → OK
  attempt=1: resp.__anext__() → ✅ OK → return _prepend_chunk(chunk, resp)

CALLER: прозрачно получает готовый стрим ✅
```

**Дополнение к `is_rate_limit` детектору:**
```python
err_str = str(e) + type(e).__name__
is_rate_limit = (
    "429" in err_str or
    "RateLimitError" in err_str or
    "MidStreamFallbackError" in err_str  # ← LiteLLM оборачивает 429 в этот тип
)
```
## Проблема 6: 429 RateLimitError (502 Bad Gateway) для конечных моделей, без fallback-вектора

**Симптом:** При прямом запросе к бесплатным моделям (например, `openrouter/meta-llama/llama-3.3-70b-instruct:free` или `hermes-3-llama-3.1-405b` на OpenRouter) периодически выпадает ошибка `429 RateLimitError` от вендора, которая приводит к падению роутера (клиенту отдается 502 Bad Gateway) даже при наличии отказоустойчивой конструкции.

**Root Cause — агрессивные лимиты бесплатных Tier'ов и отсутствие fallback-хвоста:**
OpenRouter (например, через провайдера Venice) часто дропает запросы на большие модели по квотам. Так как модель (напр. `soft-skills-llama-3.3-70b`) вызывалась как конечная инстанция, и в файле конфигурации `antigravity.json` для нее **не было определено** свойств `"fallbacks": [...]`, контур защиты Circuit Breaker не имел пути для дальнейшего маневра, исчерпав все (единственную доступную) попытки.

**Решение — Замыкание fallback-цепей:**
Абсолютно каждый узел конфигурационного файла `antigravity.json` должен обладать планом "Б".

```json
        {
            "model_name": "soft-skills-llama-3.3-70b",
            "litellm_params": {
                "model": "openrouter/meta-llama/llama-3.3-70b-instruct:free",
                "api_base": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "fallbacks": [
                    "qwen-480b-coder",
                    "deepseek-v3.2",
                    "GLM_5"
                ]
            }
        }
```
После добавления массива `fallbacks` ротация начнет работать корректно и автоматически, перенаправляя "тяжелые" неудачные вызовы на стабильные запасные мощности. Использование LiteLLM гарантирует динамичный reload конфигурации без необходимости пересборки контейнера.

## Ценность для резюме (MLOps / DevOps)
- **High Availability (HA):** Разработка Zero-Downtime шлюзов для AI API.
- **Failover Mechanisms:** Проектирование бесшовного переключения между вендорами (Vendor-Agnostic LLM Routing).
- **Graceful Degradation:** Вместо глухого падения приложения оно информирует пользователя и сохраняет отказоустойчивость.
