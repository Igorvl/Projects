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
import urllib.parse
from browser import get_browser_context, human_delay, human_scroll, human_click, human_idle_noise
from config import SEARCH_QUERIES, TARGET_DONORS, HARVEST_MAX_SCROLLS, SNOWBALL_MIN_SCORE
from scorer import evaluate_candidate
from database import (
    upsert_candidate,
    get_existing_candidate_usernames,
    get_queue_count,
    get_available_sources,
    record_source_scrape,
    add_dynamic_donor
)

def parse_stat_number(text: str) -> int:
    """
    Parses text numbers like '8 489 подписчиков', '1.2K Followers', '34.5M', '1,200', 'Followers\n1,200'.
    Robustly extracts numbers with K/M/B suffix from anywhere in the string regardless of locale or prefix.
    """
    if not text:
        return 0
    cleaned = text.replace("\xa0", " ").strip()
    m = re.search(r"([\d.,]+(?:\s*[\d.,]+)*\s*[KkMmBb]?)", cleaned)
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
    elif "B" in num_str:
        multiplier = 1000000000
        num_str = num_str.replace("B", "")
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
            
        # Extract Following and Followers counts with case-insensitive and robust fallbacks
        following_count = 0
        followers_count = 0
        
        following_link = (
            page.query_selector(f'a[href="/{clean_user}/following" i]') or
            page.query_selector('a[href$="/following" i]') or
            page.query_selector('a[href*="/following" i]')
        )
        if following_link:
            following_count = parse_stat_number(following_link.inner_text())
            
        followers_link = (
            page.query_selector(f'a[href="/{clean_user}/followers" i]') or
            page.query_selector(f'a[href="/{clean_user}/verified_followers" i]') or
            page.query_selector('a[href$="/verified_followers" i]') or
            page.query_selector('a[href$="/followers" i]') or
            page.query_selector('a[href*="/followers" i]')
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

        # Extract text from recent tweets (detect mutuals/connect announcements & art shares)
        recent_tweets_text = ""
        try:
            tweet_text_els = page.query_selector_all('article[data-testid="tweet"] div[data-testid="tweetText"]')
            if tweet_text_els:
                recent_tweets_text = " ".join([el.inner_text() for el in tweet_text_els[:2]])
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
            "last_active": last_active_str,
            "recent_tweets": recent_tweets_text
        }
    except Exception as e:
        print(f"Error inspecting @{clean_user}: {e}")
        return None

def harvest_from_search(page, query: str, max_users: int = 12) -> int:
    """
    Searches for query in X Live/Latest tab (&f=live) for fresh real-time tweets,
    grabs author usernames, and scores them with organic human pacing.
    Returns count of newly queued candidates.
    """
    print(f"\n[Scraper] Searching live chronological feed: {query}")
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://x.com/search?q={encoded_query}&f=live"
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.5, 4.5)
        
        existing_users = get_existing_candidate_usernames()
        fresh_usernames = set()
        scroll_attempts = 0
        
        while len(fresh_usernames) < max_users and scroll_attempts < HARVEST_MAX_SCROLLS:
            tweet_elements = page.query_selector_all('article[data-testid="tweet"]')
            for tw in tweet_elements:
                user_link = tw.query_selector('div[data-testid="User-Name"] a[href^="/"]')
                if user_link:
                    href = user_link.get_attribute("href") or ""
                    if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/"]):
                        u = href.replace("/", "").strip()
                        if u and len(u) < 30 and not "/" in u:
                            if u.lower() not in existing_users:
                                fresh_usernames.add(u)
                
                mentions = tw.query_selector_all('div[data-testid="tweetText"] a[href^="/"]')
                for m in mentions:
                    m_href = m.get_attribute("href") or ""
                    if m_href.startswith("/") and not any(x in m_href for x in ["/hashtag/", "/search", "/i/"]):
                        u = m_href.replace("/", "").strip()
                        if u and len(u) < 30 and not "/" in u:
                            if u.lower() not in existing_users:
                                fresh_usernames.add(u)
                            
            human_scroll(page, steps=random.randint(2, 3), allow_backtrack=True)
            human_idle_noise(page)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(fresh_usernames)} fresh creators in live feed (Scrolled {scroll_attempts} screens). Starting evaluation...")
        return _evaluate_and_store_users(page, fresh_usernames, max_users, source_label=f"search:{query[:30]}")
        
    except Exception as e:
        print(f"Error during search harvesting: {e}")
        return 0

def harvest_from_donor_replies(page, donor_username: str, max_users: int = 15) -> int:
    """
    Algorithm 1: Fresh Drop Commenters & Engagers
    Queries live chronological replies/mentions to:donor (e.g. to:readymag OR @readymag)
    Extracts active creators interacting with the studio's newest posts right now.
    Returns count of newly queued candidates.
    """
    clean_donor = donor_username.replace("@", "").strip()
    print(f"\n[Scraper] [Algorithm 1] Harvesting live commenters to studio: to:@{clean_donor}")
    search_query = f"to:{clean_donor} OR @{clean_donor}"
    search_url = f"https://x.com/search?q={urllib.parse.quote(search_query)}&f=live"
    
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        human_delay(3.0, 4.5)
        
        # Check if tweets exist at all on the initial screen to avoid blank-screen scroll delays
        initial_tweets = []
        try:
            initial_tweets = page.query_selector_all('article[data-testid="tweet"]')
        except Exception:
            human_delay(2.0, 3.0)
            initial_tweets = page.query_selector_all('article[data-testid="tweet"]')
            
        if not initial_tweets:
            # 1 gentle scroll check
            human_scroll(page, steps=1)
            human_delay(1.5, 2.5)
            try:
                initial_tweets = page.query_selector_all('article[data-testid="tweet"]')
            except Exception:
                pass
            if not initial_tweets:
                print(f"  [Scraper] No live replies or mentions found for @{clean_donor}. Skipping.")
                return 0
        
        existing_users = get_existing_candidate_usernames()
        fresh_usernames = set()
        scroll_attempts = 0
        
        while len(fresh_usernames) < max_users and scroll_attempts < HARVEST_MAX_SCROLLS:
            try:
                tweet_elements = page.query_selector_all('article[data-testid="tweet"]')
            except Exception:
                human_delay(1.5, 2.5)
                continue
                
            for tw in tweet_elements:
                try:
                    user_link = tw.query_selector('div[data-testid="User-Name"] a[href^="/"]')
                    if user_link:
                        href = user_link.get_attribute("href") or ""
                        if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/"]):
                            u = href.replace("/", "").strip()
                            if u and u.lower() != clean_donor.lower() and len(u) < 30 and not "/" in u:
                                if u.lower() not in existing_users:
                                    fresh_usernames.add(u)
                except Exception:
                    continue
                                
            human_scroll(page, steps=random.randint(1, 2), allow_backtrack=False)
            human_idle_noise(page)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(fresh_usernames)} active commenters to @{clean_donor}. Starting evaluation...")
        return _evaluate_and_store_users(page, fresh_usernames, max_users, source_label=f"donor_replies:@{clean_donor}")
        
    except Exception as e:
        print(f"Error harvesting commenters to donor @{clean_donor}: {e}")
        return 0

def harvest_from_donor_followers(page, donor_username: str, max_users: int = 15) -> int:
    """
    Visits a high-tier or mid-tier design creator/platform's followers list:
    https://x.com/{donor}/followers
    Deep-scrolls through already-known users up to HARVEST_MAX_SCROLLS (20 screens)
    to uncover fresh unscraped candidates.
    Returns count of newly queued candidates.
    """
    clean_donor = donor_username.replace("@", "").strip()
    print(f"\n[Scraper] Harvesting followers list from donor: @{clean_donor}")
    url = f"https://x.com/{clean_donor}/followers"
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.5, 4.0)
        page.mouse.wheel(0, 350)
        time.sleep(2.5)
        
        existing_users = get_existing_candidate_usernames()
        fresh_usernames = set()
        scroll_attempts = 0
        consecutive_stagnant = 0
        
        while len(fresh_usernames) < max_users and scroll_attempts < HARVEST_MAX_SCROLLS:
            prev_count = len(fresh_usernames)
            col = page.query_selector('div[data-testid="primaryColumn"]')
            user_links = col.query_selector_all('a[href^="/"]') if col else []
            if not user_links:
                user_cells = page.query_selector_all('div[data-testid="UserCell"]')
                for cell in user_cells:
                    user_links.extend(cell.query_selector_all('a[href^="/"]'))

            for ul in user_links:
                href = ul.get_attribute("href") or ""
                if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/", "/search", f"/{clean_donor}"]):
                    u = href.replace("/", "").strip()
                    if u and u.lower() != clean_donor.lower() and len(u) < 30 and not "/" in u:
                        if u.lower() not in existing_users:
                            fresh_usernames.add(u)
                            
            if len(fresh_usernames) == prev_count:
                consecutive_stagnant += 1
            else:
                consecutive_stagnant = 0

            # Stop if feed genuinely ran out of new followers after sufficient scrolling
            if consecutive_stagnant >= 4 and scroll_attempts >= 8:
                break

            human_scroll(page, steps=random.randint(1, 2), allow_backtrack=False)
            human_idle_noise(page)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(fresh_usernames)} fresh candidates from @{clean_donor}'s followers (Deep-scrolled {scroll_attempts} screens). Starting evaluation...")
        return _evaluate_and_store_users(page, fresh_usernames, max_users, source_label=f"donor_followers:@{clean_donor}")
        
    except Exception as e:
        print(f"Error harvesting followers from @{clean_donor}: {e}")
        return 0

def harvest_from_peer_following(page, seed_username: str, max_users: int = 15) -> int:
    """
    Algorithm 3: Snowball Graph of Super-Engagers
    Visits the following list of a verified Super-Engager (/{seed}/following).
    Because this creator is a proven active engager (high ratio, creative bio),
    the people they follow represent their inner circle of active peers and likers.
    Returns count of newly queued candidates.
    """
    clean_seed = seed_username.replace("@", "").strip()
    print(f"\n[Scraper] [Algorithm 3] Harvesting peer network from @{clean_seed}'s following...")
    url = f"https://x.com/{clean_seed}/following"
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        human_delay(3.0, 5.0)
        
        existing_users = get_existing_candidate_usernames()
        fresh_usernames = set()
        scroll_attempts = 0
        
        while len(fresh_usernames) < max_users and scroll_attempts < 12:
            user_cells = page.query_selector_all('div[data-testid="UserCell"]')
            for cell in user_cells:
                user_links = cell.query_selector_all('a[href^="/"]')
                for ul in user_links:
                    href = ul.get_attribute("href") or ""
                    if href and not any(x in href for x in ["/home", "/explore", "/notifications", "/i/", "/search"]):
                        u = href.replace("/", "").strip()
                        if u and u.lower() != clean_seed.lower() and len(u) < 30 and not "/" in u:
                            if u.lower() not in existing_users:
                                fresh_usernames.add(u)
                                
            human_scroll(page, steps=random.randint(1, 2), allow_backtrack=False)
            human_idle_noise(page)
            scroll_attempts += 1
            
        print(f"[Scraper] Found {len(fresh_usernames)} active peers from @{clean_seed}'s network. Starting evaluation...")
        return _evaluate_and_store_users(page, fresh_usernames, max_users, source_label=f"peer_following:@{clean_seed}")
        
    except Exception as e:
        print(f"Error harvesting peer network from @{clean_seed}: {e}")
        return 0

def _evaluate_and_store_users(page, usernames_set, max_users: int, source_label: str) -> int:
    """Helper to inspect and score a set of usernames, skipping already known candidates.
    Returns the number of candidates successfully added to queue."""
    existing_users = get_existing_candidate_usernames()
    
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
            
            # Snowball Discovery: If candidate has high score, check bio mentions for new potential donors
            IGNORED_BIO_MENTIONS = {
                'gmail', 'yahoo', 'hotmail', 'outlook', 'protonmail', 'icloud', 'mail',
                'github', 'instagram', 'linkedin', 'telegram', 'youtube', 'tiktok', 'discord', 'figma'
            }
            if evaluation['score'] >= SNOWBALL_MIN_SCORE and profile.get("bio"):
                bio_mentions = re.findall(r"(?<![a-zA-Z0-9._%+-])@([a-zA-Z0-9_]{3,25})", profile["bio"])
                for bm in bio_mentions:
                    clean_bm = bm.lower().strip()
                    if clean_bm not in existing_users and clean_bm != username.lower() and clean_bm not in IGNORED_BIO_MENTIONS:
                        add_dynamic_donor(clean_bm, discovered_from=username)
                        print(f"  [Snowball Graph] Discovered new potential donor studio @{clean_bm} from @{username}'s bio!")

            # Algorithm 3: Auto-record verified Super-Engagers as peer_seeds for network discovery
            if evaluation['status'] == 'queued' and (evaluation['score'] >= 90 or evaluation['breakdown'].get('super_engager_bonus', 0) > 0):
                add_dynamic_donor(username, discovered_from=source_label, followers_count=profile.get('followers_count', 0), donor_type="peer_seed")
                print(f"  [Snowball Graph] Recorded Super-Engager @{username} as peer_seed for network discovery!")
            
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
    Discovery Engine 2.0:
    Continuously harvests across dynamic rotating sources via get_available_sources()
    (donor_replies, peer_following, donor_followers, live search, dynamic_donors)
    respecting cooldowns, deep scrolling, and recording yield.
    """
    from database import get_available_sources, record_source_scrape, get_queue_count
    
    available_sources = get_available_sources()
    if not available_sources:
        print("[Scraper] All sources currently on cooldown. Will retry in next session.")
        return
        
    print(f"\n[Scraper] Discovery Engine 2.0: {len(available_sources)} eligible sources ready (out of cooldown).")
    print(f"[Scraper] Goal: +{target_queued} queued leads | Profile: @{profile_name}...")
    
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    
    total_queued_added = 0
    sources_processed = 0
    
    try:
        for src in available_sources:
            if sources_processed >= max_sources:
                print(f"[Scraper] Reached safety session source limit ({max_sources} sources). Resting.")
                break
                
            sources_processed += 1
            stype = src["type"]
            target = src["target"]
            ident = src["identifier"]
            cooldown = src.get("cooldown", 48)
            
            print(f"\n--- [Source #{sources_processed}/{max_sources}] Type: {stype} | Target: {target} ---")
            
            queued_this_source = 0
            if stype == "donor_replies":
                queued_this_source = harvest_from_donor_replies(page, target, max_users=15)
            elif stype == "peer_following":
                queued_this_source = harvest_from_peer_following(page, target, max_users=15)
            elif stype == "donor_followers":
                queued_this_source = harvest_from_donor_followers(page, target, max_users=18)
            elif stype == "search":
                queued_this_source = harvest_from_search(page, target, max_users=15)
            else:
                queued_this_source = harvest_from_donor_followers(page, target, max_users=12)
                
            total_queued_added += queued_this_source
            
            # Record scrape in sources_tracking to reset cooldown timer
            record_source_scrape(ident, stype, evaluated_count=12, leads_yielded=queued_this_source, cooldown_hours=cooldown)
            
            current_total_queue = get_queue_count()
            print(f"[Progress] Added +{queued_this_source} leads from this source. Total newly queued: {total_queued_added}/{target_queued} (Queue in DB: {current_total_queue})")
            
            if total_queued_added >= target_queued:
                print(f"\n🎉 [Goal Reached] Target of +{target_queued} qualified leads achieved! (Total in DB queue: {current_total_queue})")
                break
                
            # Inter-source human cooldown
            inter_pause = random.randint(15, 26)
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
