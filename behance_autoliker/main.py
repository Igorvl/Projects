"""
main.py -- Главная точка входа Behance AutoLiker (Multi-Account).

Использование:
    python main.py                     # Автозапуск готовых аккаунтов
    python main.py --account ksar_lab  # Запуск только KSAR Lab (Igor Kotov)
    python main.py --account ksar_be   # Запуск только Ksar Be (Ksar Tg)
    python main.py --all               # Принудительный запуск обоих
"""

import sys
import os
import argparse
import asyncio
import logging
from typing import List

# Принудительно UTF-8 для консоли
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from accounts_config import get_account_config, ALL_ACCOUNTS, AccountConfig
from behance_worker import BehanceAccountWorker

_TELETHON_SUPPRESS = (
    "Attempt ",
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
    "Automatic reconnection failed",
)

_tg_net_logger = logging.getLogger("tg.net")


class _TelethonNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "Automatic reconnection failed" in msg:
            _tg_net_logger.warning(
                "[TG-NET] Telegram nedostupen -- proveryayu soedinenie... "
                "Ozhidanie 60s pered perepodklyucheniem."
            )
            return False
        for pat in _TELETHON_SUPPRESS:
            if pat in msg:
                return False
        return True


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
    logging.getLogger("telethon").addFilter(_TelethonNoiseFilter())


async def run_worker_supervisor(config: AccountConfig) -> None:
    logger = logging.getLogger(__name__)
    worker = BehanceAccountWorker(config)

    while True:
        try:
            await worker.start()
            await worker.run_until_stopped()
            break
        except asyncio.CancelledError:
            await worker.stop()
            break
        except ConnectionError as conn_err:
            logger.warning(
                f"[{config.account_id}] [RECONNECT] Poterya soedineniya: {conn_err}. "
                f"Povtornoe podklyuchenie cherez 60s..."
            )
            await worker.stop()
            await asyncio.sleep(60)
        except Exception as exc:
            logger.error(f"[{config.account_id}] Kriticheskaya oshibka: {exc}", exc_info=True)
            await worker.stop()
            await asyncio.sleep(30)


async def main():
    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Behance AutoLiker Multi-Account Engine")
    parser.add_argument(
        "--account",
        choices=ALL_ACCOUNTS,
        help="Zapustit konkretny account (ksar_lab ili ksar_be)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Zapustit vse accounty parallelno",
    )

    args = parser.parse_args()

    # Opredelenie spiska zapuskaemyh accountov
    target_accounts: List[str] = []
    if args.account:
        target_accounts = [args.account]
    elif args.all:
        target_accounts = ALL_ACCOUNTS
    else:
        for acc_id in ALL_ACCOUNTS:
            cfg = get_account_config(acc_id)
            if os.path.exists(cfg.behance_cookies_path) and os.path.exists(cfg.tg_session_path):
                target_accounts.append(acc_id)

        if not target_accounts:
            logger.error("Ni odin account ne nastroen! Vypolnite: python setup_account.py --status")
            return

    logger.info("=" * 65)
    logger.info("   [ENGINE] Behance AutoLiker Multi-Account Engine")
    logger.info(f"   Celevye accounty: {', '.join(target_accounts)}")
    logger.info("=" * 65)

    tasks = []
    for acc_id in target_accounts:
        cfg = get_account_config(acc_id)
        if not os.path.exists(cfg.behance_cookies_path) or not os.path.exists(cfg.tg_session_path):
            logger.warning(
                f"[SKIP] Propuskayu {cfg.name} ({acc_id}): "
                f"ne nayden tg.session ili behance_cookies.json!"
            )
            continue
        tasks.append(asyncio.create_task(run_worker_supervisor(cfg)))

    if not tasks:
        logger.error("Net gotovyh k zapusku zadach.")
        return

    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("[STOP] Ostanovka po komande polzovatelya...")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[STOP] Process zavershyon polzovatelem.")
