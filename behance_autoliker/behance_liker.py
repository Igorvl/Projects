"""
Behance AutoLiker -- avtomatichesky layk proektov cherez Playwright.

Sessiya bereztsya iz session/behance_cookies.json (sozdayotsya setup_session.py).
"""

import asyncio
import random
import logging
import os
import sys
import re
import urllib.parse
import urllib.request
import ssl
import json
from datetime import datetime

from config import HEADLESS, BROWSER_PROXY

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

SESSION_FILE = os.path.join("session", "behance_cookies.json")

APPRECIATE_SELECTORS = [
    # Osnovnaya knopka Behance 2024-2026 (div role=button, ne button!)
    '[class*="Appreciate-wrapper"]',
    '[class*="Project-appreciateIcon"]',
    'div[role="button"][class*="Appreciate"]',
    # Plavayushchaya knopka sprava ("Otsenit")
    '[class*="ProjectActionBar"][role="button"]',
    # Starye varianty (button-element)
    'button[data-testid="appreciate-button"]',
    'button[class*="appreciate"]',
    'button[class*="Appreciate"]',
    'button[aria-label*="ppreciate"]',
    # Zapasnoj — lyuboy role=button s appreciate v klasse
    '[role="button"][class*="Appreciate"]',
    '[role="button"][class*="appreciate"]',
]

# Klassy kotorye oznachayut "uzhe layknut"
ALREADY_LIKED_CLASSES = [
    "Appreciate-appreciated",
    "appreciated",
    "active",
    "isLiked",
    "is-liked",
]

DEBUG_DIR = "debug"


def _clean_behance_path(path: str) -> str:
    """Удаляет query-параметры, хеши и завершающие слеши из пути проекта Behance."""
    for sep in ("?", "&", "#"):
        if sep in path:
            path = path.split(sep)[0]
    return path.rstrip("/")


def _get_browser_proxy() -> dict | None:
    """Проверяет доступность локального SOCKS5 прокси v2rayTun (127.0.0.1:10801)."""
    import socket
    if not BROWSER_PROXY:
        return None
    try:
        clean = BROWSER_PROXY.split("://")[-1]
        host, port_str = clean.split(":")
        with socket.create_connection((host, int(port_str)), timeout=0.3):
            logger.info(f"[PROXY] Obnaruzhen VPN-proksi ({BROWSER_PROXY}), podklyuchayu brauzer k nemu.")
            return {"server": BROWSER_PROXY}
    except Exception:
        logger.info("[PROXY] VPN-proksi ne obnaruzhen ili vykluchen, zapusk brauzera napryamuyu.")
        return None


def _resolve_redirect(url: str, timeout: float = 6.0) -> str | None:
    """Определяет конечный адрес для сокращённых ссылок (t.co, bit.ly, etc.)."""
    try:
        ctx = ssl._create_unverified_context()
        handlers = [urllib.request.HTTPSHandler(context=ctx)]
        if BROWSER_PROXY:
            handlers.append(urllib.request.ProxyHandler({"http": BROWSER_PROXY, "https": BROWSER_PROXY}))
        opener = urllib.request.build_opener(*handlers)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as resp:
            return resp.geturl()
    except Exception:
        return None


class BehanceLiker:

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def init(self):
        """Zapustit Chromium s sohranennoy sessiey Behance."""

        if not os.path.exists(SESSION_FILE):
            print()
            print("  OSHIBKA: Fayl sessii ne naydyon!")
            print(f"  Ozhidaetsya: {SESSION_FILE}")
            print()
            print("  Snachala zapustite:")
            print("    python setup_session.py")
            print()
            sys.exit(1)

        proxy_config = _get_browser_proxy()

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=HEADLESS,
            proxy=proxy_config,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )

        self._context = await self._browser.new_context(
            storage_state=SESSION_FILE,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            viewport={"width": 1280, "height": 900},
        )

        self._page = await self._context.new_page()

        # Skryvaem webdriver flag
        await self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Proveryaem chto sessiya rabotaet
        logged_in = await self._is_logged_in()
        if not logged_in:
            logger.warning("[WARN] Sessiya istekla ili ne rabotaet.")
            logger.warning("       Zapustite snova: python setup_session.py")
            print()
            print("  PREDUPREZHDENIE: Sessiya istekla!")
            print("  Zaydite v Chrome -> Behance -> zalogintes")
            print("  Zatem: python setup_session.py")
            print()

    async def resolve_intermediary_url(self, intermediary_url: str) -> str | None:
        """
        Переходит по промежуточной ссылке (Pinterest, LinkedIn, FB, IG, X и т.д.)
        и находит прямую ссылку на Behance-проект (gallery).

        Возвращает:
          str  — нормализованный URL вида https://www.behance.net/gallery/...
          None — ссылка на Behance не найдена
        """
        logger.info(f"[INTERMEDIARY] Perehozhu po ssylke sotsseti: {intermediary_url}")
        behance_gallery_re = re.compile(
            r"(?:https?://)?(?:www\.)?(?:behance\.net|be\.net)/gallery/([0-9]+(?:/[^/?#\s\"'>]+)?)",
            re.IGNORECASE
        )

        # 1. Быстрый резолвинг для X/Twitter через API (Playwright request context использует сетевой стек браузера/прокси)
        if "x.com/" in intermediary_url.lower() or "twitter.com/" in intermediary_url.lower():
            for endpoint in ("api.fxtwitter.com", "api.vxtwitter.com"):
                try:
                    parsed_tw = urllib.parse.urlparse(intermediary_url)
                    api_url = parsed_tw._replace(netloc=endpoint).geturl()
                    resp = await self._page.request.get(api_url, timeout=10_000)
                    if resp.ok:
                        data = await resp.json()
                        tweet_text = (data.get("tweet") or {}).get("text") or data.get("text") or ""
                        m = behance_gallery_re.search(tweet_text)
                        if m:
                            clean_path = _clean_behance_path(m.group(1))
                            behance_url = f"https://www.behance.net/gallery/{clean_path}"
                            logger.info(f"[INTERMEDIARY] [OK] Naydena ssylka Behance v X/Twitter ({endpoint}): {behance_url}")
                            return behance_url
                except Exception as xe:
                    logger.warning(f"[INTERMEDIARY] Oshibka {endpoint} ({xe}), probuyu dalshe...")

        try:
            # Открываем страницу соцсети в браузере
            await self._page.goto(intermediary_url, wait_until="domcontentloaded", timeout=30_000)
            # Ждём пару секунд для отрисовки динамических элементов
            await asyncio.sleep(random.uniform(3.0, 4.5))

            # Попытка 1: Проверяем все теги <a> на странице (href, textContent, title)
            link_entries = await self._page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a'));
                return links.map(a => ({
                    href: a.getAttribute('href') || a.href || '',
                    text: a.innerText || a.textContent || '',
                    title: a.getAttribute('title') || '',
                }));
            }""")

            for entry in link_entries:
                for candidate in (entry.get("href", ""), entry.get("text", ""), entry.get("title", "")):
                    if not candidate:
                        continue
                    # Прямой поиск в значении
                    m = behance_gallery_re.search(candidate)
                    if m:
                        clean_path = _clean_behance_path(m.group(1))
                        behance_url = f"https://www.behance.net/gallery/{clean_path}"
                        logger.info(f"[INTERMEDIARY] [OK] Naydena ssylka Behance v tege <a>: {behance_url}")
                        return behance_url

                    # Декодируем возможные редиректы (linkedin.com/safety/go?url=..., linkedin.com/redir/redirect?url=..., etc.)
                    try:
                        for unquoted in (urllib.parse.unquote(candidate), urllib.parse.unquote_plus(candidate)):
                            m = behance_gallery_re.search(unquoted)
                            if m:
                                clean_path = _clean_behance_path(m.group(1))
                                behance_url = f"https://www.behance.net/gallery/{clean_path}"
                                logger.info(f"[INTERMEDIARY] [OK] Naydena ssylka Behance v redirekte: {behance_url}")
                                return behance_url
                    except Exception:
                        pass

            # Попытка 1.5: Проверяем укороченные ссылки (t.co, bit.ly, lnkd.in, etc.)
            shortener_prefixes = ("t.co/", "bit.ly/", "tinyurl.com/", "lnkd.in/", "fb.me/", "ow.ly/", "is.gd/")
            for entry in link_entries:
                href = entry.get("href", "")
                if any(sp in href.lower() for sp in shortener_prefixes):
                    try:
                        resolved_url = await asyncio.to_thread(_resolve_redirect, href)
                        if resolved_url:
                            m = behance_gallery_re.search(resolved_url)
                            if m:
                                clean_path = _clean_behance_path(m.group(1))
                                behance_url = f"https://www.behance.net/gallery/{clean_path}"
                                logger.info(f"[INTERMEDIARY] [OK] Naydena ssylka Behance cherez shortener redirect ({href}): {behance_url}")
                                return behance_url
                    except Exception:
                        pass

            # Попытка 2: Поиск в видимом тексте страницы (document.body.innerText)
            body_text = await self._page.evaluate("() => document.body ? document.body.innerText : ''")
            m = behance_gallery_re.search(body_text)
            if m:
                clean_path = _clean_behance_path(m.group(1))
                behance_url = f"https://www.behance.net/gallery/{clean_path}"
                logger.info(f"[INTERMEDIARY] [OK] Naydena ssylka Behance v tekste stranitsy: {behance_url}")
                return behance_url

            # Попытка 3: Дополнительное ожидание 3с для тяжелых динамических SPA и повторная проверка
            await asyncio.sleep(3.0)
            delayed_links = await self._page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a'));
                return links.map(a => a.getAttribute('href') || a.href || '');
            }""")
            for d_href in delayed_links:
                for cand in (d_href, urllib.parse.unquote(d_href), urllib.parse.unquote_plus(d_href)):
                    m = behance_gallery_re.search(cand)
                    if m:
                        clean_path = _clean_behance_path(m.group(1))
                        behance_url = f"https://www.behance.net/gallery/{clean_path}"
                        logger.info(f"[INTERMEDIARY] [OK] Naydena ssylka Behance posle dopolnitelnogo ozhidaniya: {behance_url}")
                        return behance_url

            content = await self._page.content()
            m = behance_gallery_re.search(content)
            if m:
                clean_path = _clean_behance_path(m.group(1))
                behance_url = f"https://www.behance.net/gallery/{clean_path}"
                logger.info(f"[INTERMEDIARY] [OK] Naydena ssylka Behance v kontente stranitsy: {behance_url}")
                return behance_url

            logger.warning(f"[INTERMEDIARY] ❌ Behance-ssylka ne naydena na stranitse: {intermediary_url}")
            return None

        except Exception as exc:
            logger.error(f"[INTERMEDIARY] Oshibka pri perehode po {intermediary_url}: {exc}")
            return None

    async def like_project(self, url: str) -> str:
        """Otkryvaet proekt, scrollit, stavit layk."""
        try:
            logger.info(f"[WEB] Otkryvayu: {url}")
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await asyncio.sleep(random.uniform(1.5, 3.0))

            # 1. Medlenno scrollim ves keys sverhu vniz
            await self._slow_scroll()

            # 2. Laykayem (plavayushchaya knopka vsegda vidna)
            status = await self._click_appreciate()

            # 3. Posle layka -- estestvennoe povedeniye
            if status in ("liked", "already_liked"):
                await self._natural_post_like_browsing()

            return status

        except Exception as exc:
            logger.error(f"Oshibka pri layke {url}: {exc}")
            return "error"

    async def human_wait(self, total_seconds: float) -> None:
        """
        Chelovecheskoe ozhidanie vmesto prostogo sleep.
        Bol'shuyu chast' vremeni listayem lentu Behance,
        v poslednie 5-15 sek zamiraem (otkryvaem Telegram).
        """
        freeze_sec = random.uniform(7, 17)
        browse_sec = max(total_seconds - freeze_sec, 3.0)

        logger.info(
            f"[WAIT] Listаyu Behance {browse_sec:.0f}s, "
            f"zatem zamru {freeze_sec:.0f}s pered nazhatiyer..."
        )
        await self._browse_during_wait(browse_sec)

        logger.info(f"[WAIT] Zamirayu {freeze_sec:.0f}s (otkryvayu Telegram)...")
        await asyncio.sleep(freeze_sec)

    async def verify_like(self, url: str) -> bool:
        """
        Проверка на теневой бан: перезагружает страницу проекта и проверяет,
        сохранился ли лайк (кнопка Appreciate в состоянии «уже нажата»).

        Возвращает:
          True  — лайк подтверждён (всё ок)
          False — лайк НЕ сохранился → вероятен теневой бан

        При ошибках загрузки страницы возвращает True (чтобы не было ложной тревоги).
        """
        logger.info("[VERIFY] Жду 3с, затем перезагружаю страницу для проверки лайка...")
        await asyncio.sleep(random.uniform(3.0, 5.0))

        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except Exception as exc:
            logger.warning(f"[VERIFY] Не удалось перезагрузить страницу: {exc}. Пропускаю проверку.")
            return True  # не блокируем из-за сетевой ошибки

        # Ждём рендера кнопки
        try:
            await self._page.wait_for_load_state("networkidle", timeout=8_000)
        except Exception:
            pass
        await asyncio.sleep(random.uniform(1.5, 2.5))

        # --- Проверка через CSS-селекторы ---
        for selector in APPRECIATE_SELECTORS:
            try:
                btn = await self._page.query_selector(selector)
                if not btn:
                    continue

                aria_pressed = await btn.get_attribute("aria-pressed") or ""
                aria_label   = await btn.get_attribute("aria-label") or ""
                class_name   = await btn.get_attribute("class") or ""

                liked = (
                    aria_pressed.lower() == "true"
                    or any(c.lower() in class_name.lower() for c in ALREADY_LIKED_CLASSES)
                    or "убрать" in aria_label.lower()
                    or "remove" in aria_label.lower()
                    or "unappreci" in aria_label.lower()
                )

                if liked:
                    logger.info(f"[VERIFY] ✅ Лайк подтверждён ({selector[:45]})")
                    return True
                else:
                    logger.warning(
                        f"[VERIFY] ❌ Кнопка найдена ({selector[:45]}), "
                        f"НО лайк НЕ стоит! aria={aria_label!r} class={class_name[:40]!r}"
                    )
                    return False  # кнопка найдена, но не активна — shadow ban
            except Exception:
                continue

        # --- JS-фолбек ---
        try:
            result = await self._page.evaluate("""
                () => {
                    const all = Array.from(document.querySelectorAll('button, [role="button"]'));
                    for (const btn of all) {
                        const label = (
                            btn.getAttribute('aria-label') ||
                            btn.getAttribute('data-testid') ||
                            btn.className || ''
                        ).toLowerCase();
                        if (!label.includes('appreciate') && !label.includes('like')) continue;
                        const isLiked =
                            btn.getAttribute('aria-pressed') === 'true' ||
                            btn.classList.contains('active') ||
                            btn.classList.contains('appreciated');
                        return isLiked;   // true = liked, false = not liked
                    }
                    return null;  // кнопка вообще не найдена
                }
            """)
            if result is True:
                logger.info("[VERIFY] ✅ JS: лайк подтверждён.")
                return True
            elif result is False:
                logger.warning("[VERIFY] ❌ JS: лайк НЕ сохранился после перезагрузки!")
                return False
            else:
                # result is None — кнопка не найдена на странице (возможно другой макет)
                logger.warning("[VERIFY] ⚠️ Кнопка Appreciate не найдена при проверке — пропускаю (не false-positive).")
                return True
        except Exception as exc:
            logger.warning(f"[VERIFY] JS-проверка не удалась: {exc}. Пропускаю.")
            return True

    async def _browse_during_wait(self, seconds: float) -> None:
        """
        Listayem lentu Behance v techenie `seconds` sekund:
        - medlennyy skroll
        - sluchaynye pauzy na eskizakh (imitatsiya prosmotra)
        - dvizheniya myshi
        - esli doshli do konca — vozvrashchaemsya vverkh
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + seconds

        # Perekhod na glavnuyu lentu
        try:
            await self._page.goto(
                "https://www.behance.net/",
                wait_until="domcontentloaded",
                timeout=15_000,
            )
            await asyncio.sleep(random.uniform(1.0, 2.0))
        except Exception:
            pass  # Ostayomsya na tekushchey stranitse

        # Защита: evaluate может упасть если страница ещё в процессе навигации
        try:
            viewport_w: int = await self._page.evaluate("window.innerWidth")
            viewport_h: int = await self._page.evaluate("window.innerHeight")
        except Exception:
            viewport_w, viewport_h = 1280, 900  # fallback — продолжаем без размеров
        scroll_pos: int = 0

        while loop.time() < deadline:
            remaining = deadline - loop.time()
            if remaining < 3:
                break

            try:
                page_height: int = await self._page.evaluate("document.body.scrollHeight")

                # Esli doshli do kontsa — plavno vverkh
                if scroll_pos >= page_height - viewport_h - 200:
                    scroll_pos = 0
                    await self._page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                    continue

                # Obychny shag skrolla
                step = random.randint(50, 160)
                scroll_pos = min(scroll_pos + step, page_height - viewport_h)
                await self._page.evaluate(
                    f"window.scrollTo({{top: {scroll_pos}, behavior: 'smooth'}})"
                )

                # Sluchaynoe dvizhenie myshi (25%)
                if random.random() < 0.25:
                    await self._page.mouse.move(
                        random.randint(100, viewport_w - 100),
                        random.randint(100, viewport_h - 100),
                    )

                # Sluchaynaya pauza — "rassmatrivaem eskiz" (15%)
                if random.random() < 0.15:
                    pause = random.uniform(0.8, 3.0)
                    if remaining > pause + 5:
                        await asyncio.sleep(pause)
                        continue

            except Exception as nav_err:
                # Страница перешла на другой URL (SPA-навигация, редирект) —
                # execution context уничтожен. Просто выходим из цикла.
                logger.debug(f"[BROWSE] Navigatsiya vo vremya skrolla, vykhozhу: {nav_err}")
                break

            await asyncio.sleep(random.uniform(0.08, 0.22))

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _is_logged_in(self) -> bool:
        try:
            await self._page.goto(
                "https://www.behance.net/", wait_until="domcontentloaded", timeout=30_000
            )
            await asyncio.sleep(2.0)
            sign_in = await self._page.query_selector(
                'a[href*="/login"], button:has-text("Sign In"), a:has-text("Sign In")'
            )
            avatar = await self._page.query_selector(
                '[class*="Avatar"], [data-testid="user-avatar"], [aria-label*="profile"], [aria-label*="Profile"]'
            )
            logged_in = (sign_in is None) or (avatar is not None)
            logger.info(f"Behance: {'OK logged in' if logged_in else 'NOT logged in'}")
            return logged_in
        except Exception as exc:
            logger.warning(f"Proverka vkhoda ne udalas: {exc}")
            return False

    async def _slow_scroll(self):
        """
        Chelovecheskiy skroll: chitaem keys sverhu vniz.
        - Sluchaynye pauzy na interesnykh mestakh
        - Iногда vozvrashchaemsya nazad (perechitatvayem)
        - Dvizhenie myshi po stranitse
        - Peremenная skorost (bystree cherez tekst, medlenee cherez kartinki)
        """
        logger.info("[SCROLL] Chitayu keys...")

        page_height: int   = await self._page.evaluate("document.body.scrollHeight")
        viewport_h: int    = await self._page.evaluate("window.innerHeight")
        viewport_w: int    = await self._page.evaluate("window.innerWidth")
        current_pos: int   = 0

        # Nazhnachaem 3-6 "interesnykh" tochek gde budem zaderzhivatsya
        content_zone = range(viewport_h, max(page_height - viewport_h, viewport_h + 1), 100)
        n_pauses = min(random.randint(3, 6), len(list(content_zone)))
        pause_points = sorted(random.sample(list(content_zone), n_pauses)) if n_pauses > 0 else []
        pause_idx = 0

        # Pervoe dvizhenie myshi -- "smotrim" na stranicu
        await self._page.mouse.move(
            random.randint(viewport_w // 4, viewport_w * 3 // 4),
            random.randint(100, 300),
        )
        await asyncio.sleep(random.uniform(0.3, 0.7))

        while current_pos < page_height:

            # --- Pauza na "interesnom" meste ---
            if pause_idx < len(pause_points) and current_pos >= pause_points[pause_idx]:
                pause_duration = random.uniform(1.0, 4.0)
                logger.info(f"[SCROLL] Interesno, smotryu {pause_duration:.1f}s...")

                # Dvizhenie myshi po kartinke / bloku
                for _ in range(random.randint(1, 3)):
                    await self._page.mouse.move(
                        random.randint(100, viewport_w - 100),
                        random.randint(100, viewport_h - 100),
                    )
                    await asyncio.sleep(random.uniform(0.2, 0.6))

                await asyncio.sleep(pause_duration)
                pause_idx += 1

                # 30% shansy vvernut' nazad i posmotet eshche raz
                if random.random() < 0.30:
                    back = random.randint(80, 250)
                    logger.info("[SCROLL] Vozvrashachus, eshche razok glyanu...")
                    await self._page.evaluate(
                        f"window.scrollTo({{top: {max(current_pos - back, 0)}, behavior: 'smooth'}})"
                    )
                    await asyncio.sleep(random.uniform(0.8, 1.8))

            # --- Obychny shag skrolla ---
            # Kratkie "ryvki" -- imituem koleso myshi / svaype
            step = random.randint(60, 200)
            current_pos = min(current_pos + step, page_height)
            await self._page.evaluate(
                f"window.scrollTo({{top: {current_pos}, behavior: 'smooth'}})"
            )

            # Inogda dvigaem mysh vo vremya skrolla (20% veroytnosti)
            if random.random() < 0.20:
                await self._page.mouse.move(
                    random.randint(100, viewport_w - 100),
                    random.randint(100, viewport_h - 150),
                )

            await asyncio.sleep(random.uniform(0.06, 0.22))

        # Pauza vnizu -- "dosmatrivaem" posledniy blok
        await asyncio.sleep(random.uniform(1.5, 3.5))
        logger.info("[SCROLL] Dokrutyl do kontsa.")

    async def _natural_post_like_browsing(self):
        """
        Povedeniye posle layka:
          1. Medlenno chitaem kommentarii (scroll vniz)
          2. Smotrim na kontakty avtora ~5 sek (s dvizheniyem myshi)
          3. Proveryaem schetchik laykov (estestvennoe lyubopytstvo)
          4. Medlenno listayem obratno vverkh cherez rabotu
        """
        viewport_w: int    = await self._page.evaluate("window.innerWidth")
        viewport_h: int    = await self._page.evaluate("window.innerHeight")
        scroll_y: int      = await self._page.evaluate("window.scrollY")
        page_height: int   = await self._page.evaluate("document.body.scrollHeight")

        # --- 1. Kommentarii ---
        logger.info("[BROWSE] Chitayu kommentarii...")
        for _ in range(random.randint(5, 11)):
            step = random.randint(35, 140)
            scroll_y = min(scroll_y + step, page_height)
            await self._page.evaluate(
                f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})"
            )
            # Inogda dvizhenie myshi -- "chitaem" kommentariy
            if random.random() < 0.4:
                await self._page.mouse.move(
                    random.randint(100, viewport_w - 100),
                    random.randint(100, viewport_h - 100),
                )
            await asyncio.sleep(random.uniform(0.9, 2.5))

        await asyncio.sleep(random.uniform(3.0, 6.0))

        # --- 2. Kontakty avtora (~5 sek) ---
        logger.info("[BROWSE] Smotryu na kontakty avtora...")
        contacts_y = max(page_height - random.randint(250, 550), scroll_y - 150)
        await self._page.evaluate(
            f"window.scrollTo({{top: {contacts_y}, behavior: 'smooth'}})"
        )
        # "Chitaem" kontakty -- neskolko dvizheniy myshi
        for _ in range(random.randint(2, 4)):
            await self._page.mouse.move(
                random.randint(100, viewport_w // 2),
                random.randint(100, viewport_h - 100),
            )
            await asyncio.sleep(random.uniform(1.0, 1.8))
        await asyncio.sleep(random.uniform(1.5, 2.5))   # итого ~5 сек

        # --- 3. Lyubopytstvo: schetchik laykov ---
        logger.info("[BROWSE] Smotryu na schetchik laykov...")
        # Ищем элемент со счётчиком и наводим мышь
        try:
            counter = await self._page.query_selector('[class*="Appreciate-count"]')
            if counter:
                box = await counter.bounding_box()
                if box:
                    await self._page.mouse.move(
                        box["x"] + box["width"] / 2,
                        box["y"] + box["height"] / 2,
                    )
                    await asyncio.sleep(random.uniform(0.8, 1.5))
        except Exception:
            pass

        # --- 4. Medlenno vverkh cherez rabotu ---
        logger.info("[BROWSE] Medlenno listаyu vverkh cherez rabotu...")
        scroll_y = contacts_y
        while scroll_y > 50:
            step = random.randint(90, 260)
            scroll_y = max(scroll_y - step, 0)
            await self._page.evaluate(
                f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})"
            )
            # Redkoe dvizhenie myshi pri skrolle vverkh
            if random.random() < 0.15:
                await self._page.mouse.move(
                    random.randint(100, viewport_w - 100),
                    random.randint(100, viewport_h - 100),
                )
            await asyncio.sleep(random.uniform(0.09, 0.25))

        logger.info("[BROWSE] Prosmotr zavershen.")

    async def _click_appreciate(self) -> str:
        """Ishchet i klikaet Appreciate (plavayushchaya knopka -- vsegda vidna)."""
        # Zhdem poka stranichka polnostyu zagruzitsya
        try:
            await self._page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        await asyncio.sleep(1.5)

        # Knopka plavayushchaya -- ne nado scrollit vverkh, ishchem srazu

        for selector in APPRECIATE_SELECTORS:
            try:
                btn = await self._page.query_selector(selector)
                if not btn:
                    continue

                aria_pressed = await btn.get_attribute("aria-pressed") or ""
                aria_label   = await btn.get_attribute("aria-label") or ""
                class_name   = await btn.get_attribute("class") or ""

                # Proverka "uzhe layknut"
                already = (
                    aria_pressed.lower() == "true"
                    or any(c.lower() in class_name.lower() for c in ALREADY_LIKED_CLASSES)
                    # Russkiy: "Ubrat otsenku" = uzhe layknut
                    or "убрать" in aria_label.lower()
                    or "remove" in aria_label.lower()
                    or "unappreci" in aria_label.lower()
                )

                if already:
                    logger.info(f"[SKIP] Uzhe layknyt (class: {class_name[:60]})")
                    return "already_liked"

                logger.info(f"[CLICK] Nashel knopku: {selector[:50]}, aria={aria_label!r}")

                # Navodim mysh na knopku (natural hover pered klikom)
                await btn.scroll_into_view_if_needed()
                box = await btn.bounding_box()
                if box:
                    # Podvodim mysh "s boku" -- ne pryamo v tsentr srazu
                    await self._page.mouse.move(
                        box["x"] + box["width"] * random.uniform(0.2, 0.5),
                        box["y"] + box["height"] * random.uniform(0.2, 0.8),
                    )
                    # Zadumyvaemsya pered nazhatiyer (0.4 - 1.2 sek)
                    await asyncio.sleep(random.uniform(0.4, 1.2))

                await btn.click()
                await asyncio.sleep(random.uniform(0.5, 1.0))

                # Uvodim mysh v storonu posle klika (kak chelovek)
                if box:
                    await self._page.mouse.move(
                        box["x"] + random.randint(-100, 200),
                        box["y"] + random.randint(-50, 100),
                    )
                await asyncio.sleep(random.uniform(0.3, 0.7))

                logger.info("[LIKE] Appreciate nazhat!")
                return "liked"


            except Exception:
                continue

        # JS fallback — ishchem lyubuyu knopku s "appreciate" v svoystvakh
        try:
            result: str = await self._page.evaluate("""
                () => {
                    const all = Array.from(document.querySelectorAll('button, [role="button"]'));
                    for (const btn of all) {
                        const label = (
                            btn.getAttribute('aria-label') ||
                            btn.getAttribute('data-testid') ||
                            btn.className ||
                            btn.textContent || ''
                        ).toLowerCase();
                        if (!label.includes('appreciate') && !label.includes('like')) continue;
                        const isActive =
                            btn.getAttribute('aria-pressed') === 'true' ||
                            btn.classList.contains('active') ||
                            btn.classList.contains('appreciated');
                        if (isActive) return 'already_liked';
                        btn.click();
                        return 'liked';
                    }
                    return 'not_found';
                }
            """)
            if result in ("liked", "already_liked"):
                logger.info(f"[JS] Rezultat: {result}")
                return result
        except Exception as exc:
            logger.error(f"JS fallback: {exc}")

        # Sokhranim screenshot dlya diagnostiki
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            ts = datetime.now().strftime("%H%M%S")
            shot_path = os.path.join(DEBUG_DIR, f"no_button_{ts}.png")
            await self._page.screenshot(path=shot_path, full_page=False)
            logger.error(f"[ERROR] Knopka ne naydena! Screenshot: {shot_path}")

            # Dump vsekh knopok na stranitse dlya diagnostiki
            buttons_info = await self._page.evaluate("""
                () => Array.from(document.querySelectorAll('button')).map(b => ({
                    text: b.textContent.trim().slice(0, 40),
                    aria: b.getAttribute('aria-label'),
                    cls: b.className.slice(0, 60),
                    testid: b.getAttribute('data-testid')
                }))
            """)
            logger.info(f"[DEBUG] Vse knopki na stranitse ({len(buttons_info)} sht):")
            for b in buttons_info[:20]:  # pervye 20
                logger.info(f"  text={b['text']!r} aria={b['aria']!r} "
                            f"cls={b['cls']!r} testid={b['testid']!r}")
        except Exception as se:
            logger.error(f"Screenshot oshibka: {se}")

        return "error"

