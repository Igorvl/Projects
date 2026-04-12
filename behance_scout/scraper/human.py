"""
Human-like browser behaviour — задержки, скролл, движения мыши
"""
import asyncio
import random
from playwright.async_api import Page
from config import DELAY_MIN, DELAY_MAX, SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX


async def random_delay(min_s: float = DELAY_MIN, max_s: float = DELAY_MAX):
    """Случайная пауза как у живого пользователя."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def micro_delay():
    """Очень короткая пауза между действиями (typing, hover)."""
    await asyncio.sleep(random.uniform(0.05, 0.25))


async def human_move(page: Page, x: int, y: int):
    """Плавное движение мыши через промежуточные точки."""
    cur = await page.evaluate("() => ({x: window.mouseX || 0, y: window.mouseY || 0})")
    steps = random.randint(5, 15)
    cx, cy = cur.get("x", 0), cur.get("y", 0)
    for i in range(1, steps + 1):
        nx = cx + (x - cx) * i / steps + random.randint(-3, 3)
        ny = cy + (y - cy) * i / steps + random.randint(-3, 3)
        await page.mouse.move(nx, ny)
        await asyncio.sleep(random.uniform(0.01, 0.04))


async def human_scroll(page: Page, total_px: int = 3000, chunk_min: int = 200, chunk_max: int = 600):
    """
    Скроллит страницу вниз «по-человечески»:
    случайными порциями с паузами между ними.
    """
    scrolled = 0
    while scrolled < total_px:
        chunk = random.randint(chunk_min, chunk_max)
        await page.mouse.wheel(0, chunk)
        scrolled += chunk
        await asyncio.sleep(random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX))


async def scroll_to_bottom(page: Page, max_iterations: int = 30) -> int:
    """
    Скроллит до конца страницы с infinite scroll.
    Возвращает примерное кол-во итераций.
    Останавливается если высота страницы перестала расти.
    """
    prev_height = 0
    no_change_count = 0
    iteration = 0

    for iteration in range(max_iterations):
        height = await page.evaluate("document.body.scrollHeight")
        if height == prev_height:
            no_change_count += 1
            if no_change_count >= 3:
                break
        else:
            no_change_count = 0
        prev_height = height

        chunk = random.randint(500, 900)
        await page.mouse.wheel(0, chunk)
        pause = random.uniform(SCROLL_PAUSE_MIN, SCROLL_PAUSE_MAX * 1.5)
        await asyncio.sleep(pause)

    return iteration


async def human_type(page: Page, selector: str, text: str):
    """Вводит текст с человеческой скоростью (случайные задержки между символами)."""
    await page.click(selector)
    await micro_delay()
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.04, 0.18))
