# -*- coding: utf-8 -*-
"""
Candidate harvesting module for X (Twitter).
Finds live users from search queries (brutalism, swiss style, medtech) and donor post engagers.
Extracts Bio, Followers, Following counts and passes to the scoring engine.
"""

import re
import time
import random
from browser import get_browser_context, human_delay, human_scroll, human_click, human_idle_noise
from config import SEARCH_QUERIES, TARGET_DONORS
from scorer import evaluate_candidate
from database import upsert_candidate

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
    (mouse wandering, scrolling recent tweets), and extracts bio + counts.
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
            
        followers_link = page.query_selector(f'a[href="/{clean_user}/verified_followers"]') or page.query_selector(f'a[href="/{clean_user}/followers"]')
        if followers_link:
            followers_count = parse_stat_number(followers_link.inner_text())
            
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
            "following_count": following_count
        }
    except Exception as e:
        print(f"Error inspecting @{clean_user}: {e}")
        return None

def harvest_from_search(page, query: str, max_users: int = 12):
    """
    Searches for query in X Top tab (filters out chronological spam),
    grabs author usernames from tweets, and scores them with organic human pacing.
    """
    print(f"\n[Scraper] Searching for query: {query}")
    # Используем Top результаты без &f=live, чтобы брать реальные посты с вовлечением, а не спам-ботов
    search_url = f"https://x.com/search?q={query}"
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.5, 4.5)
        
        found_usernames = set()
        scroll_attempts = 0
        
        while len(found_usernames) < max_users and scroll_attempts < 6:
            tweet_elements = page.query_selector_all('article[data-testid="tweet"]')
            for tw in tweet_elements:
                # Автор твита
                user_link = tw.query_selector('div[data-testid="User-Name"] a[href^="/"]')
                if user_link:
                    href = user_link.get_attribute("href")
                    if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/"]):
                        u = href.replace("/", "").strip()
                        if u and len(u) < 30:
                            found_usernames.add(u)
                
                # Упомянутые дизайнеры в тексте (например: "Design by @username")
                mentions = tw.query_selector_all('div[data-testid="tweetText"] a[href^="/"]')
                for m in mentions:
                    m_href = m.get_attribute("href") or ""
                    if m_href.startswith("/") and not any(x in m_href for x in ["/hashtag/", "/search", "/i/"]):
                        u = m_href.replace("/", "").strip()
                        if u and len(u) < 30:
                            found_usernames.add(u)
                            
            human_scroll(page, steps=random.randint(2, 3), allow_backtrack=True)
            human_idle_noise(page)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(found_usernames)} unique users in feed. Starting evaluation...")
        _evaluate_and_store_users(page, found_usernames, max_users, source_label=f"search:{query[:30]}")
        
    except Exception as e:
        print(f"Error during search harvesting: {e}")

def harvest_from_donor(page, donor_username: str, max_users: int = 12):
    """
    Visits a high-tier design donor studio (e.g. readymag, framer, StudioDumbar, type01_),
    scrapes credited creators, commenters, and recent timeline engagers.
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
                # Авторы постов и ответов
                user_links = tw.query_selector_all('div[data-testid="User-Name"] a[href^="/"]')
                for ul in user_links:
                    href = ul.get_attribute("href") or ""
                    if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/"]):
                        u = href.replace("/", "").strip()
                        if u and u.lower() != clean_donor.lower() and len(u) < 30:
                            found_usernames.add(u)
                
                # Упомянутые дизайнеры в кейсах студии
                mentions = tw.query_selector_all('div[data-testid="tweetText"] a[href^="/"]')
                for m in mentions:
                    m_href = m.get_attribute("href") or ""
                    if m_href.startswith("/") and not any(x in m_href for x in ["/hashtag/", "/search", "/i/"]):
                        u = m_href.replace("/", "").strip()
                        if u and u.lower() != clean_donor.lower() and len(u) < 30:
                            found_usernames.add(u)

            human_scroll(page, steps=random.randint(2, 3), allow_backtrack=True)
            human_idle_noise(page)
            scroll_attempts += 1

        print(f"[Scraper] Found {len(found_usernames)} community designers from @{clean_donor}. Starting evaluation...")
        _evaluate_and_store_users(page, found_usernames, max_users, source_label=f"donor:@{clean_donor}")

    except Exception as e:
        print(f"Error harvesting from donor @{clean_donor}: {e}")

def _evaluate_and_store_users(page, usernames_set, max_users: int, source_label: str):
    """Helper to inspect and score a set of usernames."""
    for idx, username in enumerate(list(usernames_set)[:max_users], 1):
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
            status_emoji = "⭐ QUEUED" if evaluation['status'] == 'queued' else "ignored"
            print(f"  @{username} | Score: {evaluation['score']} | Ratio: {evaluation['ratio']} | Status: {status_emoji}")
            
            # Organic delay between candidates
            human_delay(3.0, 6.5)
            
            # Natural micro-break every 4-6 profiles
            if idx % random.randint(4, 6) == 0:
                break_sec = random.randint(12, 22)
                print(f"  [Human Pause] Short break ({break_sec}s) to maintain natural browsing patterns...")
                human_idle_noise(page)
                time.sleep(break_sec)

def run_harvesting_cycle(profile_name="test_igorvl777", queries_count=1, donors_count=1):
    """
    Runs a balanced harvesting cycle: search queries + donor studio communities.
    Includes natural warmup/glance at home feed between batches.
    """
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    selected_queries = random.sample(SEARCH_QUERIES, min(queries_count, len(SEARCH_QUERIES)))
    selected_donors = random.sample(TARGET_DONORS, min(donors_count, len(TARGET_DONORS)))
    
    tasks = [("search", q) for q in selected_queries] + [("donor", d) for d in selected_donors]
    random.shuffle(tasks)
    
    try:
        for i, (task_type, target) in enumerate(tasks, 1):
            if task_type == "search":
                harvest_from_search(page, target, max_users=10)
            else:
                harvest_from_donor(page, target, max_users=10)
            
            # Between batches: glance at home feed to blend with real traffic
            if i < len(tasks):
                inter_pause = random.randint(15, 30)
                print(f"\n[Cooldown] Taking a {inter_pause}s cooldown before next source...")
                try:
                    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
                    human_delay(2.0, 4.0)
                    human_scroll(page, steps=1)
                except Exception:
                    pass
                time.sleep(inter_pause)
                
    finally:
        ctx.close()
        pw.stop()
        print("\n[Scraper] Harvesting cycle completed.")

if __name__ == "__main__":
    import sys
    prof = sys.argv[1] if len(sys.argv) > 1 else "test_igorvl777"
    run_harvesting_cycle(profile_name=prof, queries_count=1, donors_count=1)
