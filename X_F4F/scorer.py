# -*- coding: utf-8 -*-
"""
Candidate evaluation and scoring engine.
Evaluates bio text, follower counts, follow-back ratio, and portfolio links.
"""

import re
from config import (
    KEYWORDS_ROLES,
    KEYWORDS_STYLE,
    KEYWORDS_INDUSTRY,
    KEYWORDS_ENGAGEMENT,
    KEYWORDS_CONNECT,
    KEYWORDS_LAUNCH_FREELANCE,
    PORTFOLIO_DOMAINS,
    PORTFOLIO_TLDS,
    MIN_FOLLOWERS,
    MAX_FOLLOWERS,
    MIN_RATIO,
    MAX_DAYS_INACTIVE,
    MIN_SCORE_THRESHOLD,
    NEGATIVE_KEYWORDS
)

def contains_keyword(text: str, kw: str) -> bool:
    """
    Smart keyword boundary check.
    For alphanumeric words (e.g. 'grid', 'hud', 'artist', 'founder'):
      Enforces \b boundary so 'organic ingredients' does not trigger 'grid'.
    For phrases with punctuation (e.g. 'ui/ux', 'co-founder', '3d design'):
      Uses boundary anchors respecting whitespace and punctuation.
    """
    if not text or not kw:
        return False
    if re.search(r'[^a-z0-9]', kw):
        pattern = r'(?:\b|^|[\s,;|/\(\)\[\]])' + re.escape(kw) + r'(?:\b|$|[\s,;|/\(\)\[\]])'
    else:
        pattern = r'\b' + re.escape(kw) + r'\b'
    return bool(re.search(pattern, text))

def evaluate_candidate(profile_data: dict) -> dict:
    """
    Evaluates candidate against scoring criteria.
    Returns calculated score, breakdown details, and qualification status.
    """
    bio = (profile_data.get("bio") or "").lower()
    url = (profile_data.get("url") or "").lower()
    followers = int(profile_data.get("followers_count") or 0)
    following = int(profile_data.get("following_count") or 0)
    days_inactive = profile_data.get("days_inactive")

    # 1. Рассчитываем Ratio
    ratio = round(following / followers, 2) if followers > 0 else 0.0

    breakdown = {
        "roles_matched": [],
        "styles_matched": [],
        "industry_matched": [],
        "engagement_matched": [],
        "portfolio_matched": [],
        "connect_matched": [],
        "launch_freelance_matched": [],
        "hungry_talent_bonus": False,
        "super_engager_bonus": False,
        "connect_intent_bonus": False,
        "launch_freelance_bonus": False,
        "mutual_friend_bonus": False,
        "bio_link_sniffer_bonus": False,
        "hard_gates_passed": True,
        "reject_reasons": []
    }

    # 2. Проверка Hard Gates
    # А. Негативные стоп-слова (боты, скам, офферы)
    combined_check = f"{bio} {url}"
    for neg in NEGATIVE_KEYWORDS:
        if neg in combined_check:
            breakdown["hard_gates_passed"] = False
            breakdown["reject_reasons"].append(f"Spam filter: '{neg}'")
            break

    # Bio Link Sniffer: Проверка наличия ссылки на подтвержденное портфолио
    combined_text = f"{bio} {url}"
    has_portfolio = any(domain in combined_text for domain in PORTFOLIO_DOMAINS) or any(tld in combined_text for tld in PORTFOLIO_TLDS)

    # Гибкий нижний порог подписчиков:
    # Обычный порог MIN_FOLLOWERS (40), но если есть подтвержденное дизайнерское портфолио — допускаем от 25
    effective_min_followers = 25 if has_portfolio else MIN_FOLLOWERS
    if followers < effective_min_followers:
        breakdown["hard_gates_passed"] = False
        breakdown["reject_reasons"].append(f"Followers ({followers}) < {effective_min_followers}")

    # Гибкий верхний порог подписчиков:
    # Обычный порог MAX_FOLLOWERS (3500), но для авторов с высокой взаимностью (ratio >= 0.80) допускаем до 5000
    effective_max_followers = 5000 if ratio >= 0.80 else MAX_FOLLOWERS
    if followers > effective_max_followers:
        breakdown["hard_gates_passed"] = False
        breakdown["reject_reasons"].append(f"Followers ({followers}) > {effective_max_followers}")

    # B. Проверка F4F Ratio (взаимность и щедрость на лайки)
    if ratio < MIN_RATIO:
        breakdown["hard_gates_passed"] = False
        breakdown["reject_reasons"].append(f"Ratio ({ratio}) < {MIN_RATIO} (low reciprocity)")

    # C. Проверка активности (дизайнеры постят кейсы 1-2 раза в месяц)
    if days_inactive is not None and days_inactive > MAX_DAYS_INACTIVE:
        breakdown["hard_gates_passed"] = False
        breakdown["reject_reasons"].append(f"Inactive ({days_inactive}d > {MAX_DAYS_INACTIVE}d)")

    # 3. Скоринг совпадений
    score = 0

    # Кластер A: Роли (+35 за первое совпадение, +5 за доп.)
    for role in KEYWORDS_ROLES:
        if contains_keyword(bio, role):
            breakdown["roles_matched"].append(role)
    if breakdown["roles_matched"]:
        score += 35 + min(15, (len(breakdown["roles_matched"]) - 1) * 5)

    # Кластер B: Стили и эстетика (+30 за первое, +5 за доп.)
    for style in KEYWORDS_STYLE:
        if contains_keyword(bio, style):
            breakdown["styles_matched"].append(style)
    if breakdown["styles_matched"]:
        score += 30 + min(15, (len(breakdown["styles_matched"]) - 1) * 5)

    # Кластер C: Индустрия (+25 за первое, +5 за доп.)
    for ind in KEYWORDS_INDUSTRY:
        if contains_keyword(bio, ind):
            breakdown["industry_matched"].append(ind)
    if breakdown["industry_matched"]:
        score += 25 + min(10, (len(breakdown["industry_matched"]) - 1) * 5)

    # Кластер D: Архиваторы, создатели процесса и супер-лайкеры (+25 очков)
    for eng in KEYWORDS_ENGAGEMENT:
        if contains_keyword(bio, eng):
            breakdown["engagement_matched"].append(eng)
    if breakdown["engagement_matched"]:
        score += 25 + min(15, (len(breakdown["engagement_matched"]) - 1) * 5)

    # Bio Link Sniffer: Портфолио / Профессиональные ссылки (+30 очков VIP Boost)
    # Наличие реального дизайн-портфолио (framer, readymag, layers, bento, behance, .design, .studio и т.д.)
    combined_text = f"{bio} {url}"
    for domain in PORTFOLIO_DOMAINS:
        if domain in combined_text:
            breakdown["portfolio_matched"].append(domain)
    for tld in PORTFOLIO_TLDS:
        if tld in combined_text and tld not in breakdown["portfolio_matched"]:
            breakdown["portfolio_matched"].append(tld)
    if breakdown["portfolio_matched"]:
        score += 30
        breakdown["bio_link_sniffer_bonus"] = True

    # Кластер E: Маркеры взаимности (Connect & Mutuals) - Механизм 1 (+25 очков за готовность к нетворкингу)
    # Проверяем как в Bio, так и в закрепленных / свежих твитах
    recent_tweets = (profile_data.get("recent_tweets") or "").lower()
    bio_and_tweets = f"{bio} {recent_tweets}"
    for conn_kw in KEYWORDS_CONNECT:
        if contains_keyword(bio_and_tweets, conn_kw):
            breakdown["connect_matched"].append(conn_kw)
    if breakdown["connect_matched"]:
        score += 25 + min(10, (len(breakdown["connect_matched"]) - 1) * 5)
        breakdown["connect_intent_bonus"] = True

    # Кластер G: Свежие запуски портфолио и доступность для проектов - Механизм 2 (+25 очков)
    # Дизайнеры в окне запуска (<48ч) или поиска проектов максимально вовлечены и мониторят каждое уведомление
    for launch_kw in KEYWORDS_LAUNCH_FREELANCE:
        if contains_keyword(bio_and_tweets, launch_kw):
            breakdown["launch_freelance_matched"].append(launch_kw)
    if breakdown["launch_freelance_matched"] or profile_data.get("is_launch_freelance"):
        score += 25 + min(10, (len(breakdown["launch_freelance_matched"]) - 1) * 5)
        breakdown["launch_freelance_bonus"] = True

    # Ratio scoring: Супер-бонус за щедрость на лайки и взаимность
    if ratio >= 1.10 and following >= 150:
        score += 25   # Супер-лайкер: читает больше, чем его, ставит много реакций
        breakdown["super_engager_bonus"] = True
    elif ratio >= 0.85:
        score += 15   # Отличная взаимность
    elif ratio >= MIN_RATIO:
        score += 5
    else:
        score -= 20   # Штраф за низкую взаимность

    # "Sweet Spot" авторов (100 - 1800 фолловеров, ratio >= 0.80) — максимальная вовлеченность
    if 100 <= followers <= 1800 and ratio >= 0.80:
        score += 20
        breakdown["hungry_talent_bonus"] = True

    # Кластер F: Собеседники и комментаторы проверенных пиров (+25 очков)
    if profile_data.get("is_peer_commenter"):
        score += 25
        breakdown["peer_commenter_bonus"] = True

    # Механизм 4: Triadic Closure ("Friends of Friends" - круг проверенного взаимного дизайнера) (+30 очков)
    # В интерфейсе X пишется: "Followed by @mutual_friend you know", давая конверсию в 30-45%
    if profile_data.get("is_mutual_friend"):
        score += 30
        breakdown["mutual_friend_bonus"] = True

    # Итоговый статус
    is_qualified = breakdown["hard_gates_passed"] and (score >= MIN_SCORE_THRESHOLD)
    status = "queued" if is_qualified else "ignored"

    return {
        "score": max(0, score),
        "ratio": ratio,
        "status": status,
        "breakdown": breakdown
    }

if __name__ == "__main__":
    # Быстрый тест на примере дизайнера
    sample = {
        "username": "swiss_brutalist",
        "bio": "Art Director & Co-Founder @studio | Organic Brutalism & Swiss Style typography | https://layers.to/brut",
        "url": "https://layers.to/brut",
        "followers_count": 1420,
        "following_count": 1380
    }
    res = evaluate_candidate(sample)
    print("Test scoring result:", res)
