# HTTP Methods, REST и Silent Failures

> Изучено при реализации PATCH endpoint в Project DNA (2026-03-25)

---

## REST: Архитектурный стиль API

**REST** (Representational State Transfer) — набор соглашений о том, как строить API.
В REST каждый HTTP-метод имеет чёткое назначение:

| Метод | Действие | Идемпотентный? | Тело запроса |
|-------|---------|---------------|-------------|
| `GET` | Получить данные | ✅ Да | ❌ Нет |
| `POST` | Создать ресурс | ❌ Нет | ✅ Да |
| `PUT` | Заменить ресурс целиком | ✅ Да | ✅ Да |
| `PATCH` | Обновить часть ресурса | ⚠️ Частично | ✅ Да |
| `DELETE` | Удалить ресурс | ✅ Да | ❌ Обычно нет |

**Идемпотентный** = одинаковый результат при повторных вызовах.

---

## PUT vs PATCH

```
Объект генерации в БД:
{
  "id": "abc-123",
  "prompt": "Dark Luxury sketch",
  "result_urls": [],
  "status": "generated",
  "seq_num": 13
}
```

```
# PUT /v1/dna/generations/abc-123  ← ЗАМЕНИТЬ ЦЕЛИКОМ
{
  "id": "abc-123",
  "prompt": "Dark Luxury sketch",
  "result_urls": ["http://minio/img.png"],  ← обновлено
  "status": "generated",
  "seq_num": 13                              ← нужно передать все поля!
}

# PATCH /v1/dna/generations/abc-123  ← ОБНОВИТЬ ЧАСТЬ
{
  "result_urls": ["http://minio/img.png"]    ← только нужное поле
}
```

Мы использовали `PATCH` — правильный выбор, т.к. обновляем только `result_urls`.

---

## HTTP Status Codes

```
2xx = Успех
  200 OK               — стандартный успех
  201 Created          — ресурс создан (POST)
  204 No Content       — успех, нет тела ответа

4xx = Ошибка клиента
  400 Bad Request      — неверный запрос (невалидный JSON и т.д.)
  401 Unauthorized     — нет авторизации
  403 Forbidden        — нет доступа
  404 Not Found        — ресурс не найден
  405 Method Not Allowed — метод не поддерживается эндпоинтом
  409 Conflict         — конфликт (например, дубликат)
  422 Unprocessable    — FastAPI: ошибка валидации Pydantic

5xx = Ошибка сервера
  500 Internal Server Error — необработанное исключение
  503 Service Unavailable   — сервер недоступен / overloaded
```

---

## Silent Failures: Самая Опасная Ошибка

### Что это?

Код "работает" (не бросает исключений), но данные **молча не сохраняются**.

### Как произошло у нас:

```javascript
// ❌ Код до фикса — логируем "успех" без проверки ответа:
await fetch(`${API}/v1/dna/generations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ result_urls: urls }),
});
console.log(`✅ Generation patched`);  // ← пишем всегда!
// Если сервер вернул 500 — мы НЕ ЗНАЕМ об этом!
```

```javascript
// ✅ Код после фикса — явная проверка:
const patchRes = await fetch(`${API}/v1/dna/generations/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ result_urls: urls }),
});
if (patchRes.ok) {                             // ← response.ok = status 200-299
    console.log(`✅ Generation patched`);
} else {
    const err = await patchRes.text();
    console.error(`❌ PATCH failed ${patchRes.status}: ${err}`);
}
```

### Важно о fetch() в JavaScript

```javascript
// fetch() НЕ бросает ошибку при 4xx/5xx!
// Промис резолвится в любом случае если есть HTTP ответ
// Исключение бросается ТОЛЬКО при сетевой ошибке (нет соединения, CORS и т.д.)

try {
    const res = await fetch(url);
    // res.status может быть 404, 500 — и мы здесь!
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
} catch (e) {
    // Сетевая ошибка ИЛИ наш throw из if (!res.ok)
    console.error(e.message);
}
```

---

## Data Lineage Debugging

**Data Lineage** — отслеживание данных через трансформации.

```
page-script.js          content-script.js       service-worker.js
resultBase64Images=2  →  data: {images:2}      →  capturedData.resultBase64Images=?
                                                    ↑ здесь было 0!

Техника: вставить console.log на каждом переходе
```

Применяли в этой сессии:
```javascript
// Точка 1: handleCapture (service-worker граница)
console.log(`base64=${capturedData.resultBase64Images?.length}, urls=${capturedData.resultUrls?.length}`);

// Точка 2: Phase 2 (перед условием)
console.log(`Phase2: base64=${base64Images.length}, urls=${sourceUrls.length}`);
```

В MLOps это называется **observability при расследовании инцидентов** — именно так SRE-инженеры находят где в data pipeline данные теряются или искажаются.

---

## В контексте карьеры

- **REST API дизайн** — базовый навык для любой backend/ML-позиции
- **HTTP debugging** — ключевой навык SRE/DevOps
- **Silent failures** — critical knowledge для data reliability engineer

В резюме: *"Implemented robust REST API с proper HTTP status codes и explicit error handling для ML data pipeline"*
