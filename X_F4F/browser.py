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

# Virtual mouse position tracking
_mouse_pos = [random.randint(350, 650), random.randint(250, 450)]

def human_delay(min_sec=1.5, max_sec=4.0, distribution="lognormal"):
    """
    Simulates human reaction times using log-normal distribution.
    Prevents flat random machine fingerprints.
    """
    if distribution == "lognormal":
        mean = (min_sec + max_sec) / 2.0
        val = random.gauss(mean, max(0.2, (max_sec - min_sec) / 3.2))
        actual = max(min_sec * 0.7, min(max_sec * 1.5, val))
        time.sleep(actual)
    else:
        time.sleep(random.uniform(min_sec, max_sec))

def _bezier_coord(p0, p1, p2, p3, t):
    """Calculates coordinate along a cubic Bezier curve at parameter t (0.0 to 1.0)."""
    return (
        (1 - t)**3 * p0 +
        3 * (1 - t)**2 * t * p1 +
        3 * (1 - t) * t**2 * p2 +
        t**3 * p3
    )

def human_move_to(page, target_x: float, target_y: float, steps: int = None):
    """
    Moves the mouse along a realistic curved Bezier path with organic acceleration and deceleration.
    """
    global _mouse_pos
    start_x, start_y = _mouse_pos[0], _mouse_pos[1]
    
    distance = ((target_x - start_x)**2 + (target_y - start_y)**2)**0.5
    if steps is None:
        steps = max(12, min(35, int(distance / 25)))
        
    ctrl1_x = start_x + (target_x - start_x) * random.uniform(0.1, 0.4) + random.uniform(-40, 40)
    ctrl1_y = start_y + (target_y - start_y) * random.uniform(0.1, 0.4) + random.uniform(-40, 40)
    ctrl2_x = start_x + (target_x - start_x) * random.uniform(0.6, 0.9) + random.uniform(-30, 30)
    ctrl2_y = start_y + (target_y - start_y) * random.uniform(0.6, 0.9) + random.uniform(-30, 30)
    
    for i in range(1, steps + 1):
        t = i / steps
        eased_t = t * t * (3.0 - 2.0 * t)  # Smooth ease-in-out
        
        cur_x = _bezier_coord(start_x, ctrl1_x, ctrl2_x, target_x, eased_t)
        cur_y = _bezier_coord(start_y, ctrl1_y, ctrl2_y, target_y, eased_t)
        
        try:
            page.mouse.move(cur_x, cur_y)
        except Exception:
            pass
            
        time.sleep(random.uniform(0.008, 0.022))
        
    _mouse_pos = [target_x, target_y]

def human_click(page, target) -> bool:
    """
    Smoothly approaches element, hovers with natural offset from center,
    presses down, holds briefly, and releases (real human click).
    """
    element = page.query_selector(target) if isinstance(target, str) else target
    if not element:
        return False
        
    try:
        element.scroll_into_view_if_needed(timeout=4000)
        box = element.bounding_box()
        if not box:
            return False
            
        target_x = box["x"] + box["width"] * random.uniform(0.25, 0.75)
        target_y = box["y"] + box["height"] * random.uniform(0.25, 0.75)
        
        human_move_to(page, target_x, target_y)
        time.sleep(random.uniform(0.15, 0.38))
        
        page.mouse.down()
        time.sleep(random.uniform(0.07, 0.16))
        page.mouse.up()
        
        human_delay(0.4, 1.2)
        return True
    except Exception:
        try:
            element.click()
            return True
        except Exception:
            return False

def human_scroll(page, steps=3, allow_backtrack=True):
    """
    Organic human scrolling:
    - Multi-tick deceleration
    - 18% chance of small backtrack (scrolling back up to re-read)
    - Reading pauses between scroll impulses
    """
    for s in range(steps):
        if allow_backtrack and s > 0 and random.random() < 0.18:
            back_amount = -random.randint(120, 260)
            ticks = random.randint(4, 7)
            for _ in range(ticks):
                page.mouse.wheel(0, back_amount / ticks)
                time.sleep(random.uniform(0.015, 0.035))
            time.sleep(random.uniform(1.2, 2.5))
            
        total_scroll = random.randint(320, 680)
        ticks = random.randint(6, 11)
        for _ in range(ticks):
            tick_amount = (total_scroll / ticks) * random.uniform(0.8, 1.2)
            page.mouse.wheel(0, tick_amount)
            time.sleep(random.uniform(0.02, 0.05))
            
        human_delay(1.0, 2.8)

def human_idle_noise(page):
    """Occasional idle micro-movements to mimic active user presence."""
    try:
        rand_x = random.randint(250, 950)
        rand_y = random.randint(200, 650)
        human_move_to(page, rand_x, rand_y, steps=random.randint(10, 18))
        time.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass

if __name__ == "__main__":
    print("Testing browser context launch with human mimicry...")
    pw, ctx, page = get_browser_context(headless=True)
    page.goto("https://x.com", wait_until="domcontentloaded")
    print("Page title:", page.title())
    human_idle_noise(page)
    human_scroll(page, steps=2)
    ctx.close()
    pw.stop()
    print("Browser test completed successfully.")
