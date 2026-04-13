"""
Behance Scout — конфигурация
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)
SESSION_FILE = DATA_DIR / "session.json"
DB_PATH = DATA_DIR / "behance_scout.db"
STYLE_PROFILE_PATH = DATA_DIR / "style_profile.json"

load_dotenv(BASE_DIR / ".env")

# LLM Router (наш ai-router или SiliconFlow)
LLM_API_BASE = os.getenv("LLM_API_BASE", "http://172.25.9.33:8000/v1").strip(' "\'')
LLM_API_KEY  = os.getenv("LLM_API_KEY", os.getenv("SILICONFLOW_API_KEY", "sk-any"))
if LLM_API_KEY:
    LLM_API_KEY = LLM_API_KEY.strip(' "\'')
VISION_MODEL = os.getenv("VISION_MODEL", "qwen-vision-VL-32B").strip(' "\'')   # Для анализа обложек
COMMENT_MODEL = os.getenv("COMMENT_MODEL", "qwen-vision-VL-32B").strip(' "\'')  # Для анализа всего проекта

# Critic LLM (OpenRouter - Hermes 3 405B, fallback to 70B and Llama 3.3 70B)
CRITIC_API_BASE = os.getenv("CRITIC_API_BASE", "https://openrouter.ai/api/v1").strip(' "\'')
CRITIC_API_KEY  = os.getenv("CRITIC_API_KEY", "")
if CRITIC_API_KEY:
    CRITIC_API_KEY = CRITIC_API_KEY.strip(' "\'')
CRITIC_MODEL    = os.getenv("CRITIC_MODEL", "nousresearch/hermes-3-llama-3.1-405b,nousresearch/hermes-3-llama-3.1-70b,meta-llama/llama-3.3-70b-instruct")

# Behance
TARGET_PROFILE_URL = "https://www.behance.net/kseniyaartman/appreciated"
BEHANCE_BASE       = "https://www.behance.net"

# Скрапинг — человеческие задержки (секунды)
DELAY_MIN  = 2.5
DELAY_MAX  = 7.0
SCROLL_PAUSE_MIN = 1.5
SCROLL_PAUSE_MAX = 4.0

# Discovery
DAILY_TARGET   = 60    # сколько кандидатов ищем за прогон
DAILY_LIMIT    = 29    # сколько дизайнер видит в день
VISION_THRESHOLD = 0.65  # порог visual score для принятия проекта (0..1)

# Dashboard
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 7788
PAGE_SIZE      = 29
