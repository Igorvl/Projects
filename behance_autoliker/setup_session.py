"""
setup_session.py -- Eksport cookies iz vashego Chrome v Playwright.

Zapustite ODIN RAZ pered pervym zapuskom main.py.
Chrome mozhet byt otkryt -- skript skopirует BD vo vremennyy fayl.

Trebovanie: vy dolzhny byt zalogeny v Behance v Chrome.
"""

import json
import os
import sys

SESSION_FILE = os.path.join("session", "behance_cookies.json")
os.makedirs("session", exist_ok=True)

print("=" * 55)
print("  Behance AutoLiker -- Nastroyka sessii")
print("=" * 55)
print()
print("  Chitayu cookies iz vashego Chrome...")
print("  (Vy dolzhny byt zalogeny v Behance v Chrome)")
print()

try:
    import rookiepy
except ImportError:
    print("  Ustanavlivayu rookiepy...")
    os.system(f'"{sys.executable}" -m pip install rookiepy -q')
    try:
        import rookiepy
    except ImportError:
        print("  OSHIBKA: Ne udalos ustanovit rookiepy.")
        print("  Zapustite: pip install rookiepy")
        sys.exit(1)

# Domeny Behance i Adobe (nuzhny oba dlya avtorizatsii)
TARGET_DOMAINS = ["behance.net", "adobe.com", "adobelogin.com", "account.adobe.com"]

all_cookies = []

for domain in TARGET_DOMAINS:
    try:
        cookies = rookiepy.chrome([domain])
        all_cookies.extend(cookies)
        print(f"  [{domain}]: {len(cookies)} cookies")
    except Exception as e:
        print(f"  [{domain}]: propushcheno ({e})")

if not all_cookies:
    print()
    print("  OSHIBKA: Cookies ne naydeny!")
    print("  Ubedites chto vy zalogeny v Behance v Chrome")
    print("  i Chrome ne zapit.")
    sys.exit(1)

# Konvertiruem v format Playwright storage_state
playwright_cookies = []
for c in all_cookies:
    domain = c.get("host", c.get("domain", ""))
    name = c.get("name", "")
    value = c.get("value", "")

    if not name or not value:
        continue

    expires = c.get("expires", -1)
    # Playwright trebuet float ili -1
    try:
        expires = float(expires) if expires and float(expires) > 0 else -1
    except Exception:
        expires = -1

    playwright_cookies.append({
        "name": name,
        "value": value,
        "domain": domain,
        "path": c.get("path", "/"),
        "expires": expires,
        "httpOnly": bool(c.get("httpOnly", False)),
        "secure": bool(c.get("secure", False)),
        "sameSite": "Lax",
    })

storage_state = {
    "cookies": playwright_cookies,
    "origins": [],
}

with open(SESSION_FILE, "w", encoding="utf-8") as f:
    json.dump(storage_state, f, indent=2)

print()
print(f"  [OK] Sokhraneno {len(playwright_cookies)} cookies -> {SESSION_FILE}")
print()
print("  Teper zapustite: python main.py")
print("=" * 55)
