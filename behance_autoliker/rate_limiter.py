"""
rate_limiter.py -- Защита от бана Behance.

Расписание (МСК = локальное время машины, UTC+3):

  Границы суток:  3:00 МСК → 0:00 МСК следующего дня (21-часовое окно)
  Сессия 1:       старт не ранее 6:00 МСК + случайный сдвиг 0–2ч
  Перерыв:        случайно 3ч – 5ч (с ограничением: S2 должна уложиться до 0:00)
  Сессия 2:       старт не позже 22:00 МСК (= 0:00 − MAX_SESSION_DURATION)
  После S2:       пауза до следующего дня (6:00 МСК + случайный сдвиг)

Оценка длительности одной сессии (29 лайков):
  29 × 90с (среднее из 30–150с) = 43.5 мин
  + загрузка страниц, ответ бота = +20 мин
  + сбои, повторы, пропуски     = +15 мин
  Итого ~1ч 20мин / MAX_SESSION_DURATION = 2ч (с буфером)

Максимум в сутки: 58 лайков (29 + 29).
"""

import asyncio
import json
import logging
import os
import random
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join("session", "rate_state.json")

MAX_LIKES_PER_SESSION = 29
MAX_LIKES_PER_DAY     = 58

# ── Временные параметры (часы локального времени = МСК на этой машине) ──────
DAY_START_HOUR      = 3    # 3:00 МСК — граница суток
SESSION1_OPEN_HOUR  = 6    # Сессия 1 не раньше 6:00 МСК
SESSION1_RAND_SECS  = 2 * 3600   # случайный сдвиг 0..2ч после 6:00 → не позже 8:00

SESSION_BREAK_MIN = timedelta(hours=3)
SESSION_BREAK_MAX = timedelta(hours=5)

# Сколько занимает одна сессия в худшем случае (29 задач + запасы)
MAX_SESSION_DURATION = timedelta(hours=2)


class RateLimiter:
    """Считает лайки и управляет расписанием сессий по МСК-суткам."""

    def __init__(self):
        self.session_likes: int               = 0
        self.session_number: int              = 1
        self.cycle_likes: int                 = 0
        self.cycle_start: datetime | None     = None
        self.last_like_time: datetime | None  = None
        self.pause_until: datetime | None     = None
        self.session1_earliest: datetime | None = None   # разрешённый старт S1 сегодня
        self.utc_date: str                    = ""       # YYYY-MM-DD по Гринвичу (UTC)
        self._load()
        self.check_day_rollover()
        self._refresh_session1_earliest()

    def check_day_rollover(self) -> bool:
        """
        Проверяет наступление 0:00 по Гринвичу (00:00 UTC = 03:00 МСК).
        Если наступили новые календарные сутки по UTC — сбрасывает счётчики на Сессию 1 нового дня.
        Возвращает True если произошёл сброс.
        """
        now_utc = datetime.now(timezone.utc)
        today_utc = now_utc.strftime("%Y-%m-%d")

        if not self.utc_date:
            self.utc_date = today_utc

        day_start = self.get_day_start()
        last_activity = self.last_like_time or self.cycle_start

        # Условие смены суток:
        # 1) Наступила новая календарная дата по Гринвичу (UTC), ИЛИ
        # 2) Была активность до 3:00 МСК текущих суток, ИЛИ
        # 3) Сессия != 1 или cycle_likes > 0, но активность/сессия осталась со старого дня
        is_new_utc_day = today_utc > self.utc_date
        is_stale_activity = bool(last_activity and last_activity < day_start)
        is_stale_session = bool(
            (self.session_number != 1 or self.cycle_likes > 0)
            and (not last_activity or last_activity < day_start)
        )

        if is_new_utc_day or is_stale_activity or is_stale_session:
            logger.warning(
                f"[SCHEDULE] 0:00 UTC (Grinvich / 3:00 MSK) proydeno! "
                f"Novye sutki {today_utc}. Sbros tsikla na Sessiyu 1 novogo dnya."
            )
            self.utc_date = today_utc
            self.session_number = 1
            self.session_likes = 0
            self.cycle_likes = 0
            self.cycle_start = None
            self.last_like_time = None
            # Сбрасываем вчерашнюю ночную паузу, если она истекла
            if self.pause_until and self.pause_until <= datetime.now():
                self.pause_until = None
            self._refresh_session1_earliest()
            self._save()
            return True
        return False

    # ──────────────────────────────────────────────────────────────────
    # Публичный интерфейс — расписание
    # ──────────────────────────────────────────────────────────────────

    def get_day_start(self) -> datetime:
        """3:00 МСК начала текущих суток (наивное локальное время)."""
        now = datetime.now()
        # Если 0:00–2:59 МСК — сутки начались «вчера» в 3:00
        if now.hour < DAY_START_HOUR:
            d = (now - timedelta(days=1)).date()
        else:
            d = now.date()
        return datetime(d.year, d.month, d.day, DAY_START_HOUR, 0, 0)

    def get_day_end(self) -> datetime:
        """0:00 МСК следующего дня = day_start + 21ч."""
        return self.get_day_start() + timedelta(hours=21)

    def get_session2_deadline(self) -> datetime:
        """Крайний момент старта Сессии 2 = day_end − MAX_SESSION_DURATION."""
        return self.get_day_end() - MAX_SESSION_DURATION

    def is_before_session1_start(self) -> bool:
        """True — ещё слишком рано начинать Сессию 1 (до 6:00 МСК + рандом)."""
        if self.session_number != 1 or self.cycle_likes > 0 or self.pause_until:
            return False
        target = self.session1_earliest or self._compute_session1_earliest()
        return datetime.now() < target

    def seconds_until_session1(self) -> float:
        """Секунд до разрешённого старта Сессии 1 (0 если уже можно)."""
        if not self.is_before_session1_start():
            return 0.0
        target = self.session1_earliest or self._compute_session1_earliest()
        return max(0.0, (target - datetime.now()).total_seconds())

    def is_too_late_for_session2(self) -> bool:
        """True — Сессия 2 уже не успевает завершиться до 0:00 МСК."""
        if self.session_number != 2:
            return False
        return datetime.now() > self.get_session2_deadline()

    def schedule_next_day(self):
        """
        Переносит в следующий день: сбрасывает цикл и выставляет
        pause_until = session1_earliest следующего дня.
        Вызывается когда S2 просрочена или цикл завершён раньше срока.
        """
        next_s1 = self._next_day_session1_earliest()
        self.session1_earliest = next_s1
        self.pause_until       = next_s1
        # Полный сброс цикла
        self.session_number    = 1
        self.session_likes     = 0
        self.cycle_likes       = 0
        self.cycle_start       = None
        self.last_like_time    = None
        logger.warning(
            f"[SCHEDULE] Perekhod na sleduyushchiy den'. "
            f"S1 earliest: {next_s1.strftime('%d.%m %H:%M')} MSK"
        )
        self._save()

    # ──────────────────────────────────────────────────────────────────
    # Публичный интерфейс — лайки и паузы
    # ──────────────────────────────────────────────────────────────────

    async def wait_if_needed(self):
        """Ждёт если активна пауза (опрос каждые 60 сек)."""
        if not self.pause_until:
            return

        now = datetime.now()
        if now >= self.pause_until:
            self._end_pause()
            return

        wait_sec = (self.pause_until - now).total_seconds()
        h = int(wait_sec // 3600)
        m = int((wait_sec % 3600) // 60)
        s = int(wait_sec % 60)
        reason = ("Sessiya 1 zavershena" if self.session_number == 1
                  else "Sutochny limit (58 laykov)")
        logger.info(
            f"[PAUZA] {reason}. Prodolzhu v: "
            f"{self.pause_until.strftime('%d.%m %H:%M:%S')} "
            f"(ostalot: {h}h {m}m {s}s)"
        )

        while self.pause_until and datetime.now() < self.pause_until:
            sleep_sec = min(60.0, (self.pause_until - datetime.now()).total_seconds())
            if sleep_sec > 0:
                await asyncio.sleep(sleep_sec)

        if self.pause_until:
            self._end_pause()

    def record_like(self):
        """Зафиксировать лайк. При достижении лимита — ставит паузу."""
        if self.cycle_likes == 0 and self.session_number == 1:
            self.cycle_start = datetime.now()
            logger.info(
                f"[CYCLE] Start tsikla: {self.cycle_start.strftime('%d.%m %H:%M:%S')}"
            )

        self.last_like_time = datetime.now()
        self.session_likes  += 1
        self.cycle_likes    += 1
        remaining = MAX_LIKES_PER_SESSION - self.session_likes

        logger.info(
            f"[STATS] Sessiya {self.session_number}: "
            f"{self.session_likes}/{MAX_LIKES_PER_SESSION}  |  "
            f"Tsikl: {self.cycle_likes}  |  "
            f"Do limita: {max(remaining, 0)}"
        )

        if self.session_likes >= MAX_LIKES_PER_SESSION:
            self._start_pause()

        self._save()

    def status_line(self) -> str:
        remaining = MAX_LIKES_PER_SESSION - self.session_likes
        if self.pause_until:
            return f"PAUZA do {self.pause_until.strftime('%d.%m %H:%M')}"
        if self.is_before_session1_start():
            target = self.session1_earliest
            return f"Zhdu starta S1 v {target.strftime('%H:%M')} MSK"
        return (
            f"Sessiya {self.session_number}: "
            f"{self.session_likes}/{MAX_LIKES_PER_SESSION} "
            f"(do limita: {max(remaining, 0)})"
        )

    # ──────────────────────────────────────────────────────────────────
    # Внутренние методы
    # ──────────────────────────────────────────────────────────────────

    def _compute_session1_earliest(self) -> datetime:
        """6:00 МСК + случайный сдвиг 0..2ч."""
        day_start = self.get_day_start()
        base      = day_start + timedelta(hours=(SESSION1_OPEN_HOUR - DAY_START_HOUR))
        rand_off  = random.uniform(0, SESSION1_RAND_SECS)
        return base + timedelta(seconds=rand_off)

    def _next_day_session1_earliest(self) -> datetime:
        """session1_earliest для следующего дня (от 6:00 МСК + случайный сдвиг 0..2ч)."""
        next_day_start = self.get_day_end()   # 0:00 МСК следующего дня
        base    = next_day_start + timedelta(hours=SESSION1_OPEN_HOUR)
        rand_off = random.uniform(0, SESSION1_RAND_SECS)
        return base + timedelta(seconds=rand_off)

    def _refresh_session1_earliest(self):
        """
        Пересчитывает session1_earliest если:
        - он не задан, или
        - он принадлежит прошлому дню.
        """
        day_start = self.get_day_start()
        if (self.session1_earliest is None
                or self.session1_earliest < day_start):
            self.session1_earliest = self._compute_session1_earliest()
            logger.info(
                f"[SCHEDULE] S1 earliest (segodnya): "
                f"{self.session1_earliest.strftime('%d.%m %H:%M')} MSK"
            )
            self._save()

    def _start_pause(self):
        now = datetime.now()

        if self.session_number == 1:
            # ── Перерыв между сессиями ───────────────────────────────────
            # Генерируем случайный перерыв 3–5ч
            break_sec  = random.uniform(
                SESSION_BREAK_MIN.total_seconds(),
                SESSION_BREAK_MAX.total_seconds(),
            )
            candidate  = now + timedelta(seconds=break_sec)
            deadline   = self.get_session2_deadline()

            if candidate > deadline:
                candidate = deadline
                logger.warning(
                    f"[SCHEDULE] Pereryv ukorocen: S2 dolzhna startovat "
                    f"do {deadline.strftime('%H:%M')} MSK "
                    f"(chtoby uspet do 0:00)"
                )

            # Гарантируем минимум 3ч
            minimum = now + SESSION_BREAK_MIN
            if candidate < minimum:
                # Минимальный перерыв уже превышает дедлайн — S2 не успевает
                if minimum > deadline:
                    logger.warning(
                        f"[SCHEDULE] S2 ne uspeet do 0:00 MSK — "
                        f"minimum pauzy ({minimum.strftime('%H:%M')}) > "
                        f"deadline ({deadline.strftime('%H:%M')}). "
                        f"Perekhod na sleduyushchiy den'."
                    )
                    self.pause_until = minimum  # temporary — schedule_next_day overrides
                    self._save()
                    # Запланируем через schedule_next_day (сброс будет в _end_pause)
                    # Помечаем как S2 с 0 лайков чтоб _end_pause -> S1 нового дня
                    self.session_number = 2
                    self.session_likes  = 0
                    next_s1 = self._next_day_session1_earliest()
                    self.session1_earliest = next_s1
                    self.pause_until = next_s1
                    # Полный сброс цикла для нового дня
                    self.session_number  = 1
                    self.session_likes   = 0
                    self.cycle_likes     = 0
                    self.cycle_start     = None
                    self.last_like_time  = None
                    logger.warning(
                        f"[SCHEDULE] Novyy tsikl zavtra v "
                        f"{next_s1.strftime('%d.%m %H:%M')} MSK"
                    )
                    self._save()
                    return
                candidate = minimum

            self.pause_until = candidate
            elapsed_h = (self.pause_until - now).total_seconds() / 3600
            logger.info(
                f"[LIMIT] 29 laykov (sessiya 1)! "
                f"Pereryv {elapsed_h:.1f}ch → "
                f"S2 startует ~{self.pause_until.strftime('%H:%M')} MSK"
            )

        else:
            # ── После Сессии 2: пауза до следующего дня ──────────────────
            next_s1 = self._next_day_session1_earliest()
            # Гарантируем минимум 3ч от последнего лайка
            minimum = (self.last_like_time or now) + SESSION_BREAK_MIN
            self.pause_until       = max(next_s1, minimum)
            self.session1_earliest = next_s1   # для нового дня

            elapsed_h = (self.pause_until - now).total_seconds() / 3600
            logger.info(
                f"[LIMIT] 58 laykov za sutki! "
                f"Pauza {elapsed_h:.1f}ch → "
                f"novy tsikl {self.pause_until.strftime('%d.%m %H:%M')} MSK"
            )

    def _end_pause(self):
        # 1. Проверяем смену суток по Гринвичу
        if self.check_day_rollover():
            return

        # 2. Если реально завершилась Сессия 1 (было выполнено 29 лайков) -> переходим к Сессии 2
        if self.session_number == 1 and self.session_likes >= MAX_LIKES_PER_SESSION:
            self.session_number = 2
            self.session_likes  = 0
            logger.info("[OK] Pereryv mezhdu sessiyami zakonchilsya! Nachinayu sessiyu 2.")
        else:
            # Ночной отдых или ожидание утра -> остаёмся на Сессии 1
            self.session_number  = 1
            self.session_likes   = 0
            self.cycle_likes     = 0
            self.cycle_start     = None
            self.last_like_time  = None
            logger.info("[OK] Pauza zakonchilas! Nachinayu sessiyu 1 novogo dnya.")

        self.pause_until = None
        self._save()

    def _load(self):
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                d = json.load(f)
            self.session_likes      = int(d.get("session_likes", 0))
            self.session_number     = int(d.get("session_number", 1))
            self.cycle_likes        = int(d.get("cycle_likes", 0))
            self.utc_date           = str(d.get("utc_date", ""))
            pu  = d.get("pause_until")
            self.pause_until        = datetime.fromisoformat(pu) if pu else None
            cs  = d.get("cycle_start")
            self.cycle_start        = datetime.fromisoformat(cs) if cs else None
            ll  = d.get("last_like_time")
            self.last_like_time     = datetime.fromisoformat(ll) if ll else None
            s1e = d.get("session1_earliest")
            self.session1_earliest  = datetime.fromisoformat(s1e) if s1e else None

            logger.info(
                f"[STATE] Zagruzil: sessiya {self.session_number}, "
                f"{self.session_likes} laykov v sessii, {self.cycle_likes} v tsikle"
            )
            if self.utc_date:
                logger.info(f"[STATE] UTC-data: {self.utc_date} (0:00 Grinvich)")
            if self.cycle_start:
                logger.info(
                    f"[STATE] Start tsikla: {self.cycle_start.strftime('%d.%m %H:%M')}"
                )
            if self.last_like_time:
                logger.info(
                    f"[STATE] Posledniy layk: "
                    f"{self.last_like_time.strftime('%d.%m %H:%M:%S')}"
                )
            if self.pause_until:
                logger.info(
                    f"[STATE] Pauza do: {self.pause_until.strftime('%d.%m %H:%M:%S')}"
                )

        except Exception as e:
            logger.warning(f"Ne udalos zagruzit state: {e}. Startuyem zanovo.")

    def _save(self):
        os.makedirs("session", exist_ok=True)
        data = {
            "utc_date":          self.utc_date,
            "session_likes":     self.session_likes,
            "session_number":    self.session_number,
            "cycle_likes":       self.cycle_likes,
            "cycle_start":       self.cycle_start.isoformat() if self.cycle_start else None,
            "last_like_time":    self.last_like_time.isoformat() if self.last_like_time else None,
            "pause_until":       self.pause_until.isoformat() if self.pause_until else None,
            "session1_earliest": (
                self.session1_earliest.isoformat() if self.session1_earliest else None
            ),
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
