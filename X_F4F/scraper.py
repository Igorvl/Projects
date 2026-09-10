# -*- coding: utf-8 -*-
"""
Candidate harvesting module for X (Twitter).
Finds live users from search queries (brutalism, swiss style, medtech) and donor post engagers.
Extracts Bio, Followers, Following counts and passes to the scoring engine.
"""

import re
import time
import random
import datetime
from browser import get_browser_context, human_delay, human_scroll, human_click, human_idle_noise
from config import SEARCH_QUERIES, TARGET_DONORS
from scorer import evaluate_candidate
from database import upsert_candidate, get_existing_candidate_usernames, get_queue_count

def parse_stat_number(text: str) -> int:
    """
    Parses text numbers like '8 489 подписчиков', '1.2K Followers', '34.5M', '1,200'.
    Correctly handles non-breaking spaces (\xa0) from European/Russian locales.
    """
    if not text:
        return 0
    cleaned = text.replace("\xa0", " ").strip()
    m = re.match(r"^([\d\s.,]+[KkMmBb]?)", cleaned)
    if not m:
        return 0
    num_str = m.group(1).replace(" ", "").replace(",", "").upper()
    multiplier = 1
    if "K" in num_str:
        multiplier = 1000
        num_str = num_str.replace("K", "")
    elif "M" in num_str:
        multiplier = 1000000
        num_str = num_str.replace("M", "")
    try:
        return int(float(num_str) * multiplier)
    except Exception:
        return 0

def inspect_user_profile(page, username: str) -> dict:
    """
    Navigates to user profile, simulates human reading behavior
    (mouse wandering, scrolling recent tweets), and extracts bio + counts + last active date.
    """
    clean_user = username.replace("@", "").strip()
    url = f"https://x.com/{clean_user}"
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Natural reading delay upon landing
        human_delay(2.0, 4.0)
        
        # Check if user exists or suspended
        page_text = page.inner_text("body")
        if "This account doesn’t exist" in page_text or "Account suspended" in page_text:
            return None
            
        # Extract Display Name & Bio
        name = ""
        name_el = page.query_selector('div[data-testid="UserName"]')
        if name_el:
            name = name_el.inner_text().split("\n")[0]
            
        bio = ""
        bio_el = page.query_selector('div[data-testid="UserDescription"]')
        if bio_el:
            bio = bio_el.inner_text()
            
        user_url = ""
        url_el = page.query_selector('a[data-testid="UserUrl"]')
        if url_el:
            user_url = url_el.get_attribute("href") or url_el.inner_text()
            
        # Extract Following and Followers counts
        following_count = 0
        followers_count = 0
        
        following_link = page.query_selector(f'a[href="/{clean_user}/following"]')
        if following_link:
            following_count = parse_stat_number(following_link.inner_text())
            
        # Priority: exact /followers URL. Fallback: /verified_followers only for same user.
        followers_link = (
            page.query_selector(f'a[href="/{clean_user}/followers"]') or
            page.query_selector(f'a[href="/{clean_user}/verified_followers"]')
        )
        if followers_link:
            followers_count = parse_stat_number(followers_link.inner_text())
            
        # Extract last active date from latest tweet (activity freshness check)
        days_inactive = None
        last_active_str = None
        try:
            tweet_times = page.query_selector_all('article[data-testid="tweet"] time')
            if tweet_times:
                dates = []
                for t_el in tweet_times[:3]:
                    dt_val = t_el.get_attribute("datetime")
                    if dt_val:
                        try:
                            parsed_dt = datetime.datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
                            dates.append(parsed_dt)
                        except Exception:
                            pass
                if dates:
                    most_recent = max(dates)
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    days_inactive = max(0, (now_utc - most_recent).days)
                    last_active_str = most_recent.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

        # Human mimicry: glance at recent work/tweets (scroll down 1-2 times)
        if random.random() < 0.65:
            human_scroll(page, steps=random.randint(1, 2), allow_backtrack=True)
            human_idle_noise(page)
            
        return {
            "username": clean_user,
            "name": name,
            "bio": bio,
            "url": user_url,
            "followers_count": followers_count,
            "following_count": following_count,
            "days_inactive": days_inactive,
            "last_active": last_active_str
        }
    except Exception as e:
        print(f"Error inspecting @{clean_user}: {e}")
        return None

def harvest_from_search(page, query: str, max_users: int = 12) -> int:
    """
    Searches for query in X Top tab (filters out chronological spam),
    grabs author usernames from tweets, and scores them with organic human pacing.
    Returns count of newly queued candidates.
    """
    print(f"\n[Scraper] Searching for query: {query}")
    search_url = f"https://x.com/search?q={query}"
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.5, 4.5)
        
        found_usernames = set()
        scroll_attempts = 0
        
        while len(found_usernames) < max_users and scroll_attempts < 6:
            tweet_elements = page.query_selector_all('article[data-testid="tweet"]')
            for tw in tweet_elements:
                user_link = tw.query_selector('div[data-testid="User-Name"] a[href^="/"]')
                if user_link:
                    href = user_link.get_attribute("href")
                    if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/"]):
                        u = href.replace("/", "").strip()
                        if u and len(u) < 30 and not "/" in u:
                            found_usernames.add(u)
                
                mentions = tw.query_selector_all('div[data-testid="tweetText"] a[href^="/"]')
                for m in mentions:
                    m_href = m.get_attribute("href") or ""
                    if m_href.startswith("/") and not any(x in m_href for x in ["/hashtag/", "/search", "/i/"]):
                        u = m_href.replace("/", "").strip()
                        if u and len(u) < 30 and not "/" in u:
                            found_usernames.add(u)
                            
            human_scroll(page, steps=random.randint(2, 3), allow_backtrack=True)
            human_idle_noise(page)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(found_usernames)} unique users in feed. Starting evaluation...")
        return _evaluate_and_store_users(page, found_usernames, max_users, source_label=f"search:{query[:30]}")
        
    except Exception as e:
        print(f"Error during search harvesting: {e}")
        return 0

def harvest_from_donor(page, donor_username: str, max_users: int = 12) -> int:
    """
    Visits a high-tier design donor studio (e.g. readymag, framer, StudioDumbar, type01_),
    scrapes credited creators, commenters, and recent timeline engagers.
    Returns count of newly queued candidates.
    """
    clean_donor = donor_username.replace("@", "").strip()
    print(f"\n[Scraper] Harvesting from design donor studio: @{clean_donor}")
    donor_url = f"https://x.com/{clean_donor}/with_replies"
    
    try:
        page.goto(donor_url, wait_until="domcontentloaded", timeout=20000)
        human_delay(3.0, 5.0)
        
        found_usernames = set()
        scroll_attempts = 0
        
        while len(found_usernames) < max_users and scroll_attempts < 6:
            tweet_elements = page.query_selector_all('article[data-testid="tweet"]')
            for tw in tweet_elements:
                user_links = tw.query_selector_all('div[data-testid="User-Name"] a[href^="/"]')
                for ul in user_links:
                    href = ul.get_attribute("href") or ""
                    if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/"]):
                        u = href.replace("/", "").strip()
                        if u and u.lower() != clean_donor.lower() and len(u) < 30 and not "/" in u:
                            found_usernames.add(u)
                
                mentions = tw.query_selector_all('div[data-testid="tweetText"] a[href^="/"]')
                for m in mentions:
                    m_href = m.get_attribute("href") or ""
                    if m_href.startswith("/") and not any(x in m_href for x in ["/hashtag/", "/search", "/i/"]):
                        u = m_href.replace("/", "").strip()
                        if u and u.lower() != clean_donor.lower() and len(u) < 30 and not "/" in u:
                            found_usernames.add(u)

            human_scroll(page, steps=random.randint(2, 3), allow_backtrack=True)
            human_idle_noise(page)
            scroll_attempts += 1

        print(f"[Scraper] Found {len(found_usernames)} community designers from @{clean_donor}. Starting evaluation...")
        return _evaluate_and_store_users(page, found_usernames, max_users, source_label=f"donor:@{clean_donor}")

    except Exception as e:
        print(f"Error harvesting from donor @{clean_donor}: {e}")
        return 0

def harvest_from_donor_followers(page, donor_username: str, max_users: int = 15) -> int:
    """
    Visits a high-tier or mid-tier design creator/platform's followers list:
    https://x.com/{donor}/followers
    Triggers initial wheel scroll to initialize infinite scroll feed, extracts followers.
    Returns count of newly queued candidates.
    """
    clean_donor = donor_username.replace("@", "").strip()
    print(f"\n[Scraper] Harvesting followers list from donor: @{clean_donor}")
    url = f"https://x.com/{clean_donor}/followers"
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.5, 4.0)
        # Twitter/X requires an initial wheel scroll to initialize the infinite scroll feed
        page.mouse.wheel(0, 350)
        time.sleep(2.5)
        
        found_usernames = set()
        scroll_attempts = 0
        
        while len(found_usernames) < max_users and scroll_attempts < 6:
            col = page.query_selector('div[data-testid="primaryColumn"]')
            if col:
                user_links = col.query_selector_all('a[href^="/"]')
                for ul in user_links:
                    href = ul.get_attribute("href") or ""
                    if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/", "/search", f"/{clean_donor}"]):
                        u = href.replace("/", "").strip()
                        if u and u.lower() != clean_donor.lower() and len(u) < 30 and not "/" in u:
                            found_usernames.add(u)
            else:
                user_cells = page.query_selector_all('div[data-testid="UserCell"]')
                for cell in user_cells:
                    user_links = cell.query_selector_all('a[href^="/"]')
                    for ul in user_links:
                        href = ul.get_attribute("href") or ""
                        if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/", "/search"]):
                            u = href.replace("/", "").strip()
                            if u and u.lower() != clean_donor.lower() and len(u) < 30 and not "/" in u:
                                found_usernames.add(u)
                            
            human_scroll(page, steps=random.randint(1, 2), allow_backtrack=False)
            human_idle_noise(page)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(found_usernames)} candidate designers from @{clean_donor}'s followers. Starting evaluation...")
        return _evaluate_and_store_users(page, found_usernames, max_users, source_label=f"donor_followers:@{clean_donor}")
        
    except Exception as e:
        print(f"Error harvesting followers from @{clean_donor}: {e}")
        return 0

def _evaluate_and_store_users(page, usernames_set, max_users: int, source_label: str) -> int:
    """Helper to inspect and score a set of usernames, skipping already known candidates.
    Returns the number of candidates successfully added to queue."""
    existing_users = get_existing_candidate_usernames()
    
    # Отсеиваем пользователей, которые уже есть в нашей базе (не тратим время и запросы)
    new_candidates = []
    skipped_count = 0
    for u in usernames_set:
        clean_u = u.lower().replace("@", "").strip()
        if clean_u in existing_users:
            skipped_count += 1
        else:
            new_candidates.append(u)
            
    if skipped_count > 0:
        print(f"  [Deduplication] Skipped {skipped_count} users already tracked in database.")
        
    if not new_candidates:
        print("  [Deduplication] All found users from this source are already known. Skipping to next source.")
        return 0

    queued_added = 0
    for idx, username in enumerate(new_candidates[:max_users], 1):
        profile = inspect_user_profile(page, username)
        if profile:
            evaluation = evaluate_candidate(profile)
            candidate_record = {
                **profile,
                "score": evaluation["score"],
                "ratio": evaluation["ratio"],
                "score_breakdown": evaluation["breakdown"],
                "source": source_label,
                "status": evaluation["status"]
            }
            upsert_candidate(candidate_record)
            existing_users.add(username.lower().replace("@", "").strip())
            
            if evaluation['status'] == 'queued':
                queued_added += 1
                status_emoji = "⭐ QUEUED"
            else:
                status_emoji = "ignored"
            reasons_str = f" ({', '.join(evaluation['breakdown']['reject_reasons'])})" if evaluation['breakdown']['reject_reasons'] else ""
            print(f"  @{username} | Score: {evaluation['score']} | Ratio: {evaluation['ratio']} | Status: {status_emoji}{reasons_str}")
            
            # Organic delay between candidates
            human_delay(3.0, 6.5)
            
            # Natural micro-break every 4-6 profiles
            if idx % random.randint(4, 6) == 0:
                break_sec = random.randint(12, 22)
                print(f"  [Human Pause] Short break ({break_sec}s) to maintain natural browsing patterns...")
                human_idle_noise(page)
                time.sleep(break_sec)

    return queued_added

def run_harvesting_cycle(profile_name="test_igorvl777", target_queued=10, max_sources=15):
    """
    Goal-Driven Harvesting Cycle:
    Continuously harvests across rotating sources (donor followers, search queries, donor replies)
    UNTIL target_queued candidates are newly queued OR max_sources is reached.
    If a source is exhausted or yields 0 candidates, automatically rotates to the next one!
    """
    print(f"\n[Scraper] Starting goal-driven harvesting for @{profile_name} (Goal: +{target_queued} queued leads)...")
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    
    # Сбор пула источников с приоритетом на followers доноров (самый высокий % конверсии)
    shuffled_donors = list(TARGET_DONORS)
    random.shuffle(shuffled_donors)
    
    shuffled_queries = list(SEARCH_QUERIES)
    random.shuffle(shuffled_queries)
    
    tasks = []
    # 1. Приоритет: подписчики доноров
    for d in shuffled_donors:
        tasks.append(("donor_followers", d))
    # 2. Поисковые запросы
    for q in shuffled_queries:
        tasks.append(("search", q))
    # 3. Таймлайн доноров
    for d in shuffled_donors:
        tasks.append(("donor", d))
        
    total_queued_added = 0
    sources_processed = 0
    
    try:
        for task_type, target in tasks:
            if sources_processed >= max_sources:
                print(f"[Scraper] Reached safety session source limit ({max_sources} sources). Resting.")
                break
                
            sources_processed += 1
            print(f"\n--- [Source #{sources_processed}/{max_sources}] Type: {task_type} | Target: {target} ---")
            
            queued_this_source = 0
            if task_type == "donor_followers":
                queued_this_source = harvest_from_donor_followers(page, target, max_users=12)
            elif task_type == "search":
                queued_this_source = harvest_from_search(page, target, max_users=10)
            else:
                queued_this_source = harvest_from_donor(page, target, max_users=10)
                
            total_queued_added += queued_this_source
            current_total_queue = get_queue_count()
            print(f"[Progress] Added +{queued_this_source} leads from this source. Total newly queued: {total_queued_added}/{target_queued} (Queue in DB: {current_total_queue})")
            
            # Проверяем достижение цели
            if total_queued_added >= target_queued:
                print(f"\n🎉 [Goal Reached] Target of +{target_queued} qualified leads achieved! (Total in DB queue: {current_total_queue})")
                break
                
            # Органический кулдаун перед следующим источником
            inter_pause = random.randint(15, 28)
            print(f"\n[Source Exhausted/Rotated] Taking a {inter_pause}s human break before rotating to next source...")
            try:
                page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
                human_delay(2.0, 3.5)
                human_scroll(page, steps=1)
            except Exception:
                pass
            time.sleep(inter_pause)
            
    finally:
        ctx.close()
        pw.stop()
        current_total_queue = get_queue_count()
        print(f"\n[Scraper] Harvesting cycle completed. Newly queued: +{total_queued_added} | Total ready in DB queue: {current_total_queue}.")

if __name__ == "__main__":
    import sys
    prof = "test_igorvl777"
    target = 10
    
    for arg in sys.argv[1:]:
        if arg.startswith("--target="):
            target = int(arg.split("=")[1])
        elif arg == "--target" and len(sys.argv) > sys.argv.index(arg) + 1:
            target = int(sys.argv[sys.argv.index(arg) + 1])
        elif not arg.startswith("-"):
            prof = arg
            
    run_harvesting_cycle(profile_name=prof, target_queued=target)
