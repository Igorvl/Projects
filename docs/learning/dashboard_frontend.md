# 🎨 Dashboard: Фронтенд для Project DNA

## Что такое Dashboard?
Dashboard — это веб-интерфейс (панель управления), через который пользователь 
визуально взаимодействует с системой Project DNA. Без Dashboard все данные
доступны только через терминал (`curl`), что неудобно.

## Архитектура Dashboard:

```
┌─────────────────────────────────────────────────┐
│  Браузер (Chrome/Safari)                        │
│  http://172.25.9.33:8090/dashboard/             │
│                                                  │
│  index.html (HTML + CSS + JavaScript)            │
│  ├─ fetch('/v1/dna/projects')  → список проектов │
│  ├─ fetch('/v1/dna/context/X') → DNA-контекст    │
│  ├─ fetch('/v1/dna/search')    → поиск           │
│  └─ fetch('/v1/dna/files/X')   → файлы           │
└────────────────┬────────────────────────────────┘
                 │ HTTP (CORS)
┌────────────────▼────────────────────────────────┐
│  AI-Router (FastAPI) — порт 8000                │
│  CORSMiddleware(allow_origins=["*"])             │
│  Обрабатывает запросы, отдаёт JSON              │
└────────────────┬────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
PostgreSQL    Qdrant       MinIO
```

## Ключевые понятия:

### CORS (Cross-Origin Resource Sharing)
Браузер по умолчанию запрещает JavaScript делать запросы к другому порту/домену.
Наш Dashboard живёт на порту 8090, а API — на порту 8000.
Без CORS браузер заблокирует запрос, даже если сервер работает идеально.

**Решение:** Добавить CORSMiddleware в FastAPI:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Разрешить запросы отовсюду
    allow_methods=["*"],       # Разрешить GET, POST, PUT, DELETE
    allow_headers=["*"],       # Разрешить любые заголовки
)
```

### `fetch()` — API-вызовы из JavaScript
`fetch()` — это встроенная функция браузера для HTTP-запросов. Аналог `curl` в терминале:

```javascript
// Терминал: curl -s http://localhost:8000/v1/dna/projects
// JavaScript:
const response = await fetch('http://172.25.9.33:8000/v1/dna/projects');
const data = await response.json();   // Парсим JSON-ответ
console.log(data.projects);           // [{name: "Test Project", ...}]
```

### SPA (Single Page Application)
Наш Dashboard — это одна HTML-страница (`index.html`), которая динамически 
обновляет содержимое через JavaScript без перезагрузки. 
Когда ты кликаешь на проект, страница не перезагружается — JavaScript 
делает новый `fetch()` и обновляет DOM (элементы на странице).

## Как устроен Dashboard:

### Компоненты:
1. **Header** — заголовок "Project DNA" + статус API (Online/Offline)
2. **Sidebar** — семантический поиск + список проектов
3. **Stats Row** — 4 карточки со статистикой (проекты, генерации, файлы, контексты)
4. **DNA Grid** — два блока: стратегический + тактический контекст
5. **Generations Table** — таблица всех генераций проекта

### CSS-техники:
- **CSS Custom Properties** (`:root { --bg: #0a0a0f; }`) — цветовые переменные
- **CSS Grid** (`grid-template-columns: 320px 1fr`) — сетка для layout
- **Glassmorphism** (`backdrop-filter: blur(20px)`) — эффект матового стекла
- **Gradient Text** (`background: linear-gradient(...)` + `-webkit-background-clip: text`)
- **Анимация пульса** (`@keyframes pulse`) — для индикатора статуса

## Файлы (ВНИМАНИЕ: Где искать исходники):
> [!WARNING]
> **Dashboard (index.html) НЕ ЛЕЖИТ в локальной папке проекта Windows (типа `C:\Projects\...`)!**
> 
> Файл располагается **строго на удаленном Linux-сервере (виртуалке)**, внутри примонтированного тома Docker-контейнера `ai-audio-host`. Полноценно редактировать его можно только подключившись по SSH или зная точный путь на сервере.
>
> **Точный путь на Ubuntu (где запущен Docker):**
> `/home/igorvl/ai-design-workspace/deploy/audio_out/dashboard/index.html`

- Хостится напрямую через nginx-совместимый контейнер `ai-audio-host` на порту `8090`.
- При вызове `http://172.25.9.33:8090/dashboard/` отдается именно этот файл.

## Частая ошибка: Несовпадение формата API
Когда API возвращает `{"projects": [...]}` (объект-обёртка),
а JavaScript ожидает `[...]` (чистый массив), данные не отображаются.

**Решение:** Делать "безопасный доступ":
```javascript
const data = await response.json();
const projects = data.projects || data;  // Работает с обоими форматами!
```

## Полезные инструменты для отладки Dashboard:
- **Chrome DevTools** → Network (F12) — видно все fetch-запросы и ответы
- **Chrome DevTools** → Console — видно ошибки JavaScript
- `curl` — вручную проверить, что API возвращает правильный JSON
