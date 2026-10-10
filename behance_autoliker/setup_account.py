"""
setup_account.py -- Мастер настройки и валидации аккаунтов.

Использование:
  python setup_account.py --status
      Показать текущий статус авторизации всех аккаунтов.

  1. Авторизация Telegram:
      python setup_account.py --account ksar_be --tg
      (ввод телефона и SMS кода)

  2. Получение cookies Behance (выберите любой удобный способ):
      Способ 1 (Самый простой -- войти через окно браузера):
          python setup_account.py --account ksar_be --login

      Способ 2 (Авто-экспорт из Chrome или Edge, если вы там уже залогинены):
          python setup_account.py --account ksar_be --chrome
          python setup_account.py --account ksar_be --edge

      Способ 3 (Импорт JSON-файла из Cookie-Editor):
          python setup_account.py --account ksar_be --import-cookies "путь_к_файлу.json"
"""

import sys
import os
import argparse
import asyncio
import json
import shutil

# Принудительно UTF-8 для консоли
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from accounts_config import get_account_config, ALL_ACCOUNTS
from telethon import TelegramClient

TARGET_DOMAINS = ["behance.net", "adobe.com", "adobelogin.com", "account.adobe.com"]


async def auth_telegram(account_id: str) -> None:
    config = get_account_config(account_id)
    print("=" * 60)
    print(f"  Авторизация Telegram для аккаунта: {config.name} ({account_id})")
    print(f"  Файл сессии: {config.tg_session_path}")
    print("=" * 60)

    proxy = None
    if config.tg_proxy_host and config.tg_proxy_port:
        import socks
        proxy_type = socks.SOCKS5 if config.tg_proxy_type == "socks5" else socks.HTTP
        proxy = (
            proxy_type,
            config.tg_proxy_host,
            config.tg_proxy_port,
            True,
            config.tg_proxy_user or None,
            config.tg_proxy_pass or None,
        )
        print(f"  Используется прокси: {config.tg_proxy_type}://{config.tg_proxy_host}:{config.tg_proxy_port}")

    parent = os.path.dirname(os.path.abspath(config.tg_session_path))
    os.makedirs(parent, exist_ok=True)

    client = TelegramClient(
        config.tg_session_path,
        config.tg_api_id,
        config.tg_api_hash,
        proxy=proxy,
    )

    await client.start()
    me = await client.get_me()
    print()
    print("  " + "✅" * 15)
    print(f"  УСПЕХ! Авторизован аккаунт Telegram:")
    print(f"  Имя: {me.first_name} {me.last_name or ''}")
    print(f"  Username: @{me.username}" if me.username else f"  ID: {me.id}")
    print(f"  Телефон: +{me.phone}" if me.phone else "")
    print(f"  Файл сохранён: {config.tg_session_path}")
    print("  " + "✅" * 15)
    await client.disconnect()


async def interactive_browser_login(account_id: str) -> None:
    """Открывает видимое окно браузера Playwright, дает войти и сохраняет куки."""
    from playwright.async_api import async_playwright

    config = get_account_config(account_id)
    dest_path = config.behance_cookies_path
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

    print("=" * 65)
    print(f"  ВХОД В BEHANCE ЧЕРЕЗ БРАУЗЕР: {config.name}")
    print("=" * 65)
    print("  Сейчас откроется окно Chrome.")
    print("  1. Войдите в свой аккаунт Behance (Adobe ID).")
    print("  2. Убедитесь, что вы видите свою аватарку на главной Behance.")
    print("  3. Вернитесь сюда в консоль и нажмите [ENTER] для сохранения сессии.")
    print("=" * 65)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await page.goto("https://www.behance.net", wait_until="domcontentloaded")

        # Ждем действия пользователя в консоли
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input, "\n👉 После успешного входа на Behance нажмите [ENTER] здесь в консоли: ")

        # Сохраняем сессию
        await context.storage_state(path=dest_path)
        await browser.close()

    print()
    print("  " + "✅" * 15)
    print(f"  Сессия Behance успешно сохранена в: {dest_path}")
    print("  " + "✅" * 15)


def export_from_browser(account_id: str, browser_type: str = "chrome") -> None:
    """Экспортирует cookies из установленного браузера с помощью rookiepy."""
    try:
        import rookiepy
    except ImportError:
        print("❌ Не установлена библиотека rookiepy. Запустите: pip install rookiepy")
        return

    config = get_account_config(account_id)
    dest_path = config.behance_cookies_path
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

    print(f"  Читаю куки Behance из браузера {browser_type.capitalize()}...")
    get_cookies_fn = getattr(rookiepy, browser_type.lower(), None)
    if not get_cookies_fn:
        print(f"❌ Неизвестный браузер: {browser_type}")
        return

    all_cookies = []
    for domain in TARGET_DOMAINS:
        try:
            cookies = get_cookies_fn([domain])
            all_cookies.extend(cookies)
            print(f"   ├─ [{domain}]: найдено {len(cookies)} cookies")
        except Exception as e:
            print(f"   ├─ [{domain}]: пропущено ({e})")

    if not all_cookies:
        print()
        print(f"❌ Cookies не найдены в {browser_type.capitalize()}!")
        print("   Убедитесь, что вы залогинены в Behance в этом браузере и браузер закрыт.")
        return

    playwright_cookies = []
    for c in all_cookies:
        domain = c.get("host", c.get("domain", ""))
        name = c.get("name", "")
        value = c.get("value", "")
        if not name or not value:
            continue
        expires = c.get("expires", -1)
        try:
            expires = float(expires) if expires and float(expires) > 0 else -1
        except Exception:
            expires = -1

        playwright_cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": c.get("path", "/"),
            "expires": expires,
            "httpOnly": bool(c.get("httpOnly", False)),
            "secure": bool(c.get("secure", False)),
            "sameSite": "Lax",
        })

    storage_state = {"cookies": playwright_cookies, "origins": []}
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2, ensure_ascii=False)

    print()
    print("  " + "✅" * 15)
    print(f"  УСПЕХ! Импортировано {len(playwright_cookies)} cookies из {browser_type.capitalize()}!")
    print(f"  Файл сохранён: {dest_path}")
    print("  " + "✅" * 15)


def import_cookies_file(account_id: str, src_path: str) -> None:
    """Импортирует JSON cookies (Cookie-Editor или Playwright storage_state)."""
    config = get_account_config(account_id)
    if not os.path.exists(src_path):
        print(f"❌ Файл не найден: {src_path}")
        return

    dest_path = config.behance_cookies_path
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)

    try:
        with open(src_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения JSON: {e}")
        return

    # Если уже в формате Playwright storage_state
    if isinstance(data, dict) and "cookies" in data:
        shutil.copy2(src_path, dest_path)
        print(f"✅ Готовый Playwright storage_state сохранён: {dest_path}")
        return

    # Если сырой массив из Cookie-Editor
    if isinstance(data, list):
        playwright_cookies = []
        same_site_map = {
            "no_restriction": "None",
            "lax": "Lax",
            "strict": "Strict",
            "unspecified": "Lax",
        }
        for c in data:
            name = c.get("name", "")
            value = c.get("value", "")
            if not name or not value:
                continue
            domain = c.get("domain", "")
            expires = c.get("expirationDate", -1)
            raw_same_site = (c.get("sameSite") or "lax").lower()
            same_site = same_site_map.get(raw_same_site, "Lax")

            playwright_cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": c.get("path", "/"),
                "expires": float(expires) if expires and float(expires) > 0 else -1,
                "httpOnly": bool(c.get("httpOnly", False)),
                "secure": bool(c.get("secure", False)),
                "sameSite": same_site,
            })

        storage_state = {"cookies": playwright_cookies, "origins": []}
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(storage_state, f, indent=2, ensure_ascii=False)
        print(f"✅ Импортировано и сконвертировано {len(playwright_cookies)} cookies -> {dest_path}")
        return

    print("❌ Неизвестный формат JSON файла.")


def print_status() -> None:
    print("=" * 65)
    print("   СТАТУС АККАУНТОВ BEHANCE AUTOLIKER")
    print("=" * 65)

    for acc_id in ALL_ACCOUNTS:
        cfg = get_account_config(acc_id)
        tg_ok = os.path.exists(cfg.tg_session_path)
        be_ok = os.path.exists(cfg.behance_cookies_path)
        rate_ok = os.path.exists(cfg.rate_state_path)

        tg_icon = "✅ Готово" if tg_ok else "❌ Не авторизован"
        be_icon = "✅ Файл есть" if be_ok else "❌ Нет файла cookies"

        print(f"• Аккаунт: {cfg.name} (id: {acc_id})")
        print(f"   ├─ Telegram: {tg_icon} ({cfg.tg_session_path})")
        print(f"   ├─ Behance:  {be_icon} ({cfg.behance_cookies_path})")
        print(f"   └─ Лимиты:   {'✅ Инициализированы' if rate_ok else '⏳ Начнутся с 0'}")
        print()
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Управление аккаунтами Behance AutoLiker")
    parser.add_argument("--status", action="store_true", help="Показать статус аккаунтов")
    parser.add_argument("--account", choices=ALL_ACCOUNTS, help="Выбрать аккаунт (ksar_lab / ksar_be)")
    parser.add_argument("--tg", action="store_true", help="Авторизовать Telegram сессию")
    parser.add_argument("--login", action="store_true", help="Открыть окно браузера и войти в Behance")
    parser.add_argument("--chrome", action="store_true", help="Авто-экспорт куков из Chrome")
    parser.add_argument("--edge", action="store_true", help="Авто-экспорт куков из Edge")
    parser.add_argument("--import-cookies", dest="cookies_src", help="Импортировать cookies из JSON-файла")

    args = parser.parse_args()

    if args.status or len(sys.argv) == 1:
        print_status()
        return

    if args.account:
        if args.tg:
            asyncio.run(auth_telegram(args.account))
            return
        if args.login:
            asyncio.run(interactive_browser_login(args.account))
            return
        if args.chrome:
            export_from_browser(args.account, "chrome")
            return
        if args.edge:
            export_from_browser(args.account, "edge")
            return
        if args.cookies_src:
            import_cookies_file(args.account, args.cookies_src)
            return

    parser.print_help()


if __name__ == "__main__":
    main()
