# Настройка "Pro" профиля GitHub (3D Contrib & Metrics)

## Идея
Для усиления визуального впечатления от GitHub-профиля (особенно для MLOps / DevOps резюме), мы оформили высокотехнологичный `README.md`, который динамически обновляется. Главная цель — показать хардкорные навыки (Python, Shell, Docker), скрыть "простои" в коммитах и отфильтровать фронтенд-языки (HTML, CSS), чтобы профиль выглядел строго и профессионально.

## Окончательное решение: lowlighter/metrics (Self-Hosted Action)

В процессе настройки мы столкнулись с проблемами:
1. **API `github-readme-stats` на Vercel** (изначальный вариант) оказался ненадежным — публичные инстансы регулярно падают от сбоев и Rate Limits (ошибка `503 DEPLOYMENT_PAUSED`).
2. **Экшен `yoshi389111/github-profile-3d-contrib`** рисует красивый город, но **строго за 365 дней**. Если были большие перерывы в коммитах, график выглядит пустым. Ошибка 128 (отсутствие прав `contents: write`) и Warnings (Node 20) также требовали правок.
3. **Кэширование SVG в GitHub (Camo)**: любые прямые ссылки `raw.githubusercontent.com` кэшируются. Решение: использовать **относительные пути** в markdown (`<img src="github-metrics.svg">`).
4. **Проблема со шрифтами SVG**: Браузеры помещают SVG внутри `<img>` в песочницу, не давая доступ к системным веб-шрифтам. Чтобы SVG-метрики выглядели "родными" для GitHub, мы прописали жесткий стек шрифтов в конфигурации.

### Идеальный конфиг (metrics.yml)
Мы остановились на едином экшене `lowlighter/metrics`, который решает все проблемы одним ударом:
- Отключили громоздкий модуль активности (`base: ""`).
- Отрисовали изометрический 3D-календарь, но **строго на полгода** (`plugin_isocalendar_duration: half-year`), чтобы скрыть неактивные периоды.
- Включили парсинг языков (`plugin_languages`), но жестко отфильтровали мусор (`plugin_languages_ignored: html, css, javascript, jupyter notebook, svg`).
- Добавили системные шрифты GitHub.

```yaml
name: Metrics
on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

jobs:
  github-metrics:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: lowlighter/metrics@latest
        with:
          token: ${{ secrets.GH_TOKEN }}
          user: ${{ github.repository_owner }}
          template: classic
          base: ""
          config_timezone: Europe/Moscow
          config_font: "-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif"
          
          # Круговая диаграмма языков с фильтром
          plugin_languages: yes
          plugin_languages_ignored: html, css, javascript, jupyter notebook, svg
          plugin_languages_limit: 4
          
          # 3D "Город" на полгода
          plugin_isocalendar: yes
          plugin_isocalendar_duration: half-year
```

## Интеграция в профиль
1. Файл сохраняется как `.github/workflows/metrics.yml`.
2. В самом `README.md` вставляется строка с относительным путем (для обхода CDN кэша):
   `<img src="github-metrics.svg" alt="Metrics" width="800">`

## Дополнительно для дизайна:
- Иконки и бейджи: использовать `shields.io` (например, `![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)`).
- Эмодзи: 🚀 🛠️ 📫
