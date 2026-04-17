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

# LLM Router (наш ai-router) — используется для текстовых запросов
LLM_API_BASE = os.getenv("LLM_API_BASE", "http://172.25.9.33:8000/v1").strip(' "\'')
LLM_API_KEY  = os.getenv("LLM_API_KEY", os.getenv("SILICONFLOW_API_KEY", "sk-any"))
if LLM_API_KEY:
    LLM_API_KEY = LLM_API_KEY.strip(' "\'')
VISION_MODEL = os.getenv("VISION_MODEL", "qwen-vision-VL-32B").strip(' "\'')   # Для анализа обложек
COMMENT_MODEL = os.getenv("COMMENT_MODEL", "qwen-vision-VL-32B").strip(' "\'')  # Для анализа всего проекта

# Vision LLM — ПРЯМОЙ вызов SiliconFlow, минуя DNA-роутер
# Причина: DNA-роутер имеет timeout=15s на Qwen-VL, а vision-запросы занимают ~47s → 502
# Ключ берётся из SILICONFLOW_API_KEY (или переопределяется VISION_API_KEY в .env)
VISION_API_BASE   = os.getenv("VISION_API_BASE", "https://api.siliconflow.com/v1").strip(' "\'')
VISION_API_KEY    = os.getenv("VISION_API_KEY",
    os.getenv("SILICONFLOW_API_KEY",
    os.getenv("CRITIC_API_KEY",        # OpenRouter ключ — если переключились на OR для vision
    os.getenv("LLM_API_KEY", "")))).strip(' "\'')
VISION_MODEL_DIRECT = os.getenv("VISION_MODEL_DIRECT", "Qwen/Qwen3-VL-32B-Instruct").strip(' "\'')

# Critic LLM — НАПРЯМУЮ SiliconFlow (тот же провайдер что и Stage 1)
# DeepSeek-V3.2 — быстрый текстовый модель, отлично редактирует текст (deepseek-ai/DeepSeek-V3.2 в antigravity.json)
CRITIC_API_BASE     = os.getenv("CRITIC_API_BASE", VISION_API_BASE)   # тот же SiliconFlow
CRITIC_API_KEY      = os.getenv("CRITIC_API_KEY",  VISION_API_KEY)   # тот же ключ
CRITIC_MODEL_DIRECT = os.getenv("CRITIC_MODEL_DIRECT", "deepseek-ai/DeepSeek-V3.2,Qwen/Qwen3-VL-32B-Instruct")
CRITIC_MODEL        = os.getenv("CRITIC_MODEL", CRITIC_MODEL_DIRECT)

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
