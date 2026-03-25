# 🧩 Браузерные Расширения: Архитектура Web Extensions

## Что такое Web Extension?
**Web Extension (Браузерное расширение)** — это мини-программа, которая встраивается в браузер и добавляет новую функциональность. Каждое расширение — это набор HTML, CSS и JavaScript файлов, упакованных вместе с файлом-манифестом (`manifest.json`).

### Аналогия:
Представьте себе ресторан (браузер):
- **Веб-страница** — это посетитель, который пришёл покушать.
- **Расширение** — это тайный агент, который сидит за соседним столиком, наблюдает за посетителем (страницей), записывает, что он заказывает (перехватывает запросы), и отправляет отчёт в штаб (наш API).
- При этом посетитель (страница) **не знает** о существовании агента — всё работает незаметно.

---

## Manifest V3 vs Manifest V2

Manifest — это `manifest.json`, «паспорт» расширения. Он объявляет:
- Имя, версию, описание расширения
- Какие разрешения нужны (доступ к определённым сайтам, хранилищу и т.д.)
- Какие скрипты куда инжектить
- Что показывать при клике на иконку

**Manifest V3** — это новый стандарт (с 2023 года):

| Аспект | Manifest V2 (старый) | Manifest V3 (новый) |
|--------|---------------------|---------------------|
| Фоновый скрипт | Background Page (постоянно живёт в памяти) | Service Worker (просыпается по событию) |
| Перехват запросов | `chrome.webRequest` (мог блокировать) | `chrome.declarativeNetRequest` (декларативный) |
| Модули | Нет поддержки ES modules | Поддержка `"type": "module"` |
| Safari | Не поддерживается | ✅ Полная поддержка |
| Chrome | Устарел (январь 2025) | ✅ Текущий стандарт |

**Почему мы используем V3:**
1. **Safari поддерживает только V3** (с версии 16.4)
2. Google прекратил поддержку V2 в Chrome
3. Service Workers экономят память (просыпаются только по событию)

---

## Архитектура расширения (3 «мира»)

Расширение состоит из трёх изолированных «миров» (worlds), каждый со своим окружением JavaScript:

```
┌──────────────────────────────────────────────────────────────┐
│  Вкладка браузера (например: aistudio.google.com)            │
│                                                               │
│  ┌──── МИР 1: Page Context (Контекст Страницы) ──────────┐  │
│  │  • Весь JavaScript страницы (Google AI Studio)          │  │
│  │  • window.fetch, document, console                      │  │
│  │  • Наш page-script.js (инжектированный)                │  │
│  │  • ⚠️ НЕТ доступа к chrome.runtime, chrome.storage     │  │
│  └────────────────────────────┬───────────────────────────┘  │
│                               │ window.postMessage            │
│  ┌──── МИР 2: Content Script Context ─────────────────────┐  │
│  │  • Наш content-script.js                                │  │
│  │  • Видит тот же DOM (HTML), что и страница              │  │
│  │  • НО: отдельный window, fetch, variables               │  │
│  │  • ✅ Имеет доступ к chrome.runtime.sendMessage         │  │
│  │  • ⚠️ НЕ видит переменные страницы (window.fetch)      │  │
│  └────────────────────────────┬───────────────────────────┘  │
└───────────────────────────────┼───────────────────────────────┘
                                │ chrome.runtime.sendMessage
┌───────────────────────────────▼───────────────────────────────┐
│  МИР 3: Service Worker (Фоновый процесс)                     │
│  • Наш service-worker.js                                      │
│  • Живёт отдельно от вкладок (есть при закрытых вкладках)     │
│  • ✅ Полный доступ к chrome.* API                            │
│  • ✅ Может делать fetch() к внешним серверам                 │
│  • ⚠️ НЕТ доступа к DOM (нет document, window)              │
│  • ⚠️ Может быть «усыплен» браузером (event-driven)         │
└───────────────────────────────────────────────────────────────┘
```

### Почему 3 мира?
**Безопасность!** Если бы расширение имело прямой доступ к JavaScript страницы, вредоносное расширение могло бы:
- Красть пароли из форм
- Подменять банковские реквизиты на страницах оплаты
- Читать cookie и токены авторизации

Поэтому Chrome/Safari изолируют каждый «мир» друг от друга. Общение между мирами возможно только через **строго контролируемые каналы сообщений**.

---

## Каналы коммуникации между мирами

### 1. `window.postMessage` (Мир 1 ↔ Мир 2)
Механизм передачи сообщений через DOM (общий для Page и Content Script):
```javascript
// page-script.js (МИР 1) — отправляет сообщение
window.postMessage({ type: 'MY_TYPE', data: {...} }, '*');

// content-script.js (МИР 2) — принимает сообщение
window.addEventListener('message', (event) => {
  if (event.data.type === 'MY_TYPE') {
    console.log('Получил данные от страницы:', event.data);
  }
});
```
**Аналогия:** Как передать записку через стеклянную перегородку (DOM).

### 2. `chrome.runtime.sendMessage` (Мир 2 ↔ Мир 3)
Внутренний канал расширения (недоступен для страницы):
```javascript
// content-script.js (МИР 2) — отправляет в service worker
chrome.runtime.sendMessage(
  { action: 'SAVE_DATA', data: {...} },
  (response) => { console.log('Ответ:', response); }
);

// service-worker.js (МИР 3) — принимает
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'SAVE_DATA') {
    // Обработка...
    sendResponse({ success: true });
  }
  return true; // Для async-ответа
});
```
**Аналогия:** Защищённая рация (только между своими).

---

## Monkey-Patching: Что это и зачем?

**Monkey-patching (Обезьяний патч)** — это техника замены встроенной функции своей версией «на лету» (в рантайме).

```javascript
// Сохраняем оригинал
const originalFetch = window.fetch;

// Подменяем на свою версию
window.fetch = async function(url, options) {
  console.log('Перехвачен запрос к:', url);    // ← наша логика
  const response = await originalFetch(url, options); // ← вызываем оригинал
  console.log('Получен ответ:', response.status);     // ← наша логика
  return response;                                      // ← возвращаем как есть
};
```

### Зачем это нужно?
AI Studio использует `fetch()` для отправки промптов в Gemini API. Content Script **не может** перехватить `fetch()` страницы (изолированные миры!). Единственный способ — инжектировать скрипт в контекст страницы (МИР 1) и подменить `fetch()` **до** того, как AI Studio его вызовет.

### Важные правила:
1. **Всегда сохраняй оригинал** (`const originalFetch = window.fetch`)
2. **Всегда вызывай оригинал** (не ломай функциональность страницы!)
3. **Клонируй данные** (response.clone()) — тело ответа можно прочитать только один раз

---

## Outbox Pattern: Устойчивость к сбоям

**Outbox Pattern** — это паттерн из мира микросервисов для надёжной доставки сообщений.

### Проблема:
Наш сервер (172.25.9.33) может быть недоступен:
- Сервер перезагружается
- VPN туннель упал
- Сеть временно недоступна

Без outbox'а захваченная генерация **потеряется навсегда** — ведь расширение уже перехватило данные, но не смогло их отправить.

### Решение (Outbox):
```
1. Захватили генерацию → Попробовали отправить в API
2. API недоступен? → Сохранили в chrome.storage.local (outbox/очередь)
3. API появился → Взяли из очереди, отправили, удалили из хранилища
```

```javascript
// Упрощённо:
async function sendCapture(data) {
  try {
    await fetch(API_URL, { body: JSON.stringify(data) });
    // Успех — данные доставлены!
  } catch {
    // Провал — кладём в outbox
    const queue = await chrome.storage.local.get('queue');
    queue.push(data);
    await chrome.storage.local.set({ queue });
  }
}

// Периодически проверяем outbox
async function retryQueue() {
  const queue = await chrome.storage.local.get('queue');
  for (const item of queue) {
    try {
      await fetch(API_URL, { body: JSON.stringify(item) });
      queue.remove(item); // Успех — убрали из очереди
    } catch {
      // Всё ещё недоступен — оставляем в очереди
    }
  }
}
```

Этот паттерн используется в production-системах:
- **Apache Kafka** — вся система основана на похожем принципе
- **RabbitMQ** — очереди сообщений с гарантией доставки
- **Наш реализация** — упрощённая версия в chrome.storage

---

## Service Worker: Event-Driven модель

Service Worker в расширении — это НЕ постоянно работающий процесс (как было в MV2). Это **событийная модель**:

```
Браузер запустился → Service Worker стартует → Инициализация → ЗАСЫПАЕТ 💤

... 30 секунд тишины ...

Content Script послал сообщение → Service Worker ПРОСЫПАЕТСЯ 🔔
  → Обрабатывает сообщение
  → Отправляет в API
  → ЗАСЫПАЕТ 💤

... тишина ...

Alarm сработал → Service Worker ПРОСЫПАЕТСЯ 🔔
  → Проверяет outbox
  → ЗАСЫПАЕТ 💤
```

### Важные последствия:
1. **Нельзя хранить данные в переменных** — при засыпании/пробуждении они теряются
2. **Используй `chrome.storage`** для всех данных, которые нужно сохранить
3. **`chrome.alarms`** для периодических задач (вместо `setInterval`)

---

## Полезные команды для разработки

| Что | Как |
|-----|-----|
| Загрузить расширение | Chrome → `chrome://extensions/` → Developer mode → Load unpacked |
| Логи Service Worker | Chrome → `chrome://extensions/` → click "Service Worker" |
| Логи Content Script | F12 на странице AI Studio → Console |
| Логи Popup | ПКМ на иконке → "Inspect Popup" |
| Перезагрузить расширение | Chrome → `chrome://extensions/` → 🔄 |
| Конвертировать для Safari | `xcrun safari-web-extension-converter ./` |

---

## Файлы нашего расширения:
- `project-dna-extension/manifest.json` — конфигурация расширения
- `project-dna-extension/src/content/page-script.js` — перехватчик fetch()
- `project-dna-extension/src/content/content-script.js` — мост между мирами
- `project-dna-extension/src/background/service-worker.js` — API + логика
- `project-dna-extension/src/popup/` — UI панель расширения
