# 🧬 Intercepting AI Studio Streams (gRPC-Web)

## 📋 Обзор
Google AI Studio использует протокол **gRPC-Web** поверх стандартного HTTP/XHR. Это создает уникальные сложности для перехвата данных по сравнению с обычными JSON API.

## 🛠️ Технические вызовы (накопленные, T-04 → T-06)

### 1. Бинарный формат (ArrayBuffer)
В отличие от `fetch`, где данные часто приходят как текст, XHR-стримы AI Studio передают бинарные чанки.
**Решение:** Использование `TextDecoder('utf-8').decode()` в реальном времени при получении каждого чанка (`readyState 3`).

### 2. Аномалия State-Drop (readyState 0)
Google часто вызывает `.abort()` на XHR-объекте сразу после того, как фронтенд получил EOF-сигнал внутри данных. Это переводит `readyState` из `3` сразу в `0` (Unsent), минуя `4` (Done).

**Первое решение (v2.0.x):** Накопление текста в `WeakMap` и принудительный триггер захвата при переходе `3 → 0`.

**Проблема:** Порядок данных в gRPC-Web Stream для image generation:
```
[title text ~100b] → [image base64 ~2MB] → [description text ~500b]
       ↑ state:0 abort срабатывал здесь!        ↑ description терялась!
```

**Финальное решение (v2.0.34):** Отложенный захват при state:0:
```javascript
} else if (this.readyState === 0 && !currentState.state0Scheduled) {
  // НЕ захватываем сразу — ждём 3 секунды для description
  const delay = url.includes('GenerateContent') ? 3000 : 500;
  currentState.state0Timer = setTimeout(() => {
    const latestState = xhrStateMap.get(self0); // читаем свежий текст!
    processInterceptedCall(url, requestBody, { text: async () => latestState.text }, ...);
  }, delay);
  // state:4 (если придёт раньше) — отменяет таймер и захватывает сразу
}
```

### 3. Проблема фрагментации (Chunking)
Стрим может приходить как:
- **Cumulative:** `[A, AB, ABC]` (каждый следующий чанк содержит предыдущий).
- **Incremental:** `[A, B, C]` (каждый чанк — это кусок текста).
- **Mixed:** Смесь чанков с разными метаданными.

**Регрессия (v2.0.13):** При попытке захватить «всё» (и английский промпт Imagen, и русский ответ), алгоритм склеивал слишком много мелких фрагментов через разделитель `---`, превращая текст в «лоскутное одеяло».

### 4. Два режима парсинга ответа (открыто в T-06)

AI Studio gRPC-Web ответ может находиться в двух состояниях при захвате:

| Состояние | Условие | Путь парсинга |
|-----------|---------|---------------|
| **Полный ответ** | `JSON.parse` успешен → массив `[[[[null,"text"]],...]]` | **Path 2B-bis**: рекурсивный сканер массива |
| **Частичный ответ** | `JSON.parse` упал (обрезание) → `rawText` | **Path 2D**: regex-сканер quoted-строк |

**Path 2B-bis** (JSON.parse success → Array):
```javascript
// Рекурсивно обходит вложенный массив, собирает строки с пробелами
(function scanGrpcArray(obj, depth) {
  if (typeof obj === 'string' && obj.includes(' ') && obj.length >= 2) {
    aiStudioFragments.push(obj);
  } else if (Array.isArray(obj)) {
    for (const item of obj) scanGrpcArray(item, depth + 1);
  }
})(responseData, 0);
```

**Path 2D** (rawText с частичными данными):
```javascript
// Strategy A: "data" key match — работает БЕЗ закрывающей кавычки (partial data)
const dataKeyMatch = text.match(/"data"\s*:\s*"([A-Za-z0-9+\/\\=\r\n]{400,})/);

// Strategy B: bare PNG/JPEG magic bytes
const pngIdx = text.indexOf('iVBORw0'); // PNG header
```

### 5. Imagen Prompt vs Conversational Text
Gemini Pro через batchexecute возвращает ДВА типа текста в одном ответе:
- **Conversational**: "Конечно! Вот изображение..." (русский, ответ пользователю)
- **Imagen Prompt**: "This visualization, executed in the intricate 'Synthetic Architect' style... `<IMAGE 0>`, `<IMAGE_1>`..." (английский, внутренний промпт генератора)

Маркер отличия — наличие `<IMAGE N>` тегов в строке.

**Решение (v2.0.33):** Разделение и маркировка:
```javascript
const imagenCands = candidates.filter(c => /<IMAGE[_ ]\d/i.test(c));
const convCands   = candidates.filter(c => !/<IMAGE[_ ]\d/i.test(c));
// Сборка: [русский ответ]\n\n[Imagen Prompt]\n[английский промпт]
```

---

## 🚀 Дедупликация: "Fuzzy Tightening"

Для чистого вывода в расширении реализован алгоритм агрессивной очистки:

1. **Prefix/Suffix Matching:** Если начало (первые 20 символов) или конец (последние 20 символов) двух строк совпадают — они считаются частями одного и того же блока. Оставляем только длинный вариант.
2. **Substring Removal:** Если одна строка полностью содержится в другой — она удаляется.
3. **Clean Joining:** Блоки склеиваются двойным переносом строки (`\n\n`) — выглядит как абзацы единого текста.
4. **UI Artifact Filtering:** Удаление строк короче 40 символов и специфических паттернов ("Nano Banana"), которые не являются частью ответа ИИ.

## 📊 Пример логики дедупа
```javascript
const existingIdx = unique.findIndex(u =>
  u.includes(c) || c.includes(u) ||
  (u.substring(0, 20) === c.substring(0, 20)) || // Совпадение начала
  (u.slice(-20) === c.slice(-20))                // Совпадение конца
);
```

Это гарантирует, что мы получим **цельный текст**, даже если он пришел в 80 разных RPC-сообщениях.


## 📋 Обзор
Google AI Studio использует протокол **gRPC-Web** поверх стандартного HTTP/XHR. Это создает уникальные сложности для перехвата данных по сравнению с обычными JSON API.

