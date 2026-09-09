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
    """Parses text numbers like '1.2K', '34.5M', '1,200' to integer."""
    if not text:
        return 0
    text = text.strip().upper().replace(",", "").replace(" ", "")
    multiplier = 1
    if "K" in text:
        multiplier = 1000
        text = text.replace("K", "")
    elif "M" in text:
        multiplier = 1000000
        text = text.replace("M", "")
    try:
        return int(float(text) * multiplier)
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
            following_count = parse_stat_number(following_link.inner_text().split()[0])
            
        followers_link = page.query_selector(f'a[href="/{clean_user}/verified_followers"]') or page.query_selector(f'a[href="/{clean_user}/followers"]')
        if followers_link:
            followers_count = parse_stat_number(followers_link.inner_text().split()[0])
            
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

def harvest_from_search(page, query: str, max_users: int = 15):
    """
    Searches for query in X, grabs author usernames from tweets, and scores them
    with organic human delays, micro-breaks, and natural feed scrolling.
    """
    print(f"\n[Scraper] Searching for query: {query}")
    search_url = f"https://x.com/search?q={query}&f=live"
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.5, 4.5)
        
        found_usernames = set()
        scroll_attempts = 0
        
        while len(found_usernames) < max_users and scroll_attempts < 6:
            # Find tweet author links
            tweet_elements = page.query_selector_all('article[data-testid="tweet"]')
            for tw in tweet_elements:
                user_link = tw.query_selector('div[data-testid="User-Name"] a[href^="/"]')
                if user_link:
                    href = user_link.get_attribute("href")
                    if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/"]):
                        u = href.replace("/", "").strip()
                        if u and len(u) < 30:
                            found_usernames.add(u)
                            
            human_scroll(page, steps=random.randint(2, 3), allow_backtrack=True)
            human_idle_noise(page)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(found_usernames)} unique users in feed. Starting evaluation...")
        
        # Now inspect and score each candidate with human pacing
        for idx, username in enumerate(list(found_usernames)[:max_users], 1):
            profile = inspect_user_profile(page, username)
            if profile:
                evaluation = evaluate_candidate(profile)
                candidate_record = {
                    **profile,
                    "score": evaluation["score"],
                    "ratio": evaluation["ratio"],
                    "score_breakdown": evaluation["breakdown"],
                    "source": f"search:{query[:30]}",
                    "status": evaluation["status"]
                }
                upsert_candidate(candidate_record)
                print(f"  @{username} | Score: {evaluation['score']} | Ratio: {evaluation['ratio']} | Status: {evaluation['status']}")
                
                # Organic delay between candidates
                human_delay(3.0, 7.0)
                
                # Natural micro-break every 4-6 profiles (mimics taking a sip of coffee or reading a tab)
                if idx % random.randint(4, 6) == 0:
                    break_sec = random.randint(12, 25)
                    print(f"  [Human Pause] Short break ({break_sec}s) to maintain natural browsing patterns...")
                    human_idle_noise(page)
                    time.sleep(break_sec)
                
    except Exception as e:
        print(f"Error during search harvesting: {e}")

def run_harvesting_cycle(profile_name="test_igorvl777", queries_count=3):
    """
    Runs a batch harvesting cycle across random queries.
    Includes natural warmup/glance at home feed between query batches.
    """
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    selected_queries = random.sample(SEARCH_QUERIES, min(queries_count, len(SEARCH_QUERIES)))
    
    try:
        for i, q in enumerate(selected_queries, 1):
            harvest_from_search(page, q, max_users=10)
            
            # Between queries: glance at home feed to blend with real traffic
            if i < len(selected_queries):
                inter_query_pause = random.randint(15, 30)
                print(f"\n[Cooldown] Taking a {inter_query_pause}s cooldown between search topics...")
                try:
                    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=20000)
                    human_delay(2.0, 4.0)
                    human_scroll(page, steps=1)
                except Exception:
                    pass
                time.sleep(inter_query_pause)
                
    finally:
        ctx.close()
        pw.stop()
        print("\n[Scraper] Harvesting cycle completed.")

if __name__ == "__main__":
    import sys
    prof = sys.argv[1] if len(sys.argv) > 1 else "test_igorvl777"
    run_harvesting_cycle(profile_name=prof, queries_count=2)
