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

# ── OpenRouter — единая точка входа для ВСЕХ LLM ─────────────────────────────
# Бесплатные модели: $0/M tokens, без кредитной карты.
# Rate limit: ~20 req/min, ~200 req/day — достаточно для продакшена.
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "").strip(' "\'')

# LLM Router (оставляем для совместимости, fallback на DNA-роутер если нужен)
LLM_API_BASE = os.getenv("LLM_API_BASE", "http://172.25.9.33:8000/v1").strip(' "\'')
LLM_API_KEY  = os.getenv("LLM_API_KEY", os.getenv("SILICONFLOW_API_KEY", "sk-any"))
if LLM_API_KEY:
    LLM_API_KEY = LLM_API_KEY.strip(' "\'')

# Vision LLM — OpenRouter, бесплатные multimodal-модели
# ID верифицированы через /api/v1/models (май 2026):
# nemotron-nano-12b-v2-vl: NVIDIA VL, OCR+charts, 128K ctx, free
# gemma-4-26b-a4b-it:      Google Gemma 4 26B, vision, 262K ctx, free
# gemma-4-31b-it:          Google Gemma 4 31B, vision, 262K ctx, free
# openrouter/free:         авто-роутер, сам выберет vision-модель (last resort)
VISION_API_BASE   = os.getenv("VISION_API_BASE", OPENROUTER_API_BASE).strip(' "\'')
VISION_API_KEY    = os.getenv("VISION_API_KEY", OPENROUTER_API_KEY).strip(' "\'')
VISION_MODEL_DIRECT = os.getenv(
    "VISION_MODEL_DIRECT",
    "nvidia/nemotron-nano-12b-v2-vl:free,google/gemma-4-26b-a4b-it:free,google/gemma-4-31b-it:free,openrouter/free"
).strip(' "\'')
VISION_MODEL = os.getenv("VISION_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free").strip(' "\'')

# Comment/Critic LLM — OpenRouter, бесплатные text-модели
# Актуально на май 2026 (проверено по openrouter.ai/models?free=true):
# gpt-oss-120b: OpenAI, 117B MoE, 5.1B active/pass, primary (в 6x крупнее 20b), авг 2025
# gpt-oss-20b:  OpenAI, 21B MoE, 3.6B active/pass, fallback, авг 2025
# GLM 4.5 Air:  Z.ai, thinking mode, MoE, free, июль 2025
# Qwen3 Coder:  Alibaba, 480B MoE, 35B active, 1M context, free, июль 2025
CRITIC_API_BASE     = os.getenv("CRITIC_API_BASE", OPENROUTER_API_BASE).strip(' "\'')
CRITIC_API_KEY      = os.getenv("CRITIC_API_KEY", OPENROUTER_API_KEY).strip(' "\'')
CRITIC_MODEL_DIRECT = os.getenv(
    "CRITIC_MODEL_DIRECT",
    "openai/gpt-oss-120b:free,openai/gpt-oss-20b:free,z-ai/glm-4.5-air:free,qwen/qwen3-coder-480b-a35b:free"
).strip(' "\'')
CRITIC_MODEL  = os.getenv("CRITIC_MODEL", CRITIC_MODEL_DIRECT)
COMMENT_MODEL = os.getenv("COMMENT_MODEL", "openai/gpt-oss-120b:free").strip(' "\'')

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
