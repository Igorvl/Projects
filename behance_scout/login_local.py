"""
Запускается ЛОКАЛЬНО на Windows для получения Behance-сессии.

Установка (один раз):
    pip install playwright
    playwright install chromium

Запуск:
    python login_local.py

После логина session.json скопируй на сервер:
    scp session.json igorvl@172.25.9.33:/home/igorvl/ai-design-workspace/behance_scout/data/session.json
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SESSION_OUT = Path("session.json")

BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
]


async def main():
    print("=" * 60)
    print("  BEHANCE LOGIN — локальный браузер")
    print("=" * 60)
    print()
    print("1. Откроется Chrome")
    print("2. Войди в Behance с аккаунтом antiswindler7@gmail.com")
    print("3. После успешного входа вернись сюда и нажми Enter")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=BROWSER_ARGS,
            slow_mo=50,
        )
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        # Скрываем webdriver
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        page = await ctx.new_page()
        await page.goto("https://www.behance.net/login")

        print("Браузер открыт. Войди и нажми Enter...")
        input()

        # Проверяем логин
        await page.goto("https://www.behance.net")
        await asyncio.sleep(2)

        # Сохраняем сессию
        await ctx.storage_state(path=str(SESSION_OUT))
        print(f"\n✅ Сессия сохранена → {SESSION_OUT.absolute()}")
        print()
        print("Теперь скопируй файл на сервер:")
        print(f'  scp {SESSION_OUT.absolute()} igorvl@172.25.9.33:/home/igorvl/ai-design-workspace/behance_scout/data/session.json')
        print()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
