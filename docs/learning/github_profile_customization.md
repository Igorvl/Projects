# Настройка «Pro» профиля GitHub (3D Contrib & Metrics)

## Идея
Для усиления визуального впечатления от GitHub-профиля (особенно для MLOps / DevOps резюме), мы оформили высокотехнологичный `README.md`, который динамически обновляется. Главная цель — показать хардкорные навыки (Python, Shell, Docker), скрыть «простои» в коммитах и отфильтровать фронтенд-языки (HTML, CSS), чтобы профиль выглядел строго и профессионально.

---

## Финальная архитектура (апрель 2026)

### Принятые решения:
1. **Главный SVG — `lowlighter/metrics`** (`github-metrics.svg`), тёмный фон через `extras_css`.
2. **`yoshi389111/github-profile-3d-contrib`** продолжает генерировать SVGы в папку `profile-3d-contrib/` (cron), но в README не отображается — готов к использованию.
3. **Относительный путь в README** — `./github-metrics.svg` вместо `raw.githubusercontent.com/...` — обязательно, иначе Camo CDN кешируется до 24ч.
4. **Почему 3D contrib не может показывать 6 месяцев**: проверено по исходному коду `src/github-graphql.ts` — action использует GitHub GraphQL `contributionsCollection` без параметров (последние 52 недели). `YEAR` переводит на конкретный январь-декабрь, дробного диапазона нет. Чтобы сделать 6 месяцев — нужен форк action.

---

## Как работает (GitHub Actions flow)

```
GitHub Actions (cron 0 0 * * *) → yoshi389111/github-profile-3d-contrib@latest
  ↳ Читает contribution data через API (GITHUB_TOKEN)
  ↳ Генерирует 9 SVG-файлов с разными темами в папку profile-3d-contrib/
  ↳ git commit + push → README показывает конкретный файл по относительному пути
```

### Генерируемые SVG-темы:
| Файл | Описание |
|------|----------|
| `profile-green.svg` | Классическая зелёная |
| `profile-green-animate.svg` | Зелёная с CSS-анимацией |
| `profile-season.svg` | Сезонная (Северное полушарие) |
| `profile-south-season.svg` | Сезонная (Южное полушарие) |
| `profile-night-view.svg` | Ночная, синий градиент |
| `profile-night-green.svg` | Ночная зелёная |
| **`profile-night-rainbow.svg`** | **✅ Используем — радуга на тёмном фоне** |
| `profile-gitblock.svg` | Git-блоки стиль |
| `profile-customize.svg` | Кастомная (если указан `SETTING_JSON`) |

---

## Конфигурация

### `.github/workflows/profile-3d-contrib.yml`
```yaml
name: GitHub-Profile-3D-Contrib

on:
  schedule:
    - cron: "0 0 * * *"  # Каждый день в 00:00 UTC = 03:00 MSK
  workflow_dispatch:      # Ручной запуск из Actions UI

permissions:
  contents: write         # ОБЯЗАТЕЛЬНО: action делает git push

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4  # v4 = Node 20, без Deprecation warnings

      - uses: yoshi389111/github-profile-3d-contrib@latest
        env:
          GITHUB_TOKEN: ${{ secrets.GH_TOKEN }}      # PAT для private repos contributions
          USERNAME: ${{ github.repository_owner }}   # Автоматически = "Igorvl"
          MAX_REPOS: 100                              # Учитывает до 100 репозиториев

      - name: Commit & Push
        run: |
          git config user.name github-actions
          git config user.email github-actions@github.com
          git add -A .
          # if-проверка: защита от пустого commit (без изменений) → не фейлит workflow
          if git commit -m "chore: auto-generate 3d contrib graph"; then
            git push
          fi
```

### В `README.md`:
```markdown
<div align="center">

<!-- Relative path: bypass GitHub Camo CDN cache -->
<img src="./profile-3d-contrib/profile-night-rainbow.svg" alt="3D Contribution Calendar" width="800">

</div>
```

> ⚠️ **Никогда не используй** `https://raw.githubusercontent.com/...` для SVG в профиле:
> - GitHub кеширует через Camo CDN  
> - Изображение не обновляется часами/днями  
> - Весь смысл «динамического» SVG теряется

---

## О `lowlighter/metrics` (почему убрали)

### Проблемы:
1. **Белый фон SVG (#ffffff)** — не совпадает с GitHub dark mode (`#0d1117`)
2. **Размер шрифта** — SVG внутри `<img>` рендерится в изоляции, шрифт не наследует 16px GitHub body
3. **Архивирован** — автор (lowlighter) заморозил проект в 2024, Node warnings растут
4. **Нет встроенного dark-mode пресета** — только `extras_css` хак

### extras_css фикс (если вдруг захочешь вернуть):
```yaml
extras_css: |
  .bg { fill: #0d1117 !important; }
  svg { background-color: #0d1117 !important; }
  text, tspan { fill: #e6edf3 !important; }
  .section-title > text { fill: #58a6ff !important; }
```
Workflow продолжает генерировать `github-metrics.svg` в репозиторий (cron активен).
Чтобы вернуть — добавь в README:
```markdown
<img src="./github-metrics.svg" alt="Metrics" width="800">
```

---

## Проблема с Camo CDN — подробнее

GitHub проксирует все внешние изображения через свой CDN (Camo) для безопасности.
Когда ты пишешь `https://raw.githubusercontent.com/Igorvl/.../file.svg` в README:
1. GitHub видит внешнюю ссылку → проксирует через Camo
2. Camo агрессивно кеширует → TTL может быть до 24+ часов
3. Даже если action перегенерировал SVG → пользователи видят старую версию

**Решение**: относительный путь `./file.svg` — GitHub рендерит его напрямую из репозитория, без Camo. Изображение обновляется сразу после коммита action.

---

*Последнее обновление: 2026-04-06*
