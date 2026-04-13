# Browser Extension: CSP Bypass via manifest world:MAIN

**Дата:** 2026-04-07  
**Статус:** ✅ Исправлено в v2.2.0

---

## Суть проблемы

Расширение Project DNA перехватывает запросы к Gemini API через monkey-patching `window.fetch`.
Для этого `page-script.js` должен выполниться **в контексте страницы** (Main World),
а не в изолированном мире расширения (Isolated World).

### Что сломалось?

Google обновил **Content-Security-Policy** на `gemini.google.com`.
Наш прежний метод инжекции (из `content-script.js`) создавал `<script>` тег и добавлял его в DOM:

```js
// СЛОМАНО — CSP блокирует оба метода:
script.text = code;   // Метод 1: Inline script → CSP без 'unsafe-inline' блокирует
// Fallback:
fbScript.src = blobUrl; // Метод 2: blob: URL → CSP без 'blob:' в script-src блокирует
```

**Коварность:** в WebKit (Orion/Safari) `onerror` на inline `<script>` **не стреляет** при блокировке CSP.
Браузер молча игнорирует скрипт, fallback не срабатывает, `window.fetch` не перехватывается.

### Симптомы

| Симптом | Причина |
|---------|---------|
| 0 captures в popup | `page-script.js` не выполнен → `window.fetch` не перехвачен |
| `[Project DNA]` нет в консоли Gemini | Скрипт не выполнялся, нечему логировать |
| Сервер Online (5ms) | health check работает через SW — ок |
| Генерация в 3x медленнее | **Отдельный баг**: Orion Content Blocker (см. ниже) |

---

## Решение: `world: "MAIN"` в manifest.json

MV3 поддерживает инжекцию content scripts прямо в **Main World** страницы,
объявив это в манифесте. Браузерный runtime инжектирует скрипт **до CSP страницы** — CSP не применяется.

```json
// manifest.json
"content_scripts": [
  {
    "matches": ["https://gemini.google.com/*"],
    "js": ["src/content/content-script.js"]
    // Нет world — по умолчанию "ISOLATED"
  },
  {
    "matches": ["https://gemini.google.com/*"],
    "js": ["src/content/page-script.js"],
    "world": "MAIN",          // ← Выполняется в контексте страницы
    "run_at": "document_start" // ← До загрузки страницы, чтобы перехватить fetch с самого начала
  }
]
```

### Почему это работает?

```
Браузер runtime инжектирует → window.fetch ещё не определён → page-script.js перехватывает
                              (до CSP страницы)
```

CSP применяется только к ресурсам, загружаемым **самой страницей** (через HTML/JS).
Расширения имеют привилегированный доступ к инжекции — это фундаментальный контракт Chrome Extension API.

### Отличие "worlds"

| | Isolated World | Main World |
|---|---|---|
| Доступ к DOM | ✅ | ✅ |
| Chrome Extension APIs | ✅ | ❌ |
| Доступ к `window.fetch` страницы | ❌ | ✅ |
| Подчиняется CSP страницы | ❌ | ❌ (при инжекции через manifest) |

---

## Защита от двойного запуска

Если по какой-то причине скрипт выполняется дважды (обновление расширения без перезагрузки),
`window.fetch` будет перехвачен вложенно. Защита:

```js
// page-script.js — первая строка после 'use strict':
if (window.__DNA_PAGE_SCRIPT_LOADED) {
  console.log('[Project DNA] ⚡ page-script.js already loaded — skipping double-init.');
  return;
}
window.__DNA_PAGE_SCRIPT_LOADED = true;
```

---

## Баг 2: Замедление Gemini через Orion Content Blocker

### Причина

Orion блокирует `play.google.com/log` (Google аналитика/телеметрия).
Gemini's streaming UI имеет callbacks, ожидающие ответа этих запросов.
При блокировке браузер ждёт таймаут → рендер тормозит в 3x.

В консоли:
```
⛔ Resource blocked by content blocker
⛔ Fetch API cannot load https://play.google.com/log?format=json... due to access control checks
⛔ Content blocker prevented frame displaying...
```

### Фикс

В Orion: `Preferences → Content blocker → Exceptions → добавить gemini.google.com`

Или более хирургически: разрешить только `play.google.com` на `gemini.google.com`.

> ⚠️ `No ID or name found in config.` в консоли — это Gemini's own компонентная система,
> не наш код. Появляется когда заблокирована телеметрия. Игнорировать.

---

## Инструкция по обновлению расширения в Orion

После изменения `manifest.json`:

1. Orion → `Tools → Extensions`
2. Найти "Project DNA — AI Studio Capture"
3. Нажать кнопку обновления (🔄) или выключить/включить
4. **Перезагрузить вкладку** `gemini.google.com` (Cmd+R)
5. Открыть консоль → проверить:
   ```
   [Project DNA] 🧬 Content script loaded on: https://gemini.google.com/...
   [Project DNA] 🧬 page-script.js injected via manifest world:MAIN — fetch interceptor active.
   ```

## Диагностика

| Лог в консоли страницы | Значение |
|------------------------|---------|
| `[Project DNA] 🧬 Content script loaded on:` | content-script.js работает ✅ |
| `[Project DNA] 🧬 page-script.js injected via manifest` | page-script.js работает ✅ |
| `[Project DNA] 🧬 Intercepted AI Studio API call:` | fetch перехвачен ✅ |
| Ничего из вышеперечисленного | Расширение не загружено на этой вкладке ❌ |
