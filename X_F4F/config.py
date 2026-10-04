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

# Кластер E: Маркеры взаимного нетворкинга (Connect, Moots, Mutuals) - Вес: +25 (Механизм 1)
KEYWORDS_CONNECT = [
    "looking for mutuals", "design mutuals", "need mutuals", "creative mutuals",
    "looking to connect", "let's connect", "lets connect", "open to connect",
    "moots", "design moots", "art moots", "connect with designers",
    "connect with creators", "mutuals?", "moots?", "mutuals welcome",
    "looking for moots", "open to collabs and connect", "f4f design",
    "design twitter moots", "designtwitter moots", "design twitter mutuals",
    "designtwitter mutuals", "looking for design mutuals", "let's be mutuals",
    "lets be mutuals", "need design mutuals", "mutuals open", "art moots welcome"
]

# Кластер G: Свежие запуски портфолио и доступность (Launch & Booking Window < 48h) - Вес: +25 (Механизм 2)
KEYWORDS_LAUNCH_FREELANCE = [
    "just launched", "new portfolio", "portfolio is live", "site is live",
    "v2 is live", "redesign is live", "launched my new portfolio",
    "available for freelance", "open for freelance", "freelance availability",
    "booking for q", "booking for 2026", "available for projects", "open for projects",
    "taking new clients", "accepting new projects", "open for work", "available for work",
    "freelance art director", "freelance designer", "booking q4", "booking q1", "booking q2", "booking q3"
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

# Bio Link Sniffer: Ссылки на профессиональные дизайнерские портфолио в Bio/URL (+30 очков)
PORTFOLIO_DOMAINS = [
    "framer.website", "framer.app", "framer.com", "framer.photos", "framer.ai",
    "readymag.site", "readymag.com",
    "layers.to",
    "bento.me",
    "behance.net",
    "dribbble.com",
    "contra.com",
    "cosmos.so",
    "are.na",
    "cargo.site", "cargocollective.com",
    "format.com",
    "webflow.io", "webflow.com",
    "notion.site",
    "polywork.com",
    "savee.it"
]

# Профессиональные TLD-домены для персональных дизайн-сайтов
PORTFOLIO_TLDS = [
    ".design", ".studio", ".works", ".graphics", ".art"
]

# Минимальный проходной балл скоринга для постановки в очередь на подписку
MIN_SCORE_THRESHOLD = 40

# ==========================================
# 2. ЖЕСТКИЕ КРИТЕРИИ ОТБОРА: СУПЕР-ЛАЙКЕРЫ (HARD GATES)
# ==========================================
MIN_FOLLOWERS = 40         # Отсекаем пустые аккаунты, берем реальных авторов от 40 (высокая взаимность)
MAX_FOLLOWERS = 3500       # "Sweet Spot": авторы до 3500 лично читают уведомления и взаимят
MIN_RATIO = 0.50           # Живые авторы с балансом подписок (Following / Followers >= 0.50)
MAX_DAYS_INACTIVE = 14     # Активность: последний твит не старше 14 дней (дизайнеры постят кейсы 1-2 раза в месяц)

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
        "unfollows": 250,  # Безопасный суточный потолок отписок (защита от X Churn Detection)
        "likes": 400,
        "batch": (20, 22),
        "pause": (15, 35),
        "desc": "Полный выход на целевой порог (290–310 follow / 380–420 likes / 250 safe unfollows)."
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
MAX_HOURLY_MUTATIONS = 40      # Жесткий предохранитель антиспама: не более 40 мутаций (follow + unfollow) в любой скользящий 1 час

# Настройки Схемы 1: «Дифференцированный каскад касаний»
TRI_TOUCH_ENABLED = True       # Включение многоэтапного лайкинга + Dwell Time
TRI_TOUCH_VIP_SCORE = 75       # Порог для VIP-каскада из 2 лайков (Score >= 75 или Blue Checkmark)
TRI_TOUCH_MIN_SCORE = 75       # Синоним для обратной совместимости
TRI_TOUCH_PAUSE_BETWEEN_LIKES = (10, 20) # Органическая пауза чтения и скролла между лайками
TRI_TOUCH_PAUSE_BEFORE_FOLLOW = (6, 12)  # Финальная пауза перед кликом Follow

# Настройки Схемы 3: «Тщеславные списки» (Ego-List Bombing)
DAILY_LIST_ADD_LIMIT = 35      # Суточная квота добавлений в списки (отдельный счетчик в X)
EGO_LIST_DEFAULT_NAME = "✦ Top 1% Designers 2026"  # Основной публичный статусный список (макс. 25 симв. в X)
EGO_LIST_MIN_SCORE = 50        # Минимальный скор кандидата для включения в список
LIST_ADD_DELAY_SECONDS = (30, 60) # Случайная пауза между добавлениями в список

# Настройки Discovery Engine 2.0 (Кулдауны источников и Snowball Graph)
DONOR_COOLDOWN_HOURS = 48      # Кулдаун для повторного парсинга подписчиков донора
DONOR_LIKES_COOLDOWN_HOURS = 24 # Кулдаун для парсинга лайкеров свежих твитов донора
SEARCH_COOLDOWN_HOURS = 3     # Кулдаун для повторного запуска поискового запроса
HARVEST_MAX_SCROLLS = 12       # Глубокий скролл для пробития слоя уже собранных подписчиков
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
    # Механизм 1: Креативные «Пузыри взаимности» (Design Connect, Moots & Mutuals) - ТОП КОНВЕРСИЯ
    '#DesignTwitter "looking for mutuals"',
    '#DesignTwitter "design moots"',
    '#DesignTwitter "let\'s connect"',
    '#DesignTwitter "mutuals"',
    '#DesignTwitter "moots"',
    '#designmoots',
    '"design mutuals" "let\'s connect"',
    '"looking for design mutuals"',
    '"creative mutuals" "connect"',
    '"mutuals welcome" designer',
    '"moots?" design',
    'designer "looking to connect"',
    'ui/ux "let\'s connect"',
    'ui designer "looking to connect"',
    '#buildinpublic "connect with designers"',
    '#artshare "let\'s connect"',
    '#artshare "mutuals"',
    'framer "let\'s connect"',
    'figma "looking to connect"',
    '"graphic designer" "connect"',
    '"mutuals?" design',
    '"open to connect" designer',
    # Механизм 2: Свежие запуски портфолио и доступность (Hyper-Active Booking/Launch Window < 48h)
    '("just launched my portfolio" OR "new portfolio is live")',
    '("portfolio is live" OR "new site is live") (framer OR readymag OR layers.to)',
    '("just launched" portfolio) (framer OR readymag OR behance)',
    '("available for freelance" OR "open for freelance") (designer OR "art director")',
    '("booking for Q4" OR "taking freelance clients") (designer OR figma)',
    '("available for new projects" OR "open for projects") (designer OR "brand identity")',
    '"my new portfolio" framer',
    '"my portfolio" behance',
    '"my portfolio" layers.to',
    '"just launched" site framer',
    '"just launched" site readymag',
    '"redesign" wip figma',
    '"available for freelance" designer',
    '"available for freelance" brand'
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
