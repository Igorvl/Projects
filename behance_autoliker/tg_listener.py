"""
Telegram-слушатель с очередью задач.

Все входящие задания ставятся в очередь и обрабатываются
СТРОГО по одному — никаких гонок браузера.
"""

import re
import asyncio
import random
import logging
import csv
import os
from datetime import datetime, timezone, timedelta

from telethon import TelegramClient, events
from telethon.tl.custom import Message

from config import TG_API_ID, TG_API_HASH, BOT_USERNAME, DELAY_MIN, DELAY_MAX, \
    PROXY_HOST, PROXY_PORT, PROXY_TYPE, PROXY_USER, PROXY_PASS
from behance_liker import BehanceLiker
from rate_limiter import RateLimiter, MAX_LIKES_PER_SESSION

logger = logging.getLogger(__name__)

BEHANCE_RE = re.compile(r"https?://(?:www\.)?(?:behance\.net|be\.net)/gallery/[\w/%-]+")
BOT_REQUEST_CMD = "▶️ Доступные задания"

# Максимальный возраст задания при catchup — старше не берём (уже выполнено/устарело)
CATCHUP_MAX_AGE = timedelta(minutes=15)
LOG_FILE = "likes_log.csv"
EXCLUSIONS_FILE = "excluded_projects.txt"

# Глобальный лок — только ОДНА копия _auto_resume работает одновременно
_resume_lock: asyncio.Lock | None = None

# Флаг теневого бана — если True, новые задания не берутся
_shadow_ban_active: bool = False

# Время последней активности (для watchdog поллинга при простое)
_last_activity_time: datetime = datetime.now()


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _is_direct_behance(url: str) -> bool:
    """Проверяет: является ли ссылка прямой ссылкой на Behance (запрещено переходить)."""
    u = url.lower()
    return "behance.net" in u or "be.net" in u


def _extract_urls(message: Message) -> list[str]:
    """Извлекает все HTTP/HTTPS ссылки из текста сообщения и из entities (гиперссылки)."""
    urls = []
    text = message.text or ""
    # 1. Из обычного текста
    for match in re.finditer(r"https?://[^\s)\]\"'>]+", text):
        urls.append(match.group(0).rstrip(".,;"))
    # 2. Из entities (вшитые ссылки в слова)
    if message.entities:
        from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl
        for ent in message.entities:
            if isinstance(ent, MessageEntityTextUrl) and ent.url:
                urls.append(ent.url.rstrip(".,;"))
            elif isinstance(ent, MessageEntityUrl):
                extracted = text[ent.offset:ent.offset + ent.length].strip()
                if extracted.startswith("http"):
                    urls.append(extracted.rstrip(".,;"))
    seen = set()
    unique_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    return unique_urls


def _write_log(url: str, status: str) -> None:
    write_header = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["timestamp", "url", "status"])
        writer.writerow([datetime.now().isoformat(), url, status])


def _normalize_url(url: str) -> str:
    """Нормализует URL для сравнения: нижний регистр, без www, без слеша в конце, без query/fragment."""
    url = url.lower().strip().rstrip("/")
    url = url.replace("//www.behance.net", "//behance.net")
    for sep in ("?", "#"):
        idx = url.find(sep)
        if idx != -1:
            url = url[:idx]
    return url


def _load_exclusions() -> set:
    """
    Читает файл исключений (excluded_projects.txt).
    Строки с # и пустые — игнорируются.
    Возвращает set нормализованных URL.
    """
    if not os.path.exists(EXCLUSIONS_FILE):
        return set()
    excluded = set()
    with open(EXCLUSIONS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            excluded.add(_normalize_url(line))
    return excluded


def _is_excluded(url: str, exclusions: set) -> bool:
    """Проверяет: входит ли URL в список исключений."""
    return _normalize_url(url) in exclusions


async def _click_button(message: Message, text_fragment: str) -> bool:
    """Ищет inline-кнопку и кликает."""
    if not message.buttons:
        return False
    for row in message.buttons:
        for btn in row:
            if text_fragment.lower() in btn.text.lower():
                try:
                    await btn.click()
                    logger.info(f"[BTN] Nazhata knopka: [{btn.text.strip()}]")
                    return True
                except Exception as exc:
                    logger.warning(f"[BTN] Oshibka klika [{btn.text}]: {exc}")
    return False


# ---------------------------------------------------------------------------
# Обработка одного задания (вызывается строго по одному из очереди)
# ---------------------------------------------------------------------------

async def _process_task(
    message: Message,
    intermediary_url: str,
    liker: BehanceLiker,
    rate_limiter: RateLimiter,
    client,
) -> bool:
    """
    Обрабатывает одно задание от бота:
      1. Проверяет не является ли ссылка прямой на Behance (безопасность).
      2. Переходит по ссылке соцсети и находит Behance-проект.
      3. Лайкает + проверяет + нажимает кнопку Готово.
    """
    global _shadow_ban_active

    logger.info(f"[TASK] Vhodyashchaya ssylka: {intermediary_url}")
    logger.info(f"[TASK] Limit: {rate_limiter.status_line()}")

    # Ждём если активна пауза (4ч или 24ч10м)
    await rate_limiter.wait_if_needed()

    # === 1. ПРОВЕРКА НА ПРЯМУЮ ССЫЛКУ BEHANCE ИЗ СООБЩЕНИЯ ТГ-БОТА ===
    if _is_direct_behance(intermediary_url):
        logger.warning(
            f"[SECURITY] ⚠️ ТГ-бот выдал прямую ссылку Behance в задании: {intermediary_url}! "
            "По правилам безопасности прямые ссылки из Telegram запрещены (нет внешнего реферера соцсети). Нажимаю [❌ Пропустить]."
        )
        await _click_button(message, "Пропустить")
        _write_log(intermediary_url, "security_skip_direct")
        return True

    # === 2. РЕЗОЛВИНГ ЧЕРЕЗ СОЦСЕТЬ (Pinterest, LinkedIn, FB, IG, X и т.д.) ===
    await asyncio.sleep(random.uniform(1.5, 3.5))
    behance_url = await liker.resolve_intermediary_url(intermediary_url)

    if not behance_url:
        logger.warning(
            f"[TASK] ❌ Не удалось найти Behance-ссылку внутри страницы соцсети ({intermediary_url}). "
            "Нажимаю [❌ Пропустить] в Telegram-боте, чтобы перейти к следующему заданию."
        )
        _write_log(intermediary_url, "no_behance_link")
        await _click_button(message, "Пропустить")
        return True

    # === 3. ПРОВЕРКА СПИСКА ИСКЛЮЧЕНИЙ ===
    if _is_excluded(behance_url, _load_exclusions()):
        logger.warning(f"[SKIP] Проект в списке исключений: {behance_url}. Нажимаю [❌ Пропустить].")
        _write_log(behance_url, "excluded")
        await _click_button(message, "Пропустить")
        return True

    # === 4. ПЕРЕХОДИМ НА BEHANCE И ЛАЙКАЕМ ===
    # Ссылка получена со страницы соцсети — открываем её в браузере и ставим лайк
    status = await liker.like_project(behance_url)
    _write_log(behance_url, status)
    logger.info(f"[TASK] Status: {status}")

    # Фиксируем в лимитере только реальный новый лайк
    if status == "liked":
        rate_limiter.record_like()

        # === ПРОВЕРКА НА ТЕНЕВОЙ БАН ===
        like_confirmed = await liker.verify_like(behance_url)
        if not like_confirmed:
            _shadow_ban_active = True
            _write_log(behance_url, "shadowban")
            logger.error("=" * 60)
            logger.error("[SHADOWBAN] ❌ ПОДОЗРЕНИЕ НА ТЕНЕВОЙ БАН BEHANCE!")
            logger.error(f"[SHADOWBAN] URL: {behance_url}")
            logger.error("[SHADOWBAN] Лайк был нажат, но после перезагрузки — НЕ сохранился.")
            logger.error("[SHADOWBAN] Выполнение заданий остановлено!")
            logger.error("=" * 60)

            # Уведомление в Telegram (в «Избранное» — Saved Messages)
            shadowban_msg = (
                "🚨 *ВНИМАНИЕ! Подозрение на теневой бан Behance!*\n\n"
                f"🔗 URL: `{behance_url}`\n"
                "❌ Лайк был нажат, но после перезагрузки страницы — *не сохранился*.\n\n"
                "🛑 *Выполнение заданий автоматически остановлено.*\n\n"
                "Что делать:\n"
                "1. Откройте Behance вручную и проверьте аккаунт\n"
                "2. Попробуйте поставить лайк вручную\n"
                "3. Если лайки не ставятся — сделайте перерыв 24+ часов\n"
                "4. Перезапустите скрипт только после снятия бана"
            )
            try:
                await client.send_message("me", shadowban_msg, parse_mode="md")
                logger.info("[SHADOWBAN] Уведомление отправлено в Saved Messages.")
            except Exception as e:
                logger.error(f"[SHADOWBAN] Не удалось отправить уведомление: {e}")

            return False  # сигнал воркеру остановить обработку

    # Задержка перед кнопкой (имитируем ручное нажатие)
    try:
        if rate_limiter.session_likes >= MAX_LIKES_PER_SESSION:
            short_delay = random.uniform(5.0, 15.0)
            logger.info(
                f"[TASK] Posledniy layk sessii — zhdu vsego {short_delay:.0f}s pered knopkoy "
                f"(vmesto {DELAY_MIN:.0f}-{DELAY_MAX:.0f}s)."
            )
            await asyncio.sleep(short_delay)
        else:
            delay = random.uniform(DELAY_MIN, DELAY_MAX)
            logger.info(f"[TASK] Zhdu {delay:.0f}s (listаyu Behance, zatem zamru pered knopkoy)...")
            await liker.human_wait(delay)
    except Exception as wait_err:
        logger.warning(
            f"[TASK] Oshibka vo vremya ozhidaniya (ignoiruyu, zhmu knopku): {wait_err}"
        )

    # === НАЖИМАЕМ КНОПКУ В БОТЕ ===
    if status == "liked":
        ok = await _click_button(message, "Готово")
        if not ok:
            ok = await _click_button(message, "Gotovo")
        if not ok:
            logger.warning("[BTN] Knopka 'Готово' ne naydena!")
    else:
        ok = await _click_button(message, "Пропустить")
        if not ok:
            ok = await _click_button(message, "Propustit")
        if not ok:
            logger.warning("[BTN] Knopka 'Пропустить' ne naydena!")

    global _last_activity_time
    _last_activity_time = datetime.now()
    logger.info("[TASK] Zadaniye zaversheno.\n" + "-" * 50)
    return True


# ---------------------------------------------------------------------------
# Воркер очереди
# ---------------------------------------------------------------------------

async def _queue_worker(
    queue: asyncio.Queue,
    liker: BehanceLiker,
    rate_limiter: RateLimiter,
    client,
) -> None:
    """Бесконечно читает задания из очереди и выполняет их по одному."""
    global _shadow_ban_active
    while True:
        message, url = await queue.get()
        try:
            # Если теневой бан уже обнаружен — не берём новые задания
            if _shadow_ban_active:
                logger.warning(f"[WORKER] 🛑 Теневой бан активен — пропускаю задание: {url}")
                queue.task_done()
                continue

            ok = await _process_task(message, url, liker, rate_limiter, client)
            if not ok:
                # _shadow_ban_active уже выставлен внутри _process_task
                logger.error("[WORKER] 🛑 Теневой бан обнаружен. Дальнейшие задания заблокированы.")
        except Exception as exc:
            logger.error(f"[WORKER] Oshibka pri obrabotke zadaniya: {exc}", exc_info=True)
        finally:
            queue.task_done()


# ---------------------------------------------------------------------------
# Watchdog — periodicheska proverka istekshe pauzy vo vremya raboty
# ---------------------------------------------------------------------------

async def _pause_watchdog(
    client,
    rate_limiter: RateLimiter,
    task_queue: asyncio.Queue,
) -> None:
    """
    Каждые 3 минуты проверяет:
    1. Смену календарных суток (после 3:00 МСК) -> сброс на Сессию 1.
    2. Истечение плановой паузы -> автовозобновление.
    3. Долгий простой в рабочее время (30+ мин без задач при пустой очереди) -> запрос '▶️Копить баллы'.
    """
    global _last_activity_time
    while True:
        await asyncio.sleep(180)  # проверяем каждые 3 минуты
        from datetime import datetime as _dt

        # 1. Проверка смены суток
        rate_limiter.check_day_rollover()

        now = _dt.now()

        # 2. Истекла ли плановая пауза?
        if rate_limiter.pause_until:
            if now >= rate_limiter.pause_until:
                mins_ago = int((now - rate_limiter.pause_until).total_seconds() // 60)
                logger.warning(
                    f"[WATCHDOG] Pauza istekla {mins_ago} min nazad! "
                    f"Zapuskayu avtovozobnovleniye..."
                )
                asyncio.ensure_future(_auto_resume(client, rate_limiter))
            continue

        # 3. Если паузы нет — проверяем рабочий график и простой
        if rate_limiter.is_before_session1_start():
            continue

        if rate_limiter.is_too_late_for_session2():
            rate_limiter.schedule_next_day()
            continue

        if rate_limiter.cycle_likes >= 58:
            continue

        # В рабочее время при пустой очереди и простое 30+ минут напоминаем боту
        idle_secs = (now - _last_activity_time).total_seconds()
        if task_queue.empty() and idle_secs >= 1800:
            logger.info(
                f"[WATCHDOG] Prostoy {idle_secs/60:.0f} min v rabochee vremya (ochered pusta). "
                f"Napominayu botu: '{BOT_REQUEST_CMD}'..."
            )
            _last_activity_time = now
            try:
                await client.send_message(BOT_USERNAME, BOT_REQUEST_CMD)
            except Exception as e:
                logger.error(f"[WATCHDOG] Oshibka otpravki: {e}")


# ---------------------------------------------------------------------------
# Основная точка входа
# ---------------------------------------------------------------------------

async def start_telegram_listener(liker: BehanceLiker) -> None:
    """Запускает Telethon + очередь задач."""

    global _resume_lock, _shadow_ban_active
    _resume_lock = asyncio.Lock()
    _shadow_ban_active = False  # сбрасываем флаг при каждом (пере)запуске

    proxy = None
    if PROXY_HOST and PROXY_PORT:
        import socks
        proxy_type = socks.SOCKS5 if PROXY_TYPE == "socks5" else socks.HTTP
        proxy = (proxy_type, PROXY_HOST, PROXY_PORT, True, PROXY_USER or None, PROXY_PASS or None)
        logger.info(f"[TG] Proksi: {PROXY_TYPE}://{PROXY_HOST}:{PROXY_PORT}")
    else:
        logger.info("[TG] Soedinenie napryamuyu (cherez TUN VPN / bez proksi)")

    # -----------------------------------------------------------------------
    # РЕШЕНИЕ зависания при старте:
    #
    # Telethon вызывает GetStateRequest() без таймаута в _on_login() и в
    # set_receive_updates(). Через медленный HTTP-прокси -- зависает.
    #
    # receive_updates=False → Telethon использует InvokeWithoutUpdatesRequest
    # → сервер не шлёт апдейты при init → get_me() отвечает мгновенно.
    # После start() включаем апдейты вручную с wait_for таймаутом.
    # -----------------------------------------------------------------------
    client = TelegramClient(
        "behance_tg", TG_API_ID, TG_API_HASH,
        proxy=proxy,
        receive_updates=False,  # блокируем апдейты во время start()
    )
    try:
        await asyncio.wait_for(client.start(), timeout=60.0)
    except asyncio.TimeoutError:
        logger.error("[TG] client.start() timeout 60s!")
        try:
            await client.disconnect()
        except Exception:
            pass
        raise ConnectionError("Telegram start() timeout")
    logger.info("[TG] Podklyuchenie ustanovleno.")

    # Теперь включаем апдейты: устанавливаем флаг и делаем GetState с таймаутом
    # (это именно то, что делает set_receive_updates, но с нашим таймаутом)
    client._no_updates = False
    try:
        from telethon.tl.functions.updates import GetStateRequest
        _state = await asyncio.wait_for(client(GetStateRequest()), timeout=25.0)
        client.session.set_update_state(0, _state)
        client.session.save()
        logger.info(
            f"[TG] Apdeyty vklyucheny: pts={_state.pts}, qts={_state.qts}, seq={_state.seq}"
        )
    except asyncio.TimeoutError:
        logger.warning("[TG] GetState timeout — apdeyty budut rabotat bez sinhronizacii pts.")
    except Exception as _ge:
        logger.warning(f"[TG] GetState oshibka: {_ge}")

    me = await client.get_me()
    logger.info(f"[TG] Podklyuchon kak: {me.first_name} (@{me.username})")
    logger.info(f"[TG] Slushayu @{BOT_USERNAME}...")

    rate_limiter = RateLimiter()
    logger.info(f"[LIMIT] Status: {rate_limiter.status_line()}")

    # Очередь задач — обрабатываем строго по одному
    task_queue: asyncio.Queue = asyncio.Queue()

    # Запускаем воркер в фоне
    asyncio.ensure_future(_queue_worker(task_queue, liker, rate_limiter, client))

    # Watchdog: каждые 3 мин проверяет сутки, истечение паузы и простой
    asyncio.ensure_future(_pause_watchdog(client, rate_limiter, task_queue))

    # === CATCHUP: skan posled. 20 soobshcheniy ===
    logger.info("[STARTUP] Skaniruju posled. 20 soobshcheniy bota...")
    catchup_count = 0
    found_resume   = False   # bot skazal «pauza zakончilas»
    found_new_limit = False  # posle resume snova bylo 29

    messages_buf = []
    async for message in client.iter_messages(BOT_USERNAME, limit=20):
        messages_buf.append(message)

    # Soobshcheniya prishli v poryadke novye→starye; obrabotayem starye→novye
    for message in reversed(messages_buf):
        text = message.text or ""

        # Фильтр по возрасту: задания старше CATCHUP_MAX_AGE пропускаем
        # (уже обработаны вручную или кнопки уже нажаты)
        msg_age = datetime.now(timezone.utc) - message.date
        if msg_age > CATCHUP_MAX_AGE:
            # Служебные сообщения (limit/resume) всё равно анализируем — они не устаревают
            if not (_is_limit_message(text) or _is_resume_message(text)):
                continue

        # Limit: зафиксировать что лимит был
        if _is_limit_message(text):
            found_new_limit = True
            found_resume    = False   # сбрасываем — нужен новый resume

        # Resume: бот говорит «можно продолжать»
        # Засчитываем только если ДО этого было limit-сообщение
        elif _is_resume_message(text):
            if found_new_limit:
                found_resume    = True
                found_new_limit = False

        # Обычное задание со ссылкой и активными кнопками
        urls = _extract_urls(message)
        if urls and message.buttons:
            has_action_btn = any(
                any("готово" in btn.text.lower() or "пропустить" in btn.text.lower()
                    for btn in row)
                for row in message.buttons
            )
            if has_action_btn:
                target_url = urls[0]
                # Проверяем прямую ссылку (безопасность)
                if _is_direct_behance(target_url):
                    logger.warning(f"[STARTUP-SECURITY] Прямая Behance ссылка в catchup ({target_url})! Пропускаю.")
                    await _click_button(message, "Пропустить")
                    continue
                logger.info(f"[STARTUP] Пропущенное задание (возраст {msg_age.seconds//60}м): {target_url}")
                await task_queue.put((message, target_url))
                catchup_count += 1
                found_resume = False  # уже получили задание после resume

    if catchup_count:
        logger.info(f"[STARTUP] Dobavleno v ochered: {catchup_count} zadaniy.")

    from datetime import datetime as _dt

    # === PAUZA UZE ISTEKLA poka bot byl vyklyuchen? ===
    if rate_limiter.pause_until and _dt.now() >= rate_limiter.pause_until:
        mins_ago = int((_dt.now() - rate_limiter.pause_until).total_seconds() // 60)
        logger.warning(
            f"[STARTUP] Pauza istekla {mins_ago} minut nazad! "
            f"Avtomaticheski vozobnovlyayu rabotu..."
        )
        asyncio.ensure_future(_auto_resume(client, rate_limiter))
    # === BOT SKAZAL «PAUZA ZAKONCHILAS» no taymer eshche idet ===
    elif found_resume and rate_limiter.pause_until and _dt.now() < rate_limiter.pause_until:
        logger.warning("[STARTUP] Bot: pauza zakonchilas, vozobnovlyayu po signalu bota!")
        asyncio.ensure_future(_auto_resume(client, rate_limiter))
    elif not catchup_count and not found_resume:
        if not rate_limiter.pause_until:
            # Нет задач, нет паузы — автоматически запрашиваем следующее задание
            logger.info("[STARTUP] Нет задач и паузы — автозапрос задания через 5с...")
            asyncio.ensure_future(_startup_request(client, rate_limiter))
        else:
            logger.info("[STARTUP] Нет задач, пауза активна — жду окончания паузы.")

    @client.on(events.NewMessage(from_users=BOT_USERNAME))
    async def handle_message(event: events.NewMessage.Event) -> None:
        global _last_activity_time
        _last_activity_time = datetime.now()

        message: Message = event.message
        text: str = message.text or ""

        preview = text[:120].replace("\n", " ")
        logger.info(f"[BOT] {preview}...")

        # Возраст сообщения (Telethon возвращает UTC с tzinfo)
        msg_age_sec = (datetime.now(timezone.utc) - message.date).total_seconds()
        is_fresh = msg_age_sec <= 120  # свежее 2 минут

        # === 1. ЛИМИТ ДОСТИГНУТ — принудительная пауза ===
        if _is_limit_message(text):
            if not is_fresh:
                logger.info(f"[BOT-LIMIT] Staroe soobshcheniye ({msg_age_sec:.0f}s), propuskayu.")
                return

            if rate_limiter.session_likes == 0 and not rate_limiter.pause_until:
                retry_until = datetime.now() + timedelta(minutes=10)
                rate_limiter.pause_until = retry_until
                rate_limiter._save()
                logger.warning(
                    f"[BOT-LIMIT] Lozhniy limit — startanuli na 1-2 min ranshe bota! "
                    f"Zhdu 10min do {retry_until.strftime('%H:%M:%S')}."
                )
                return

            logger.warning("[BOT-LIMIT] Bot: 29 laikov vypolneno, stavlyu pauzu!")
            if not rate_limiter.pause_until:
                rate_limiter.session_likes = max(rate_limiter.session_likes, 29)
                rate_limiter._start_pause()
                rate_limiter._save()
            logger.warning(f"[BOT-LIMIT] Pauza do: "
                           f"{rate_limiter.pause_until.strftime('%d.%m %H:%M')}")
            return

        # === 2. ПАУЗА ЗАКОНЧИЛАСЬ — автовозобновление ===
        if _is_resume_message(text):
            if not is_fresh:
                logger.info(f"[BOT-RESUME] Staroe soobshcheniye ({msg_age_sec:.0f}s), propuskayu.")
                return
            logger.info("[BOT-RESUME] Bot: pauza zakonchilas! Vozobnovlyayu...")
            asyncio.ensure_future(_auto_resume(client, rate_limiter))
            return

        # === 3. НАЖАТИЕ ИНЛАЙН-КНОПКИ В УВЕДОМЛЕНИЯХ (Новые задания / Доступные задания) ===
        if message.buttons:
            for row in message.buttons:
                for btn in row:
                    if any(k in btn.text.lower() for k in ["новые задания", "доступные задания"]):
                        if not (rate_limiter.pause_until and _dt.now() < rate_limiter.pause_until):
                            logger.info(f"[BOT-NOTIFICATION] Нажимаю инлайн-кнопку: [{btn.text.strip()}]")
                            await asyncio.sleep(random.uniform(1.0, 2.5))
                            try:
                                await btn.click()
                                return
                            except Exception as be:
                                logger.warning(f"[BTN] Ошибка нажатия [{btn.text}]: {be}")

        # === 3.8. ЗАДАНИЯ ВРЕМЕННО ЗАКОНЧИЛИСЬ В БОТЕ ===
        if _is_no_tasks_message(text):
            if not is_fresh:
                logger.info("[BOT-EMPTY] Staroe soobshchenie o net zadaniy, propuskayu.")
                return

            retry_mins = random.uniform(15.0, 25.0)
            logger.warning(
                f"[BOT-EMPTY] V bote vremenno net zadaniy. "
                f"Povtorniy zapros cherez {retry_mins:.1f} min..."
            )
            asyncio.ensure_future(_retry_after_no_tasks(client, rate_limiter, retry_mins * 60))
            return

        # === 4. ОБЫЧНОЕ ЗАДАНИЕ СО ССЫЛКОЙ ===
        urls = _extract_urls(message)
        if not urls:
            logger.info("  -> Net ssylki v soobshchenii, propuskayu.")
            return

        target_url = urls[0]

        # === ПРОВЕРКА НА ПРЯМУЮ ССЫЛКУ BEHANCE В СООБЩЕНИИ БОТА (ПРАВИЛО БЕЗОПАСНОСТИ) ===
        if _is_direct_behance(target_url):
            logger.warning(
                f"[SECURITY] ⚠️ ТГ-бот выдал прямую ссылку Behance в задании ({target_url})! "
                "По правилам безопасности прямые переходы из Telegram запрещены (нет внешнего реферера). Нажимаю [❌ Пропустить]."
            )
            await _click_button(message, "Пропустить")
            return

        # Не берём задание если активна дневная пауза (58/58 лайков)
        if rate_limiter.pause_until and rate_limiter.cycle_likes >= 58:
            logger.warning(
                f"[SKIP] Dnevnoy limit (58 laykov). Propuskayu zadaniye do "
                f"{rate_limiter.pause_until.strftime('%d.%m %H:%M')}."
            )
            await _click_button(message, "Пропустить")
            return

        # Не берём задание если просрочен дедлайн Сессии 2 (22:00 МСК)
        if rate_limiter.is_too_late_for_session2():
            deadline = rate_limiter.get_session2_deadline()
            logger.warning(
                f"[SKIP] Deadline S2 ({deadline.strftime('%H:%M')} MSK) proshedel — "
                f"ne berу zadanie, perehozhu na sleduyushchiy den'."
            )
            await _click_button(message, "Пропустить")
            rate_limiter.schedule_next_day()
            return

        qsize = task_queue.qsize()
        logger.info(f"  -> Dobavlyayu v ochered: {target_url}  (v ocheredi: {qsize})")
        await task_queue.put((message, target_url))

    await client.run_until_disconnected()



# ---------------------------------------------------------------------------
# Детектирование служебных сообщений бота
# ---------------------------------------------------------------------------

def _is_limit_message(text: str) -> bool:
    """
    Бот сообщает о достижении лимита 29 лайков.

    Сообщение 1: "🔥Ты выполнил 29 заданий подряд ... пауза 3 часа"
    Сообщение 2: "‼️ВАЖНО‼️в ближайшие 3 часа не ставь лайки"
    """
    t = text.lower()
    patterns = [
        # Сообщение 1
        "выполнил 29",
        "29 заданий подряд",
        "пауза в активности на 3",
        "соблюдай этот лимит",
        # Сообщение 2 (‼️ВАЖНО‼️)
        "в ближайшие 3 часа не ставь",
        "ближайшие 3 часа не ставь лайки",
        "ни в нашем боте",
        "✋пауза на 3 часа",
        "29 лайков\n✋стоп",
    ]
    return any(p in t for p in patterns)


def _is_resume_message(text: str) -> bool:
    """
    Бот сообщает что пауза закончилась — можно продолжать.

    Примеры реальных сообщений:
      "⏰ Прошло 3 часа, можешь дальше лайкать"
      "⏰ Пауза давно закончилась — до дневной нормы осталось 29 лайков."

    ВАЖНО: паттерн "продолжай выполнять задания" УБРАН — он слишком широкий
    и совпадает с обычными задачными сообщениями бота.
    """
    t = text.lower()
    patterns = [
        "прошло 3 часа",
        "пауза давно закончилась",
        "можешь дальше лайкать",
        "осталось 29 лайков",
        "можешь продолжать лайкать",  # возможные варианты
        "пауза закончилась",
    ]
    return any(p in t for p in patterns)


def _is_task_selection_message(text: str, message) -> bool:
    """
    Бот предлагает выбрать тип задания (после нажатия Копить баллы).

    Пример: "Выбери тип задания для выполнения"
    с кнопками: 👍Лайк | 💬Комментарий | 👥Подписка | 📌Сохранение
    """
    t = text.lower()
    has_text = any(p in t for p in ["выбери тип задания", "тип задания"])
    has_like_btn = False
    if message.buttons:
        for row in message.buttons:
            for btn in row:
                if "лайк" in btn.text.lower():
                    has_like_btn = True
    # Оба условия обязательны: текст про «тип задания» И кнопка «Лайк»
    return has_text and has_like_btn


def _is_not_credited_message(text: str) -> bool:
    """
    Бот сообщает что баллы за предыдущее задание не начислены.

    Пример: "Баллы за предыдущее задание не начислены
             Похоже, бот не увидел лайк на проекте..."
    Кнопка: ❌Пропустить
    """
    t = text.lower()
    patterns = [
        "баллы за предыдущее задание не начислены",
        "бот не увидел лайк",
        "не увидел лайк на проекте",
    ]
    return any(p in t for p in patterns)


def _is_no_tasks_message(text: str) -> bool:
    """
    Бот сообщает, что задания закончились на данный момент.
    Пример: "Ты выполнил все доступные задания на данный момент..."
    """
    t = text.lower()
    patterns = [
        "выполнил все доступные задания",
        "все доступные задания",
        "доступные задания на данный момент",
        "нет доступных заданий",
        "задания закончились",
        "новых заданий пока нет",
    ]
    return any(p in t for p in patterns)


async def _retry_after_no_tasks(client, rate_limiter: RateLimiter, delay_sec: float) -> None:
    """Ждёт delay_sec и отправляет BOT_REQUEST_CMD, если бот в рабочем окне."""
    await asyncio.sleep(delay_sec)

    rate_limiter.check_day_rollover()

    if rate_limiter.pause_until and datetime.now() < rate_limiter.pause_until:
        logger.info("[EMPTY-RETRY] Aktivna planovaya pauza, propuskayu retry.")
        return

    if rate_limiter.is_too_late_for_session2():
        logger.info("[EMPTY-RETRY] Proshedel deadline S2, propuskayu retry.")
        rate_limiter.schedule_next_day()
        return

    if rate_limiter.is_before_session1_start():
        logger.info("[EMPTY-RETRY] Eshche rano dlya S1, zhdu utra.")
        return

    logger.info(f"[EMPTY-RETRY] Proveryayu novye zadaniya v bote: otpravlyayu '{BOT_REQUEST_CMD}'...")
    try:
        await client.send_message(BOT_USERNAME, BOT_REQUEST_CMD)
    except Exception as e:
        logger.error(f"[EMPTY-RETRY] Oshibka otpravki: {e}")


async def _auto_resume(client, rate_limiter: RateLimiter) -> None:
    """
    Автоматически возобновляет сбор лайков после истечения паузы.
    Защита: asyncio.Lock гарантирует что только ОДНА копия работает одновременно.
    """
    global _resume_lock
    if _resume_lock is None or _resume_lock.locked():
        logger.info("[RESUME] Uzhe vypolnyaetsya ili lock ne inicializirovan, propuskayu.")
        return

    async with _resume_lock:
        # Перепроверяем: пауза ещё активна? Если да — слишком рано
        now = datetime.now()
        if rate_limiter.pause_until and now < rate_limiter.pause_until:
            remaining = (rate_limiter.pause_until - now).total_seconds()
            logger.info(
                f"[RESUME] Pauza eshche aktivna ({remaining/60:.0f} min), "
                f"propuskayu avtovozobnovleniye."
            )
            return

        # Дедлайн Сессии 2 уже прошёл — откладываем на завтра
        if rate_limiter.is_too_late_for_session2():
            deadline = rate_limiter.get_session2_deadline()
            logger.warning(
                f"[RESUME] Slishkom pozdno dlya S2 "
                f"(deadline {deadline.strftime('%H:%M')} MSK uzhe proshedel). "
                f"Otkladyvayu na sleduyushchiy den'."
            )
            rate_limiter.schedule_next_day()
            return

        # МИНИ-ПАУЗА (после ложного лимита из-за раннего старта).
        is_retry_after_early_start = (
            rate_limiter.pause_until is None
            and rate_limiter.session_likes == 0
            and rate_limiter.cycle_likes > 0  # цикл идёт, сессия ещё не началась
        )
        if is_retry_after_early_start:
            logger.info(
                "[RESUME] Mini-pauza istekla (povtor posle rannego starta). "
                f"Ne menyayu sessiyu — prosto snova otpravlyayu '{BOT_REQUEST_CMD}'."
            )
            await asyncio.sleep(random.uniform(3.0, 8.0))
            try:
                await client.send_message(BOT_USERNAME, BOT_REQUEST_CMD)
                logger.info(f"[RESUME] Zapros '{BOT_REQUEST_CMD}' povtorno otpravlen.")
            except Exception as e:
                logger.error(f"[RESUME] Oshibka otpravki: {e}")
            return

        # Завершаем паузу и переключаем сессию
        if rate_limiter.pause_until:
            rate_limiter._end_pause()
            rate_limiter._save()
            logger.info("[RESUME] Pauza zakonchena, sessiya pereklyuchena.")

        # Человеческая задержка перед нажатием
        await asyncio.sleep(random.uniform(3.0, 8.0))

        logger.info(f"[RESUME] Zaprawivayu zadaniya: '{BOT_REQUEST_CMD}'...")
        try:
            await client.send_message(BOT_USERNAME, BOT_REQUEST_CMD)
        except Exception as e:
            logger.error(f"[RESUME] Oshibka otpravki: {e}")

async def _startup_request(client, rate_limiter: RateLimiter) -> None:
    """
    Автоматически запрашивает задание при старте:
    — если до 6:00 МСК (+ рандом) — ждёт до session1_earliest
    — если просрочен дедлайн S2 (22:00 МСК) — не запрашивает
    """
    # ── Проверка: не слишком ли рано для Сессии 1 ──
    wait_secs = rate_limiter.seconds_until_session1()
    if wait_secs > 0:
        wake_at = rate_limiter.session1_earliest
        logger.info(
            f"[SCHEDULE] Ranshe {wake_at.strftime('%H:%M')} MSK nachinat nelzya. "
            f"Zhdu {wait_secs/3600:.1f}ch ({wait_secs/60:.0f} min)..."
        )
        await asyncio.sleep(wait_secs)
        logger.info(f"[SCHEDULE] Vremya prishlo! Otpravlyayu '{BOT_REQUEST_CMD}'...")

    # ── Проверка: дедлайн Сессии 2 ──
    if rate_limiter.is_too_late_for_session2():
        deadline = rate_limiter.get_session2_deadline()
        logger.warning(
            f"[SCHEDULE] Slishkom pozdno dlya S2 "
            f"(deadline {deadline.strftime('%H:%M')} MSK). "
            f"Zhdyu sleduyushchego dnya."
        )
        rate_limiter.schedule_next_day()
        return

    delay = random.uniform(4.0, 9.0)
    logger.info(f'[STARTUP] Zhdu {delay:.0f}s pered zaprosom zadaniya...')
    await asyncio.sleep(delay)
    logger.info(f"[STARTUP] Otpravlyayu '{BOT_REQUEST_CMD}' botu...")
    try:
        await client.send_message(BOT_USERNAME, BOT_REQUEST_CMD)
        logger.info('[STARTUP] Zapros otpravlen — zhdu otveta bota.')
    except Exception as e:
        logger.error(f'[STARTUP] Oshibka otpravki zaprosa: {e}')
