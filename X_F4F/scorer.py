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
    PORTFOLIO_DOMAINS,
    MIN_FOLLOWERS,
    MAX_FOLLOWERS,
    MIN_RATIO,
    MIN_SCORE_THRESHOLD,
    NEGATIVE_KEYWORDS
)

def evaluate_candidate(profile_data: dict) -> dict:
    """
    Evaluates candidate against scoring criteria.
    Returns calculated score, breakdown details, and qualification status.
    """
    bio = (profile_data.get("bio") or "").lower()
    url = (profile_data.get("url") or "").lower()
    followers = int(profile_data.get("followers_count") or 0)
    following = int(profile_data.get("following_count") or 0)

    # 1. Рассчитываем Ratio
    ratio = round(following / followers, 2) if followers > 0 else 0.0

    breakdown = {
        "roles_matched": [],
        "styles_matched": [],
        "industry_matched": [],
        "portfolio_matched": [],
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

    if followers < MIN_FOLLOWERS:
        breakdown["hard_gates_passed"] = False
        breakdown["reject_reasons"].append(f"Followers ({followers}) < {MIN_FOLLOWERS}")

    if followers > MAX_FOLLOWERS:
        breakdown["hard_gates_passed"] = False
        breakdown["reject_reasons"].append(f"Followers ({followers}) > {MAX_FOLLOWERS}")

    # Ratio — soft check only: very low ratio is penalised in scoring, not hard-rejected.
    # Hard rejection only for extreme ghost accounts (ratio < 0.05).
    if ratio < 0.05 and followers > 500:
        breakdown["hard_gates_passed"] = False
        breakdown["reject_reasons"].append(f"Ratio ({ratio}) < 0.05 (ghost account)")

    # 3. Скоринг совпадений
    score = 0

    # Кластер A: Роли (+35 за первое совпадение, +5 за доп.)
    # NOTE: не используем \b word boundary — символ '/' в 'ui/ux' ломает границу слова.
    # Вместо этого: точный substring match (bio уже в lower())
    for role in KEYWORDS_ROLES:
        if role in bio:
            breakdown["roles_matched"].append(role)
    if breakdown["roles_matched"]:
        score += 35 + min(15, (len(breakdown["roles_matched"]) - 1) * 5)

    # Кластер B: Стили и эстетика (+30 за первое, +5 за доп.)
    for style in KEYWORDS_STYLE:
        if style in bio:
            breakdown["styles_matched"].append(style)
    if breakdown["styles_matched"]:
        score += 30 + min(15, (len(breakdown["styles_matched"]) - 1) * 5)

    # Кластер C: Индустрия (+30 за первое, +5 за доп.)
    for ind in KEYWORDS_INDUSTRY:
        if ind in bio:
            breakdown["industry_matched"].append(ind)
    if breakdown["industry_matched"]:
        score += 30 + min(10, (len(breakdown["industry_matched"]) - 1) * 5)

    # Портфолио / Ссылки (+15 очков)
    combined_text = f"{bio} {url}"
    for domain in PORTFOLIO_DOMAINS:
        if domain in combined_text:
            breakdown["portfolio_matched"].append(domain)
    if breakdown["portfolio_matched"]:
        score += 15

    # Ratio scoring: бонус за активных взаимщиков, штраф за «звёзд»
    if ratio >= 0.95:
        score += 10   # Активный взаимщик — отличный F4F кандидат
    elif ratio >= MIN_RATIO:   # 0.50+ — хороший взаимщик
        score += 5
    elif ratio < 0.15:         # Очень низкий ratio — звезда, вряд ли ответит
        score -= 10

    # Итоговый статус
    is_qualified = breakdown["hard_gates_passed"] and (score >= MIN_SCORE_THRESHOLD)
    status = "queued" if is_qualified else "ignored"

    return {
        "score": score,
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
