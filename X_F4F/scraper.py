# -*- coding: utf-8 -*-
"""
Candidate harvesting module for X (Twitter).
Finds live users from search queries (brutalism, swiss style, medtech) and donor post engagers.
Extracts Bio, Followers, Following counts and passes to the scoring engine.
"""

import re
import random
from browser import get_browser_context, human_delay, human_scroll
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
    Navigates to user profile and extracts bio, counts, url, and checks recency.
    """
    clean_user = username.replace("@", "").strip()
    url = f"https://x.com/{clean_user}"
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        human_delay(1.5, 3.0)
        
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
        # X uses links like /username/following and /username/verified_followers
        following_count = 0
        followers_count = 0
        
        following_link = page.query_selector(f'a[href="/{clean_user}/following"]')
        if following_link:
            following_count = parse_stat_number(following_link.inner_text().split()[0])
            
        followers_link = page.query_selector(f'a[href="/{clean_user}/verified_followers"]') or page.query_selector(f'a[href="/{clean_user}/followers"]')
        if followers_link:
            followers_count = parse_stat_number(followers_link.inner_text().split()[0])
            
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
    Searches for query in X, grabs author usernames from tweets, and scores them.
    """
    print(f"\n[Scraper] Searching for query: {query}")
    search_url = f"https://x.com/search?q={query}&f=live"
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.0, 4.0)
        
        found_usernames = set()
        scroll_attempts = 0
        
        while len(found_usernames) < max_users and scroll_attempts < 5:
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
                            
            human_scroll(page, steps=2)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(found_usernames)} unique users in feed. Starting evaluation...")
        
        # Now inspect and score each candidate
        for username in list(found_usernames)[:max_users]:
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
                human_delay(1.5, 3.5)
                
    except Exception as e:
        print(f"Error during search harvesting: {e}")

def run_harvesting_cycle(profile_name="test_igorvl777", queries_count=3):
    """Runs a batch harvesting cycle across random queries."""
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    selected_queries = random.sample(SEARCH_QUERIES, min(queries_count, len(SEARCH_QUERIES)))
    
    try:
        for q in selected_queries:
            harvest_from_search(page, q, max_users=10)
    finally:
        ctx.close()
        pw.stop()
        print("\n[Scraper] Harvesting cycle completed.")

if __name__ == "__main__":
    import sys
    prof = sys.argv[1] if len(sys.argv) > 1 else "test_igorvl777"
    run_harvesting_cycle(profile_name=prof, queries_count=2)
