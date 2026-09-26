# 🤖 Behance AutoLiker — Инструкция по запуску

## Что делает скрипт

```
@Behavtop_bot присылает ссылку → скрипт открывает проект →
медленно скроллит → нажимает Appreciate → нажимает ✅Готово в боте
```

---

## ШАГ 1 — Получить Telegram API ключи

> Это делается **один раз**. Займёт 2 минуты.

1. Открой в браузере: **https://my.telegram.org**
2. Войди через номер телефона (тот аккаунт, который подписан на бота)
3. Нажми **"API development tools"**
4. Заполни форму:
   - **App title**: `BehanceAutoLiker`
   - **Short name**: `autoliker`
   - **Platform**: `Other`
5. Нажми **"Create application"**
6. Скопируй:
   - `App api_id` → это `TG_API_ID`
   - `App api_hash` → это `TG_API_HASH`

---

## ШАГ 2 — Создать файл .env

Скопируй `.env.example` → переименуй в `.env`, заполни:

```env
TG_API_ID=7654321
TG_API_HASH=abc123...

BEHANCE_EMAIL=igor@mail.ru
BEHANCE_PASSWORD=MyPass123

DELAY_MIN=4
DELAY_MAX=10
HEADLESS=false
```

---

## ШАГ 3 — Установить зависимости

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

---

## ШАГ 4 — Запустить

```powershell
python main.py
```

**При первом запуске:**
1. Откроется браузер с Behance → автоматический вход
2. Telegram попросит код — введи в консоль
3. После этого скрипт работает автоматически

---

## Структура

```
behance_autoliker/
├── .env                      ← ключи (НЕ В GIT!)
├── .env.example              ← шаблон
├── requirements.txt
├── main.py                   ← запуск
├── config.py
├── behance_liker.py          ← браузер + лайки
├── tg_listener.py            ← чтение бота
├── session/
│   └── behance_cookies.json  ← сессия Behance
├── behance_tg.session        ← сессия Telegram
├── likes_log.csv             ← лог лайков
└── autoliker.log             ← лог скрипта
```

---

## Таблица проблем

| Проблема | Решение |
|----------|---------|
| `ModuleNotFoundError` | Активируй `venv` |
| Браузер не открывается | `playwright install chromium` |
| Кнопка Appreciate не найдена | Обратись — исправим селекторы |
| Telegram просит код | Введи из SMS в консоль |
| Adobe 2FA / капча | Введи вручную в браузере |
