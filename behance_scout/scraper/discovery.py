"""
Phase 2: Discovery — поиск новых проектов в стиле Ксении.

Алгоритм:
1. Извлекаем топ-теги из базы (из её appreciated проектов)
2. Ищем на Behance по этим тегам свежие проекты
3. Фильтруем дубликаты (уже есть в БД)
4. Сохраняем новые проекты + делаем скрин обложки
"""
import asyncio
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import async_playwright, Page

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BEHANCE_BASE, SCREENSHOTS_DIR, DB_PATH,
    DAILY_TARGET,
)
from scraper.human import random_delay, scroll_to_bottom, human_move, micro_delay
from scraper.auth import BROWSER_ARGS, VIEWPORT, create_context
import database as db


# ── Категории Behance для поиска (как fallback если мало тегов) ────────────────
DEFAULT_SEARCH_TERMS = [
    "brand identity", "visual identity", "logo design",
    "typography poster", "motion design branding",
    "packaging design", "editorial design",
]

# Минимум дней назад — берём только свежие (до 9 мес)
MAX_AGE_DAYS = 270


def get_top_tags(limit: int = 15) -> list[str]:
    """Извлекаем самые частые теги из базы appreciated-проектов."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT tags FROM projects WHERE tags IS NOT NULL AND tags != '[]'"
    ).fetchall()
    conn.close()

    counter = Counter()
    for row in rows:
        try:
            tags = json.loads(row[0])
            for t in tags:
                t = t.strip().lower()
                if 2 < len(t) < 40:
                    counter[t] += 1
        except Exception:
            pass

    # Берём теги с частотой ≥ 2
    top = [tag for tag, cnt in counter.most_common(limit) if cnt >= 2]
    if not top:
        top = DEFAULT_SEARCH_TERMS[:5]
    return top


def _extract_id(url: str) -> str | None:
    m = re.search(r"/gallery/(\d+)/", url)
    return m.group(1) if m else None


def _parse_behance_date(raw: str | None) -> str | None:
    """Парсит дату Behance в ISO формат."""
    if not raw:
        return None
    raw = raw.strip()
    
    # ISO datetime атрибут: "2025-01-15T10:30:00.000Z"
    m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return m.group(1)

    # Относительные: "2 months ago", "3 days ago", "1 year ago"
    now = datetime.utcnow()
    rel = raw.lower()
    try:
        if "just now" in rel or "second" in rel:
            return now.date().isoformat()
        m = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", rel)
        if m:
            n, unit = int(m.group(1)), m.group(2)
            delta_map = {
                "second": timedelta(seconds=n),
                "minute": timedelta(minutes=n),
                "hour":   timedelta(hours=n),
                "day":    timedelta(days=n),
                "week":   timedelta(weeks=n),
                "month":  timedelta(days=n * 30),
                "year":   timedelta(days=n * 365),
            }
            return (now - delta_map[unit]).date().isoformat()
    except Exception:
        pass

    # "January 5, 2025" или "Jan 5, 2025"
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass

    return None


async def _get_project_meta_fast(page: Page, url: str) -> dict:
    """Быстрый сбор метаданных проекта (дата + теги + скриншот)."""
    result = {"posted_at": None, "tags": []}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await random_delay(1.0, 2.5)

        # Ищем <time> с datetime атрибутом
        time_el = await page.query_selector("time[datetime]")
        if time_el:
            raw = await time_el.get_attribute("datetime")
            result["posted_at"] = _parse_behance_date(raw)
        
        # Если нет — ищем по тексту
        if not result["posted_at"]:
            for selector in [
                "[class*='ProjectDate']",
                "[class*='date']",
                "[class*='Date']",
                "time",
            ]:
                el = await page.query_selector(selector)
                if el:
                    txt = (await el.inner_text()).strip()
                    parsed = _parse_behance_date(txt)
                    if parsed:
                        result["posted_at"] = parsed
                        break

        # Теги
        tag_els = await page.query_selector_all(
            "a[href*='/search?search='], "
            "a[href*='field='], "
            "a[class*='Tag'], "
            "a[class*='tag']"
        )
        tags = []
        for el in tag_els[:12]:
            t = (await el.inner_text()).strip()
            if t and 1 < len(t) < 40:
                tags.append(t)
        result["tags"] = list(set(tags))

    except Exception as e:
        print(f"    [meta] {e}")
    return result


async def _screenshot_project(page: Page, behance_id: str) -> str | None:
    """Скриншот обложки проекта."""
    try:
        path = SCREENSHOTS_DIR / f"{behance_id}.png"
        # Пробуем найти главное изображение
        img_el = await page.query_selector(
            "figure img, "
            "[class*='Cover'] img, "
            "[class*='ProjectImage'] img, "
            "[class*='projectCover'] img"
        )
        if img_el:
            await img_el.screenshot(path=str(path))
        else:
            # Скриншот верхней части страницы
            await page.screenshot(
                path=str(path),
                clip={"x": 0, "y": 0, "width": 1440, "height": 560}
            )
        return str(path)
    except Exception as e:
        print(f"    [screenshot] {e}")
        return None


async def _search_behance(page: Page, query: str, limit: int = 30) -> list[dict]:
    """Ищет проекты на Behance по запросу."""
    url = f"{BEHANCE_BASE}/search/projects?search={query.replace(' ', '+')}&sort=publishedDate"
    results = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await random_delay(2, 4)

        # Скроллим чтобы загрузить больше
        await scroll_to_bottom(page, max_iterations=5)
        await random_delay(1, 2)

        # Собираем карточки
        cards = await page.query_selector_all(
            "a[href*='/gallery/'], "
            "a.ContentGrid-gridItem-XZq, "
            "a[class*='ContentGrid-gridItem']"
        )
        seen_ids = set()
        for card in cards:
            try:
                href = await card.get_attribute("href")
                if not href or "/gallery/" not in href:
                    continue
                full_url = href if href.startswith("http") else BEHANCE_BASE + href
                bid = _extract_id(full_url)
                if not bid or bid in seen_ids:
                    continue
                seen_ids.add(bid)

                title_el = await card.query_selector(
                    "a[class*='Title'], a[class*='title'], [class*='title']"
                )
                title = (await title_el.inner_text()).strip() if title_el else ""

                author_el = await card.query_selector(
                    "a[class*='Owners'], a[class*='owner']"
                )
                author = (await author_el.inner_text()).strip() if author_el else ""
                author_href = await author_el.get_attribute("href") if author_el else ""
                author_url = (BEHANCE_BASE + author_href) if author_href and not author_href.startswith("http") else author_href

                results.append({
                    "behance_id":  bid,
                    "behance_url": full_url,
                    "title":       title,
                    "author_name": author,
                    "author_url":  author_url or "",
                    "cover_url":   "",
                    "tags":        "[]",
                    "posted_at":   None,
                })
                if len(results) >= limit:
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"  [search] Ошибка поиска '{query}': {e}")
    return results


async def discover_new_projects(target: int = DAILY_TARGET):
    """
    Главная функция Phase 2:
    - Получает теги из БД
    - Ищет новые проекты на Behance
    - Сохраняет в БД с метаданными и скринами
    """
    print(f"\n[Discovery] Старт. Цель: {target} новых проектов")

    # Получаем уже известные ID
    conn = sqlite3.connect(DB_PATH)
    known_ids = set(
        r[0] for r in conn.execute("SELECT behance_id FROM projects").fetchall()
    )
    conn.close()
    print(f"[Discovery] Уже в БД: {len(known_ids)} проектов")

    # Топ-теги из appreciated
    tags = get_top_tags(limit=12)
    print(f"[Discovery] Теги для поиска: {tags[:8]}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        ctx = await create_context(browser)
        page = await ctx.new_page()

        candidates = []
        per_tag = max(3, target // len(tags) + 2)

        for tag in tags:
            if len(candidates) >= target * 2:
                break
            print(f"\n  🔍 Поиск: '{tag}'")
            found = await _search_behance(page, tag, limit=per_tag)
            new_found = [p for p in found if p["behance_id"] not in known_ids]
            
            # Добавляем только уникальные
            existing_ids = {c["behance_id"] for c in candidates}
            for proj in new_found:
                if proj["behance_id"] not in existing_ids:
                    candidates.append(proj)
                    existing_ids.add(proj["behance_id"])
            
            print(f"    Найдено: {len(found)}, новых: {len(new_found)}")
            await random_delay(2, 5)

        print(f"\n[Discovery] Кандидатов для обработки: {len(candidates)}")

        saved = 0
        skipped_old = 0

        for i, proj in enumerate(candidates[:target * 2], 1):
            if saved >= target:
                break

            print(f"  [{i}/{min(len(candidates), target*2)}] {proj['title'][:50] or proj['behance_url']}")

            # Получаем метаданные
            meta = await _get_project_meta_fast(page, proj["behance_url"])
            proj["posted_at"] = meta["posted_at"]
            proj["tags"]      = json.dumps(meta["tags"])

            # Фильтр по возрасту — пропускаем слишком старые
            if proj["posted_at"]:
                try:
                    age = (datetime.utcnow() - datetime.fromisoformat(proj["posted_at"])).days
                    if age > MAX_AGE_DAYS:
                        print(f"    ⏭  Слишком старый ({age} дней) — пропуск")
                        skipped_old += 1
                        continue
                except Exception:
                    pass

            # Скриншот
            screenshot = await _screenshot_project(page, proj["behance_id"])
            
            # Сохраняем
            is_new = db.save_project(proj)
            if is_new:
                if screenshot:
                    db.update_screenshot(proj["behance_id"], screenshot)
                saved += 1
                age_str = f"{proj['posted_at']}" if proj["posted_at"] else "дата неизвестна"
                print(f"    ✅ Сохранён ({age_str})")
            else:
                print(f"    ⏭  Уже в БД")

            await random_delay()

        await browser.close()

    print(f"\n[Discovery] ✅ Готово!")
    print(f"  Сохранено новых: {saved}")
    print(f"  Пропущено (старые): {skipped_old}")
    return saved
