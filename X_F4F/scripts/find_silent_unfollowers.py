# -*- coding: utf-8 -*-
"""
Direct Diagnostic Script:
Checks recent mutuals on X to detect exactly who unfollowed us (the missing 503rd follower).
Reports their username, bio, and executes an immediate retaliatory unfollow.
"""

import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from browser import get_browser_context, human_delay
from database import get_connection, log_action, get_account_stats
from config import TARGET_ACCOUNT, is_whitelisted_account
from follower import check_is_mutual, unfollow_user_on_current_page, sync_target_profile_stats

def audit_recent_mutuals(limit=35):
    print("\n=======================================================")
    print("  [Audit] Starting Silent Unfollower Audit on X...")
    print("=======================================================\n")

    conn = get_connection()
    cur = conn.cursor()

    # Get recent mutuals
    cur.execute("""
        SELECT username, name, updated_at, followed_at 
        FROM candidates 
        WHERE status = 'mutual'
        ORDER BY updated_at DESC 
        LIMIT ?
    """, (limit,))
    candidates = cur.fetchall()
    conn.close()

    print(f"Loaded {len(candidates)} recent mutual candidates from database.")

    pw, ctx, page = get_browser_context(profile_name="test_igorvl777", headless=False)

    traitors = []
    loyal = []
    skipped = []

    try:
        # Check our profile stats first
        stats = sync_target_profile_stats(page=page, account=TARGET_ACCOUNT)
        print(f"Current stats on X: {stats.get('followers_count')} Followers, {stats.get('following_count')} Following\n")

        for idx, row in enumerate(candidates, 1):
            username = row[0]
            name = row[1] or ""
            updated_at = row[2]
            followed_at = row[3]

            if is_whitelisted_account(username, name):
                print(f"[{idx}/{len(candidates)}] @{username} is WHITELISTED. Skipping.")
                skipped.append(username)
                continue

            print(f"[{idx}/{len(candidates)}] Checking @{username} ({name})... [Mutual since: {updated_at}]")
            is_mutual = check_is_mutual(page, username)

            if is_mutual is None:
                print(f"  ⚠️ Network/DOM lag for @{username}. Skipping.")
                continue

            if is_mutual is False:
                print(f"\n  🚨 BUSTED! @{username} SILENTLY UNFOLLOWED US!")
                print(f"  ⚡ Executing retaliatory UNFOLLOW...")
                ok = unfollow_user_on_current_page(page, username)
                
                # Update DB
                c_conn = get_connection()
                c_cur = c_conn.cursor()
                c_cur.execute("UPDATE candidates SET status = 'unfollowed_me', updated_at = CURRENT_TIMESTAMP WHERE LOWER(username) = LOWER(?)", (username,))
                c_conn.commit()
                c_conn.close()
                log_action(username, "unfollow", success=True, error="silent_unfollower_retaliation")
                
                traitors.append({
                    "username": username,
                    "name": name,
                    "updated_at": updated_at,
                    "followed_at": followed_at
                })
                print(f"  🎯 Status updated to 'unfollowed_me'. Retaliation recorded.\n")
                human_delay(2.0, 4.0)
            else:
                print(f"  ✅ Still loyal MUTUAL.")
                c_conn = get_connection()
                c_cur = c_conn.cursor()
                c_cur.execute("UPDATE candidates SET last_active = CURRENT_TIMESTAMP WHERE LOWER(username) = LOWER(?)", (username,))
                c_conn.commit()
                c_conn.close()
                loyal.append(username)
                human_delay(1.0, 2.0)

            # If we already found traitor(s) and checked at least 15 candidates, we can stop or continue
            if len(traitors) >= 2 and idx >= 20:
                print("\nIdentified multiple traitors. Halting audit.")
                break

    finally:
        ctx.close()
        pw.stop()

    print("\n=======================================================")
    print("  [Audit Summary]")
    print(f"  Total checked:       {len(loyal) + len(traitors)}")
    print(f"  Loyal mutuals:       {len(loyal)}")
    print(f"  Silent unfollowers:  {len(traitors)}")
    for t in traitors:
        print(f"    ❌ @{t['username']} ({t['name']}) - Mutual date: {t['updated_at']}")
    print("=======================================================\n")

if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    audit_recent_mutuals(limit=lim)
