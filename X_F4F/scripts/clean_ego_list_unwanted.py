# -*- coding: utf-8 -*-
"""
Script to remove non-designer accounts (hair vendors, construction CEOs,
football meme accounts, medical educators, crypto traders, pure SWE developers)
from '✦ Top 1% Designers 2026' on Twitter, and clean their list_add_sent status
in data/x_growth.db.
"""

import os
import sys
import time
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from browser import get_browser_context, human_delay
from list_bomber import remove_user_from_list, EGO_LIST_DEFAULT_NAME

# Accounts confirmed to be non-designers, spam, or noise
UNWANTED_MEMBERS = [
    # Категория 1: Спам, нерелевантные сферы, товары и спорт/мемы
    "aeesha_bby",        # Продавец средств для волос (Ayurvedic Hair Growth)
    "_foster_joshua_",   # Тяжелая строительная техника и нефть (Construction Equipment)
    "mrstrangemed",      # Медицинский лектор (Health Educator)
    "steroyyama",        # Западный дракон / аниме 18 лет
    "leokoesters",       # Психологическое консультирование
    "santanbob",         # Футбол: Челси, Роналду
    "stillsireultra",    # Посол хлеба и семо
    "ace_szn30",         # Манчестер Юнайтед
    "annybesto",         # Пошив одежды, швея (Bespoke tailor)
    "defipresh",         # Криптотрейдинг
    "theritechain",      # Крипта / Web3 BD
    "bnb_africa08",      # Продавец предметов роскоши (BnB Luxury)
    "monster13liar",     # 13-летний подросток
    "sheratoshi",        # Биткоин-блогер

    # Категория 2: Чистые разработчики, SWE и SaaS-фаундеры без дизайна
    "dotnetsme",         # .NET / AI Software Developer
    "thexsami",          # 12 лет Software Engineer
    "yagcidev",          # Инженер/бэкендер
    "insigdev",          # Бэкенд-инженер
    "willundrll",        # AI SaaS фаундер
    "eldridqe",          # SaaS Retainlens фаундер
    "rodri_shema",       # Фаундер email-инфраструктуры
    "foxrick01",         # Бывший венчурный ангел / инвестор
    "johnny_schae",      # 21-летний разработчик мобильных приложений
    "sachinbrao1",       # Ко-фаундер B2B Outreach SaaS
    "am56ay",            # SaaS фаундер
    "dantegaleazzi",     # Инди-хакер Shipathon
    "sl1sov",            # Генеративный артист
    "just1kelvin",       # Неподтвержденный графический аккаунт
    "bellovisuals",      # Неподтвержденный аккаунт
    "lakix0",            # Разработчик
    "seponabdulazeez",   # Неподтвержденный аккаунт
    "rajtilakvi",        # Видео для SaaS
    "infiloop2"          # Технический разработчик
]

def main():
    profile = "test_igorvl777"
    if len(sys.argv) > 1:
        profile = sys.argv[1]

    print(f"\n=======================================================")
    print(f"  [List Purge] Purging {len(UNWANTED_MEMBERS)} non-designers from '{EGO_LIST_DEFAULT_NAME}'")
    print(f"=======================================================\n")

    pw, ctx, page = get_browser_context(profile_name=profile, headless=False)

    db_path = os.path.join(BASE_DIR, "data", "x_growth.db")

    try:
        removed_count = 0
        for idx, u in enumerate(UNWANTED_MEMBERS, 1):
            print(f"\n[Cleanup] [{idx}/{len(UNWANTED_MEMBERS)}] Processing @{u}...")
            ok = remove_user_from_list(page, u, list_name=EGO_LIST_DEFAULT_NAME)
            if ok:
                removed_count += 1
                print(f"  ✅ Successfully removed @{u} from list on X.")
            else:
                print(f"  ⚠️ Could not remove or already removed @{u}.")

            # Update DB regardless so they are never considered active in this list
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("UPDATE candidates SET list_add_sent = 0 WHERE LOWER(username) = LOWER(?)", (u,))
                cur.execute("DELETE FROM actions_history WHERE LOWER(candidate_username) = LOWER(?) AND action_type = 'list_add'", (u,))
                conn.commit()
                conn.close()
                print(f"  💾 Database tracking cleared for @{u}.")
            except Exception as dbe:
                print(f"  DB clear error for @{u}: {dbe}")

            human_delay(2.0, 4.0)

        print(f"\n=======================================================")
        print(f"  [List Purge Summary]")
        print(f"  Total processed: {len(UNWANTED_MEMBERS)}")
        print(f"  Successfully removed: {removed_count}")
        print(f"=======================================================\n")

    finally:
        ctx.close()
        pw.stop()

if __name__ == "__main__":
    main()
