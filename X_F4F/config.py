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

# Кластер D: Архиваторы, создатели процесса и супер-лайкеры (Высокая взаимность и реакция) - Вес: +25
KEYWORDS_ENGAGEMENT = [
    "archive", "curating", "curator", "daily render", "wip", "work in progress",
    "visual diary", "collecting", "moodboard", "visual exploration", "type exploration",
    "daily design", "experiments", "study", "building in public", "framer experiment",
    "blender wip", "design diary", "visual archive", "generative"
]

# Кластер E: Маркеры взаимного нетворкинга (Connect, Moots, Mutuals) - Вес: +20
KEYWORDS_CONNECT = [
    "looking for mutuals", "design mutuals", "need mutuals", "creative mutuals",
    "looking to connect", "let's connect", "lets connect", "open to connect",
    "moots", "design moots", "art moots", "connect with designers",
    "connect with creators", "mutuals?", "moots?", "mutuals welcome",
    "looking for moots", "open to collabs and connect"
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
# 2. ЖЕСТКИЕ КРИТЕРИИ ОТБОРА: СУПЕР-ЛАЙКЕРЫ (HARD GATES)
# ==========================================
MIN_FOLLOWERS = 80         # Отсекаем пустые аккаунты, берем реальных авторов от 80
MAX_FOLLOWERS = 2200       # "Sweet Spot": авторы до 2200 читают каждое уведомление и лично взаимят
MIN_RATIO = 0.65           # Только щедрые на взаимные действия пользователи (Following / Followers >= 0.65)
MAX_DAYS_INACTIVE = 4      # Гипер-активность: последний твит не старше 4 дней (постоянно онлайн)

# ==========================================
# 3. СТУПЕНЧАТЫЙ РАЗГОН: 4 ЭТАПА ПО 2 ДНЯ (SMART RAMP-UP)
# Целевой максимум (290-310 follow / 380-420 likes / 72h) достигается равными долями за 8 дней
# ==========================================
RAMP_UP_START_DATE = "2026-09-17"  # День старта разгона

RAMP_UP_STAGES = {
    1: {
        "name": "Этап 1 (Дни 1–2, 17–18 сен)",
        "follows": 125,
        "unfollows": 125,
        "likes": 200,
        "batch": (8, 10),
        "pause": (25, 45),
        "desc": "Мягкий старт после 65 (+60 follow). Защита от спайк-фильтра."
    },
    2: {
        "name": "Этап 2 (Дни 3–4, 19–20 сен)",
        "follows": 185,
        "unfollows": 185,
        "likes": 270,
        "batch": (12, 14),
        "pause": (20, 40),
        "desc": "Разгон до 50% мощности (+60 follow)."
    },
    3: {
        "name": "Этап 3 (Дни 5–6, 21–22 сен)",
        "follows": 245,
        "unfollows": 245,
        "likes": 340,
        "batch": (16, 18),
        "pause": (15, 35),
        "desc": "Предмаксимальный уровень (+60 follow)."
    },
    4: {
        "name": "Этап 4 (Целевой боевой максимум с 23 сен)",
        "follows": 300,
        "unfollows": 300,
        "likes": 400,
        "batch": (20, 22),
        "pause": (15, 35),
        "desc": "Полный выход на целевой порог (290–310 follow / 380–420 likes)."
    }
}

def get_current_ramp_up():
    """Calculates active ramp-up stage and limits based on calendar date."""
    import datetime
    start = datetime.datetime.strptime(RAMP_UP_START_DATE, "%Y-%m-%d").date()
    today = datetime.date.today()
    diff_days = max(0, (today - start).days)
    stage_idx = min(4, (diff_days // 2) + 1)
    return stage_idx, RAMP_UP_STAGES[stage_idx], diff_days + 1

# Активные динамические квоты для текущего дня
CURRENT_STAGE_IDX, CURRENT_STAGE_DATA, CURRENT_RAMP_DAY = get_current_ramp_up()
DAILY_FOLLOW_LIMIT = CURRENT_STAGE_DATA["follows"]
DAILY_UNFOLLOW_LIMIT = CURRENT_STAGE_DATA["unfollows"]
DAILY_LIKE_LIMIT = CURRENT_STAGE_DATA["likes"]

LIKE_PROBABILITY = 0.90        # Высокая вероятность теплого касания
MIN_DELAY_SECONDS = 20         # Минимальная пауза между целями (регламент 20–45с)
MAX_DELAY_SECONDS = 45         # Максимальная пауза между целями
UNFOLLOW_AFTER_DAYS = 3        # 72 часа (3 суток) дедлайн взаимности

# Настройки Схемы 1: «Каскадный Tri-Touch»
TRI_TOUCH_ENABLED = True       # Включение 2-этапного лайкинга + Dwell Time
TRI_TOUCH_MIN_SCORE = 60       # Порог для активации каскада из 2 лайков
TRI_TOUCH_PAUSE_BETWEEN_LIKES = (10, 20) # Органическая пауза чтения и скролла между лайками
TRI_TOUCH_PAUSE_BEFORE_FOLLOW = (6, 12)  # Финальная пауза перед кликом Follow

# Настройки Схемы 3: «Тщеславные списки» (Ego-List Bombing)
DAILY_LIST_ADD_LIMIT = 35      # Суточная квота добавлений в списки (отдельный счетчик в X)
EGO_LIST_DEFAULT_NAME = "✦ Top 1% Frontier Designers 2026"  # Основной публичный статусный список
EGO_LIST_MIN_SCORE = 50        # Минимальный скор кандидата для включения в список
LIST_ADD_DELAY_SECONDS = (30, 60) # Случайная пауза между добавлениями в список

# Настройки Discovery Engine 2.0 (Кулдауны источников и Snowball Graph)
DONOR_COOLDOWN_HOURS = 48      # Кулдаун для повторного парсинга донора
SEARCH_COOLDOWN_HOURS = 12     # Кулдаун для повторного запуска поискового запроса
HARVEST_MAX_SCROLLS = 20       # Глубокий скролл для пробития слоя уже собранных подписчиков
SNOWBALL_MIN_SCORE = 65        # Порог скора кандидата для парсинга его подписок в базу доноров
SNOWBALL_DONOR_MIN_FOLLOWERS = 1500  # Мин. подписчиков у аккаунта, чтобы стать новым донором
SNOWBALL_DONOR_MAX_FOLLOWERS = 120000 # Макс. подписчиков у нового донора

# ==========================================
# 4. ПОИСКОВЫЕ ЗАПРОСЫ: АКТИВНЫЕ АВТОРЫ И ЛАЙКЕРЫ
# ==========================================
SEARCH_QUERIES = [
    '"daily render" 3d',
    '"work in progress" design',
    '"wip" poster',
    '"wip" typography',
    '"framer experiment"',
    '"type design" wip',
    '"poster archive"',
    '"brand identity exploration"',
    'built with framer',
    'blender 3d wip',
    'swiss typography poster',
    'brutalist design web',
    'editorial design typography',
    'speculative design futures',
    'visual identity exploration',
    '"readymag.site" portfolio',
    'layers.to portfolio',
    'design system figma',
    'to:readymag portfolio',
    'to:framer website',
    'to:type01_',
    # 5. Креативные «Пузыри взаимности» (Design Connect & Mutuals)
    '#DesignTwitter "let\'s connect"',
    '#DesignTwitter "mutuals"',
    '#DesignTwitter "moots"',
    '#DesignTwitter "connect"',
    'designer "looking to connect"',
    'ui/ux "let\'s connect"',
    '#buildinpublic "connect with designers"',
    '#artshare "let\'s connect"',
    '#artshare "mutuals"',
    'framer "let\'s connect"',
    'figma "looking to connect"',
    '"graphic designer" "connect"'
]

# Аккаунты-доноры (студии, дизайн-инструменты, инди-типографии, кураторы)
TARGET_DONORS = [
    # Инструменты и платформы
    "readymag",
    "framer",
    "layers",
    "spline_3d",
    "rive_app",
    "godlywebsite",
    "hoverstat_es",
    "MinimalGallery",
    "SiteInspire",
    "Linear",
    "raycastapp",
    # Типографика и шрифтовые бюро
    "type01_",
    "grillitype",
    "pangram_pangram",
    "dinamo_bureau",
    "v_j_t_y_p_e",
    "tightype",
    "schicktoikka",
    # Передовые брендинговые и дизайн-студии
    "StudioDumbar",
    "PentagramDesign",
    "kaborist",
    "bauxitedesign",
    "koto_studios",
    "designstudio",
    "monopo_london",
    "buck_design",
    "wolffolins",
    "HugeInc",
    # Кураторские каналы и медиа
    "MindsparkleMag",
    "itwisthard",
    "CuratedSystem"
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
TARGET_ACCOUNT = os.getenv("TARGET_ACCOUNT", "GerritBrandt777")
