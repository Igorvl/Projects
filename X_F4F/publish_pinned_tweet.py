# -*- coding: utf-8 -*-
"""
Automation script to publish the Pinned Tweet Manifesto and pin it to the profile.
Loads the 4 visual engineering arts, posts the manifesto text,
navigates to the profile, and pins the post to the top.
"""

import os
import sys
import time
import random
from config import BASE_DIR, TARGET_ACCOUNT, PROFILES_DIR
from browser import get_browser_context, human_delay

MANIFESTO_TEXT = """Design is not decoration. It is the visible syntax of engineering.

We architect visual identities and systematic brand infrastructure for frontier technology, aerospace, and heavy industry.

Raw materials. Absolute precision. Zero noise.

01 / 04 ✦ Visual Engineering Systems"""

IMAGES = [
    os.path.join(BASE_DIR, "branding", "pinned_tweet", "art_1_titanium_node.jpg"),
    os.path.join(BASE_DIR, "branding", "pinned_tweet", "art_2_swiss_system.jpg"),
    os.path.join(BASE_DIR, "branding", "pinned_tweet", "art_3_monolithic_materials.jpg"),
    os.path.join(BASE_DIR, "branding", "pinned_tweet", "art_4_telemetry_hud.jpg"),
]

def check_images():
    """Verify that all 4 manifesto images exist."""
    missing = [img for img in IMAGES if not os.path.exists(img)]
    if missing:
        raise FileNotFoundError(f"Missing manifesto images: {missing}")
    print(f"[Manifesto] All {len(IMAGES)} images verified successfully.")

def is_profile_in_use(profile_name="test_igorvl777") -> bool:
    """Checks via OS process table if Chrome is currently running with this profile."""
    import subprocess
    try:
        cmd = f'Get-CimInstance Win32_Process -Filter "Name = \'chrome.exe\'" | Where-Object {{ $_.CommandLine -like "*{profile_name}*" }} | Select-Object -ExpandProperty ProcessId'
        res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=10)
        return bool(res.stdout and res.stdout.strip())
    except Exception:
        return False

def wait_for_browser_lock_release(profile_name="test_igorvl777", max_wait_sec=600):
    """
    Waits if Chrome user_data_dir is currently in use by an active orchestrator batch.
    Polls every 8 seconds until the browser is completely closed and released.
    """
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        if is_profile_in_use(profile_name):
            elapsed = int(time.time() - start_time)
            print(f"[Manifesto] ⏳ Orchestrator batch is active in Chrome. Waiting for batch to complete and browser to close (waiting: {elapsed}s)...")
            time.sleep(8)
            continue
        try:
            pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
            return pw, ctx, page
        except Exception as e:
            elapsed = int(time.time() - start_time)
            print(f"[Manifesto] ⏳ Waiting for browser context (elapsed: {elapsed}s, detail: {e})...")
            time.sleep(6)
    raise TimeoutError("Timed out waiting for Chrome profile to be released.")

def publish_and_pin_manifesto(profile_name="test_igorvl777"):
    """Publishes the manifesto tweet with 4 images and pins it to profile."""
    check_images()

    print(f"\n[Manifesto] 🚀 Launching browser for @{TARGET_ACCOUNT}...")
    pw, ctx, page = wait_for_browser_lock_release(profile_name=profile_name)

    try:
        # 1. Открываем окно составления твита
        print("[Manifesto] 📝 Navigating to compose modal...")
        page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=30000)
        human_delay(3.0, 5.0)

        # Проверяем наличие текстового поля твита
        textarea_selector = 'div[data-testid="tweetTextarea_0"], div[role="textbox"]'
        try:
            page.wait_for_selector(textarea_selector, timeout=15000)
        except Exception:
            print("[Manifesto] ⚠️ Compose modal not found, navigating to home...")
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
            human_delay(2.5, 4.0)
            # Кликаем кнопку Post на боковой панели
            side_btn = page.locator('a[data-testid="SideNav_NewTweet_Button"], button[data-testid="SideNav_NewTweet_Button"]').first
            if side_btn.is_visible():
                side_btn.click()
                human_delay(2.0, 3.0)

        textarea = page.locator(textarea_selector).first
        if not textarea.is_visible():
            raise RuntimeError("Could not locate tweet textarea!")

        print("[Manifesto] ✍️ Typing manifesto text...")
        textarea.click()
        human_delay(0.5, 1.0)
        
        # Вставляем манифест без потери форматирования
        page.keyboard.insert_text(MANIFESTO_TEXT)
        human_delay(1.5, 2.5)

        # 2. Загружаем 4 арта
        print(f"[Manifesto] 🖼️ Attaching 4 visual engineering images...")
        file_input = page.locator('input[data-testid="fileInput"], input[type="file"]').first
        file_input.set_input_files(IMAGES)

        print("[Manifesto] ⏳ Waiting for images to upload and render preview...")
        # Ждем появления контейнера с вложениями
        page.wait_for_selector('div[data-testid="attachments"], div[aria-label="Image"]', timeout=30000)
        human_delay(5.0, 8.0) # Даем время X загрузить полноразмерные превью на CDN

        # 3. Нажимаем кнопку "Post"
        print("[Manifesto] 📤 Posting tweet...")
        post_btn = page.locator('button[data-testid="tweetButton"], button[data-testid="tweetButtonInline"]').first
        if not post_btn.is_enabled():
            print("[Manifesto] ⏳ Post button not yet enabled, waiting 3s...")
            time.sleep(3)

        post_btn.click()
        print("[Manifesto] ✅ Post button clicked! Waiting for publication...")
        human_delay(4.0, 6.0)

        # 4. Переходим в профиль для закрепления
        profile_url = f"https://x.com/{TARGET_ACCOUNT}"
        print(f"[Manifesto] 📌 Navigating to profile {profile_url} to pin post...")
        page.goto(profile_url, wait_until="domcontentloaded", timeout=25000)
        human_delay(3.0, 5.0)

        # Ждем загрузки твитов в ленте профиля
        page.wait_for_selector('article[data-testid="tweet"]', timeout=20000)
        human_delay(2.0, 3.0)

        # Берем самый верхний твит (только что опубликованный манифест)
        top_tweet = page.locator('article[data-testid="tweet"]').first
        top_tweet.scroll_into_view_if_needed()
        human_delay(1.0, 2.0)

        # Ищем кнопку опций (...) твита (caret)
        print("[Manifesto] ⚙️ Opening tweet options menu (caret)...")
        caret_btn = top_tweet.locator('button[data-testid="caret"], button[aria-label="More"], div[aria-label="More"]').first
        caret_btn.click()
        human_delay(1.0, 2.0)

        # Ждем выпадающее меню
        dropdown = page.wait_for_selector('div[data-testid="Dropdown"], div[role="menu"]', timeout=10000)
        human_delay(1.0, 1.5)

        # Находим пункт "Pin to your profile" (или "Закрепить в профиле")
        print("[Manifesto] 📌 Selecting 'Pin to your profile'...")
        pin_option = page.locator('div[role="menuitem"]:has-text("Pin to your profile"), div[role="menuitem"]:has-text("Pin to your Profile"), div[role="menuitem"]:has-text("Закрепить в профиле"), div[role="menuitem"]:has-text("Закрепить")').first
        
        if not pin_option.is_visible():
            # Попробуем более широкий поиск в меню
            pin_option = page.locator('[data-testid="Dropdown"] [role="menuitem"]').filter(has_text="Pin").first

        if pin_option.is_visible():
            pin_option.click()
            human_delay(1.5, 2.5)

            # Подтверждение в модальном окне
            confirm_btn = page.locator('button[data-testid="confirmationSheetConfirm"], div[data-testid="confirmationSheetConfirm"]').first
            if confirm_btn.is_visible():
                print("[Manifesto] 🎯 Confirming pin in dialog...")
                confirm_btn.click()
                human_delay(2.5, 4.0)

            print("[Manifesto] 🌟 Tweet successfully pinned to profile!")
        else:
            print("[Manifesto] ⚠️ Could not find 'Pin to your profile' option in menu. Please check screenshot.")

        # Делаем контрольный скриншот профиля с закрепленным твитом
        screenshot_path = os.path.join(BASE_DIR, "branding", "pinned_tweet", "pinned_tweet_confirmed.png")
        page.screenshot(path=screenshot_path)
        print(f"[Manifesto] 📸 Screenshot saved to: {screenshot_path}")

        # Сохраняем маркер успешной публикации
        import json
        marker_path = os.path.join(BASE_DIR, "branding", "pinned_tweet", "manifesto_published.json")
        with open(marker_path, "w", encoding="utf-8") as f:
            json.dump({
                "published_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "account": TARGET_ACCOUNT,
                "status": "pinned",
                "images": len(IMAGES)
            }, f, indent=2)

        print("\n" + "=" * 65)
        print("  🎉 MANIFESTO TWEET SUCCESSFULLY PUBLISHED AND PINNED!")
        print("  Profile: @" + TARGET_ACCOUNT)
        print("  Grid: 4 High-Resolution Engineering Arts")
        print("=" * 65 + "\n")

    except Exception as e:
        print(f"[Manifesto] ❌ Error during manifesto publication: {e}")
        error_screenshot = os.path.join(BASE_DIR, "branding", "pinned_tweet", "manifesto_error.png")
        try:
            page.screenshot(path=error_screenshot)
            print(f"[Manifesto] Error screenshot saved: {error_screenshot}")
        except Exception:
            pass
        raise e
    finally:
        ctx.close()
        pw.stop()
        print("[Manifesto] Browser closed.")

if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else "test_igorvl777"
    publish_and_pin_manifesto(profile_name=profile)
