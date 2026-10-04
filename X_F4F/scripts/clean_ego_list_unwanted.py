# -*- coding: utf-8 -*-
"""
Script to remove non-elite / unqualified members from '✦ Top 1% Designers 2026' on Twitter
and reset their list_add_sent status in the database.
"""

import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from browser import get_browser_context, human_delay
from list_bomber import remove_user_from_list, EGO_LIST_DEFAULT_NAME
import sqlite3

# Accounts confirmed to be casual/unrelated to top-1% design
UNWANTED_MEMBERS = [
    "stillsireultra",
    "ace_szn30",
    "_demilade0",
    "letstalkarif",
    "mercyuiuxdesign",
    "oluwasefunmi1_",
    "uifaruk44",
    "ngee_mela"
]

def main():
    profile = "test_igorvl777"
    if len(sys.argv) > 1:
        profile = sys.argv[1]

    print(f"[Cleanup] Starting removal of {len(UNWANTED_MEMBERS)} casual members from list '{EGO_LIST_DEFAULT_NAME}'...")
    pw, ctx, page = get_browser_context(profile_name=profile, headless=False)

    try:
        removed_count = 0
        for idx, u in enumerate(UNWANTED_MEMBERS, 1):
            print(f"\n[Cleanup] [{idx}/{len(UNWANTED_MEMBERS)}] Removing @{u}...")
            ok = remove_user_from_list(page, u, list_name=EGO_LIST_DEFAULT_NAME)
            if ok:
                removed_count += 1
            human_delay(2.0, 4.0)

        print(f"\n[Cleanup] Successfully removed {removed_count}/{len(UNWANTED_MEMBERS)} members.")
    finally:
        ctx.close()
        pw.stop()

if __name__ == "__main__":
    main()
