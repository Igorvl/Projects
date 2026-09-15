# -*- coding: utf-8 -*-
"""
Scheme 3: Ego-List Bombing Automation Engine.
Manages prestigious public Twitter lists and curates candidates to trigger
high-priority system push notifications to target creators.
"""

import random
import time
import sys
from browser import (
    get_browser_context,
    human_delay,
    human_click,
    human_scroll,
    human_type
)
from config import (
    DAILY_LIST_ADD_LIMIT,
    EGO_LIST_DEFAULT_NAME,
    EGO_LIST_MIN_SCORE,
    LIST_ADD_DELAY_SECONDS
)
from database import (
    get_candidates_for_list_bombing,
    get_today_list_adds,
    log_action
)

def ensure_ego_list_exists(page, list_name: str = EGO_LIST_DEFAULT_NAME) -> bool:
    """
    Checks if the designated public ego list exists under current account.
    If not, navigates to Lists creation page and creates it publicly.
    """
    print(f"[List Bomber] Verifying existence of public list: '{list_name}'...")
    try:
        page.goto("https://x.com/i/lists", wait_until="domcontentloaded", timeout=20000)
        human_delay(2.0, 3.5)

        # Check if list name is already present on page
        page_text = page.inner_text("body")
        if list_name.lower() in page_text.lower() or "Frontier Designers" in page_text:
            print(f"[List Bomber] ✅ Verified: Public list '{list_name}' exists.")
            return True

        print(f"[List Bomber] List '{list_name}' not found. Creating it now...")
        
        # Click "New List" button
        create_btn = page.query_selector('a[href="/i/lists/create"]') or page.query_selector('button[data-testid="createListButton"]')
        if not create_btn:
            # Fallback direct URL
            page.goto("https://x.com/i/lists/create", wait_until="domcontentloaded", timeout=15000)
            human_delay(2.0, 3.0)
        else:
            human_click(page, create_btn)
            human_delay(1.5, 2.5)

        # Name input field
        name_input = page.query_selector('input[name="name"]') or page.query_selector('input[data-testid="listNameInput"]')
        if name_input:
            human_click(page, name_input)
            human_delay(0.5, 1.0)
            human_type(page, name_input, list_name)
            human_delay(0.8, 1.5)

        # Description input field
        desc_input = page.query_selector('textarea[name="description"]') or page.query_selector('textarea[data-testid="listDescriptionInput"]')
        if desc_input:
            human_click(page, desc_input)
            human_delay(0.5, 1.0)
            human_type(page, desc_input, "Curated index of exceptional visual systems architects, frontier tech designers, and computational artists.")
            human_delay(0.8, 1.5)

        # CRITICAL: Ensure "Make private" checkbox is UNCHECKED (must be PUBLIC to trigger notifications!)
        private_toggle = page.query_selector('input[type="checkbox"][name="is_private"]') or page.query_selector('[data-testid="privateListToggle"]')
        if private_toggle and private_toggle.is_checked():
            human_click(page, private_toggle)
            human_delay(0.5, 1.0)

        # Click Save / Create button
        save_btn = page.query_selector('button[data-testid="listCreateSaveButton"]') or page.query_selector('button:has-text("Save")') or page.query_selector('button:has-text("Сохранить")')
        if save_btn:
            human_click(page, save_btn)
            human_delay(2.0, 3.5)
            print(f"[List Bomber] 🎉 Successfully created public list: '{list_name}'!")
            return True

        return False

    except Exception as e:
        print(f"[List Bomber] Notice during list verification: {e}")
        return False

def add_user_to_list(page, username: str, list_name: str = EGO_LIST_DEFAULT_NAME) -> bool:
    """
    Navigates to candidate profile, opens '...' user actions menu,
    selects 'Add/remove from Lists', checks the public list, and saves.
    This triggers a system push notification:
    'Gerrit Brandt added you to the list [list_name]'.
    """
    clean_user = username.replace("@", "").strip()
    url = f"https://x.com/{clean_user}"
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        human_delay(2.0, 3.5)

        # 1. Locate user actions '...' button in profile header
        actions_btn = page.query_selector('button[data-testid="userActions"]')
        if not actions_btn:
            print(f"  [List Bomber] Actions button '...' not found on @{clean_user}")
            log_action(clean_user, "list_add", success=False, error="actions_button_not_found")
            return False

        human_click(page, actions_btn)
        human_delay(1.0, 2.0)

        # 2. In dropdown menu, locate 'Add/remove @user from Lists' item
        list_menu_item = (
            page.query_selector('[data-testid="listAddRemove"]') or
            page.query_selector('div[role="menuitem"]:has-text("Lists")') or
            page.query_selector('div[role="menuitem"]:has-text("Списки")')
        )
        if not list_menu_item:
            print(f"  [List Bomber] 'Lists' menu option not found for @{clean_user}")
            page.keyboard.press("Escape")
            log_action(clean_user, "list_add", success=False, error="menu_item_not_found")
            return False

        human_click(page, list_menu_item)
        human_delay(1.5, 2.5)

        # 3. In the modal dialog, find our target list
        modal = page.locator('div[role="dialog"]')
        if modal.count() == 0:
            print(f"  [List Bomber] List selection dialog did not open for @{clean_user}")
            log_action(clean_user, "list_add", success=False, error="dialog_not_found")
            return False

        list_entry = modal.locator(f'span:has-text("{list_name}")')
        if list_entry.count() == 0:
            list_entry = modal.locator('span:has-text("Frontier"), span:has-text("Visual")')

        if list_entry.count() == 0:
            print(f"  [List Bomber] List '{list_name}' not available in selection modal for @{clean_user}")
            close_btn = modal.locator('button[aria-label="Close"], [data-testid="app-bar-close"]')
            if close_btn.count() > 0:
                human_click(page, close_btn.first)
            log_action(clean_user, "list_add", success=False, error="list_not_in_modal")
            return False

        # Click list item row to toggle checkbox
        human_click(page, list_entry.first)
        human_delay(0.8, 1.5)

        # 4. Click Save button in modal
        save_btn = (
            modal.locator('button[data-testid="listSaveButton"]') or
            modal.locator('button:has-text("Save")') or
            modal.locator('button:has-text("Сохранить")')
        )
        if save_btn.count() > 0:
            human_click(page, save_btn.first)
            human_delay(1.5, 2.5)
            print(f"  [List Bomber] 🏆 Added @{clean_user} to public list '{list_name}'! (Push notification triggered)")
            log_action(clean_user, "list_add", success=True)
            return True
        else:
            close_btn = modal.locator('button[aria-label="Close"], [data-testid="app-bar-close"]')
            if close_btn.count() > 0:
                human_click(page, close_btn.first)
            print(f"  [List Bomber] 🏆 Added @{clean_user} to list (auto-close applied)!")
            log_action(clean_user, "list_add", success=True)
            return True

    except Exception as e:
        print(f"  [List Bomber] Error adding @{clean_user} to list: {e}")
        log_action(clean_user, "list_add", success=False, error=str(e))
        return False

def run_list_bombing_batch(profile_name="test_igorvl777", batch_size=8, list_name=EGO_LIST_DEFAULT_NAME):
    """
    Executes a controlled batch of public list additions for top candidates.
    Respects DAILY_LIST_ADD_LIMIT and applies human composure delays.
    """
    adds_today = get_today_list_adds()
    if adds_today >= DAILY_LIST_ADD_LIMIT:
        print(f"[List Bomber] Daily list addition limit reached ({adds_today}/{DAILY_LIST_ADD_LIMIT}). Halting.")
        return

    allowed_count = min(batch_size, DAILY_LIST_ADD_LIMIT - adds_today)
    candidates = get_candidates_for_list_bombing(limit=allowed_count, min_score=EGO_LIST_MIN_SCORE)

    if not candidates:
        print("[List Bomber] No qualifying candidates found in queue for list addition.")
        return

    print(f"\n" + "=" * 65)
    print(f"  [List Bomber] Starting Ego-List session for {len(candidates)} candidates")
    print(f"  Target List: '{list_name}'")
    print(f"  Progress today: {adds_today}/{DAILY_LIST_ADD_LIMIT}")
    print("=" * 65 + "\n")

    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)

    try:
        # 1. First ensure the public list exists on our account
        ensure_ego_list_exists(page, list_name=list_name)
        human_delay(2.0, 4.0)

        # 2. Process candidates
        for idx, c in enumerate(candidates, 1):
            u = c["username"]
            print(f"\n[List Bomber] [{idx}/{len(candidates)}] Curating @{u} (Score: {c['score']}, Ratio: {c['ratio']})...")
            
            success = add_user_to_list(page, u, list_name=list_name)
            
            if success and idx < len(candidates):
                delay = random.randint(LIST_ADD_DELAY_SECONDS[0], LIST_ADD_DELAY_SECONDS[1])
                print(f"  [List Bomber] Composure pause: {delay}s before next candidate...")
                time.sleep(delay)

        print("\n[List Bomber] Batch completed successfully.")

    except Exception as e:
        print(f"[List Bomber] Batch error: {e}")
    finally:
        try:
            ctx.close()
            pw.stop()
        except Exception:
            pass

if __name__ == "__main__":
    profile = "test_igorvl777"
    count = 5
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        profile = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            count = int(sys.argv[2])
        except ValueError:
            pass
            
    run_list_bombing_batch(profile_name=profile, batch_size=count)
