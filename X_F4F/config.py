# -*- coding: utf-8 -*-
"""
Configuration module for X (Twitter) F4F Growth Engine.
Contains scoring matrices, search queries, safety limits, and database settings.
"""

import os

# ==========================================
# 1. СКОРИНГОВАЯ МАТРИЦА КЛЮЧЕВЫХ СЛОВ (BIO)
# ==========================================

# Кластер A: Должности и статус (Лица принимающие решения / Коллеги) - Вес: +35
KEYWORDS_ROLES = [
    "art director", "creative director", "design lead", "head of design",
    "brand director", "founder", "co-founder", "spatial designer",
    "design engineer", "creative technologist", "type designer", "design principal",
    "lead designer", "design partner", "vp design"
]

# Кластер B: Эстетика и стиль (Прямой визуальный match) - Вес: +30
KEYWORDS_STYLE = [
    "brutalism", "brutalist", "neo-brutalism", "neo-brutalist",
    "swiss style", "swiss design", "editorial design", "information design",
    "data visualization", "generative design", "speculative design",
    "monospace", "typography", "grid systems", "modular design",
    "3d design", "functional typography", "utilitarian design", "hud design"
]

# Кластер C: Индустрия и ниша (Высокочековые заказчики / Студии) - Вес: +30
KEYWORDS_INDUSTRY = [
    "healthtech", "medtech", "biotech", "life sciences", "longevity",
    "packaging design", "spatial wayfinding", "future ui", "creative studio",
    "brand identity", "brand architecture", "cleanroom", "clinical aesthetic",
    "pharma branding", "dermatology clinic", "cosmeceuticals"
]

# Ссылки на дизайнерские портфолио в Bio/URL (+15 очков)
PORTFOLIO_DOMAINS = [
    "behance.net", "layers.to", "framer.website", "framer.com",
    "readymag.site", "dribbble.com", "cosmos.so", "bento.me",
    "are.na", "contra.com"
]

# Минимальный проходной балл скоринга для постановки в очередь на подписку
MIN_SCORE_THRESHOLD = 50

# ==========================================
# 2. ЖЕСТКИЕ КРИТЕРИИ ОТБОРА (HARD GATES)
# ==========================================
MIN_FOLLOWERS = 200        # Отсекаем ботов и пустые аккаунты
MAX_FOLLOWERS = 6000       # Отсекаем звезд, которые никогда не подпишутся в ответ
MIN_RATIO = 0.65           # Following / Followers (0.65+ признак взаимщика)
MAX_DAYS_INACTIVE = 3      # Аккаунт должен проявлять активность в последние 3 дня

# ==========================================
# 3. БЕЗОПАСНЫЕ ЛИМИТЫ (RATE LIMITS)
# ==========================================
DAILY_FOLLOW_LIMIT = 40        # Стартовый лимит подписок в сутки (для прогрева)
DAILY_UNFOLLOW_LIMIT = 40      # Стартовый лимит отписок в сутки
MIN_DELAY_SECONDS = 25         # Минимальная пауза между действиями
MAX_DELAY_SECONDS = 75         # Максимальная случайная пауза
UNFOLLOW_AFTER_DAYS = 5        # Через сколько дней отписываться, если нет взаимности

# ==========================================
# 4. ПОИСКОВЫЕ ЗАПРОСЫ ДЛЯ СБОРА КАНДИДАТОВ
# ==========================================
SEARCH_QUERIES = [
    '"swiss style" typography',
    '"brutalist" design',
    '"editorial design" grid',
    '"speculative design"',
    '"spatial design" 3d',
    '"healthtech" branding',
    '"medtech" brand identity',
    '"biotech" design',
    '"futuristic UI" OR "HUD design"',
    '"packaging design" pharma OR serum',
    '"brand guidelines" typography grid',
    '"identity system" brutalism'
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
