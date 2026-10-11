"""
behance_worker.py -- Модульный воркер для одного аккаунта Behance + Telegram.

Инкапсулирует браузер Playwright, сессию Telethon, RateLimiter и очередь задач.
Может работать независимо или параллельно с другими воркерами.
"""

import re
import asyncio
import random
import logging
import csv
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.custom import Message

from accounts_config import AccountConfig
from behance_liker import BehanceLiker
from rate_limiter import RateLimiter, MAX_LIKES_PER_SESSION

logger = logging.getLogger(__name__)

BEHANCE_RE = re.compile(r"https?://(?:www\.)?(?:behance\.net|be\.net)/gallery/[\w/%-]+")
BOT_REQUEST_CMD = "▶️ Доступные задания"

CATCHUP_MAX_AGE = timedelta(minutes=15)


def _is_direct_behance(url: str) -> bool:
    u = url.lower()
    return "behance.net" in u or "be.net" in u


def _extract_urls(message: Message) -> list[str]:
    urls = []
    text = message.text or ""
    for match in re.finditer(r"https?://[^\s)\]\"'>]+", text):
        urls.append(match.group(0).rstrip(".,;"))
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


def _normalize_url(url: str) -> str:
    url = url.lower().strip().rstrip("/")
    url = url.replace("//www.behance.net", "//behance.net")
    for sep in ("?", "#"):
        idx = url.find(sep)
        if idx != -1:
            url = url[:idx]
    return url


class BehanceAccountWorker:
    """Изолированный воркер одного аккаунта (Telegram + Behance)."""

    def __init__(self, config: AccountConfig):
        self.config = config
        self.account_id = config.account_id
        self.name = config.name

        self.liker = BehanceLiker(
            cookies_file=config.behance_cookies_path,
            browser_proxy=config.browser_proxy,
            headless=config.headless,
            account_id=config.account_id,
        )

        self.rate_limiter = RateLimiter(
            state_file=config.rate_state_path,
            account_id=config.account_id,
        )

        self.client: Optional[TelegramClient] = None
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.shadow_ban_active: bool = False
        self.resume_lock: asyncio.Lock = asyncio.Lock()
        self.last_activity_time: datetime = datetime.now()
        self.is_running: bool = False
        self._morning_requested: bool = False

        self._worker_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self.exclusions = self._load_exclusions()

    def _log(self, level: str, msg: str, **kwargs):
        prefix = f"[{self.account_id}]"
        getattr(logger, level)(f"{prefix} {msg}", **kwargs)

    def _load_exclusions(self) -> set:
        if not os.path.exists(self.config.exclusions_path):
            return set()
        excluded = set()
        try:
            with open(self.config.exclusions_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    excluded.add(_normalize_url(line))
        except Exception as e:
            self._log("warning", f"Oshibka chteniya exclusions: {e}")
        return excluded

    def _is_excluded(self, url: str) -> bool:
        return _normalize_url(url) in self.exclusions

    def _write_log(self, url: str, status: str) -> None:
        log_file = self.config.log_file_path
        parent = os.path.dirname(os.path.abspath(log_file))
        if parent:
            os.makedirs(parent, exist_ok=True)
        write_header = not os.path.exists(log_file)
        try:
            with open(log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(["timestamp", "url", "status"])
                writer.writerow([datetime.now().isoformat(), url, status])
        except Exception as e:
            self._log("warning", f"Oshibka zapisi loga: {e}")

    async def _click_button(self, message: Message, text_fragment: str) -> bool:
        if not message.buttons:
            return False
        for row in message.buttons:
            for btn in row:
                if text_fragment.lower() in btn.text.lower():
                    try:
                        await btn.click()
                        self._log("info", f"[BTN] Nazhata knopka: [{btn.text.strip()}]")
                        return True
                    except Exception as exc:
                        self._log("warning", f"[BTN] Oshibka klika [{btn.text}]: {exc}")
        return False

    async def _auto_resume(self) -> None:
        async with self.resume_lock:
            if not self.rate_limiter.pause_until:
                return
            if datetime.now() < self.rate_limiter.pause_until:
                return

            self._log("info", "=" * 50)
            self._log("info", "[RESUME] Pauza isteka! Proveryayu smenu sutok...")
            self.rate_limiter._end_pause()

            self._log("info", f"[RESUME] Zapushchena Sessiya {self.rate_limiter.session_number}!")
            self._log("info", f"[RESUME] Zaprashivayu novye zadaniya: '{BOT_REQUEST_CMD}'...")
            try:
                await self.client.send_message(self.config.bot_username, BOT_REQUEST_CMD)
                self.last_activity_time = datetime.now()
            except Exception as e:
                self._log("error", f"[RESUME] Oshibka otpravki zaprosa: {e}")
            self._log("info", "=" * 50)

    async def _process_task(self, message: Message, intermediary_url: str) -> bool:
        self._log("info", f"[TASK] Vhodyashchaya ssylka: {intermediary_url}")
        self._log("info", f"[TASK] Limit: {self.rate_limiter.status_line()}")

        await self.rate_limiter.wait_if_needed()

        if _is_direct_behance(intermediary_url):
            self._log(
                "warning",
                f"[SECURITY] ⚠️ TG-bot vydal pryamuyu ssylku Behance: {intermediary_url}! "
                "Pryamye ssylki zapreshcheny (net referera). Nazhimayu [❌ Propustit]."
            )
            await self._click_button(message, "Пропустить")
            self._write_log(intermediary_url, "security_skip_direct")
            return True

        await asyncio.sleep(random.uniform(1.5, 3.5))
        behance_url = await self.liker.resolve_intermediary_url(intermediary_url)

        if not behance_url:
            self._log(
                "warning",
                f"[TASK] ❌ Ne udalos nayti Behance-ssylku vnutri sotsseti ({intermediary_url}). "
                "Nazhimayu [❌ Propustit] v TG-bote."
            )
            self._write_log(intermediary_url, "no_behance_link")
            await self._click_button(message, "Пропустить")
            return True

        if self._is_excluded(behance_url):
            self._log("warning", f"[SKIP] Proekt v spiske isklyucheniy: {behance_url}. Nazhimayu [❌ Propustit].")
            self._write_log(behance_url, "excluded")
            await self._click_button(message, "Пропустить")
            return True

        status = await self.liker.like_project(behance_url)
        self._write_log(behance_url, status)
        self._log("info", f"[TASK] Status: {status}")

        if status == "liked":
            self.rate_limiter.record_like()

            like_confirmed = await self.liker.verify_like(behance_url)
            if not like_confirmed:
                self.shadow_ban_active = True
                self._write_log(behance_url, "shadowban")
                self._log("error", "=" * 60)
                self._log("error", f"[SHADOWBAN] ❌ PODODZRENIYE NA TENOVOY BAN BEHANCE! URL: {behance_url}")
                self._log("error", "=" * 60)

                shadowban_msg = (
                    f"🚨 *ВНИМАНИЕ! Подозрение на теневой бан Behance для аккаунта {self.name}!*\n\n"
                    f"🔗 URL: `{behance_url}`\n"
                    "❌ Лайк был нажат, но после перезагрузки — не сохранился.\n\n"
                    "🛑 *Выполнение заданий автоматически остановлено.*"
                )
                try:
                    await self.client.send_message("me", shadowban_msg, parse_mode="md")
                except Exception as e:
                    self._log("error", f"[SHADOWBAN] Ne udalos otpravit v me: {e}")
                return False

        try:
            if self.rate_limiter.session_likes >= MAX_LIKES_PER_SESSION:
                short_delay = random.uniform(5.0, 15.0)
                self._log("info", f"[TASK] Posledniy layk sessii — zhdu {short_delay:.0f}s pered knopkoy.")
                await asyncio.sleep(short_delay)
            else:
                delay = random.uniform(self.config.delay_min, self.config.delay_max)
                self._log("info", f"[TASK] Zhdu {delay:.0f}s pered knopkoy Gotovo...")
                await self.liker.human_wait(delay)
        except Exception as wait_err:
            self._log("warning", f"[TASK] Oshibka vo vremya ozhidaniya: {wait_err}")

        if status == "liked":
            ok = await self._click_button(message, "Готово")
            if not ok:
                ok = await self._click_button(message, "Gotovo")
            if not ok:
                self._log("warning", "[BTN] Knopka 'Готово' ne naydena!")
        else:
            ok = await self._click_button(message, "Пропустить")
            if not ok:
                ok = await self._click_button(message, "Propustit")
            if not ok:
                self._log("warning", "[BTN] Knopka 'Пропустить' ne naydena!")

        self.last_activity_time = datetime.now()
        self._log("info", "[TASK] Zadaniye zaversheno. " + "-" * 50)
        return True

    async def _queue_worker(self) -> None:
        while self.is_running:
            try:
                message, url = await self.task_queue.get()
            except asyncio.CancelledError:
                break
            try:
                if self.shadow_ban_active:
                    self._log("warning", f"[WORKER] 🛑 Tenovoy ban aktiven — propuskayu zadaniye: {url}")
                    self.task_queue.task_done()
                    continue

                ok = await self._process_task(message, url)
                if not ok:
                    self._log("error", "[WORKER] 🛑 Tenovoy ban obnaruzhen. Dalneyshie zadaniya zablokirovany.")
            except Exception as exc:
                self._log("error", f"[WORKER] Oshibka pri obrabotke zadaniya: {exc}", exc_info=True)
            finally:
                self.task_queue.task_done()

    async def _pause_watchdog(self) -> None:
        while self.is_running:
            try:
                await asyncio.sleep(180)
            except asyncio.CancelledError:
                break

            self.rate_limiter.check_day_rollover()
            now = datetime.now()

            if self.rate_limiter.pause_until:
                if now >= self.rate_limiter.pause_until:
                    mins_ago = int((now - self.rate_limiter.pause_until).total_seconds() // 60)
                    self._log("warning", f"[WATCHDOG] Pauza istekla {mins_ago} min nazad! Avtovozobnovlyayu...")
                    asyncio.ensure_future(self._auto_resume())
                continue

            if self.rate_limiter.is_before_session1_start():
                self._morning_requested = False
                continue

            if self.rate_limiter.session_likes == 0 and not self._morning_requested and self.task_queue.empty():
                self._morning_requested = True
                self.last_activity_time = now
                self._log("info", f"[WATCHDOG] ☀️ Nastupilo utro! Zaprashivayu pervye zadaniya dnya: '{BOT_REQUEST_CMD}'...")
                try:
                    await self.client.send_message(self.config.bot_username, BOT_REQUEST_CMD)
                except Exception as e:
                    self._log("error", f"[WATCHDOG] Oshibka utrennego zaprosa: {e}")
                continue

            if self.rate_limiter.is_too_late_for_session2():
                self.rate_limiter.schedule_next_day()
                continue

            if self.rate_limiter.cycle_likes >= 58:
                continue

            idle_secs = (now - self.last_activity_time).total_seconds()
            if self.task_queue.empty() and idle_secs >= 7200:
                self._log(
                    "info",
                    f"[WATCHDOG] Prostoy {idle_secs/60:.0f} min v rabochee vremya. "
                    f"Napominayu botu: '{BOT_REQUEST_CMD}'..."
                )
                self.last_activity_time = now
                try:
                    await self.client.send_message(self.config.bot_username, BOT_REQUEST_CMD)
                except Exception as e:
                    self._log("error", f"[WATCHDOG] Oshibka otpravki: {e}")

    async def start(self) -> None:
        self._log("info", "=" * 55)
        self._log("info", f"   [START] Zapusk vorkera {self.name}...")
        self._log("info", "=" * 55)

        if not os.path.exists(self.config.behance_cookies_path):
            raise FileNotFoundError(f"Cookies ne naydeny: {self.config.behance_cookies_path}")


        if not os.path.exists(self.config.tg_session_path):
            raise FileNotFoundError(f"Sessiya TG ne naydena: {self.config.tg_session_path}")


        self._log("info", "Initsializiruyu brauzer Behance...")
        await self.liker.init()
        self._log("info", "[OK] Brauzer Behance gotov.")

        proxy = None
        if self.config.tg_proxy_host and self.config.tg_proxy_port:
            import socks
            proxy_type = socks.SOCKS5 if self.config.tg_proxy_type == "socks5" else socks.HTTP
            proxy = (
                proxy_type,
                self.config.tg_proxy_host,
                self.config.tg_proxy_port,
                True,
                self.config.tg_proxy_user or None,
                self.config.tg_proxy_pass or None,
            )
            self._log("info", f"[TG] Proksi: {self.config.tg_proxy_type}://{self.config.tg_proxy_host}:{self.config.tg_proxy_port}")

        self.client = TelegramClient(
            self.config.tg_session_path,
            self.config.tg_api_id,
            self.config.tg_api_hash,
            proxy=proxy,
            receive_updates=False,
        )

        try:
            await asyncio.wait_for(self.client.start(), timeout=60.0)
        except asyncio.TimeoutError:
            raise ConnectionError(f"[{self.account_id}] Telegram client.start() timeout 60s")

        self.client._no_updates = False
        try:
            from telethon.tl.functions.updates import GetStateRequest
            _state = await asyncio.wait_for(self.client(GetStateRequest()), timeout=25.0)
            self.client.session.set_update_state(0, _state)
            self.client.session.save()
            self._log("info", "[TG] Sinhronizatsiya sostoyaniya uspeshna.")
        except Exception as e:
            self._log("warning", f"[TG] GetStateRequest propushchen: {e}")

        me = await self.client.get_me()
        user_display = f"@{me.username}" if me.username else f"ID:{me.id}"
        self._log("info", f"[TG] Avtorizovan kak: {user_display} ({me.first_name})")

        self.is_running = True
        self._worker_task = asyncio.create_task(self._queue_worker())
        self._watchdog_task = asyncio.create_task(self._pause_watchdog())

        bot_username = self.config.bot_username

        @self.client.on(events.NewMessage(chats=bot_username))
        async def on_new_message(event: events.NewMessage.Event):
            msg: Message = event.message
            text = msg.text or ""
            self.last_activity_time = datetime.now()

            # Proverka na otsutstvie zadaniy
            if "нет заданий" in text.lower() or "в боте временно нет" in text.lower():
                wait_min = round(random.uniform(120.0, 180.0), 1)
                self._log("warning", f"[BOT-EMPTY] V bote net zadaniy. Povtor cherez {wait_min} min...")
                await asyncio.sleep(wait_min * 60)
                try:
                    await self.client.send_message(bot_username, BOT_REQUEST_CMD)
                except Exception as ex:
                    self._log("error", f"[BOT-EMPTY] Oshibka zaprosa: {ex}")
                return

            if "вам начислено" in text.lower() or "баллов" in text.lower():
                self._log("info", f"[POINTS] {text.strip()[:100]}")

            urls = _extract_urls(msg)
            for u in urls:
                self._log("info", f"[NEW-TASK] Dobavleno v ochered: {u}")
                await self.task_queue.put((msg, u))

        @self.client.on(events.MessageEdited(chats=bot_username))
        async def on_message_edited(event: events.MessageEdited.Event):
            msg: Message = event.message
            self.last_activity_time = datetime.now()
            urls = _extract_urls(msg)
            for u in urls:
                self._log("info", f"[EDIT-TASK] Dobavleno v ochered: {u}")
                await self.task_queue.put((msg, u))

        # Catchup: proverka aktivnyh i nedavnih zadaniy bota
        try:
            self._log("info", "Proveryayu poslednie soobshcheniya bota...")
            messages = await self.client.get_messages(bot_username, limit=10)
            now_utc = datetime.now(timezone.utc)
            found_any = False
            
            # Ishchem samoe svezhee zadanie s aktivnymi knopkami [Gotovo / Propustit]
            for m in messages:
                if not m.date:
                    continue
                urls = _extract_urls(m)
                if urls and m.buttons:
                    has_action_btn = any(
                        any("готово" in btn.text.lower() or "gotovo" in btn.text.lower()
                            or "пропустить" in btn.text.lower() or "propustit" in btn.text.lower()
                            for btn in row)
                        for row in m.buttons
                    )
                    if has_action_btn:
                        target_url = urls[0]
                        msg_age_m = int((now_utc - m.date.replace(tzinfo=timezone.utc)).total_seconds() // 60)
                        self._log("info", f"[CATCHUP] Naydeno aktivnoe zadaniye (vozrast {msg_age_m}m): {target_url}")
                        await self.task_queue.put((m, target_url))
                        found_any = True
                        break

            if not found_any and self.task_queue.empty():
                if self.rate_limiter.is_before_session1_start():
                    target = self.rate_limiter.session1_earliest or self.rate_limiter._compute_session1_earliest()
                    self._log("info", f"[NIGHT] Seychas noch. Zaprashivat zadaniya v bot budu utrom v {target.strftime('%H:%M')} MSK.")
                else:
                    self._log("info", f"Zaprashivayu zadaniya: '{BOT_REQUEST_CMD}'...")
                    await self.client.send_message(bot_username, BOT_REQUEST_CMD)
        except Exception as e:
            self._log("warning", f"Oshibka catchup: {e}")

        self._log("info", f"[OK] Vorker {self.name} uspeshno zapushchen i slushaet bota!")

    async def run_until_stopped(self) -> None:
        try:
            await self.client.run_until_disconnected()
        finally:
            await self.stop()

    async def stop(self) -> None:
        if not self.is_running:
            return
        self.is_running = False
        self._log("info", f"Ostanavlivayu vorker {self.name}...")

        if self._worker_task:
            self._worker_task.cancel()
        if self._watchdog_task:
            self._watchdog_task.cancel()

        if self.client and self.client.is_connected():
            await self.client.disconnect()

        await self.liker.close()
        self._log("info", f"[STOP] Vorker {self.name} ostanovlen.")
