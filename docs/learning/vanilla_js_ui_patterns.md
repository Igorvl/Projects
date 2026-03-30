# 🧩 Vanilla JS UI Patterns — Продвинутые приёмы без фреймворков

> **Дата:** 2026-03-28  
> **Контекст:** Паттерны, реализованные в Dashboard Project DNA v2.2.0  
> **Уровень:** Intermediate → Advanced  

---

## Почему это важно для MLOps/DevOps?

Инструменты мониторинга, внутренние дашборды, панели управления кластером —
всё это часто делается на чистом HTML/JS без React/Vue, потому что:
- Нет зависимостей (нет `npm install`, нет сборки)
- Деплой = скопировал один `.html` файл
- Работает на любом сервере (nginx, python -m http.server, S3 bucket)
- Легко встроить в уже существующую инфраструктуру

**В резюме:** "Developed internal tooling dashboards with zero build-step vanilla HTML/JS"

---

## 1. localStorage — постоянное состояние без бэкенда

### Аналогия
`localStorage` — это как маленькая таблица в браузере, которая не исчезает при закрытии вкладки.
Как ENV-переменные, но для UI-конфигурации.

### Паттерн: Save/Load JSON-состояния

```javascript
// Сохраняем массив объектов (например, папки проектов)
function saveFoldersLS(folders) {
    localStorage.setItem('dna_folders', JSON.stringify(folders));
}

// Загружаем с fallback на дефолтные значения
function loadFoldersLS() {
    try {
        const saved = localStorage.getItem('dna_folders');
        return saved ? JSON.parse(saved) : DEFAULT_FOLDERS;
    } catch {
        return DEFAULT_FOLDERS;  // Защита от битого JSON
    }
}
```

**Когда использовать:**
- UI-конфигурация (открыты/закрыты секции, цвета, порядок)
- Кэш данных (не нужно каждый раз грузить с API)
- Feature flags для разработки

**Когда НЕ использовать:**
- Чувствительные данные (токены, пароли) — **никогда**
- Данные, которые должны синхронизироваться между устройствами
- Объём > ~5MB

---

## 2. CSS Grid — сложные layouts без Bootstrap

### Паттерн: Элемент на всю ширину в grid (span)

```css
/* Grid из 2 колонн */
.dna-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

/* Первый элемент занимает обе колонки */
.dna-card.dna-document {
    grid-column: 1 / -1;  /* от первой до последней колонки */
}
```

**Результат:**
```
┌──────────────────────────────────────┐
│  DNA Document (spans full width)     │
└──────────────────────────────────────┘
┌──────────────────┐ ┌─────────────────┐
│  Strategic       │ │ Tactical        │
└──────────────────┘ └─────────────────┘
```

`1 / -1` означает: "начни с колонки 1, заканчивай в последней" — работает с любым числом колонок.

---

## 3. Sticky Modal Header — скролл только контента

### Проблема
Длинный текст в модальном окне заставляет скроллить заголовок с кнопками.
Кнопки "Copy", "Delete" пропадают из поля видимости.

### Решение: Flex-Column + overflow

```css
/* Контейнер модального окна — не скроллится сам */
.modal-content {
    max-height: 90vh;
    overflow: hidden;        /* ← Важно: убираем scrollbar с modal-content */
    display: flex;
    flex-direction: column;
}

/* Заголовок — flex-shrink:0 = не сжимается */
.modal-header {
    flex-shrink: 0;
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 10;
}

/* Панель кнопок — тоже не скроллится */
.modal-actions {
    flex-shrink: 0;
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
}

/* Контент — ТОЛЬКО ОН скроллится */
.modal-scroll-area {
    flex: 1;
    overflow-y: auto;   /* ← Скроллбар только здесь */
    padding: 1.5rem;
}
```

**HTML структура:**
```html
<div class="modal-content">
    <div class="modal-header">Заголовок</div>  <!-- Фиксирован -->
    <div class="modal-body">
        <div class="modal-actions">Кнопки</div>  <!-- Фиксирован -->
        <div class="modal-scroll-area">          <!-- Скроллится -->
            длинный текст...
        </div>
    </div>
</div>
```

**Аналогия в MLOps:** Как `tmux` split — верхняя панель (stat/header) фиксирована, нижняя (логи) скроллится.

---

## 4. Contextual Dropdown Menu — ⋮ без библиотек

### Паттерн: CSS opacity + JS class toggle

```css
/* Кнопка ⋮ появляется только при hover */
.proj-menu-btn {
    opacity: 0;
    transition: opacity 0.15s;
}
.project-item:hover .proj-menu-btn { opacity: 1; }

/* Dropdown скрыт по умолчанию */
.proj-dropdown { display: none; }
.proj-dropdown.open { display: block; }
```

```javascript
function closeProjMenus() {
    document.querySelectorAll('.proj-dropdown.open')
        .forEach(d => d.classList.remove('open'));
}

function toggleProjMenu(event, slug) {
    event.stopPropagation();  // ← Важно! Не триггерим клик по проекту
    const dropdown = document.getElementById('pdrop-' + slug);
    const isOpen = dropdown.classList.contains('open');
    closeProjMenus();              // Закрыть все другие
    if (!isOpen) dropdown.classList.add('open');  // Открыть текущий
}

// Закрыть по клику снаружи
document.addEventListener('click', closeProjMenus);
```

**Ключевые моменты:**
- `event.stopPropagation()` — предотвращает "всплывание" события (bubble) к родительскому элементу
- `document.addEventListener('click', closeProjMenus)` — глобальный хандлер закрытия
- Паттерн "закрыть все, потом открыть нужный" — проще чем отслеживать состояние

---

## 5. Flat Array Pattern — навигация через группы данных

### Проблема
Данные хранятся вложенно: `generations[i].result_urls[j]`.
При навигации через кнопки ← → нужно знать "общий индекс" по всем группам.

### Решение: Flatten into indexed array

```javascript
// Из: [{result_urls: ["a","b"]}, {result_urls: ["c"]}]
// В:  [{url:"a", genIdx:0, imgIdx:0, seqNum:7},
//       {url:"b", genIdx:0, imgIdx:1, seqNum:7},
//       {url:"c", genIdx:1, imgIdx:0, seqNum:8}]

function buildAllImages() {
    lbAllImages = [];
    for (let gi = 0; gi < currentGenerations.length; gi++) {
        const g = currentGenerations[gi];
        if (!g.result_urls?.length) continue;
        g.result_urls.forEach((url, ii) => {
            lbAllImages.push({ url, genIdx: gi, imgIdx: ii, seqNum: g.seq_num });
        });
    }
}

// Найти позицию кликнутого элемента в плоском массиве:
function openLightbox(genIdx, imgIdx) {
    buildAllImages();
    const found = lbAllImages.findIndex(
        img => img.genIdx === genIdx && img.imgIdx === imgIdx
    );
    lbGlobalIdx = found >= 0 ? found : 0;
    renderLightbox();
}
```

**Аналогия в Python:**
```python
# То же самое, но в Python:
all_images = [
    {"url": url, "gen_idx": gi, "seq_num": gen.seq_num}
    for gi, gen in enumerate(generations)
    for url in gen.result_urls
]
```

**Применение в MLOps:** Flatten + index — стандартный приём для обработки батчей,
логов из нескольких подов, метрик из нескольких контейнеров.

---

## 6. event.stopPropagation() — контроль всплывания

### Аналогия
DOM-события как TCP пакеты: когда ты кликаешь на кнопку внутри карточки,
событие "всплывает" снизу вверх: кнопка → div.карточка → body → document.

```
document ← body ← .card ← .button  (обычное "всплывание")
```

```javascript
// Без stopPropagation: клик на кнопку Archive → ТАКЖЕ триггерит selectProject()
<button onclick="promptArchive(slug)">Archive</button>

// С stopPropagation: клик на кнопку Archive → ТОЛЬКО Archive
<button onclick="event.stopPropagation(); promptArchive(slug)">Archive</button>
```

**Правило:** Любая кнопка внутри кликабельного элемента **должна** иметь `event.stopPropagation()`.

---

## 7. asyncpg Connection Pool Pattern (Backend)

### Почему Depends(get_db) не работает с нашим синглтоном

FastAPI `Depends(get_db)` — паттерн для инъекции зависимостей, рассчитан на то
что `get_db` возвращает новое соединение каждый раз. Наш `db` — синглтон:
один объект на всё приложение.

```python
# ❌ Неправильно (Depends ожидает generator/callable, не синглтон)
@router.post("/projects/{slug}/archive")
async def archive_project(slug: str, db=Depends(get_db)):  # get_db не определён!
    ...

# ✅ Правильно: использовать глобальный пул напрямую
from db import db  # Импортируем синглтон

@router.post("/projects/{slug}/archive")
async def archive_project(slug: str):
    async with db.pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE projects SET archived = TRUE WHERE slug = $1", slug
        )
    if res == "UPDATE 0":
        raise HTTPException(404, "Project not found")
    return {"success": True}
```

**Как читать `res == "UPDATE 0"`:**
asyncpg возвращает строку вроде `"UPDATE 1"` (количество затронутых строк).
Если `"UPDATE 0"` — ни одна строка не обновилась = slug не найден.

---

## Связь с MLOps/DevOps рынком

| Паттерн | Применение в работе |
|---------|---------------------|
| localStorage persist | Grafana preferences, Kibana saved searches |
| CSS Grid span | Kubernetes dashboard layouts, Prometheus панели |
| Sticky modal | Любой admin UI без фреймворка |
| Dropdown ⋮ menu | GitHub Actions UI, ArgoCD, k9s web UI |
| Flat array nav | Log aggregation (Loki), metric batch processing |
| asyncpg pool | Любой production FastAPI + PostgreSQL backend |

**Ключевый вывод:** Zero-dependency SPA — это не "устаревший" подход. 
Grafana, Prometheus, MinIO Console — все написаны на Go+vanilla или минималистичных фреймворках.
Умение строить такие интерфейсы ценится именно в DevOps/MLOps — там нет команды frontend-разработчиков,
и тебе нужно самому быстро сделать работающий инструмент.
