# -*- coding: utf-8 -*-
"""
Configuration module for X (Twitter) F4F Growth Engine.
Contains scoring matrices, search queries, safety limits, and database settings.
"""

import os

# ==========================================
# 1. СКОРИНГОВАЯ МАТРИЦА КЛЮЧЕВЫХ СЛОВ (BIO)
# ==========================================

# Кластер A: Должности и статус (Лица принимающие решения / Дизайнеры) - Вес: +35
KEYWORDS_ROLES = [
    "art director", "creative director", "design lead", "head of design",
    "brand director", "founder", "co-founder", "ceo", "design partner", "vp design",
    "design principal", "lead designer", "product designer", "graphic designer",
    "brand designer", "visual designer", "motion designer", "type designer",
    "spatial designer", "design engineer", "creative technologist", "ui/ux designer",
    "ui/ux", "ui designer", "ux designer", "web designer", "designer",
    "artist", "architect"
]

# Кластер B: Эстетика и стиль (Прямой визуальный match) - Вес: +30
KEYWORDS_STYLE = [
    "brutalism", "brutalist", "neo-brutalism", "neo-brutalist",
    "swiss style", "swiss design", "editorial design", "editorial", "information design",
    "data visualization", "generative design", "speculative design",
    "monospace", "typography", "grid systems", "modular design", "grid",
    "3d design", "functional typography", "utilitarian design", "hud design", "hud",
    "branding", "brand identity", "visual identity", "design system", "poster design",
    "framer", "figma", "spline", "blender", "touchdesigner", "cinema4d", "c4d"
]

# Кластер C: Индустрия и ниша (Высокочековые заказчики / Студии) - Вес: +30
KEYWORDS_INDUSTRY = [
    "healthtech", "medtech", "biotech", "life sciences", "longevity",
    "packaging design", "spatial wayfinding", "future ui", "creative studio",
    "brand identity", "brand architecture", "cleanroom", "clinical aesthetic",
    "pharma branding", "dermatology clinic", "cosmeceuticals", "studio"
]

# Негативные стоп-слова (боты, спам, криптоскам, офферы) - Жесткий бан
NEGATIVE_KEYWORDS = [
    "crypto", "airdrop", "solana", "memecoin", "forex", "trading",
    "pump & dump", "pump and dump", "crypto pump",
    "bounty", "affiliate", "paid collab", "paid collaboration",
    "dm for paid promo", "dm for promo", "send dm for promo",
    "maga", "trump", "politician", "onlyfans", "nsfw", "porn", "casino",
    "18+", "dropshipping", "dm for paid", "prompt engineer",
    "tips/note", "brain/tips", "earn daily", "make money", "passive income",
    "nft project", "web3 creator", "100x"
]

# Ссылки на дизайнерские портфолио в Bio/URL (+15 очков)
PORTFOLIO_DOMAINS = [
    "behance.net", "layers.to", "framer.website", "framer.com",
    "readymag.site", "dribbble.com", "cosmos.so", "bento.me",
    "are.na", "contra.com", "github.com", "notion.site"
]

# Минимальный проходной балл скоринга для постановки в очередь на подписку
MIN_SCORE_THRESHOLD = 40

# ==========================================
# 2. ЖЕСТКИЕ КРИТЕРИИ ОТБОРА (HARD GATES)
# ==========================================
MIN_FOLLOWERS = 80         # Отсекаем ботов, но не блокируем начинающих/нишевых дизайнеров
MAX_FOLLOWERS = 3000       # Отсекаем звезд и перегруженные аккаунты, максимизируем конверсию F4F
MIN_RATIO = 0.35           # Following / Followers (0.35+ реалистичное соотношение для дизайнеров-взаимщиков)
MAX_DAYS_INACTIVE = 3      # Аккаунт должен проявлять активность в последние 3 дня

# ==========================================
# 3. БЕЗОПАСНЫЕ ЛИМИТЫ (RATE LIMITS)
# ==========================================
DAILY_FOLLOW_LIMIT = 35        # Безопасный умеренный лимит подписок в сутки
DAILY_UNFOLLOW_LIMIT = 35      # Стартовый лимит отписок в сутки
DAILY_LIKE_LIMIT = 55          # Безопасный потолок лайков (поддерживает 25-30 каскадов + ручной люфт)
LIKE_PROBABILITY = 0.85        # Вероятность теплого касания для обычных лидов
MIN_DELAY_SECONDS = 30         # Минимальная пауза между целями
MAX_DELAY_SECONDS = 80         # Максимальная случайная пауза
UNFOLLOW_AFTER_DAYS = 5        # Через сколько дней отписываться, если нет взаимности

# Настройки Схемы 1: «Каскадный Tri-Touch»
TRI_TOUCH_ENABLED = True       # Включение 2-этапного лайкинга + Dwell Time
TRI_TOUCH_MIN_SCORE = 65       # Порог для активации каскада из 2 лайков (только для топовых лидов)
TRI_TOUCH_PAUSE_BETWEEN_LIKES = (12, 25) # Органическая пауза чтения и скролла между лайками
TRI_TOUCH_PAUSE_BEFORE_FOLLOW = (8, 15)  # Финальная пауза перед кликом Follow

# ==========================================
# 4. ПОИСКОВЫЕ ЗАПРОСЫ ДЛЯ СБОРА КАНДИДАТОВ
# ==========================================
SEARCH_QUERIES = [
    'editorial design typography',
    'brand identity studio',
    'swiss style typography',
    'brutalist design web',
    'visual identity poster',
    'speculative design futures',
    'spatial design 3d',
    'packaging design branding',
    'brand guidelines typography',
    'built with framer portfolio',
    'readymag design portfolio',
    'product designer ui ux',
    'type design typography studio',
    'graphic designer behance',
    'to:readymag portfolio',
    'to:framer website',
    'to:type01_'
]

# Аккаунты-доноры (чьих недавних лайкеров/ретвитеров будем парсить)
TARGET_DONORS = [
    "StudioDumbar",
    "readymag",
    "framer",
    "layers",
    "bauxitedesign",
    "kaborist",
    "PentagramDesign",
    "type01_"
]

# ==========================================
# 5. ИНФРАСТРУКТУРА И ПУТИ
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PROFILES_DIR, exist_ok=True)

# База данных: локально SQLite, на сервере можно переключить на Postgres через env
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
SQLITE_PATH = os.path.join(DATA_DIR, "x_growth.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{SQLITE_PATH}")

# Web Dashboard
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", 8085))

# Ntfy уведомления
NTFY_URL = os.getenv("NTFY_URL", "")  # e.g. http://inux-job:9080/x-growth-alerts

# Целевой аккаунт (тестовый или продовый)
TARGET_ACCOUNT = os.getenv("TARGET_ACCOUNT", "Igorvl777")
