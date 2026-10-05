# -*- coding: utf-8 -*-
"""
Scan following list on X (https://x.com/{TARGET_ACCOUNT}/following),
detect who does NOT follow us back ('Follows you' badge missing),
and register/update them in data/x_growth.db as legacy 'followed' accounts
with followed_at = '2024-01-01 00:00:00'.

This ensures that the orchestrator's unfollow pipeline picks up the oldest
non-mutual follows first (followed_at ASC) at 12–20 per session,
smoothly and safely bringing Following down to Followers parity.
"""

import os
import sys
import time
import re
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from browser import get_browser_context, human_delay, wait_for_x_page_load, handle_x_retry_button
from config import TARGET_ACCOUNT, DB_TYPE
from database import get_connection, log_action

def sync_legacy_following(profile_name="test_igorvl777", max_scrolls=60):
    url = f"https://x.com/{TARGET_ACCOUNT}/following"
    print(f"\n=======================================================")
    print(f"  [Legacy Sync] Scanning {url}")
    print(f"=======================================================\n")

    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    
    scanned_users = {} # handle -> {"is_mutual": bool, "name": str}

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        wait_for_x_page_load(page, ready_selector='[data-testid="UserCell"]', max_wait_sec=10.0, max_retries=2)
        handle_x_retry_button(page)
        human_delay(2.0, 3.5)

        last_count = 0
        stagnant_scrolls = 0

        for scroll_idx in range(1, max_scrolls + 1):
            cells = page.locator('[data-testid="UserCell"]')
            count = cells.count()

            for i in range(count):
                try:
                    cell = cells.nth(i)
                    cell_text = cell.inner_text()
                    handles = re.findall(r'@([A-Za-z0-9_]+)', cell_text)
                    if not handles:
                        continue
                    handle = handles[0].lower()
                    
                    # Detect mutual badge
                    # X displays "Follows you" / "Вас читают" in UserCell
                    is_mutual = bool(
                        re.search(r'\b(follows you|вас читают)\b', cell_text, re.IGNORECASE)
                    )

                    lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
                    name = lines[0] if lines else handle

                    if handle not in scanned_users or (not scanned_users[handle]["is_mutual"] and is_mutual):
                        scanned_users[handle] = {
                            "is_mutual": is_mutual,
                            "name": name,
                            "original_handle": handles[0]
                        }
                except Exception:
                    pass

            current_count = len(scanned_users)
            print(f"  [Scroll {scroll_idx}/{max_scrolls}] Scanned: {current_count} accounts so far...")

            if current_count == last_count and current_count > 0:
                stagnant_scrolls += 1
                if stagnant_scrolls >= 4:
                    print("  [Legacy Sync] Reached end of following list or no new items loaded.")
                    break
            else:
                stagnant_scrolls = 0

            last_count = current_count
            page.mouse.wheel(0, 900)
            time.sleep(1.2)

        print(f"\n[Legacy Sync] Completed scan. Total accounts found in following: {len(scanned_users)}")

    finally:
        ctx.close()
        pw.stop()

    if not scanned_users:
        print("[Legacy Sync] No users found. Please check browser session.")
        return

    # Database ingestion
    conn = get_connection()
    cur = conn.cursor()
    ph = "?" if DB_TYPE == "sqlite" else "%s"

    mutual_count = 0
    legacy_unfollow_queued = 0
    already_tracked = 0

    legacy_date = "2024-01-01 00:00:00"

    for handle, data in scanned_users.items():
        orig_handle = data["original_handle"]
        is_mutual = data["is_mutual"]

        cur.execute(f"SELECT id, username, status, followed_at FROM candidates WHERE LOWER(username) = LOWER({ph})", (handle,))
        row = cur.fetchone()

        if is_mutual:
            mutual_count += 1
            if row:
                if row[2] != "mutual":
                    cur.execute(f"UPDATE candidates SET status = 'mutual', updated_at = CURRENT_TIMESTAMP WHERE id = {ph}", (row[0],))
                    print(f"  ✅ [Mutual] Updated @{orig_handle} to 'mutual'")
            else:
                cur.execute(f"""
                    INSERT INTO candidates (username, name, status, score, source, created_at, updated_at)
                    VALUES ({ph}, {ph}, 'mutual', 50, 'legacy_sync', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (orig_handle, data["name"]))
                print(f"  ✅ [Mutual] Added new mutual @{orig_handle}")
        else:
            # Does NOT follow back
            if row:
                status = row[2]
                followed_at = row[3]
                if status == "mutual":
                    # Keep safe: don't demote existing mutuals based on a single badge check
                    pass
                elif status == "followed":
                    already_tracked += 1
                    # Ensure followed_at is legacy if it was NULL
                    if not followed_at:
                        cur.execute(f"UPDATE candidates SET followed_at = {ph} WHERE id = {ph}", (legacy_date, row[0]))
                else:
                    # 'discovered', 'queued', 'dismissed' but we are actually following them!
                    cur.execute(f"""
                        UPDATE candidates 
                        SET status = 'followed', followed_at = {ph}, source = 'legacy_following', updated_at = CURRENT_TIMESTAMP
                        WHERE id = {ph}
                    """, (legacy_date, row[0]))
                    legacy_unfollow_queued += 1
                    print(f"  📌 [Legacy Unfollow Queue] @{orig_handle} (status: {status} -> 'followed', date: 2024-01-01)")
            else:
                # Not in DB at all, but we follow them! Insert as legacy followed
                cur.execute(f"""
                    INSERT INTO candidates (username, name, status, score, source, followed_at, created_at, updated_at)
                    VALUES ({ph}, {ph}, 'followed', 0, 'legacy_following', {ph}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (orig_handle, data["name"], legacy_date))
                legacy_unfollow_queued += 1
                print(f"  📌 [Legacy Unfollow Queue] Added @{orig_handle} (status: 'followed', date: 2024-01-01)")

    conn.commit()
    conn.close()

    print("\n=======================================================")
    print(f"  [Legacy Sync Summary]")
    print(f"  Total following scanned: {len(scanned_users)}")
    print(f"  Mutuals confirmed:       {mutual_count}")
    print(f"  Legacy non-mutual queued: {legacy_unfollow_queued}")
    print(f"  Already tracked followed: {already_tracked}")
    print(f"=======================================================\n")

if __name__ == "__main__":
    prof = sys.argv[1] if len(sys.argv) > 1 else "test_igorvl777"
    sync_legacy_following(profile_name=prof)
