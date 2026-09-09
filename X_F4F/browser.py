# -*- coding: utf-8 -*-
"""
Browser automation layer using Playwright.
Supports persistent browser profiles, human-like typing/scrolling, and stealth settings.
"""

import os
import random
import time
from playwright.sync_api import sync_playwright
from config import PROFILES_DIR

def get_browser_context(profile_name="test_igorvl777", headless=False):
    """
    Launches browser with persistent context to keep login cookies and sessions.
    """
    user_data_dir = os.path.join(PROFILES_DIR, profile_name)
    os.makedirs(user_data_dir, exist_ok=True)
    
    playwright = sync_playwright().start()
    
    # Check if real Chrome is requested or fallback to Chromium
    browser_channel = os.getenv("BROWSER_CHANNEL", "chrome")
    
    # Modern Chrome flags for stability and stealth
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--start-maximized",
        "--no-first-run",
        "--no-default-browser-check"
    ]
    if os.name != "nt":
        args.extend(["--no-sandbox", "--disable-dev-shm-usage"])
    
    launch_kwargs = {
        "user_data_dir": user_data_dir,
        "headless": headless,
        "viewport": None,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "args": args,
        "ignore_default_args": ["--enable-automation"]
    }
    
    try:
        if browser_channel:
            context = playwright.chromium.launch_persistent_context(
                channel=browser_channel,
                **launch_kwargs
            )
        else:
            context = playwright.chromium.launch_persistent_context(**launch_kwargs)
    except Exception as e:
        # Fallback to default chromium if specific channel (e.g. chrome) is not found
        context = playwright.chromium.launch_persistent_context(**launch_kwargs)
    
    # Apply anti-detection script to all pages and popups in context
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    
    # Auto-load cookies.json if present
    cookie_file = os.path.join(user_data_dir, "cookies.json")
    if os.path.exists(cookie_file):
        try:
            import json
            with open(cookie_file, "r", encoding="utf-8") as f:
                saved_cookies = json.load(f)
                if saved_cookies:
                    context.add_cookies(saved_cookies)
        except Exception:
            pass
            
    page = context.pages[0] if context.pages else context.new_page()
    return playwright, context, page

def human_delay(min_sec=1.5, max_sec=4.0):
    """Randomized human-like sleep."""
    time.sleep(random.uniform(min_sec, max_sec))

def human_scroll(page, steps=3):
    """Smooth, human-like scrolling down the page."""
    for _ in range(steps):
        scroll_amount = random.randint(300, 750)
        page.mouse.wheel(0, scroll_amount)
        human_delay(0.8, 2.2)

if __name__ == "__main__":
    print("Testing browser context launch...")
    pw, ctx, page = get_browser_context(headless=True)
    page.goto("https://x.com", wait_until="domcontentloaded")
    print("Page title:", page.title())
    ctx.close()
    pw.stop()
    print("Browser test completed successfully.")
