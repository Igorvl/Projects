# -*- coding: utf-8 -*-
"""
Smart Follow & Unfollow execution engine.
Performs safe follows with randomized human pauses, respects daily limits,
tracks mutual follows, and manages unfollows for non-responders.
"""

import sys
import random
import time
import datetime
import re

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from browser import (
    get_browser_context,
    human_delay,
    human_click,
    human_scroll,
    human_idle_noise,
    handle_x_retry_button,
    wait_for_x_page_load,
    test_x_connectivity,
    wait_for_x_channel_recovery
)
from config import (
    DAILY_FOLLOW_LIMIT,
    DAILY_UNFOLLOW_LIMIT,
    DAILY_LIKE_LIMIT,
    LIKE_PROBABILITY,
    MIN_DELAY_SECONDS,
    MAX_DELAY_SECONDS,
    UNFOLLOW_AFTER_DAYS,
    UNFOLLOW_REGULAR_HOURS,
    UNFOLLOW_VERIFIED_HOURS,
    is_whitelisted_account,
    TARGET_ACCOUNT,
    TRI_TOUCH_ENABLED,
    TRI_TOUCH_MIN_SCORE,
    TRI_TOUCH_PAUSE_BETWEEN_LIKES,
    TRI_TOUCH_PAUSE_BEFORE_FOLLOW,
    MAX_HOURLY_MUTATIONS,
    get_current_ramp_up
)
from database import (
    get_connection,
    get_candidates_for_follow,
    log_action,
    update_candidate_status,
    touch_candidate_last_active,
    check_hourly_mutation_governor,
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

def execute_engagement_cascade(page, username: str, candidate_score: int = 0, is_hungry_talent: bool = False, is_verified: bool = False, is_mutuals_source: bool = False) -> int:
    """
    Executes Scheme 1: Differentiated Micro-Engagement Cascade.
    VIP candidates (Score >= TRI_TOUCH_MIN_SCORE [75] OR verified Blue Checkmark) receive
    a dense 2-like cascade (Fresh thought + Media/Portfolio) separated by organic Dwell Time.
    Standard candidates and mutuals-seeking authors receive a single warm-touch like.
    Strictly enforces DAILY_LIKE_LIMIT to safeguard account quotas.
    Returns: count of likes executed (0, 1, or 2).
    """
    likes_today = get_today_likes()
    _, stage_data, _ = get_current_ramp_up()
    daily_like_limit = stage_data["likes"]
    if likes_today >= daily_like_limit:
        print(f"  [Cascade] Daily like limit reached ({likes_today}/{daily_like_limit}). Preserving quota.")
        return 0

    likes_remaining = daily_like_limit - likes_today
    
    # Check if candidate qualifies for dense Tri-Touch cascade (2 likes)
    # VIP RULE: (Score >= 75 OR verified blue checkmark) AND NOT seeking mutuals (mutuals-seekers get 1 like)
    qualifies_for_cascade = (
        TRI_TOUCH_ENABLED and 
        (is_verified or candidate_score >= TRI_TOUCH_MIN_SCORE) and 
        not is_mutuals_source and
        likes_remaining >= 2
    )

    max_likes_target = 2 if qualifies_for_cascade else 1

    mode_label = "VIP Tri-Touch (2 likes + Dwell)" if qualifies_for_cascade else "Single-Touch (1 like + Follow)"
    verified_label = " 🔷[Verified]" if is_verified else ""
    print(f"  [Cascade] Mode: {mode_label} for @{username}{verified_label} (Score: {candidate_score}, Quota remaining: {likes_remaining})")

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
    is_verified = False
    is_mutuals_source = False
    if candidate_meta:
        candidate_score = candidate_meta.get("score", 0)
        is_verified = bool(candidate_meta.get("is_verified", 0))
        source = (candidate_meta.get("source") or "").lower()
        if any(term in source for term in ["mutual", "moot", "connect"]):
            is_mutuals_source = True
        breakdown = candidate_meta.get("score_breakdown", {})
        if isinstance(breakdown, str):
            import json
            try:
                breakdown = json.loads(breakdown)
            except Exception:
                breakdown = {}
        if isinstance(breakdown, dict):
            is_hungry_talent = breakdown.get("hungry_talent_bonus", False)
            if breakdown.get("blue_checkmark_bonus"):
                is_verified = True
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        wait_for_x_page_load(
            page, 
            ready_selector='button[data-testid$="-follow"], button[data-testid$="-unfollow"], button:has-text("Follow"), button:has-text("Following")',
            max_wait_sec=8.0,
            max_retries=2
        )
        handle_x_retry_button(page)
        human_delay(1.5, 3.0)

        # Live Blue Checkmark Hunter detection on profile
        try:
            badge = (
                page.query_selector('div[data-testid="UserName"] [data-testid="icon-verified"]') or
                page.query_selector('div[data-testid="UserName"] svg[data-testid="icon-verified"]') or
                page.query_selector('a[href$="/verified_followers" i]')
            )
            if badge and not is_verified:
                is_verified = True
                from database import update_candidate_verified
                update_candidate_verified(clean_user, True)
                print(f"  [Follower] 🔷 Detected live Blue Checkmark for @{clean_user}! Upgraded to VIP.")
        except Exception:
            pass

        # Wait up to 5s for follow/unfollow buttons to mount in DOM
        try:
            page.wait_for_selector(
                'button[data-testid$="-follow"], button[data-testid$="-unfollow"], '
                'button:has-text("Follow"), button:has-text("Following"), '
                'button:has-text("Читать"), button:has-text("Читаю"), button:has-text("Подписаться")',
                timeout=5000
            )
        except Exception:
            pass

        # Check if already following
        unfollow_btn = (
            page.query_selector('button[data-testid$="-unfollow"]') or 
            page.query_selector('button:has-text("Following")') or
            page.query_selector('button:has-text("Читаю")')
        )
        if unfollow_btn:
            print(f"  [Follower] Already following @{clean_user}, skipping.")
            log_action(clean_user, "follow", success=True, error="already_following")
            return False
            
        follow_btn = (
            page.query_selector('button[data-testid$="-follow"]') or 
            page.query_selector('button:has-text("Follow")') or
            page.query_selector('button:has-text("Читать")') or
            page.query_selector('button:has-text("Подписаться")')
        )
        if not follow_btn:
            # Diagnostic check: suspended, protected, or temporary glitch
            body_text = page.inner_text("body") if page else ""
            if "Account suspended" in body_text or "Учетная запись приостановлена" in body_text:
                print(f"  [Follower] ⚠️ Account @{clean_user} is suspended by X. Marking ignored.")
                log_action(clean_user, "follow", success=False, error="account_suspended")
            elif "These posts are protected" in body_text or "Этот аккаунт защищен" in body_text:
                print(f"  [Follower] ℹ️ Account @{clean_user} is private/protected. Skipping.")
                log_action(clean_user, "follow", success=False, error="account_protected")
            elif "Try again" in body_text or "Something went wrong" in body_text:
                print(f"  [Follower] ⚠️ Temporary X server glitch ('Try again') for @{clean_user}.")
                log_action(clean_user, "follow", success=False, error="x_glitch_try_again")
            else:
                print(f"  [Follower] Follow button not found for @{clean_user}")
                log_action(clean_user, "follow", success=False, error="button_not_found")
            return False

        # 1. Execute Engagement Cascade (VIP Tri-Touch: 2 likes or Single-Touch: 1 like)
        likes_placed = execute_engagement_cascade(
            page, 
            clean_user, 
            candidate_score=candidate_score, 
            is_hungry_talent=is_hungry_talent,
            is_verified=is_verified,
            is_mutuals_source=is_mutuals_source
        )
        
        # СТРОГОЕ ПРАВИЛО: Подписываться на кандидатов без лайков бессмысленно (теряется конверсия)!
        # Если лимит лайков исчерпан или каскад не смог поставить лайк — ПОДПИСКА ОТМЕНЯЕТСЯ!
        likes_today = get_today_likes()
        _, stage_data, _ = get_current_ramp_up()
        daily_like_limit = stage_data["likes"]

        if likes_today >= daily_like_limit:
            print(f"  [Follower] 🛑 Daily like limit reached ({likes_today}/{daily_like_limit}). Dry follow prohibited for @{clean_user}! Preserving candidate.")
            log_action(clean_user, "follow", success=False, error="like_limit_reached")
            return False

        if likes_placed == 0:
            print(f"  [Follower] ⚠️ 0 likes placed for @{clean_user} (no eligible tweets/media). Skipping follow to preserve conversion quality.")
            log_action(clean_user, "follow", success=False, error="no_likes_placed")
            return False
        
        # 2. Scroll back to top if needed and locate Follow button
        follow_btn = (
            page.query_selector('button[data-testid$="-follow"]') or 
            page.query_selector('button:has-text("Follow")') or
            page.query_selector('button:has-text("Читать")') or
            page.query_selector('button:has-text("Подписаться")')
        )
        if not follow_btn:
            page.evaluate("window.scrollTo(0, 0)")
            human_delay(1.2, 2.0)
            follow_btn = (
                page.query_selector('button[data-testid$="-follow"]') or 
                page.query_selector('button:has-text("Follow")') or
                page.query_selector('button:has-text("Читать")') or
                page.query_selector('button:has-text("Подписаться")')
            )

        if follow_btn:
            # Human smooth click with Bezier trajectory
            clicked = human_click(page, follow_btn)
            if clicked:
                mode_tag = "VIP Tri-Touch, 2 likes" if likes_placed >= 2 else f"Single-Touch, {likes_placed} like"
                verified_tag = " 🔷[Verified]" if is_verified else ""
                print(f"  [Follower] 🎯 Successfully followed @{clean_user}{verified_tag}! ({mode_tag})")
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

def check_is_mutual(page, username: str):
    """
    Checks if user follows us back on their profile page.
    Returns:
      True  -> Verified mutual ('Follows you' / 'Читает вас')
      False -> Verified NOT mutual (profile page loaded successfully)
      None  -> Network / connection / channel failure (profile failed to load).
               DO NOT treat as non-mutual! DO NOT penalize!
    """
    clean_user = username.replace("@", "").strip()
    profile_url = f"https://x.com/{clean_user}"
    
    max_nav_attempts = 2
    for attempt in range(1, max_nav_attempts + 1):
        try:
            page.goto(profile_url, wait_until="domcontentloaded", timeout=25000)
            wait_for_x_page_load(
                page, 
                ready_selector='div[data-testid="UserName"], div[data-testid="primaryColumn"], main[role="main"]',
                max_wait_sec=8.0, 
                max_retries=2
            )
            handle_x_retry_button(page)
            human_delay(1.0, 2.0)

            page_text = ""
            try:
                page_text = page.inner_text("body")
            except Exception:
                pass

            is_net_error = any(err in page_text for err in [
                "ERR_CONNECTION", "ERR_TIMED_OUT", "ERR_NAME_NOT_RESOLVED", 
                "can't be reached", "Не удается получить доступ", "No internet",
                "DNS_PROBE", "Connection reset", "Connection refused"
            ])

            if len(page_text) < 50 or is_net_error or "Try again" in page_text or "Something went wrong" in page_text:
                if handle_x_retry_button(page):
                    human_delay(2.0, 3.5)
                    try:
                        page_text = page.inner_text("body")
                    except Exception:
                        pass

                if len(page_text) < 50 or is_net_error or "Try again" in page_text or "Something went wrong" in page_text:
                    print(f"  [Follower] ⚠️ Channel to X unstable during navigation to @{clean_user} (attempt {attempt}/{max_nav_attempts}).")
                    channel_ok = wait_for_x_channel_recovery(page, max_standby_min=10, check_interval_sec=15)
                    if not channel_ok:
                        return None
                    continue

            # Profile loaded successfully! Check mutual indicator
            is_mutual = False
            indicator = page.locator('[data-testid="userFollowIndicator"]')
            if indicator.count() > 0 and indicator.first.is_visible():
                is_mutual = True
            elif "Follows you" in page_text or "Читает вас" in page_text:
                is_mutual = True

            # Accurate Blue Checkmark verification & automatic DB sync
            try:
                is_verified = False
                user_name_block = page.query_selector('div[data-testid="UserName"]')
                if user_name_block:
                    verified_badge = (
                        user_name_block.query_selector('[data-testid="icon-verified"]') or
                        user_name_block.query_selector('svg[data-testid="icon-verified"]') or
                        user_name_block.query_selector('svg[aria-label*="Verified" i]') or
                        user_name_block.query_selector('svg[aria-label*="Подтвержден" i]')
                    )
                    if verified_badge:
                        is_verified = True
                from database import update_candidate_verified
                update_candidate_verified(clean_user, is_verified)
            except Exception:
                pass

            return is_mutual

        except Exception as e:
            print(f"  [Follower] ⚠️ Navigation error for @{clean_user}: {e}")
            channel_ok = wait_for_x_channel_recovery(page, max_standby_min=10, check_interval_sec=15)
            if not channel_ok:
                return None

    return None

def unfollow_user_on_current_page(page, clean_user: str):
    """
    Executes unfollow on the already-loaded profile page:
    - Verifies account status (suspended/missing/blocked)
    - Locates the Following/Читаю button strictly inside the main profile column
    - Returns True on successful unfollow or already-not-following / suspended
    - Returns None if channel/network lag prevented verifying the button (NO PENALTY!)
    - Returns False only on real logic failure
    """
    if is_whitelisted_account(clean_user):
        print(f"  [Follower] 🛡️ Account @{clean_user} is in WHITELIST (свои). Unfollow strictly forbidden!")
        log_action(clean_user, "whitelist_protect", success=True)
        return True

    gov = check_hourly_mutation_governor(limit=MAX_HOURLY_MUTATIONS, target_safe=28)
    if gov.get("triggered", False):
        print(f"  [Follower] 🛑 Rolling 1-hour mutation limit reached ({gov['mutations']}/{MAX_HOURLY_MUTATIONS}). Halting unfollow for @{clean_user}.")
        return False

    try:
        page_text = ""
        try:
            page_text = page.inner_text("body")
        except Exception:
            pass

        # 1. Account status
        if any(msg in page_text for msg in [
            "Account suspended", "Учетная запись заблокирована", "Учетная запись приостановлена",
            "This account doesn’t exist", "Такой учетной записи нет",
            "You’re blocked", "Вы заблокированы"
        ]):
            print(f"  [Follower] Account @{clean_user} is suspended, blocked or doesn't exist. Marking unfollowed.")
            log_action(clean_user, "unfollow", success=True, error="account_unavailable")
            return True

        # Check for network error page or blank body
        is_net_error = any(err in page_text for err in [
            "ERR_CONNECTION", "ERR_TIMED_OUT", "ERR_NAME_NOT_RESOLVED", 
            "can't be reached", "Не удается получить доступ", "No internet",
            "DNS_PROBE", "Connection reset", "Connection refused"
        ])
        if len(page_text) < 50 or is_net_error or "Try again" in page_text or "Something went wrong" in page_text:
            if handle_x_retry_button(page):
                human_delay(2.5, 4.0)
                try:
                    page_text = page.inner_text("body")
                except Exception:
                    pass
            if len(page_text) < 50 or is_net_error or "Try again" in page_text or "Something went wrong" in page_text:
                print(f"  [Follower] ⚠️ Network / server glitch for @{clean_user}. Triggering channel recovery (NO PENALTY).")
                wait_for_x_channel_recovery(page, max_standby_min=10, check_interval_sec=15)
                return None

        # 2. Check profile header mounting
        col = page.locator('div[data-testid="primaryColumn"], main[role="main"]')
        target_scope = col.first if col.count() > 0 else page

        user_name_loc = target_scope.locator('div[data-testid="UserName"]')
        if user_name_loc.count() == 0 or not user_name_loc.first.is_visible():
            try:
                user_name_loc.first.wait_for(state="visible", timeout=6000)
            except Exception:
                print(f"  [Follower] ⚠️ Profile header not rendered for @{clean_user} (network/hydration lag). Skipping without penalty.")
                return None

        # 3. Locate Following / Читаю / Подписан button
        unfollow_btn = None
        btn_loc = target_scope.locator('button[data-testid$="-unfollow"]')
        if btn_loc.count() > 0 and btn_loc.first.is_visible():
            unfollow_btn = btn_loc.first
        else:
            aria_loc = target_scope.locator('button[aria-label*="Following" i], button[aria-label*="Читаю" i]')
            if aria_loc.count() > 0 and aria_loc.first.is_visible():
                unfollow_btn = aria_loc.first
            else:
                for txt in ["Following", "Читаю", "Подписан"]:
                    btn_txt = target_scope.get_by_role("button", name=re.compile(rf"^{txt}", re.I))
                    if btn_txt.count() > 0 and btn_txt.first.is_visible():
                        unfollow_btn = btn_txt.first
                        break

        if not unfollow_btn:
            try:
                page.evaluate("window.scrollTo(0, 0)")
                human_delay(0.5, 1.0)
                btn_loc = target_scope.locator('button[data-testid$="-unfollow"]')
                if btn_loc.count() > 0 and btn_loc.first.is_visible():
                    unfollow_btn = btn_loc.first
                else:
                    aria_loc = target_scope.locator('button[aria-label*="Following" i], button[aria-label*="Читаю" i]')
                    if aria_loc.count() > 0 and aria_loc.first.is_visible():
                        unfollow_btn = aria_loc.first
                    else:
                        for txt in ["Following", "Читаю", "Подписан"]:
                            btn_txt = target_scope.get_by_role("button", name=re.compile(rf"^{txt}", re.I))
                            if btn_txt.count() > 0 and btn_txt.first.is_visible():
                                unfollow_btn = btn_txt.first
                                break
            except Exception:
                pass

        if unfollow_btn:
            human_click(page, unfollow_btn)
            human_delay(0.8, 1.8)

            try:
                page.wait_for_selector(
                    'button[data-testid="confirmationSheetConfirm"], '
                    'div[data-testid="confirmationSheetDialog"] button, '
                    'div[role="dialog"] button:has-text("Unfollow"), '
                    'div[role="dialog"] button:has-text("Отписаться"), '
                    'div[role="dialog"] button:has-text("Отменить подписку")',
                    timeout=4500
                )
            except Exception:
                pass

            confirm_btn = (
                page.query_selector('button[data-testid="confirmationSheetConfirm"]') or
                page.query_selector('div[data-testid="confirmationSheetDialog"] button:not([data-testid="confirmationSheetCancel"])') or
                page.query_selector('div[role="dialog"] button:has-text("Unfollow")') or
                page.query_selector('div[role="dialog"] button:has-text("Отписаться")') or
                page.query_selector('div[role="dialog"] button:has-text("Отменить подписку")') or
                page.query_selector('div[role="dialog"] button:has-text("Отменить читаемое")')
            )
            if confirm_btn:
                human_click(page, confirm_btn)
                human_delay(1.0, 2.0)

            print(f"  [Follower] 🎯 Successfully unfollowed @{clean_user} (organic click)")
            try:
                log_action(clean_user, "unfollow", success=True)
            except Exception as db_err:
                print(f"  [Follower] ⚠️ DB log error for @{clean_user}: {db_err}")
            return True

        # 4. Check if already not following (exact Follow button in profile header)
        follow_loc = target_scope.locator('button[data-testid$="-follow"]:not([data-testid$="-unfollow"])')
        already_not_following = False
        if follow_loc.count() > 0 and follow_loc.first.is_visible():
            already_not_following = True
        else:
            aria_follow = target_scope.locator('button[aria-label*="Follow @" i], button[aria-label*="Читать @" i]')
            if aria_follow.count() > 0 and aria_follow.first.is_visible():
                already_not_following = True
            else:
                for txt in ["Follow", "Читать", "Подписаться"]:
                    btn_f = target_scope.get_by_role("button", name=re.compile(rf"^{txt}\b", re.I))
                    if btn_f.count() > 0 and btn_f.first.is_visible():
                        already_not_following = True
                        break

        if already_not_following:
            print(f"  [Follower] Verified: already not following @{clean_user} in profile header. Marking as unfollowed.")
            try:
                log_action(clean_user, "unfollow", success=True, error="already_not_following")
            except Exception as db_err:
                print(f"  [Follower] ⚠️ DB log error for @{clean_user}: {db_err}")
            return True

        # If header rendered but buttons not ready yet -> lag, do not penalize!
        print(f"  [Follower] ⚠️ Action buttons not visible for @{clean_user} (DOM lag). Skipping without penalty.")
        return None

    except Exception as e:
        print(f"  [Follower] ⚠️ Error unfollowing @{clean_user}: {e}. Skipping without penalty.")
        return None

def unfollow_user(page, username: str) -> bool:
    """Navigates to user profile and unfollows with human curve clicks."""
    clean_user = username.replace("@", "").strip()
    try:
        page.goto(f"https://x.com/{clean_user}", wait_until="domcontentloaded", timeout=20000)
        wait_for_x_page_load(page, ready_selector='div[data-testid="UserName"], button[data-testid$="-unfollow"], button[data-testid$="-follow"], button:has-text("Following"), button:has-text("Читаю"), button:has-text("Follow")', max_wait_sec=8.0, max_retries=2)
        handle_x_retry_button(page)
        human_delay(1.5, 3.0)
        return unfollow_user_on_current_page(page, clean_user)
    except Exception as e:
        print(f"  [Follower] Navigation error for @{clean_user}: {e}")
        log_action(clean_user, "unfollow", success=False, error=str(e))
        return False

def get_candidates_for_unfollow(
    regular_hours: int = UNFOLLOW_REGULAR_HOURS,
    verified_hours: int = UNFOLLOW_VERIFIED_HOURS,
    days: int = None,
    limit: int = 20
) -> list:
    """
    Returns users we followed who still haven't followed back:
    - Regular authors: older than regular_hours (48h)
    - Verified authors (Blue badge): older than verified_hours (30h)
    Prioritizes fresh candidates (0 failed attempts) and oldest follow dates first (followed_at ASC).
    Excludes candidates with 3+ failed unfollow attempts.
    """
    if days is not None:
        regular_hours = days * 24
        verified_hours = min(30, regular_hours)
    conn = get_connection()
    cur = conn.cursor()
    ph = "?" if DB_TYPE == "sqlite" else "%s"
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff_reg = (now - datetime.timedelta(hours=regular_hours)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_ver = (now - datetime.timedelta(hours=verified_hours)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(f"""
        SELECT username FROM candidates
        WHERE status = 'followed' 
          AND COALESCE(unfollow_attempts, 0) < 3
          AND (
              (COALESCE(is_verified, 0) = 1 AND COALESCE(followed_at, updated_at) <= {ph})
              OR
              (COALESCE(is_verified, 0) = 0 AND COALESCE(followed_at, updated_at) <= {ph})
          )
        ORDER BY COALESCE(unfollow_attempts, 0) ASC, COALESCE(followed_at, updated_at) ASC
        LIMIT {ph}
    """, (cutoff_ver, cutoff_reg, limit))
    rows = [r[0] for r in cur.fetchall() if not is_whitelisted_account(r[0])]
    conn.close()
    return rows

def run_follow_batch(profile_name="test_igorvl777", batch_size=5):
    """
    Executes a small batch of follows safely within limits with log-normal delays
    and natural rest breaks. Strictly enforces like quota: NO follows without likes!
    """
    follows_today, _ = get_today_counts()
    likes_today = get_today_likes()
    _, stage_data, _ = get_current_ramp_up()
    daily_follow_limit = stage_data["follows"]
    daily_like_limit = stage_data["likes"]

    if follows_today >= daily_follow_limit:
        print(f"[Follower] Daily follow limit reached ({follows_today}/{daily_follow_limit}). Halting.")
        return

    # СТРОГОЕ ПРАВИЛО: Без лайков подписываться бессмысленно (нет Tri-Touch Cascade)
    if likes_today >= daily_like_limit:
        print(f"[Follower] 🛑 Daily like limit reached ({likes_today}/{daily_like_limit}). Tri-Touch Cascade impossible without likes. Halting follow batch for today!")
        return

    likes_remaining = daily_like_limit - likes_today
    if likes_remaining < 2:
        print(f"[Follower] 🛑 Only {likes_remaining} like(s) remaining today (need at least 2 for Tri-Touch). Halting follow batch!")
        return
        
    # Рассчитываем, сколько подписок мы реально можем обеспечить каскадом лайков
    max_possible_by_likes = likes_remaining // 2
    allowed_count = min(batch_size, daily_follow_limit - follows_today, max_possible_by_likes)
    if allowed_count <= 0:
        print(f"[Follower] 🛑 Like quota insufficient for batch ({likes_today}/{daily_like_limit}). Halting.")
        return

    candidates = get_candidates_for_follow(limit=allowed_count)
    
    if not candidates:
        print("[Follower] No candidates in queue with qualifying score.")
        return
        
    print(f"[Follower] Starting safe follow batch for {len(candidates)} candidates (Likes left: {likes_remaining})...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    
    try:
        for idx, c in enumerate(candidates, 1):
            if get_today_likes() >= daily_like_limit:
                print(f"[Follower] 🛑 Daily like limit reached during batch. Stopping immediately.")
                break

            # Проверка жесткого часового лимита мутаций (>= 40)
            gov = check_hourly_mutation_governor(limit=MAX_HOURLY_MUTATIONS, target_safe=28)
            if gov["triggered"]:
                print(f"[Follower] 🛑 Rolling 1-hour mutation limit reached ({gov['mutations']}/{MAX_HOURLY_MUTATIONS}). Pausing follow batch.")
                break

            u = c["username"]
            print(f"\n[Follower] Processing candidate @{u} (Score: {c['score']}, Ratio: {c['ratio']})...")
            success = follow_user(page, u, candidate_meta=c)
            
            if success:
                # Algorithm 5b: Opportunistic Live Thread Scouting on Follow (для 100% зафолловленных)
                try:
                    from scraper import scout_thread_commenters_on_follow
                    scout_thread_commenters_on_follow(page, u, max_leads=7)
                except Exception:
                    pass

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
    finally:
        ctx.close()
        pw.stop()
        print("\n[Follower] Follow batch finished.")

def sync_target_profile_stats(page=None, profile_name="test_igorvl777", account=None) -> dict:
    """
    Directly navigates to x.com/{account}, extracts live followers and following counts,
    and updates the database. Fast, robust, and headless-friendly.
    """
    import re
    from scraper import parse_stat_number

    if not account:
        account = TARGET_ACCOUNT

    should_close = False
    pw = ctx = None
    if page is None:
        pw, ctx, page = get_browser_context(profile_name=profile_name, headless=True)
        should_close = True

    res = {
        "success": False,
        "account": account,
        "followers_count": 0,
        "following_count": 0
    }

    try:
        url = f"https://x.com/{account}"
        print(f"[Profile Sync] Fetching live stats for @{account} from {url}...")
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        wait_for_x_page_load(page, ready_selector='a[href*="/followers" i]', max_wait_sec=8.0, max_retries=2)
        handle_x_retry_button(page)

        # 1. Following count
        following_link = (
            page.query_selector(f'a[href="/{account}/following" i]') or
            page.query_selector('a[href$="/following" i]') or
            page.query_selector('a[href*="/following" i]')
        )
        following_text = following_link.inner_text() if following_link else ""

        # 2. Followers count
        followers_link = (
            page.query_selector(f'a[href="/{account}/verified_followers" i]') or
            page.query_selector(f'a[href="/{account}/followers" i]') or
            page.query_selector('a[href$="/verified_followers" i]') or
            page.query_selector('a[href$="/followers" i]') or
            page.query_selector('a[href*="/followers" i]')
        )
        followers_text = followers_link.inner_text() if followers_link else ""

        following_cnt = parse_stat_number(following_text)
        followers_cnt = parse_stat_number(followers_text)

        if following_cnt > 0 or followers_cnt > 0:
            res["followers_count"] = followers_cnt
            res["following_count"] = following_cnt
            res["success"] = True

            conn = get_connection()
            cur = conn.cursor()
            ph = "?" if DB_TYPE == "sqlite" else "%s"

            cur.execute(f"SELECT id FROM candidates WHERE LOWER(username) = LOWER({ph})", (account,))
            existing = cur.fetchone()
            if existing:
                cur.execute(f"""
                    UPDATE candidates 
                    SET followers_count = {ph}, following_count = {ph}, updated_at = CURRENT_TIMESTAMP 
                    WHERE LOWER(username) = LOWER({ph})
                """, (followers_cnt, following_cnt, account))
            else:
                cur.execute(f"""
                    INSERT INTO candidates (username, name, followers_count, following_count, status)
                    VALUES ({ph}, {ph}, {ph}, {ph}, 'target_profile')
                """, (account, account, followers_cnt, following_cnt))

            conn.commit()
            conn.close()
            print(f"[Profile Sync] Successfully updated @{account}: {followers_cnt} followers, {following_cnt} following [OK]")
    except Exception as e:
        print(f"[Profile Sync] Error updating stats for @{account}: {e}")
        res["error"] = str(e)
    finally:
        if should_close and ctx:
            ctx.close()
            if pw:
                pw.stop()

    return res

def sync_mutual_followers(page=None, profile_name="test_igorvl777") -> int:
    """
    Scans our followers page (x.com/{TARGET_ACCOUNT}/followers),
    dynamically scrolling to capture all current followers,
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
        # Also sync target profile stats
        try:
            sync_target_profile_stats(page=page, account=TARGET_ACCOUNT)
        except Exception as se:
            print(f"[Follower Sync] Profile stats sub-sync notice: {se}")

        url = f"https://x.com/{TARGET_ACCOUNT}/followers"
        print(f"[Follower Sync] Checking {url} for mutual follow-backs...")
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        wait_for_x_page_load(page, ready_selector='[data-testid="UserCell"]', max_wait_sec=8.0, max_retries=2)
        handle_x_retry_button(page)
        human_delay(1.5, 3.0)

        # Dynamic scroll to load all followers (up to 12 scrolls or until list stops growing)
        all_handles = set()
        last_count = 0
        consecutive_same = 0

        for _ in range(12):
            cells = page.locator('[data-testid="UserCell"]')
            count = cells.count()
            for i in range(count):
                try:
                    cell_text = cells.nth(i).inner_text()
                    handles = re.findall(r'@([A-Za-z0-9_]+)', cell_text)
                    if handles:
                        all_handles.add(handles[0].lower())
                except Exception:
                    pass

            if len(all_handles) == last_count and len(all_handles) > 0:
                consecutive_same += 1
                if consecutive_same >= 2:
                    break
            else:
                consecutive_same = 0

            last_count = len(all_handles)
            page.mouse.wheel(0, 700)
            time.sleep(1.2)

        print(f"[Follower Sync] Scanned {len(all_handles)} unique followers on X.")
        
        conn = get_connection()
        cur = conn.cursor()
        ph = "?" if DB_TYPE == "sqlite" else "%s"

        # 1. Update any 'followed' candidate who is in all_handles -> 'mutual'
        for handle in all_handles:
            cur.execute(f"SELECT username, status FROM candidates WHERE LOWER(username) = LOWER({ph})", (handle,))
            row = cur.fetchone()
            if row and row[1] == "followed":
                actual_user = row[0]
                print(f"  [Follower Sync] Found follow-back from @{actual_user}! Marking MUTUAL [OK]")
                log_action(actual_user, "mutual", success=True)
                mutual_found += 1

        # Clean up stale test mutuals from old test accounts (where followed_at was NULL and user is not in all_handles)
        if len(all_handles) >= 400:
            cur.execute(f"SELECT username FROM candidates WHERE status = 'mutual' AND followed_at IS NULL")
            stale_rows = cur.fetchall()
            for s_row in stale_rows:
                u_name = s_row[0]
                if u_name.lower() not in all_handles and not is_whitelisted_account(u_name):
                    print(f"  [Follower Sync] Reclassifying legacy test profile @{u_name} from previous test account to ignored.")
                    cur.execute(f"UPDATE candidates SET status = 'ignored', updated_at = CURRENT_TIMESTAMP WHERE LOWER(username) = LOWER({ph})", (u_name,))
            conn.commit()

        conn.close()
        print(f"[Follower Sync] Sync complete. Newly promoted mutuals: {mutual_found}")
    except Exception as e:
        print(f"[Follower Sync] Warning during mutual sync: {e}")
    finally:
        if should_close and ctx:
            ctx.close()
            if pw:
                pw.stop()

    return mutual_found


def hunt_and_retaliate_silent_unfollowers(page=None, profile_name="test_igorvl777", max_checks=6) -> int:
    """
    Step 0 of Orchestrator Cycle:
    Checks for users who quietly unfollowed us ("отписались втихую").
    1. Updates our account profile stats (followers, following) and compares against prior DB stats.
    2. Scans recent followers to catch mutual candidates who vanished from the top.
    3. Directly visits profile to verify reciprocity ('Follows you' badge missing) with zero false positives.
    4. Immediately executes retaliatory unfollow on confirmed traitors on the spot!
    5. Updates DB status to 'unfollowed_me' and logs retaliatory unfollow.
    """
    import re
    should_close = False
    pw = ctx = None
    if page is None:
        pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
        should_close = True

    retaliations = 0
    try:
        from database import get_account_stats
        prev_followers, prev_following = get_account_stats(TARGET_ACCOUNT)
        
        # 1. Update target profile stats
        curr_stats = sync_target_profile_stats(page=page, account=TARGET_ACCOUNT)
        raw_followers = curr_stats.get("followers_count", 0)

        # Guard: If page failed to load or follower count parsed as 0 while we previously had followers, ignore glitch!
        if not curr_stats.get("success") or (raw_followers == 0 and prev_followers > 10):
            print(f"[Silent Hunter] ⚠️ Target profile stats parsing lagged/failed (got {raw_followers}). Preserving prior count ({prev_followers}).")
            curr_followers = prev_followers
        else:
            curr_followers = raw_followers

        churn_detected = max(0, prev_followers - curr_followers) if prev_followers > 0 else 0
        if churn_detected > 0:
            session_max_checks = min(max_checks * 2, churn_detected + 4, 25)
            print(f"\n[Silent Hunter] 🚨 CHURN DETECTED: Followers dropped from {prev_followers} to {curr_followers} (-{churn_detected})!")
            print(f"[Silent Hunter] Initiating emergency silent-unfollower audit ({session_max_checks} checks)...")
        else:
            session_max_checks = max_checks
            print(f"\n[Silent Hunter] 🛡️ Continuous Reciprocity Patrol (Target: {session_max_checks} oldest mutuals, Followers: {curr_followers})...")

        # 2. Quick scan top recent followers (6-8 scrolls = ~120-160 users)
        url = f"https://x.com/{TARGET_ACCOUNT}/followers"
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        wait_for_x_page_load(page, ready_selector='[data-testid="UserCell"]', max_wait_sec=8.0, max_retries=2)
        handle_x_retry_button(page)
        human_delay(1.5, 2.5)

        recent_followers = set()
        for _ in range(8):
            cells = page.locator('[data-testid="UserCell"]')
            count = cells.count()
            for i in range(count):
                try:
                    cell_text = cells.nth(i).inner_text()
                    handles = re.findall(r'@([A-Za-z0-9_]+)', cell_text)
                    if handles:
                        recent_followers.add(handles[0].lower())
                except Exception:
                    pass
            page.mouse.wheel(0, 800)
            time.sleep(0.8)

        print(f"[Silent Hunter] Scanned {len(recent_followers)} top recent followers on X.")

        # 3. Form suspect pool from DB
        conn = get_connection()
        cur = conn.cursor()
        ph = "?" if DB_TYPE == "sqlite" else "%s"

        # A. Detect fresh follow-backs among top followers
        fresh_mutuals = []
        for h in recent_followers:
            cur.execute(f"SELECT username, status FROM candidates WHERE LOWER(username) = LOWER({ph})", (h,))
            r = cur.fetchone()
            if r and r[1] == "followed":
                fresh_mutuals.append(r[0])

        # B. Get recent mutuals (followed back recently, e.g. in last 14 days)
        cur.execute(f"""
            SELECT username, name, updated_at, followed_at 
            FROM candidates 
            WHERE status = 'mutual'
            ORDER BY updated_at DESC 
            LIMIT 50
        """)
        recent_mutuals = cur.fetchall()

        suspects = []
        for m in recent_mutuals:
            u = m[0]
            if is_whitelisted_account(u, m[1] or ""):
                continue
            if u.lower() not in recent_followers:
                suspects.append(u)

        # C. If suspects list is small, add oldest checked mutuals to ensure continuous rotation
        if len(suspects) < session_max_checks:
            cur.execute(f"""
                SELECT username, name FROM candidates 
                WHERE status = 'mutual'
                ORDER BY COALESCE(last_active, '2000-01-01') ASC, updated_at ASC
                LIMIT {ph}
            """, (session_max_checks - len(suspects),))
            for om in cur.fetchall():
                ou = om[0]
                if not is_whitelisted_account(ou, om[1] or "") and ou not in suspects:
                    suspects.append(ou)

        conn.close()

        # Safely log fresh follow-backs without holding an outer uncommitted transaction
        for fm in fresh_mutuals:
            print(f"  [Silent Hunter] Detected fresh follow-back from @{fm} -> marked MUTUAL ✅")
            log_action(fm, "mutual", success=True)

        print(f"[Silent Hunter] Identified {len(suspects)} suspect(s) for reciprocity verification.")

        # 4. In-flight verification & immediate retaliatory unfollow
        _, stage_data, _ = get_current_ramp_up()
        daily_unfollow_limit = stage_data["unfollows"]

        for u in suspects[:session_max_checks]:
            gov = check_hourly_mutation_governor(limit=MAX_HOURLY_MUTATIONS, target_safe=28)
            if gov.get("triggered", False):
                print(f"[Silent Hunter] 🛑 Rolling 1-hour mutation limit reached ({gov['mutations']}/{MAX_HOURLY_MUTATIONS}). Halting audit.")
                break

            _, unfollows_today = get_today_counts()
            if unfollows_today >= daily_unfollow_limit:
                print(f"[Silent Hunter] Daily unfollow limit reached ({unfollows_today}/{daily_unfollow_limit}). Halting audit.")
                break

            clean_user = u.replace("@", "").strip()
            print(f"\n[Silent Hunter] Investigating suspected traitor @{clean_user}...")

            is_mutual = check_is_mutual(page, clean_user)
            if is_mutual is None:
                print(f"  [Silent Hunter] ⚠️ Connection lag inspecting @{clean_user}. Skipping without penalty.")
                continue

            if is_mutual is False:
                # CONFIRMED SILENT UNFOLLOWER!
                print(f"  ⚔️ [Silent Hunter] BUSTED! @{clean_user} was MUTUAL but silently UNFOLLOWED us!")
                print(f"  ⚡ Executing immediate retaliatory unfollow...")
                ok = unfollow_user_on_current_page(page, clean_user)
                if ok:
                    update_candidate_status(clean_user, "unfollowed_me")
                    retaliations += 1
                    print(f"  🎯 Retaliatory unfollow completed for @{clean_user} (status -> 'unfollowed_me').")
                human_delay(2.0, 3.5)
            else:
                # Loyal mutual! Just not at the top of the scroll
                print(f"  ✅ Verified: @{clean_user} is still a loyal MUTUAL. Updating last_active.")
                touch_candidate_last_active(clean_user)
                human_delay(1.0, 2.0)

        print(f"\n[Silent Hunter] Audit finished. Retaliatory unfollows executed: {retaliations}")

    except Exception as e:
        print(f"[Silent Hunter] Warning during audit: {e}")
    finally:
        if should_close and ctx:
            ctx.close()
            if pw:
                pw.stop()

    return retaliations


def run_unfollow_batch(profile_name="test_igorvl777", batch_size=10):
    """
    Checks candidates followed N+ days ago, verifies mutual status,
    unfollows non-responders, marks mutuals.
    Uses single-page DOM inspection to avoid double page loads.
    """
    _, unfollows_today = get_today_counts()
    _, stage_data, _ = get_current_ramp_up()
    daily_unfollow_limit = stage_data["unfollows"]
    if unfollows_today >= daily_unfollow_limit:
        print(f"[Follower] Daily unfollow limit reached ({unfollows_today}/{daily_unfollow_limit}). Halting.")
        return

    candidates = get_candidates_for_unfollow(
        regular_hours=UNFOLLOW_REGULAR_HOURS,
        verified_hours=UNFOLLOW_VERIFIED_HOURS,
        limit=batch_size
    )
    if not candidates:
        print("[Follower] No candidates pending unfollow check.")
        return

    print(f"[Follower] Starting unfollow check for {len(candidates)} candidates (Today: {unfollows_today}/{daily_unfollow_limit})...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)

    try:
        for username in candidates:
            clean_user = username.replace("@", "").strip()
            if is_whitelisted_account(clean_user):
                print(f"\n[Follower] 🛡️ Account @{clean_user} is in WHITELIST (свои). Skipping unfollow.")
                continue

            print(f"\n[Follower] Inspecting @{clean_user} for reciprocity / unfollow...")

            # 1. Заходим на профиль и проверяем взаимность (один переход вместо двух!)
            is_mutual = check_is_mutual(page, clean_user)

            if is_mutual is None:
                # Сетевой сбой канала связи с X — ждем восстановления канала и повторяем
                print(f"  [Follower] 📡 Connection to X dropped during @{clean_user}. Waiting for channel recovery...")
                recovered = wait_for_x_channel_recovery(page, max_standby_min=10, check_interval_sec=15)
                if recovered:
                    is_mutual = check_is_mutual(page, clean_user)
                if is_mutual is None:
                    print(f"  [Follower] ⚠️ X channel remains unstable. Postponing remaining unfollows to avoid false penalties.")
                    break

            if is_mutual:
                # Взаимный подписчик — повышаем статус и сохраняем подписку
                log_action(clean_user, "mutual", success=True)
                print(f"  [Follower] 🎯 @{clean_user} followed back — marked as MUTUAL ✅")
                human_delay(2.0, 4.0)
                continue

            # 2. Проверка суточного лимита отписок
            _, unfollows_today = get_today_counts()
            if unfollows_today >= daily_unfollow_limit:
                print(f"[Follower] Daily unfollow limit reached ({unfollows_today}/{daily_unfollow_limit}). Halting batch.")
                break

            # 3. Проверка жесткого часового лимита мутаций (>= 40)
            gov = check_hourly_mutation_governor(limit=MAX_HOURLY_MUTATIONS, target_safe=28)
            if gov["triggered"]:
                print(f"[Follower] 🛑 Rolling 1-hour mutation limit reached ({gov['mutations']}/{MAX_HOURLY_MUTATIONS}). Halting unfollow batch.")
                break

            # 4. Мы уже на странице профиля! Выполняем отписку на открытой странице без лишней перезагрузки
            success = unfollow_user_on_current_page(page, clean_user)
            if success is None:
                # Сбой сети или задержка рендера кнопок — ждем восстановления канала и повторяем для ЭТОГО ЖЕ кандидата
                print(f"  [Follower] 📡 Action button delayed by network for @{clean_user}. Testing channel...")
                recovered = wait_for_x_channel_recovery(page, max_standby_min=10, check_interval_sec=15)
                if recovered:
                    try:
                        page.reload(wait_until="domcontentloaded", timeout=25000)
                        human_delay(2.0, 3.5)
                        success = unfollow_user_on_current_page(page, clean_user)
                    except Exception:
                        success = None

            if success is True:
                delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                print(f"  [Follower] Human pacing delay: {delay}s...")
                time.sleep(delay)
            else:
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
    Executes Funnel Stage 2 Second-Wave Nudge for candidates followed 20h+ ago.
    """
    from database import get_candidates_for_nudge
    from config import DAILY_LIKE_LIMIT, FUNNEL_NUDGE_HOURS

    today_likes = get_today_likes()
    if today_likes >= DAILY_LIKE_LIMIT:
        print(f"[Nudge] Daily like limit reached ({today_likes}/{DAILY_LIKE_LIMIT}). Postponing nudge batch.")
        return

    candidates = get_candidates_for_nudge(hours=FUNNEL_NUDGE_HOURS, limit=batch_size)
    if not candidates:
        print("[Nudge] No candidates currently due for Stage 2 Nudge.")
        return

    print(f"[Nudge] Starting Stage 2 Nudge batch ({FUNNEL_NUDGE_HOURS}h+) for {len(candidates)} candidates...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    try:
        for c in candidates:
            u = c["username"]
            print(f"\n[Nudge] Processing Stage 2 Nudge for @{u} (Score: {c.get('score', 0)})...")
            success = nudge_user_like(page, u)
            if success:
                delay = random.randint(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                print(f"  [Nudge] Organic pause {delay}s...")
                time.sleep(delay)
            human_delay(2.0, 3.5)
    finally:
        ctx.close()
        pw.stop()
        print("\n[Nudge] Stage 2 Nudge batch completed.")

def run_funnel_list_batch(profile_name="test_igorvl777", batch_size=3):
    """
    Executes Funnel Stage 3 Last-Chance Ego-List addition for candidates followed 34h+ ago.
    """
    from database import get_candidates_for_funnel_list_add, get_today_list_adds
    from config import DAILY_LIST_ADD_LIMIT, EGO_LIST_DEFAULT_NAME, FUNNEL_LIST_HOURS
    import importlib
    import list_bomber
    try:
        importlib.reload(list_bomber)
    except Exception:
        pass
    from list_bomber import add_user_to_list, ensure_ego_list_exists

    today_adds = get_today_list_adds()
    if today_adds >= DAILY_LIST_ADD_LIMIT:
        print(f"[Funnel List] Daily list add limit reached ({today_adds}/{DAILY_LIST_ADD_LIMIT}). Postponing.")
        return

    candidates = get_candidates_for_funnel_list_add(hours=FUNNEL_LIST_HOURS, limit=batch_size)
    if not candidates:
        print("[Funnel List] No candidates currently due for Stage 3 Ego-List addition.")
        return

    print(f"[Funnel List] Starting Stage 3 Ego-List batch ({FUNNEL_LIST_HOURS}h+) for {len(candidates)} candidates...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    try:
        if not ensure_ego_list_exists(page, EGO_LIST_DEFAULT_NAME):
            print("[Funnel List] Could not verify ego list. Aborting batch.")
            return

        for c in candidates:
            u = c["username"]
            print(f"\n[Funnel List] Checking Stage 3 Ego-List addition for @{u}...")
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

