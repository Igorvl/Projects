import os
from dotenv import load_dotenv

load_dotenv()

TG_API_ID: int = int(os.getenv("TG_API_ID", "2040"))
TG_API_HASH: str = os.getenv("TG_API_HASH", "b18441a1ff607e10a989891a5462e627")
DELAY_MIN: float = float(os.getenv("DELAY_MIN", "4"))
DELAY_MAX: float = float(os.getenv("DELAY_MAX", "10"))
HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "behancer_bot")

# Proxy settings for Telethon (needed if Telegram is blocked)
PROXY_TYPE: str = os.getenv("PROXY_TYPE", "http").lower()
PROXY_HOST: str = os.getenv("PROXY_HOST", "")
PROXY_PORT: int = int(os.getenv("PROXY_PORT", "0") or "0")
PROXY_USER: str = os.getenv("PROXY_USER", "")
PROXY_PASS: str = os.getenv("PROXY_PASS", "")

# Proxy for Playwright browser and HTTP resolvers (v2rayTun SOCKS5 proxy)
BROWSER_PROXY: str = os.getenv("BROWSER_PROXY", "socks5://127.0.0.1:10801")
