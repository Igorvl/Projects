# -*- coding: utf-8 -*-
"""
Helper script to open a real browser window once for logging in to X (Twitter).
Cookies and auth state will be automatically saved in the persistent profile folder.
"""

import sys
import time
from browser import get_browser_context
from config import PROFILES_DIR

def login_flow(profile_name="test_igorvl777"):
    print("=" * 60)
    print(f"Запуск браузера для авторизации в профиле: {profile_name}")
    print("Профиль сохраняется в:", PROFILES_DIR)
    print("Пожалуйста, войдите в свой аккаунт X (Twitter).")
    print("После успешного входа закройте окно браузера или нажмите Ctrl+C здесь.")
    print("=" * 60)
    
    pw, ctx, page = get_browser_context(profile_name=profile_name, headless=False)
    page.goto("https://x.com/login", wait_until="domcontentloaded")
    
    logged_in = False
    try:
        while True:
            time.sleep(1)
            try:
                active_pages = [p for p in ctx.pages if not p.is_closed()]
                if not active_pages:
                    print("\nОкно браузера закрыто пользователем.")
                    break
                
                for p in active_pages:
                    try:
                        cur_url = p.url
                        if "x.com/home" in cur_url or "twitter.com/home" in cur_url:
                            if not logged_in:
                                logged_in = True
                                print("\n" + "=" * 60)
                                print("🎉 УСПЕШНАЯ АВТОРИЗАЦИЯ! Обнаружен вход в аккаунт (x.com/home).")
                                print("Сохраняем сессию и завершаем работу через 5 секунд...")
                                print("=" * 60 + "\n")
                                time.sleep(5)
                                return
                    except Exception:
                        pass
            except Exception:
                pass
    except KeyboardInterrupt:
        print("\nЗавершение по запросу...")
    finally:
        try:
            ctx.close()
            pw.stop()
        except Exception:
            pass
        print("Сессия и cookies успешно сохранены!")

if __name__ == "__main__":
    profile = sys.argv[1] if len(sys.argv) > 1 else "test_igorvl777"
    login_flow(profile)
