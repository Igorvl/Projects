# -*- coding: utf-8 -*-
"""
Phase 2: Discovery — поиск новых проектов в стиле Ксении.

Алгоритм:
1. Извлекаем топ-теги из базы (из её appreciated проектов)
2. Ищем на Behance по этим тегам свежие проекты
3. Фильтруем дубликаты (уже есть в БД)
4. Сохраняем новые проекты + делаем скрин обложки
"""
import asyncio
import base64
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, Page

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BEHANCE_BASE, SCREENSHOTS_DIR, DB_PATH,
    DAILY_TARGET,
    VISION_API_BASE, VISION_API_KEY, VISION_MODEL_DIRECT,
)
from scraper.human import random_delay, scroll_to_bottom, human_move, micro_delay
from scraper.auth import BROWSER_ARGS, VIEWPORT, create_context
import database as db
sys.path.insert(0, str(Path(__file__).parent.parent / "dashboard"))
import api_quota


# ── Категории Behance для поиска (fallback если мало тегов) ───────────────────
DEFAULT_SEARCH_TERMS = [
    "brand identity", "visual identity", "logo design",
    "typography poster", "motion design branding",
    "packaging design", "editorial design",
]

# Максимальный возраст проекта (дней)
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

    m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    if m:
        return m.group(1)

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

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %Y", "%b %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass

    return None


async def _get_project_meta_fast(page: Page, url: str) -> dict:
    """Быстрый сбор метаданных проекта (дата + теги)."""
    result = {"posted_at": None, "tags": []}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await random_delay(1.0, 2.5)

        time_el = await page.query_selector("time[datetime]")
        if time_el:
            raw = await time_el.get_attribute("datetime")
            result["posted_at"] = _parse_behance_date(raw)

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
    """Скачивает обложку (og:image) проекта."""
    try:
        og_image = await page.get_attribute('meta[property="og:image"]', 'content')

        if og_image:
            ext = ".jpg"
            if ".png" in og_image.lower():
                ext = ".png"
            elif ".webp" in og_image.lower():
                ext = ".webp"

            path = SCREENSHOTS_DIR / f"{behance_id}{ext}"
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(og_image)
                r.raise_for_status()
                with open(path, "wb") as f:
                    f.write(r.content)
        else:
            path = SCREENSHOTS_DIR / f"{behance_id}.png"
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
    url = f"{BEHANCE_BASE}/search/projects?search={query.replace(' ', '+')}&sort=published_date"
    results = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await random_delay(2, 4)

        await scroll_to_bottom(page, max_iterations=5)
        await random_delay(1, 2)

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
                author_url = (
                    (BEHANCE_BASE + author_href)
                    if author_href and not author_href.startswith("http")
                    else author_href
                )

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

    conn = sqlite3.connect(DB_PATH)
    known_ids = set(
        r[0] for r in conn.execute("SELECT behance_id FROM projects").fetchall()
    )
    conn.close()
    print(f"[Discovery] Уже в БД: {len(known_ids)} проектов")

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

            url_short = proj["title"][:50] or proj["behance_url"]
            print(f"  [{i}/{min(len(candidates), target*2)}] {url_short}")

            # Метаданные
            meta = await _get_project_meta_fast(page, proj["behance_url"])
            proj["posted_at"] = meta["posted_at"]
            proj["tags"]      = json.dumps(meta["tags"])

            # Фильтр по возрасту
            if proj["posted_at"]:
                try:
                    age = (datetime.utcnow() - datetime.fromisoformat(proj["posted_at"])).days
                    if age > MAX_AGE_DAYS:
                        print(f"    ⏭  Слишком старый ({age} дней) — пропуск")
                        skipped_old += 1
                        continue
                except Exception:
                    pass

            # Скриншот — всегда скачиваем ДО vision-фильтра
            screenshot = await _screenshot_project(page, proj["behance_id"])
            if not screenshot:
                print("    ⏭  Ошибка скачивания обложки")
                continue

            # --- ВИЗУАЛЬНЫЙ ФИЛЬТР ЦВЕТОВ (OpenRouter free vision models) ---
            try:
                # Pre-flight: проверяем квоту ДО любых API-вызовов
                ok, calls_today, limit = api_quota.check_limit("vision")
                if not ok:
                    print(f"    ⚠️  Vision: квота исчерпана ({calls_today}/{limit} req/day) — пропускаем фильтр")
                    vision_ans = None
                else:
                    img_ext = Path(screenshot).suffix.lower()
                    mime = (
                        "image/jpeg" if img_ext in (".jpg", ".jpeg") else
                        "image/png"  if img_ext == ".png" else
                        "image/webp" if img_ext == ".webp" else
                        "image/jpeg"
                    )
                    with open(screenshot, "rb") as f:
                        b64_img = base64.b64encode(f.read()).decode("utf-8")

                    vision_ans = None
                    vision_models = [m.strip() for m in VISION_MODEL_DIRECT.split(",") if m.strip()]

                    for v_model in vision_models:
                        # Проверяем квоту перед каждой попыткой
                        ok, calls_today, limit = api_quota.check_limit("vision")
                        if not ok:
                            print(f"    ⚠️  Vision: квота исчерпана ({calls_today}/{limit}) — останавливаем каскад")
                            break
                        try:
                            await asyncio.sleep(3)  # ~20 req/min на бесплатном tier
                            async with httpx.AsyncClient(timeout=60) as client:
                                vr = await client.post(
                                    f"{VISION_API_BASE}/chat/completions",
                                    headers={
                                        "Authorization": f"Bearer {VISION_API_KEY}",
                                        "HTTP-Referer": "https://behance-scout.local",
                                        "X-Title": "Behance Scout",
                                    },
                                    json={
                                        "model": v_model,
                                        "messages": [
                                            {
                                                "role": "user",
                                                "content": [
                                                    {"type": "text", "text": (
                                                        "Analyze this design portfolio project cover image. "
                                                        "Allowed colors: Black, White, Grey, Orange ONLY. "
                                                        "If you see ANY other noticeable color (blue, green, red, "
                                                        "pink, purple, yellow, brown, beige, teal etc.) — "
                                                        "reply with exactly 'REJECT'. "
                                                        "If the image strictly uses only black/white/grey/orange — "
                                                        "reply with exactly 'APPROVE'. One word only."
                                                    )},
                                                    {"type": "image_url", "image_url": {
                                                        "url": f"data:{mime};base64,{b64_img}"
                                                    }}
                                                ]
                                            }
                                        ],
                                        "max_tokens": 10,
                                        "temperature": 0.0,
                                    }
                                )
                                vr.raise_for_status()
                                vision_ans = vr.json()["choices"][0]["message"]["content"].strip().upper()
                                print(f"    [Vision] {v_model.split('/')[-1]}: {vision_ans[:30]}")
                                api_quota.log_call("vision", v_model, success=True)
                                break  # Успех — выходим из каскада
                        except Exception as ve:
                            print(f"    [Vision] {v_model.split('/')[-1]} failed: {ve}")
                            api_quota.log_call("vision", v_model, success=False)
                            continue

                if vision_ans and "REJECT" in vision_ans:
                    print("    ⏭  REJECT по цветам обложки (Ч/Б/Серый/Оранжевый only)")
                    continue
                elif vision_ans is None:
                    print("    ⚠️  Vision: все модели недоступны, пропускаем фильтр")

            except Exception as e:
                print(f"    [Vision ошибка] {e}")

            # Сохраняем
            is_new = db.save_project(proj)
            if is_new:
                if screenshot:
                    db.update_screenshot(proj["behance_id"], screenshot)
                saved += 1
                age_str = proj["posted_at"] if proj["posted_at"] else "дата неизвестна"
                print(f"    ✅ Сохранён ({age_str})")
            else:
                print("    ⏭  Уже в БД")

            await random_delay()

        await browser.close()

    print(f"\n[Discovery] ✅ Готово!")
    print(f"  Сохранено новых: {saved}")
    print(f"  Пропущено (старые): {skipped_old}")
    return saved
