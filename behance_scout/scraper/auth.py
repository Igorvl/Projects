"""
Авторизация в Behance через сохранённую сессию.

Первый запуск (ручной логин):
    python run.py --login
→ Открывает браузер с GUI, пользователь логинится через Google,
  сессия сохраняется в data/session.json.

Последующие запуски используют сохранённую сессию.
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SESSION_FILE, BEHANCE_BASE
from scraper.human import random_delay


BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-extensions-except=",  # без расширений
]

VIEWPORT = {"width": 1440, "height": 900}


async def create_context(browser: Browser, headless: bool = True) -> BrowserContext:
    """Создаёт контекст с сохранённой сессией (если есть)."""
    kwargs = {
        "viewport": VIEWPORT,
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "locale": "en-US",
        "timezone_id": "Europe/Helsinki",
        "extra_http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if SESSION_FILE.exists():
        kwargs["storage_state"] = str(SESSION_FILE)
        print(f"[Auth] Загружена сессия из {SESSION_FILE}")
    else:
        print("[Auth] Сессия не найдена — нужен --login")

    ctx = await browser.new_context(**kwargs)

    # Скрываем признаки Playwright
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        window.chrome = { runtime: {} };
    """)
    return ctx


async def save_session(context: BrowserContext):
    await context.storage_state(path=str(SESSION_FILE))
    print(f"[Auth] Сессия сохранена → {SESSION_FILE}")


async def login_flow():
    """
    Интерактивный логин — запускает видимый браузер,
    ждёт пока пользователь залогинится, сохраняет сессию.
    """
    print("\n" + "="*60)
    print("  РУЧНОЙ ЛОГИН В BEHANCE")
    print("  1. Откроется браузер")
    print("  2. Войдите через Google (antiswindler7@gmail.com)")
    print("  3. После входа нажмите Enter в этом терминале")
    print("="*60 + "\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=BROWSER_ARGS,
        )
        ctx = await browser.new_context(
            viewport=VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()
        await page.goto(f"{BEHANCE_BASE}/login?original_uri=%2F")
        await random_delay(2, 4)

        # Нажимаем кнопку входа через Google
        try:
            await page.click('a[href*="google"]', timeout=5000)
        except Exception:
            print("[Auth] Кнопка Google не найдена автоматически — войдите вручную")

        print("\n[Auth] Войдите в браузере, затем нажмите Enter...")
        input()

        # Проверяем что залогинились
        await page.goto(BEHANCE_BASE)
        await random_delay(2, 3)
        is_logged = await page.evaluate(
            "() => !!document.querySelector('[data-testid=\"user-avatar\"]') || "
            "!!document.querySelector('.user-avatar')"
        )
        if is_logged:
            print("[Auth] ✅ Успешно залогинились!")
        else:
            print("[Auth] ⚠️ Не удалось определить статус. Сохраняем сессию в любом случае.")

        await save_session(ctx)
        await browser.close()


async def check_session() -> bool:
    """Проверяет что сохранённая сессия ещё активна."""
    if not SESSION_FILE.exists():
        return False
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        ctx = await create_context(browser)
        page = await ctx.new_page()
        try:
            await page.goto(BEHANCE_BASE, timeout=15000)
            await random_delay(1, 2)
            is_logged = await page.evaluate(
                "() => document.cookie.includes('bcp') || "
                "!!document.querySelector('[data-testid=\"user-avatar\"]')"
            )
            await browser.close()
            return bool(is_logged)
        except Exception as e:
            print(f"[Auth] Ошибка проверки сессии: {e}")
            await browser.close()
            return False
