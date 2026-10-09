"""
setup_account.py -- Мастер настройки и валидации аккаунтов.

Использование:
  python setup_account.py --status
      Показать текущий статус авторизации всех аккаунтов.

  python setup_account.py --account ksar_be --tg
      Авторизовать Telegram-сессию для аккаунта ksar_be (ввод телефона и SMS кода).

  python setup_account.py --account ksar_lab --tg
      Авторизовать Telegram-сессию для ksar_lab.

  python setup_account.py --account ksar_be --import-cookies path/to/cookies.json
      Импортировать готовые cookies Behance в профиль аккаунта.
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


def import_cookies(account_id: str, src_path: str) -> None:
    config = get_account_config(account_id)
    if not os.path.exists(src_path):
        print(f"❌ Файл не найден: {src_path}")
        return

    dest_path = config.behance_cookies_path
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    shutil.copy2(src_path, dest_path)
    print(f"✅ Cookies успешно скопированы: {dest_path}")


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
    parser.add_argument("--import-cookies", dest="cookies_src", help="Импортировать cookies из указанного файла")

    args = parser.parse_args()

    if args.status or len(sys.argv) == 1:
        print_status()
        return

    if args.account:
        if args.tg:
            asyncio.run(auth_telegram(args.account))
            return
        if args.cookies_src:
            import_cookies(args.account, args.cookies_src)
            return

    parser.print_help()


if __name__ == "__main__":
    main()
