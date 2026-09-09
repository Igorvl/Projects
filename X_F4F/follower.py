# -*- coding: utf-8 -*-
"""
Smart Follow & Unfollow execution engine.
Performs safe follows with randomized human pauses, respects daily limits,
tracks mutual follows, and manages unfollows for non-responders.
"""

import random
import time
import datetime
from browser import get_browser_context, human_delay
from config import (
    DAILY_FOLLOW_LIMIT,
    DAILY_UNFOLLOW_LIMIT,
    MIN_DELAY_SECONDS,
    MAX_DELAY_SECONDS,
    UNFOLLOW_AFTER_DAYS
)
from database import (
    get_connection,
    get_candidates_for_follow,
    log_action,
    DB_TYPE
)

def get_today_counts():
    """Gets total actions executed today."""
    conn = get_connection()
    cur = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cur.execute(f"SELECT follows_sent, unfollows_done FROM daily_stats WHERE date = {ph}", (today,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return 0, 0

def follow_user(page, username: str) -> bool:
    """Navigates to user profile and clicks the Follow button if not already followed."""
    clean_user = username.replace("@", "").strip()
    url = f"https://x.com/{clean_user}"
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.0, 3.5)
        
        # Look for Follow button
        # In X, the button has testid="[id]-follow" or text "Follow"
        follow_btn = page.query_selector('button[data-testid$="-follow"]') or page.query_selector('button:has-text("Follow")')
        
        # Check if already following (Following button has testid="[id]-unfollow")
        unfollow_btn = page.query_selector('button[data-testid$="-unfollow"]') or page.query_selector('button:has-text("Following")')
        if unfollow_btn:
            print(f"  [Follower] Already following @{clean_user}, skipping.")
            log_action(clean_user, "follow", success=True, error="already_following")
            return False
            
        if follow_btn:
            follow_btn.click()
            print(f"  [Follower] Successfully followed @{clean_user}!")
            log_action(clean_user, "follow", success=True)
            return True
        else:
            print(f"  [Follower] Follow button not found for @{clean_user}")
            log_action(clean_user, "follow", success=False, error="button_not_found")
            return False
            
    except Exception as e:
        print(f"  [Follower] Error following @{clean_user}: {e}")
        log_action(clean_user, "follow", success=False, error=str(e))
        return False

def check_is_mutual(page, username: str) -> bool:
    """
    Checks if user follows us back.
    X shows 'Follows you' badge on their profile page.
    """
    clean_user = username.replace("@", "").strip()
    try:
        page.goto(f"https://x.com/{clean_user}", wait_until="domcontentloaded", timeout=20000)
        human_delay(1.5, 3.0)
        page_text = page.inner_text("body")
        # X shows "Follows you" text in profile header for mutual followers
        return "Follows you" in page_text
    except Exception as e:
        print(f"  [Follower] Error checking mutual @{clean_user}: {e}")
        return False

def unfollow_user(page, username: str) -> bool:
    """Navigates to user profile and unfollows if they don't follow back."""
    clean_user = username.replace("@", "").strip()
    try:
        page.goto(f"https://x.com/{clean_user}", wait_until="domcontentloaded", timeout=20000)
        human_delay(2.0, 3.5)
        
        # Find "Following" button (means we follow them — can unfollow)
        unfollow_btn = page.query_selector('button[data-testid$="-unfollow"]') or page.query_selector('button:has-text("Following")')
        if unfollow_btn:
            unfollow_btn.click()
            human_delay(0.5, 1.5)
            # X shows a confirm modal "Unfollow @user?" — click confirm
            confirm_btn = page.query_selector('button[data-testid="confirmationSheetConfirm"]')
            if confirm_btn:
                confirm_btn.click()
            print(f"  [Follower] Unfollowed @{clean_user}")
            log_action(clean_user, "unfollow", success=True)
            return True
        else:
            print(f"  [Follower] Unfollow button not found for @{clean_user}")
            log_action(clean_user, "unfollow", success=False, error="button_not_found")
            return False
    except Exception as e:
        print(f"  [Follower] Error unfollowing @{clean_user}: {e}")
        log_action(clean_user, "unfollow", success=False, error=str(e))
        return False

def get_candidates_for_unfollow(days: int = UNFOLLOW_AFTER_DAYS, limit: int = 20) -> list:
    """
    Returns users we followed N+ days ago who still haven't followed back.
    """
    conn = get_connection()
    cur = conn.cursor()
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(f"""
        SELECT username FROM candidates
        WHERE status = 'followed' AND updated_at <= {ph}
        ORDER BY updated_at ASC
        LIMIT {ph}
    """, (cutoff, limit))
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

def run_follow_batch(profile_name="test_igorvl777", batch_size=5):
    """Executes a small batch of follows safely within limits."""
    follows_today, _ = get_today_counts()
    if follows_today >= DAILY_FOLLOW_LIMIT:
        print(f"[Follower] Daily follow limit reached ({follows_today}/{DAILY_FOLLOW_LIMIT}). Halting.")
        return
        
    allowed_count = min(batch_size, DAILY_FOLLOW_LIMIT - follows_today)
    candidates = get_candidates_for_follow(limit=allowed_count)
    
    if not candidates:
        print("[Follower] No candidates in queue with qualifying score.")
        return
        
    print(f"[Follower] Starting follow batch for {len(candidates)} candidates...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    
    try:
        for c in candidates:
            u = c["username"]
            print(f"\n[Follower] Processing candidate @{u} (Score: {c['score']}, Ratio: {c['ratio']})...")
            success = follow_user(page, u)
            
            if success:
                delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                print(f"  [Follower] Sleeping for {delay} seconds (safe delay)...")
                time.sleep(delay)
            else:
                human_delay(2.0, 4.0)
    finally:
        ctx.close()
        pw.stop()
        print("\n[Follower] Follow batch finished.")

def run_unfollow_batch(profile_name="test_igorvl777", batch_size=5):
    """
    Checks candidates followed N+ days ago, verifies mutual status,
    unfollows non-responders, marks mutuals.
    """
    _, unfollows_today = get_today_counts()
    if unfollows_today >= DAILY_UNFOLLOW_LIMIT:
        print(f"[Follower] Daily unfollow limit reached ({unfollows_today}/{DAILY_UNFOLLOW_LIMIT}). Halting.")
        return

    candidates = get_candidates_for_unfollow(days=UNFOLLOW_AFTER_DAYS, limit=batch_size)
    if not candidates:
        print("[Follower] No candidates pending unfollow check.")
        return

    print(f"[Follower] Starting unfollow check for {len(candidates)} candidates...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)

    try:
        for username in candidates:
            print(f"\n[Follower] Checking mutual for @{username}...")
            is_mutual = check_is_mutual(page, username)

            if is_mutual:
                # They followed back — mark as mutual, keep following
                log_action(username, "mutual", success=True)
                print(f"  [Follower] @{username} followed back — marked as MUTUAL ✅")
            else:
                # No reciprocity after N days — unfollow
                _, unfollows_today = get_today_counts()
                if unfollows_today >= DAILY_UNFOLLOW_LIMIT:
                    print("[Follower] Daily unfollow limit reached mid-batch. Stopping.")
                    break
                success = unfollow_user(page, username)
                if success:
                    delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                    print(f"  [Follower] Sleeping {delay}s...")
                    time.sleep(delay)

            human_delay(2.0, 4.0)
    finally:
        ctx.close()
        pw.stop()
        print("\n[Follower] Unfollow batch finished.")


if __name__ == "__main__":
    import sys
    prof = sys.argv[1] if len(sys.argv) > 1 else "test_igorvl777"
    mode = sys.argv[2] if len(sys.argv) > 2 else "follow"
    if mode == "unfollow":
        run_unfollow_batch(profile_name=prof, batch_size=3)
    else:
        run_follow_batch(profile_name=prof, batch_size=3)

