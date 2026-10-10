import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass
class AccountConfig:
    account_id: str
    name: str
    tg_session_path: str
    behance_cookies_path: str
    rate_state_path: str
    log_file_path: str
    exclusions_path: str
    bot_username: str = "behancer_bot"
    tg_api_id: int = 2040
    tg_api_hash: str = "b18441a1ff607e10a989891a5462e627"
    delay_min: float = 30.0
    delay_max: float = 150.0
    headless: bool = True
    browser_proxy: Optional[str] = None
    tg_proxy_type: str = "http"
    tg_proxy_host: Optional[str] = None
    tg_proxy_port: int = 0
    tg_proxy_user: Optional[str] = None
    tg_proxy_pass: Optional[str] = None


def get_account_config(account_id: str) -> AccountConfig:
    default_tg_id = int(os.getenv("TG_API_ID", "2040"))
    default_tg_hash = os.getenv("TG_API_HASH", "b18441a1ff607e10a989891a5462e627")
    default_delay_min = float(os.getenv("DELAY_MIN", "30"))
    default_delay_max = float(os.getenv("DELAY_MAX", "150"))
    default_headless = os.getenv("HEADLESS", "true").lower() == "true"
    default_bot = os.getenv("BOT_USERNAME", "behancer_bot")
    default_browser_proxy = os.getenv("BROWSER_PROXY", "socks5://127.0.0.1:10801")
    default_exclusions = os.path.join(BASE_DIR, "excluded_projects.txt")

    if account_id == "ksar_lab":
        session_dir = os.path.join(BASE_DIR, "sessions", "ksar_lab")
        os.makedirs(session_dir, exist_ok=True)
        return AccountConfig(
            account_id="ksar_lab",
            name="KSAR Lab (Igor Kotov)",
            tg_session_path=os.path.join(session_dir, "tg.session"),
            behance_cookies_path=os.path.join(session_dir, "behance_cookies.json"),
            rate_state_path=os.path.join(session_dir, "rate_state.json"),
            log_file_path=os.path.join(session_dir, "likes_log.csv"),
            exclusions_path=default_exclusions,
            bot_username=default_bot,
            tg_api_id=default_tg_id,
            tg_api_hash=default_tg_hash,
            delay_min=default_delay_min,
            delay_max=default_delay_max,
            headless=default_headless,
            browser_proxy=default_browser_proxy,
        )
    elif account_id == "ksar_be":
        session_dir = os.path.join(BASE_DIR, "sessions", "ksar_be")
        os.makedirs(session_dir, exist_ok=True)
        be_proxy = os.getenv("KSAR_BE_PROXY", default_browser_proxy)
        return AccountConfig(
            account_id="ksar_be",
            name="Ksar Be (Ksar Tg)",
            tg_session_path=os.path.join(session_dir, "tg.session"),
            behance_cookies_path=os.path.join(session_dir, "behance_cookies.json"),
            rate_state_path=os.path.join(session_dir, "rate_state.json"),
            log_file_path=os.path.join(session_dir, "likes_log.csv"),
            exclusions_path=default_exclusions,
            bot_username=default_bot,
            tg_api_id=default_tg_id,
            tg_api_hash=default_tg_hash,
            delay_min=default_delay_min,
            delay_max=default_delay_max,
            headless=default_headless,
            browser_proxy=be_proxy,
        )
    else:
        raise ValueError(f"Unknown account_id: {account_id}")


ALL_ACCOUNTS = ["ksar_lab", "ksar_be"]
