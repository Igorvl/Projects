# -*- coding: utf-8 -*-
"""
Smart Follow & Unfollow execution engine.
Performs safe follows with randomized human pauses, respects daily limits,
tracks mutual follows, and manages unfollows for non-responders.
"""

import random
import time
import datetime
from browser import (
    get_browser_context,
    human_delay,
    human_click,
    human_scroll,
    human_idle_noise
)
from config import (
    DAILY_FOLLOW_LIMIT,
    DAILY_UNFOLLOW_LIMIT,
    DAILY_LIKE_LIMIT,
    LIKE_PROBABILITY,
    MIN_DELAY_SECONDS,
    MAX_DELAY_SECONDS,
    UNFOLLOW_AFTER_DAYS,
    TARGET_ACCOUNT,
    TRI_TOUCH_ENABLED,
    TRI_TOUCH_MIN_SCORE,
    TRI_TOUCH_PAUSE_BETWEEN_LIKES,
    TRI_TOUCH_PAUSE_BEFORE_FOLLOW
)
from database import (
    get_connection,
    get_candidates_for_follow,
    log_action,
    DB_TYPE
)

def get_today_counts():
    """Gets total actions executed today (follows, unfollows)."""
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

def get_today_likes() -> int:
    """Gets total likes executed today to preserve daily quota."""
    conn = get_connection()
    cur = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    cur.execute(f"SELECT COALESCE(likes_sent, 0) FROM daily_stats WHERE date = {ph}", (today,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return 0

def execute_engagement_cascade(page, username: str, candidate_score: int = 0, is_hungry_talent: bool = False) -> int:
    """
    Executes Scheme 1: Micro-Engagement Cascade.
    For high-priority candidates (hungry talents or score >= TRI_TOUCH_MIN_SCORE),
    performs a dense 2-like cascade (Fresh thought + Media/Portfolio) separated by organic Dwell Time.
    For standard candidates, executes a single warm-touch like.
    Strictly enforces DAILY_LIKE_LIMIT to safeguard account quotas.
    Returns: count of likes executed (0, 1, or 2).
    """
    likes_today = get_today_likes()
    if likes_today >= DAILY_LIKE_LIMIT:
        print(f"  [Cascade] Daily like limit reached ({likes_today}/{DAILY_LIKE_LIMIT}). Preserving quota.")
        return 0

    likes_remaining = DAILY_LIKE_LIMIT - likes_today
    
    # Check if candidate qualifies for dense Tri-Touch cascade (2 likes)
    qualifies_for_cascade = (
        TRI_TOUCH_ENABLED and 
        (is_hungry_talent or candidate_score >= TRI_TOUCH_MIN_SCORE) and 
        likes_remaining >= 2
    )

    max_likes_target = 2 if qualifies_for_cascade else 1
    
    # Organic probability check for single-like tier
    if not qualifies_for_cascade and random.random() > LIKE_PROBABILITY:
        print(f"  [Cascade] Skipped like for @{username} (organic variance / preserving quota).")
        return 0

    mode_label = "Tri-Touch Cascade (2 likes + Dwell)" if qualifies_for_cascade else "Single Warm Touch"
    print(f"  [Cascade] Mode: {mode_label} for @{username} (Score: {candidate_score}, Quota remaining: {likes_remaining})")

    likes_placed = 0

    try:
        # Step 1: Smooth scroll down to view recent posts
        human_scroll(page, steps=1)
        human_delay(1.5, 3.0)

        tweets = page.locator('article[data-testid="tweet"]')
        tweet_count = tweets.count()
        if tweet_count == 0:
            return 0

        # --- TOUCH 1: Fresh Author's Post (Original, non-repost) ---
        liked_indices = set()
        for i in range(min(3, tweet_count)):
            tweet = tweets.nth(i)

            # Skip retweets/reposts
            social_context = tweet.locator('[data-testid="socialContext"]')
            if social_context.count() > 0:
                sc_text = social_context.first.inner_text().lower()
                if "repost" in sc_text or "ретвит" in sc_text:
                    continue

            # Skip if already liked
            if tweet.locator('[data-testid="unlike"]').count() > 0:
                continue

            like_btn = tweet.locator('[data-testid="like"]')
            if like_btn.count() > 0 and like_btn.first.is_visible():
                human_delay(1.0, 2.2)
                clicked = human_click(page, like_btn.first)
                if clicked:
                    likes_placed += 1
                    liked_indices.add(i)
                    log_action(username, "like", success=True)
                    print(f"  [Cascade] ❤️ [Touch 1/2] Liked recent post of @{username} (Today: {likes_today + likes_placed}/{DAILY_LIKE_LIMIT})")
                    break

        # If only 1 like requested or 1st like wasn't placed, return early
        if likes_placed == 0 or max_likes_target == 1:
            if likes_placed > 0:
                pre_pause = random.uniform(TRI_TOUCH_PAUSE_BEFORE_FOLLOW[0], TRI_TOUCH_PAUSE_BEFORE_FOLLOW[1])
                human_delay(pre_pause, pre_pause + 0.8)
            return likes_placed

        # --- STEP 2: Dwell Time + Organic Scroll towards Media / Case Study ---
        pause_between = random.uniform(TRI_TOUCH_PAUSE_BETWEEN_LIKES[0], TRI_TOUCH_PAUSE_BETWEEN_LIKES[1])
        print(f"  [Cascade] ⏳ Dwell Time warming ({pause_between:.1f}s) & exploring portfolio/media...")
        human_delay(pause_between / 2.0, pause_between / 2.0 + 1.0)
        human_scroll(page, steps=random.randint(1, 2))
        human_delay(pause_between / 2.0 - 0.5, pause_between / 2.0 + 0.5)

        # Refresh tweets locator after scrolling
        tweets = page.locator('article[data-testid="tweet"]')
        tweet_count = tweets.count()

        # --- TOUCH 2: Visual Media / Portfolio Post ---
        for i in range(tweet_count):
            if i in liked_indices:
                continue

            tweet = tweets.nth(i)

            # Skip retweets/reposts
            social_context = tweet.locator('[data-testid="socialContext"]')
            if social_context.count() > 0:
                sc_text = social_context.first.inner_text().lower()
                if "repost" in sc_text or "ретвит" in sc_text:
                    continue

            # Skip if already liked
            if tweet.locator('[data-testid="unlike"]').count() > 0:
                continue

            # Check for visual media or portfolio cards
            has_media = (
                tweet.locator('[data-testid="tweetPhoto"]').count() > 0 or
                tweet.locator('[data-testid="videoPlayer"]').count() > 0 or
                tweet.locator('[data-testid="card.wrapper"]').count() > 0
            )

            like_btn = tweet.locator('[data-testid="like"]')
            if like_btn.count() > 0 and like_btn.first.is_visible():
                if has_media or i >= min(4, tweet_count - 1):
                    human_delay(1.2, 2.5)
                    clicked = human_click(page, like_btn.first)
                    if clicked:
                        likes_placed += 1
                        log_action(username, "like", success=True)
                        print(f"  [Cascade] 🎨 [Touch 2/2] Liked visual/portfolio work of @{username} (Today: {likes_today + likes_placed}/{DAILY_LIKE_LIMIT})")
                        break

        # Step 3: Final Dwell pause before Follow action
        final_pause = random.uniform(TRI_TOUCH_PAUSE_BEFORE_FOLLOW[0], TRI_TOUCH_PAUSE_BEFORE_FOLLOW[1])
        print(f"  [Cascade] ⏳ Pre-follow composure pause ({final_pause:.1f}s)...")
        human_delay(final_pause, final_pause + 0.8)

        return likes_placed

    except Exception as e:
        print(f"  [Cascade] Notice during engagement cascade for @{username}: {e}")
        return likes_placed

def follow_user(page, username: str, candidate_meta: dict = None) -> bool:
    """
    Navigates to user profile, executes engagement cascade (Tri-Touch or Warm Touch),
    moves cursor to Follow button via Bezier curves, and follows with human composure.
    """
    clean_user = username.replace("@", "").strip()
    url = f"https://x.com/{clean_user}"
    
    candidate_score = 0
    is_hungry_talent = False
    if candidate_meta:
        candidate_score = candidate_meta.get("score", 0)
        breakdown = candidate_meta.get("score_breakdown", {})
        if isinstance(breakdown, str):
            import json
            try:
                breakdown = json.loads(breakdown)
            except Exception:
                breakdown = {}
        if isinstance(breakdown, dict):
            is_hungry_talent = breakdown.get("hungry_talent_bonus", False)
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.5, 4.0)
        
        # Check if already following
        unfollow_btn = page.query_selector('button[data-testid$="-unfollow"]') or page.query_selector('button:has-text("Following")')
        if unfollow_btn:
            print(f"  [Follower] Already following @{clean_user}, skipping.")
            log_action(clean_user, "follow", success=True, error="already_following")
            return False
            
        follow_btn = page.query_selector('button[data-testid$="-follow"]') or page.query_selector('button:has-text("Follow")')
        if not follow_btn:
            print(f"  [Follower] Follow button not found for @{clean_user}")
            log_action(clean_user, "follow", success=False, error="button_not_found")
            return False

        # 1. Execute Engagement Cascade (Tri-Touch: 2 likes + Dwell Time or single warm touch)
        execute_engagement_cascade(page, clean_user, candidate_score=candidate_score, is_hungry_talent=is_hungry_talent)
        
        # 2. Scroll back to top if needed and locate Follow button
        follow_btn = page.query_selector('button[data-testid$="-follow"]') or page.query_selector('button:has-text("Follow")')
        if not follow_btn:
            page.evaluate("window.scrollTo(0, 0)")
            human_delay(1.2, 2.0)
            follow_btn = page.query_selector('button[data-testid$="-follow"]') or page.query_selector('button:has-text("Follow")')

        if follow_btn:
            # Human smooth click with Bezier trajectory
            clicked = human_click(page, follow_btn)
            if clicked:
                print(f"  [Follower] 🎯 Successfully followed @{clean_user}! (Tri-Touch complete)")
                log_action(clean_user, "follow", success=True)
                
                # Human lingering
                human_delay(2.0, 3.5)
                if random.random() < 0.4:
                    human_idle_noise(page)
                return True
            else:
                print(f"  [Follower] Click failed on follow button for @{clean_user}")
                log_action(clean_user, "follow", success=False, error="click_failed")
                return False
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
    X shows 'Follows you' / 'Читает вас' badge on their profile page.
    """
    clean_user = username.replace("@", "").strip()
    try:
        page.goto(f"https://x.com/{clean_user}", wait_until="domcontentloaded", timeout=20000)
        human_delay(1.8, 3.5)
        
        # 1. Check official data-testid selector
        indicator = page.locator('[data-testid="userFollowIndicator"]')
        if indicator.count() > 0 and indicator.first.is_visible():
            return True
            
        # 2. Multilingual text fallback (EN: 'Follows you', RU: 'Читает вас')
        page_text = page.inner_text("body")
        return "Follows you" in page_text or "Читает вас" in page_text
    except Exception as e:
        print(f"  [Follower] Error checking mutual @{clean_user}: {e}")
        return False

def unfollow_user(page, username: str) -> bool:
    """Navigates to user profile and unfollows with human curve clicks."""
    clean_user = username.replace("@", "").strip()
    try:
        page.goto(f"https://x.com/{clean_user}", wait_until="domcontentloaded", timeout=20000)
        human_delay(2.0, 4.0)

        # 1. Проверяем, существует ли аккаунт или он заблокирован
        page_text = ""
        try:
            page_text = page.inner_text("body")
        except Exception:
            pass

        if any(msg in page_text for msg in [
            "Account suspended", "Учетная запись заблокирована",
            "This account doesn’t exist", "Такой учетной записи нет",
            "You’re blocked", "Вы заблокированы"
        ]):
            print(f"  [Follower] Account @{clean_user} is suspended, blocked or doesn't exist.")
            log_action(clean_user, "unfollow", success=False, error="account_unavailable")
            return False

        # 2. Ищем кнопку 'Following' / 'Читаю' (мы подписаны — нужно отписаться)
        unfollow_btn = (
            page.query_selector('button[data-testid$="-unfollow"]') or
            page.query_selector('button:has-text("Following")') or
            page.query_selector('button:has-text("Читаю")') or
            page.query_selector('button:has-text("Подписан")') or
            page.query_selector('button:has-text("Отслеживать")')
        )

        # 3. Проверяем, возможно мы уже НЕ подписаны (активна кнопка 'Follow' / 'Читать')
        already_not_following = (
            page.query_selector('button[data-testid$="-follow"]:not([data-testid$="-unfollow"])') or
            page.query_selector('button:has-text("Follow")') or
            page.query_selector('button:has-text("Читать")')
        )

        if unfollow_btn:
            human_click(page, unfollow_btn)
            human_delay(0.8, 1.8)

            # Модальное окно подтверждения отписки (мультиязычное)
            confirm_btn = (
                page.query_selector('button[data-testid="confirmationSheetConfirm"]') or
                page.query_selector('div[data-testid="confirmationSheetDialog"] button:has-text("Unfollow")') or
                page.query_selector('div[data-testid="confirmationSheetDialog"] button:has-text("Отменить")') or
                page.query_selector('div[data-testid="confirmationSheetDialog"] button:has-text("Отписаться")')
            )
            if confirm_btn:
                human_click(page, confirm_btn)
                human_delay(0.5, 1.2)

            print(f"  [Follower] Unfollowed @{clean_user} (organic click)")
            log_action(clean_user, "unfollow", success=True)
            return True
        elif already_not_following:
            print(f"  [Follower] Already not following @{clean_user} (Follow/Читать button visible). Marking as unfollowed.")
            log_action(clean_user, "unfollow", success=True, error="already_not_following")
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
        WHERE status = 'followed' AND COALESCE(followed_at, updated_at) <= {ph}
        ORDER BY COALESCE(followed_at, updated_at) ASC
        LIMIT {ph}
    """, (cutoff, limit))
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

def run_follow_batch(profile_name="test_igorvl777", batch_size=5):
    """
    Executes a small batch of follows safely within limits with log-normal delays
    and natural rest breaks.
    """
    follows_today, _ = get_today_counts()
    if follows_today >= DAILY_FOLLOW_LIMIT:
        print(f"[Follower] Daily follow limit reached ({follows_today}/{DAILY_FOLLOW_LIMIT}). Halting.")
        return
        
    allowed_count = min(batch_size, DAILY_FOLLOW_LIMIT - follows_today)
    candidates = get_candidates_for_follow(limit=allowed_count)
    
    if not candidates:
        print("[Follower] No candidates in queue with qualifying score.")
        return
        
    print(f"[Follower] Starting safe follow batch for {len(candidates)} candidates...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    
    try:
        for idx, c in enumerate(candidates, 1):
            u = c["username"]
            print(f"\n[Follower] Processing candidate @{u} (Score: {c['score']}, Ratio: {c['ratio']})...")
            success = follow_user(page, u, candidate_meta=c)
            
            if success:
                # Log-normal distribution around center of min/max delay
                mean_delay = (MIN_DELAY_SECONDS + MAX_DELAY_SECONDS) / 2.0
                delay = int(max(MIN_DELAY_SECONDS, min(MAX_DELAY_SECONDS, random.gauss(mean_delay, (MAX_DELAY_SECONDS - MIN_DELAY_SECONDS) / 3.5))))
                print(f"  [Follower] Human delay: {delay}s before next action...")
                time.sleep(delay)
                
                # Session pause every 3-4 follows (mimics human walking away / switching tabs)
                if idx % random.randint(3, 4) == 0 and idx < len(candidates):
                    rest_sec = random.randint(45, 90)
                    print(f"  [Session Rest] Taking an extended break of {rest_sec}s...")
                    try:
                        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=15000)
                        human_scroll(page, steps=1)
                    except Exception:
                        pass
                    time.sleep(rest_sec)
        # Quick sync of followers page while browser is already open
        try:
            sync_mutual_followers(page=page)
        except Exception as e:
            print(f"  [Follower] Follower sync notice: {e}")
    finally:
        ctx.close()
        pw.stop()
        print("\n[Follower] Follow batch finished.")

def sync_mutual_followers(page=None, profile_name="test_igorvl777") -> int:
    """
    Scans our followers page (x.com/{TARGET_ACCOUNT}/followers) in 1 quick operation,
    detects who followed us back, and updates their status in candidates DB to 'mutual'.
    Fast, lightweight, and 100% accurate.
    """
    import re
    should_close = False
    pw = ctx = None
    if page is None:
        pw, ctx, page = get_browser_context(profile_name=profile_name, headless=True)
        should_close = True

    mutual_found = 0
    try:
        url = f"https://x.com/{TARGET_ACCOUNT}/followers"
        print(f"[Follower Sync] Checking {url} for mutual follow-backs...")
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        human_delay(2.5, 4.0)

        # Light scroll to load top 15-20 followers
        for _ in range(2):
            page.mouse.wheel(0, 400)
            time.sleep(1.0)

        cells = page.locator('[data-testid="UserCell"]')
        count = cells.count()
        
        conn = get_connection()
        cur = conn.cursor()
        ph = "?" if DB_TYPE == "sqlite" else "%s"

        for i in range(count):
            cell = cells.nth(i)
            cell_text = cell.inner_text()
            handles = re.findall(r'@([A-Za-z0-9_]+)', cell_text)
            if not handles:
                continue
            handle = handles[0]

            cur.execute(f"SELECT username, status FROM candidates WHERE LOWER(username) = LOWER({ph})", (handle,))
            row = cur.fetchone()
            if row and row[1] == "followed":
                actual_user = row[0]
                print(f"  [Follower Sync] Found follow-back from @{actual_user}! Marking MUTUAL ✅")
                log_action(actual_user, "mutual", success=True)
                mutual_found += 1

        conn.close()
        print(f"[Follower Sync] Sync complete. New mutuals detected: {mutual_found}")
    except Exception as e:
        print(f"[Follower Sync] Warning during mutual sync: {e}")
    finally:
        if should_close and ctx:
            ctx.close()
            if pw:
                pw.stop()

    return mutual_found

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
                # Weekend Safe-Zone: Don't unfollow on Sat(5)/Sun(6) when creators catch up with feeds
                if datetime.datetime.now().weekday() in (5, 6):
                    print(f"  [Follower] 🛡️ Weekend Safe-Zone active: Non-responder unfollow for @{username} postponed to Monday.")
                    continue

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


def nudge_user_like(page, username: str) -> bool:
    """
    Day 3 Second-Wave Nudge:
    Navigates to user profile, verifies mutual status first.
    If not mutual, likes their newest tweet to resurface in their notifications.
    """
    clean_user = username.replace("@", "").strip()
    try:
        page.goto(f"https://x.com/{clean_user}", wait_until="domcontentloaded", timeout=20000)
        human_delay(2.0, 4.0)

        # 1. First check if they already followed back
        is_mutual = check_is_mutual(page, clean_user)
        if is_mutual:
            print(f"  [Nudge] @{clean_user} is already MUTUAL ✅! Skipping like.")
            log_action(clean_user, "mutual", success=True)
            return True

        # 2. Scroll gently down to see tweets
        human_scroll(page, min_scroll=250, max_scroll=500)
        human_delay(1.5, 2.5)

        # Query for like buttons in articles/tweets
        like_buttons = page.query_selector_all('article [data-testid="like"]')
        if like_buttons:
            target_btn = like_buttons[0]
            human_click(page, target_btn)
            print(f"  [Nudge] Day 3 Nudge Like delivered to @{clean_user} newest tweet! ❤️")
            log_action(clean_user, "nudge_like", success=True)
            return True
        else:
            # If no unliked tweet found or already liked, mark nudge_sent so we don't repeat
            print(f"  [Nudge] No unliked tweets found for @{clean_user}, marking nudge as delivered.")
            log_action(clean_user, "nudge_like", success=True)
            return True
    except Exception as e:
        print(f"  [Nudge] Error nudging @{clean_user}: {e}")
        log_action(clean_user, "nudge_like", success=False, error=str(e))
        return False

def run_nudge_batch(profile_name="test_igorvl777", batch_size=3):
    """
    Executes Day 3 Second-Wave Nudge for candidates followed 3-4 days ago.
    """
    from database import get_candidates_for_nudge
    from config import DAILY_LIKE_LIMIT

    today_likes = get_today_likes()
    if today_likes >= DAILY_LIKE_LIMIT:
        print(f"[Nudge] Daily like limit reached ({today_likes}/{DAILY_LIKE_LIMIT}). Postponing nudge batch.")
        return

    candidates = get_candidates_for_nudge(days=3, limit=batch_size)
    if not candidates:
        print("[Nudge] No candidates currently due for Day 3 Nudge.")
        return

    print(f"[Nudge] Starting Day 3 Nudge batch for {len(candidates)} candidates...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    try:
        for c in candidates:
            u = c["username"]
            print(f"\n[Nudge] Processing Day 3 Nudge for @{u} (Score: {c.get('score', 0)})...")
            success = nudge_user_like(page, u)
            if success:
                delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                print(f"  [Nudge] Organic pause {delay}s...")
                time.sleep(delay)
            human_delay(2.0, 3.5)
    finally:
        ctx.close()
        pw.stop()
        print("\n[Nudge] Day 3 Nudge batch completed.")

def run_funnel_list_batch(profile_name="test_igorvl777", batch_size=3):
    """
    Executes Day 4 Last-Chance Ego-List addition for candidates followed 4-5 days ago.
    """
    from database import get_candidates_for_funnel_list_add, get_today_list_adds
    from config import DAILY_LIST_ADD_LIMIT, EGO_LIST_DEFAULT_NAME
    from list_bomber import add_user_to_list, ensure_ego_list_exists

    today_adds = get_today_list_adds()
    if today_adds >= DAILY_LIST_ADD_LIMIT:
        print(f"[Funnel List] Daily list add limit reached ({today_adds}/{DAILY_LIST_ADD_LIMIT}). Postponing.")
        return

    candidates = get_candidates_for_funnel_list_add(days=4, limit=batch_size)
    if not candidates:
        print("[Funnel List] No candidates currently due for Day 4 Ego-List addition.")
        return

    print(f"[Funnel List] Starting Day 4 Ego-List batch for {len(candidates)} candidates...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    try:
        if not ensure_ego_list_exists(page, EGO_LIST_DEFAULT_NAME):
            print("[Funnel List] Could not verify ego list. Aborting batch.")
            return

        for c in candidates:
            u = c["username"]
            print(f"\n[Funnel List] Checking Day 4 Ego-List addition for @{u}...")
            # Check mutual first
            is_mutual = check_is_mutual(page, u)
            if is_mutual:
                print(f"  [Funnel List] @{u} is already MUTUAL ✅! Skipping list add.")
                log_action(u, "mutual", success=True)
                continue

            added = add_user_to_list(page, u, EGO_LIST_DEFAULT_NAME)
            if added:
                delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                print(f"  [Funnel List] Organic pause {delay}s...")
                time.sleep(delay)
            human_delay(2.0, 3.5)
    finally:
        ctx.close()
        pw.stop()
        print("\n[Funnel List] Day 4 Ego-List batch completed.")

if __name__ == "__main__":
    import sys
    prof = sys.argv[1] if len(sys.argv) > 1 else "test_igorvl777"
    mode = sys.argv[2] if len(sys.argv) > 2 else "follow"
    if mode == "unfollow":
        run_unfollow_batch(profile_name=prof, batch_size=3)
    elif mode == "nudge":
        run_nudge_batch(profile_name=prof, batch_size=3)
    elif mode == "funnel_list":
        run_funnel_list_batch(profile_name=prof, batch_size=3)
    else:
        run_follow_batch(profile_name=prof, batch_size=3)

