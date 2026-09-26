"""
Behance AutoLiker -- точка входа.

Запуск:
    python main.py
"""

import asyncio
import logging
import sys

# Фикс для Windows: принудительно UTF-8 в консоли (иначе эмодзи ломают вывод)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from behance_liker import BehanceLiker
from tg_listener import start_telegram_listener


# ---------------------------------------------------------------------------
# Фильтр шума от внутреннего reconnect-механизма Telethon
# ---------------------------------------------------------------------------

# Паттерны которые ПОЛНОСТЬЮ подавляются (не выводятся в консоль)
_TELETHON_SUPPRESS = (
    "Attempt ",                                    # "Attempt N at connecting failed"
    "at connecting failed",
    "Closing current connection to begin reconnect",
    "Connection closed while receiving data",
    "Server closed the connection",
    "during disconnect",
    "Disconnecting from ",
    "Disconnection from ",
    "Not disconnecting",
    "Failed reconnection attempt",
    "Future exception was never retrieved",
    "Automatic reconnection failed",               # заменяем своим сообщением
)

_tg_net_logger = logging.getLogger("tg.net")      # наш лаконичный логгер


class _TelethonNoiseFilter(logging.Filter):
    """
    Перехватывает внутренние сообщения Telethon о переподключении:
      - подавляет спам "Attempt N / Failed reconnection / ..."
      - при "Automatic reconnection failed" выводит ОДНО краткое предупреждение
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()

        # Финальное сообщение об исчерпании попыток -> наше краткое предупреждение
        if "Automatic reconnection failed" in msg:
            _tg_net_logger.warning(
                "[TG-NET] Telegram nedostupen — vse popytki ispolzovany (proverte VPN/TUN). "
                "Zhdu 60s pered povtornym podklyucheniem..."
            )
            return False  # оригинал подавляем

        # Остальные шумные паттерны — молча отбрасываем
        for pat in _TELETHON_SUPPRESS:
            if pat in msg:
                return False

        return True


def _install_telethon_filter() -> None:
    """Устанавливает фильтр на все суб-логгеры Telethon."""
    f = _TelethonNoiseFilter()
    logging.getLogger("telethon").addFilter(f)


def setup_logging() -> None:
    fmt = "%(asctime)s  [%(levelname)s]  %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("autoliker.log", encoding="utf-8"),
        ],
    )
    # Фильтруем шум от Telethon ПОСЛЕ basicConfig
    _install_telethon_filter()


async def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 55)
    logger.info("   [START] Behance AutoLiker zapuskaetsya...")
    logger.info("=" * 55)

    liker = BehanceLiker()
    try:
        logger.info("Initializiruyu brauzer Behance...")
        await liker.init()
        logger.info("[OK] Brauzer gotov! Zhdu zadaniy ot bota...")

        # Reconnect loop: при сетевых сбоях ждём 60с и переподключаемся
        while True:
            try:
                await start_telegram_listener(liker)
                break  # нормальное завершение (например Ctrl+C поднимется выше)
            except ConnectionError as conn_err:
                logger.warning(
                    f"[TG] Poterya soedineniya: {conn_err}. "
                    f"Povtornoe podklyuchenie cherez 60 sekund..."
                )
                await asyncio.sleep(60)

    except KeyboardInterrupt:
        logger.info("[STOP] Ostanovleno polzovatelem (Ctrl+C).")
    except Exception as exc:
        logger.error(f"Kriticheskaya oshibka: {exc}", exc_info=True)
    finally:
        logger.info("Zakryvayu brauzer...")
        await liker.close()
        logger.info("[BYE] Do svidaniya!")


if __name__ == "__main__":
    asyncio.run(main())
