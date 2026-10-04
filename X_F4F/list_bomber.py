# -*- coding: utf-8 -*-
"""
Scheme 3: Ego-List Bombing Automation Engine.
Manages prestigious public Twitter lists and curates candidates to trigger
high-priority system push notifications to target creators.
"""

import random
import time
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from browser import (
    get_browser_context,
    human_delay,
    human_click,
    human_scroll,
    human_type,
    wait_for_x_page_load,
    handle_x_retry_button,
    test_x_connectivity,
    wait_for_x_channel_recovery
)
from config import (
    BASE_DIR,
    DAILY_LIST_ADD_LIMIT,
    EGO_LIST_DEFAULT_NAME,
    EGO_LIST_MIN_SCORE,
    LIST_ADD_DELAY_SECONDS,
    TARGET_ACCOUNT
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
    Enforces Twitter/X 25-character list name maximum limit.
    """
    if len(list_name) > 25:
        list_name = list_name[:25].strip()

    print(f"[List Bomber] Verifying existence of public list: '{list_name}' ({len(list_name)}/25 chars)...")
    try:
        # 1. Check /i/lists with scrolling to ensure 'Your Lists' section is hydrated in DOM
        try:
            page.goto("https://x.com/i/lists", wait_until="domcontentloaded", timeout=30000)
            wait_for_x_page_load(page, ready_selector='div[data-testid="cellInnerDiv"], div[data-testid="primaryColumn"], main[role="main"]', max_wait_sec=8.0, max_retries=2)
            handle_x_retry_button(page)
            human_delay(1.5, 2.5)

            # Smooth scrolling down to trigger GraphQL hydration for "Your Lists" section
            for _ in range(3):
                page.mouse.wheel(0, 450)
                human_delay(0.8, 1.5)

            try:
                page_text = page.inner_text("body")
            except Exception:
                page_text = ""

            recognized_lists = [list_name.lower(), "top 1% designers", "frontier designers"]
            if any(term in page_text.lower() for term in recognized_lists):
                print(f"[List Bomber] ✅ Verified: Public ego list '{list_name}' exists in Your Lists.")
                return True
        except Exception as e:
            print(f"[List Bomber] Lists page check notice: {e}")

        # 2. Check target account lists directly: /account/lists
        lists_url = f"https://x.com/{TARGET_ACCOUNT}/lists"
        try:
            page.goto(lists_url, wait_until="domcontentloaded", timeout=30000)
            wait_for_x_page_load(page, ready_selector='div[data-testid="cellInnerDiv"], div[data-testid="primaryColumn"], main[role="main"]', max_wait_sec=8.0, max_retries=2)
            handle_x_retry_button(page)
            human_delay(1.5, 2.5)

            for _ in range(2):
                page.mouse.wheel(0, 400)
                human_delay(0.8, 1.5)

            try:
                page_text = page.inner_text("body")
            except Exception:
                page_text = ""

            if any(term in page_text.lower() for term in [list_name.lower(), "top 1% designers", "frontier designers"]):
                print(f"[List Bomber] ✅ Verified: Public list '{list_name}' exists on @{TARGET_ACCOUNT}/lists.")
                return True
        except Exception:
            pass

        print(f"[List Bomber] List '{list_name}' not found. Creating it now...")
        
        # 1. Look for "New List" button on page or navigate
        create_btn = (
            page.query_selector('a[href="/i/lists/create"]') or
            page.query_selector('a[aria-label="Create a List"]') or
            page.query_selector('a[aria-label="New List"]') or
            page.query_selector('a[aria-label="Создать список"]') or
            page.query_selector('button[data-testid="createListButton"]') or
            page.query_selector('a[href*="/lists/create"]')
        )
        if create_btn:
            print("[List Bomber] Clicking 'New List' button...")
            human_click(page, create_btn)
            human_delay(2.0, 3.5)
        else:
            print("[List Bomber] Navigating to https://x.com/i/lists/create...")
            page.goto("https://x.com/i/lists/create", wait_until="domcontentloaded", timeout=25000)
            wait_for_x_page_load(page, max_wait_sec=6.0)
            handle_x_retry_button(page)
            human_delay(2.0, 3.5)

        # 2. Wait for modal dialog or input field
        try:
            page.wait_for_selector('div[role="dialog"], input[name="name"], input[data-testid="listNameInput"]', timeout=8000)
        except Exception:
            pass

        # 3. Name input field (max 25 characters in X)
        name_input = (
            page.query_selector('div[role="dialog"] input[name="name"]') or
            page.query_selector('input[name="name"]') or
            page.query_selector('input[data-testid="listNameInput"]') or
            page.query_selector('div[role="dialog"] input[type="text"]') or
            page.query_selector('input[placeholder*="Name"]') or
            page.query_selector('input[placeholder*="Имя"]')
        )

        if not name_input:
            print("[List Bomber] ⚠️ Name input field not found in dialog!")
            return False

        print(f"[List Bomber] Entering list name: '{list_name}'...")
        human_click(page, name_input)
        human_delay(0.5, 1.0)
        name_input.fill(list_name)
        human_delay(0.5, 1.0)
        page.keyboard.press("Space")
        page.keyboard.press("Backspace")
        human_delay(0.5, 1.0)

        # 4. Description input field
        desc_input = (
            page.query_selector('div[role="dialog"] textarea[name="description"]') or
            page.query_selector('textarea[name="description"]') or
            page.query_selector('textarea[data-testid="listDescriptionInput"]') or
            page.query_selector('div[role="dialog"] textarea') or
            page.query_selector('textarea[placeholder*="Description"]')
        )
        if desc_input:
            human_click(page, desc_input)
            human_delay(0.5, 1.0)
            desc_input.fill("Curated index of exceptional visual systems architects and frontier designers.")
            human_delay(0.5, 1.0)

        # 5. CRITICAL: Ensure "Make private" checkbox is UNCHECKED
        private_toggle = (
            page.query_selector('div[role="dialog"] input[type="checkbox"][name="is_private"]') or
            page.query_selector('input[type="checkbox"][name="is_private"]') or
            page.query_selector('[data-testid="privateListToggle"]')
        )
        if private_toggle and private_toggle.is_checked():
            print("[List Bomber] Unchecking private toggle...")
            human_click(page, private_toggle)
            human_delay(0.5, 1.0)

        # 6. Click Next / Save / Create button
        # In Twitter/X, Step 1 top-right button is "Next" (or "Save" / "Далее")
        save_btn = (
            page.query_selector('button[data-testid="listCreateSaveButton"]') or
            page.query_selector('button[data-testid="listCreateNextButton"]') or
            page.query_selector('div[role="dialog"] button:has-text("Next")') or
            page.query_selector('div[role="dialog"] button:has-text("Save")') or
            page.query_selector('div[role="dialog"] button:has-text("Create")') or
            page.query_selector('div[role="dialog"] button:has-text("Далее")') or
            page.query_selector('div[role="dialog"] button:has-text("Сохранить")') or
            page.query_selector('div[role="dialog"] button:has-text("Создать")') or
            page.query_selector('button[role="button"]:has-text("Save")') or
            page.query_selector('button[role="button"]:has-text("Next")')
        )

        if not save_btn:
            # Fallback to dialog header primary button
            save_btn = page.query_selector('div[role="dialog"] div[data-testid="toolBar"] button:not([aria-label="Close"]):not([aria-label="Назад"])')

        if not save_btn:
            print("[List Bomber] ⚠️ Save/Next button not found in list modal!")
            return False

        btn_txt = save_btn.inner_text().strip() if save_btn else "Action"
        print(f"[List Bomber] Clicking list modal button: '{btn_txt}'...")
        human_click(page, save_btn)
        human_delay(2.5, 4.0)

        # 7. Check if Step 2 ("Add to your List" with 'Done' button) appeared
        done_btn = (
            page.query_selector('button[data-testid="listCreateDoneButton"]') or
            page.query_selector('div[role="dialog"] button:has-text("Done")') or
            page.query_selector('div[role="dialog"] button:has-text("Готово")') or
            page.query_selector('div[role="dialog"] button:has-text("Save")')
        )
        if done_btn and done_btn.is_visible():
            print(f"[List Bomber] Step 2: Clicking '{done_btn.inner_text().strip()}' to finalize list...")
            human_click(page, done_btn)
            human_delay(2.0, 3.5)

        # 8. Check if modal needs close
        try:
            close_btn = page.query_selector('div[role="dialog"] button[aria-label="Close"]')
            if close_btn and close_btn.is_visible():
                human_click(page, close_btn)
                human_delay(1.0, 2.0)
        except Exception:
            pass

        print(f"[List Bomber] 🎉 Successfully created public list: '{list_name}'!")
        return True

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
    if len(list_name) > 25:
        list_name = list_name[:25].strip()

    clean_user = username.replace("@", "").strip()
    url = f"https://x.com/{clean_user}"
    
    try:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"  [List Bomber] ⚠️ Navigation timeout to @{clean_user}: {e}. Testing channel...")
            wait_for_x_channel_recovery(page, max_standby_min=10, check_interval_sec=15)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Robust wait for profile to load (UserName in main container)
        try:
            page.wait_for_selector('div[data-testid="UserName"]', timeout=15000)
        except Exception:
            pass
        wait_for_x_page_load(page, ready_selector='div[data-testid="UserName"]', max_wait_sec=8.0)
        handle_x_retry_button(page)
        human_delay(1.0, 2.0)

        # 1. Locate user actions '...' button in profile header (scoped to primary column / main)
        main_container = page.locator('main[role="main"], div[data-testid="primaryColumn"]').first
        if main_container.count() > 0 and main_container.is_visible():
            actions_btn = main_container.locator('button[data-testid="userActions"], div[data-testid="userActions"]').first
        else:
            actions_btn = page.locator('button[data-testid="userActions"], div[data-testid="userActions"]').first

        if actions_btn.count() == 0 or not actions_btn.is_visible():
            print(f"  [List Bomber] Actions button '...' not found on @{clean_user}")
            log_action(clean_user, "list_add", success=False, error="actions_button_not_found")
            return False

        try:
            actions_btn.click(timeout=3000)
        except Exception:
            human_click(page, actions_btn)
        human_delay(1.5, 2.5)

        # 2. In dropdown menu, locate 'Add/remove from Lists' item
        # Live DOM: <a href="/i/lists/add_member" role="menuitem"> with text 'Add/remove from Lists'
        add_item = page.locator('[role="menuitem"][href="/i/lists/add_member"], [role="menuitem"]:has-text("Add/remove"), [role="menuitem"]:has-text("Внести")').first
        if add_item.count() == 0 or not add_item.is_visible():
            menu_items = page.locator('[role="menuitem"]').all()
            for mi in menu_items:
                try:
                    txt = mi.inner_text().strip().lower()
                    href = mi.get_attribute("href") or ""
                    if ("lists" in txt or "списк" in txt) and "view" not in txt and not href.endswith("/lists"):
                        add_item = mi
                        break
                except Exception:
                    continue

        if not add_item or add_item.count() == 0 or not add_item.is_visible():
            print(f"  [List Bomber] [Warning] 'Add/remove from Lists' menu option not found for @{clean_user}")
            page.keyboard.press("Escape")
            log_action(clean_user, "list_add", success=False, error="menu_item_not_found")
            return False

        print(f"  [List Bomber] Opening Lists modal for @{clean_user}...")
        initial_url = page.url
        try:
            add_item.click(timeout=3000)
        except Exception:
            human_click(page, add_item)
        human_delay(1.5, 2.5)

        # Detect accidental navigation
        if page.url != initial_url and "/lists" in page.url and "/add_member" not in page.url:
            print(f"  [List Bomber] [Warning] Accidental navigation to {page.url}, returning to profile...")
            page.go_back(wait_until="domcontentloaded")
            human_delay(2.0, 3.0)
            log_action(clean_user, "list_add", success=False, error="navigated_away")
            return False

        # 3. Explicitly wait for VISIBLE modal dialog to mount in DOM
        # Note: Twitter renders multiple div[role="dialog"] containers; only one is visible.
        try:
            page.wait_for_selector('div[role="dialog"]', timeout=8000)
        except Exception:
            pass

        modal = None
        dialogs = page.locator('div[role="dialog"]').all()
        for d in dialogs:
            if d.is_visible():
                modal = d
                break

        if not modal or not modal.is_visible():
            print(f"  [List Bomber] List selection dialog did not open for @{clean_user}")
            try:
                err_shot = os.path.join(BASE_DIR, "branding", f"list_dialog_err_{clean_user}.png")
                page.screenshot(path=err_shot)
            except Exception:
                pass
            page.keyboard.press("Escape")
            log_action(clean_user, "list_add", success=False, error="dialog_not_found")
            return False

        human_delay(1.0, 1.8)

        # 4. Strictly target our public ego list row: 'Top 1% Designers'
        # In live DOM: <div role="checkbox" data-testid="listCell"> or [role="checkbox"]
        clean_target_keyword = "Top 1% Designers"
        list_row = modal.locator('div[role="checkbox"], [data-testid="listCell"]').filter(has_text=clean_target_keyword).first
        if list_row.count() == 0:
            list_row = modal.locator('[role="button"], div[data-testid*="list" i]').filter(has_text=clean_target_keyword).first

        if list_row.count() == 0 or not list_row.is_visible():
            print(f"  [List Bomber] List '{clean_target_keyword}' not found in modal for @{clean_user}")
            close_btn = modal.locator('button[aria-label="Close"], [data-testid="app-bar-close"]').first
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
            else:
                page.keyboard.press("Escape")
            log_action(clean_user, "list_add", success=False, error="list_not_in_modal")
            return False

        # Check aria-checked attribute to avoid toggling off
        checked = list_row.get_attribute("aria-checked")
        if checked == "true":
            print(f"  [List Bomber] [Info] @{clean_user} is ALREADY in list '{list_name}'!")
        else:
            print(f"  [List Bomber] Toggling ego list checkbox for @{clean_user}...")
            try:
                list_row.click(timeout=3000)
            except Exception:
                human_click(page, list_row)
            human_delay(1.0, 1.8)

        # 5. Click Save button in modal
        save_btn = modal.locator('button[role="button"], button').filter(has_text="Save").first
        if save_btn.count() == 0:
            save_btn = modal.locator('button[role="button"], button').filter(has_text="Сохранить").first
        if save_btn.count() == 0:
            save_btn = modal.locator('button[data-testid="listSaveButton"], button:has-text("Done")').first

        if save_btn.count() > 0 and save_btn.is_visible():
            try:
                save_btn.click(timeout=3000)
            except Exception:
                human_click(page, save_btn)
            human_delay(1.5, 2.5)
            print(f"  [List Bomber] [Success] Added @{clean_user} to public list '{list_name}'! (Push notification triggered)")
            log_action(clean_user, "list_add", success=True)
            return True
        else:
            close_btn = modal.locator('button[aria-label="Close"], [data-testid="app-bar-close"]').first
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
            else:
                page.keyboard.press("Escape")
            print(f"  [List Bomber] [Success] Added @{clean_user} to list (auto-close applied)!")
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
