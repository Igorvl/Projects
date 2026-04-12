"""
Скрапинг appreciated-проектов Ксении и её комментариев.
Phase 1: Style Learning
"""
import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Page, BrowserContext

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    TARGET_PROFILE_URL, BEHANCE_BASE, SCREENSHOTS_DIR
)
from scraper.human import random_delay, scroll_to_bottom, human_move, micro_delay
from scraper.auth import BROWSER_ARGS, VIEWPORT, create_context
import database as db


# ─── Селекторы ────────────────────────────────────────────────────────────────
SEL_CARD     = "a.ContentGrid-gridItem-XZq, a[class*='ContentGrid-gridItem']"
SEL_TITLE    = "a.Title-title-lpJ, a[class*='Title-title']"
SEL_AUTHOR   = "a.Owners-owner-EEG, a[class*='Owners-owner']"
SEL_COVER    = "div.Cover-cover-S9_, div[class*='Cover-cover']"


def _extract_id(url: str) -> str | None:
    """Извлекаем числовой ID из /gallery/12345/slug"""
    m = re.search(r"/gallery/(\d+)/", url)
    return m.group(1) if m else None


async def _get_project_meta(page: Page, project_url: str) -> dict:
    """
    Заходим на страницу проекта, берём:
    - дату публикации
    - теги/категории
    - комментарий Ксении (если есть)
    """
    result = {"posted_at": None, "tags": [], "kseniya_comment": None}
    try:
        await page.goto(project_url, wait_until="domcontentloaded", timeout=30000)
        await random_delay(1.5, 3.5)

        # Дата публикации
        date_el = await page.query_selector(
            "time, [class*='ProjectDate'], [class*='date'], [datetime]"
        )
        if date_el:
            dt_attr = await date_el.get_attribute("datetime")
            if dt_attr:
                result["posted_at"] = dt_attr
            else:
                txt = await date_el.inner_text()
                result["posted_at"] = txt.strip()

        # Теги
        tag_els = await page.query_selector_all(
            "a[href*='/search?search='], a[class*='Tag'], a[class*='tag']"
        )
        tags = []
        for el in tag_els[:15]:
            t = (await el.inner_text()).strip()
            if t:
                tags.append(t)
        result["tags"] = tags

        # Ищем комментарий Ксении
        # Скроллим к комментариям
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
        await random_delay(1, 2)

        comments_block = await page.query_selector_all(
            "[class*='Comment'], [class*='comment']"
        )
        for block in comments_block:
            # Ищем имя автора
            author_el = await block.query_selector(
                "a[href*='kseniyaartman'], [class*='username'], [class*='commentAuthor']"
            )
            if not author_el:
                text = await block.inner_text()
                if "kseniyaartman" in text.lower():
                    author_el = block

            if author_el:
                # Берём текст комментария
                comment_text_el = await block.query_selector(
                    "[class*='commentText'], [class*='CmtText'], p"
                )
                if comment_text_el:
                    result["kseniya_comment"] = (await comment_text_el.inner_text()).strip()
                else:
                    result["kseniya_comment"] = (await block.inner_text()).strip()
                break

    except Exception as e:
        print(f"    [meta] Ошибка для {project_url}: {e}")

    return result


async def _screenshot_cover(page: Page, project_url: str, behance_id: str) -> str | None:
    """Скриншот обложки проекта."""
    try:
        cover_el = await page.query_selector(
            "figure img, [class*='Cover'] img, [class*='ProjectCoverImage'] img"
        )
        if not cover_el:
            # Скриншот всего вьюпорта
            path = SCREENSHOTS_DIR / f"{behance_id}.png"
            await page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": 1440, "height": 600})
        else:
            path = SCREENSHOTS_DIR / f"{behance_id}.png"
            await cover_el.screenshot(path=str(path))
        db.update_screenshot(behance_id, str(path))
        return str(path)
    except Exception as e:
        print(f"    [screenshot] Ошибка: {e}")
        return None


async def scrape_appreciated(max_projects: int = 200, save_comments: bool = True):
    """
    Главная функция Phase 1:
    - Скроллит /kseniyaartman/appreciated
    - Для каждого проекта: сохраняет метаданные, скрин, комментарий Ксении
    """
    print(f"\n[Appreciated] Старт. Цель: до {max_projects} проектов")
    print(f"[Appreciated] URL: {TARGET_PROFILE_URL}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        ctx = await create_context(browser)
        page = await ctx.new_page()

        # Открываем appreciated
        await page.goto(TARGET_PROFILE_URL, wait_until="domcontentloaded", timeout=30000)
        await random_delay(3, 5)

        # Скроллим чтобы загрузить все проекты
        print("[Appreciated] Скроллим страницу...")
        iters = await scroll_to_bottom(page, max_iterations=20)
        print(f"[Appreciated] Прокрутили {iters} итераций")
        await random_delay(2, 3)

        # Собираем все карточки
        cards = await page.query_selector_all(SEL_CARD)
        print(f"[Appreciated] Найдено карточек: {len(cards)}")

        projects_data = []
        for card in cards:
            try:
                href = await card.get_attribute("href")
                if not href or "/gallery/" not in href:
                    continue
                full_url = href if href.startswith("http") else BEHANCE_BASE + href

                title_el = await card.query_selector(SEL_TITLE)
                title = (await title_el.inner_text()).strip() if title_el else ""

                author_el = await card.query_selector(SEL_AUTHOR)
                author_text = (await author_el.inner_text()).strip() if author_el else ""
                author_href  = await author_el.get_attribute("href") if author_el else ""
                author_url   = (BEHANCE_BASE + author_href) if author_href and not author_href.startswith("http") else author_href

                behance_id = _extract_id(full_url)
                if not behance_id:
                    continue

                projects_data.append({
                    "behance_id":  behance_id,
                    "behance_url": full_url,
                    "title":       title,
                    "author_name": author_text,
                    "author_url":  author_url,
                    "cover_url":   "",
                    "tags":        "[]",
                    "posted_at":   None,
                })
            except Exception as e:
                print(f"  [card] Ошибка: {e}")
                continue

        print(f"[Appreciated] Обрабатываем {min(len(projects_data), max_projects)} проектов...")

        new_count    = 0
        comment_count = 0

        for i, proj in enumerate(projects_data[:max_projects], 1):
            print(f"  [{i}/{min(len(projects_data), max_projects)}] {proj['title'][:50]}")

            # Переходим на проект
            meta = await _get_project_meta(page, proj["behance_url"])
            await random_delay(1.5, 3.0)

            # Обновляем данные
            proj["posted_at"] = meta["posted_at"]
            proj["tags"]      = json.dumps(meta["tags"])

            # Скрин обложки
            screenshot = await _screenshot_cover(page, proj["behance_url"], proj["behance_id"])

            # Сохраняем проект
            is_new = db.save_project(proj)
            if is_new:
                new_count += 1

            if screenshot:
                db.update_screenshot(proj["behance_id"], screenshot)

            # Сохраняем комментарий Ксении как обучающий пример
            if save_comments and meta.get("kseniya_comment"):
                db.save_style_sample(proj["behance_url"], meta["kseniya_comment"])
                comment_count += 1
                print(f"    💬 Комментарий сохранён: {meta['kseniya_comment'][:60]}...")

            await random_delay()  # человеческая пауза между проектами

        await browser.close()

    samples_total = len(db.get_style_samples(200))
    print(f"\n[Appreciated] ✅ Готово!")
    print(f"  Новых проектов: {new_count}")
    print(f"  Комментариев найдено: {comment_count}")
    print(f"  Всего обучающих примеров: {samples_total}")
    return new_count, comment_count
