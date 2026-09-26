"""
import_cookies.py -- Import cookies iz Cookie-Editor v format Playwright.

Instruktsiya:
1. Ustanovite Cookie-Editor: https://cookie-editor.cgagnier.ca/
   (ili poiskat v Chrome Web Store: "Cookie-Editor")
2. Zaydite na https://www.behance.net (dolzhny byt zalogeny)
3. Nazhmite ikonu Cookie-Editor v Chrome
4. Kliknite knopku "Export" (strelka vniz, v nizhnem pravom uglu)
5. Vyberte "Export as JSON" -- skopiruetsya v bufer obmena
6. Sozdayte fayl behance_cookies_export.json v etoy papke i vstavte
7. Zapustite: python import_cookies.py
"""

import json
import os
import sys

INPUT_FILE = "behance_cookies_export.json"
SESSION_FILE = os.path.join("session", "behance_cookies.json")

os.makedirs("session", exist_ok=True)

print("=" * 55)
print("  Import cookies -> Playwright sessiya")
print("=" * 55)

if not os.path.exists(INPUT_FILE):
    print()
    print(f"  OSHIBKA: fayl '{INPUT_FILE}' ne naydyon!")
    print()
    print("  Chto sdelat:")
    print("  1. Otkroyte Chrome")
    print("  2. Zaydite na https://www.behance.net")
    print("     (ubedites chto vy zalogeny)")
    print("  3. Ustanovite Cookie-Editor:")
    print("     https://cookie-editor.cgagnier.ca/")
    print("  4. Kliknite ikonu Cookie-Editor v Chrome")
    print("  5. Kliknite 'Export' -> 'Export as JSON'")
    print("     (skopiruetsya v bufer obmena)")
    print(f"  6. Sozdayte fayl: {INPUT_FILE}")
    print("     i vstavte tuda skopirovanny JSON")
    print("  7. Snova: python import_cookies.py")
    sys.exit(1)

try:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
    raw_cookies = json.loads(content)
except json.JSONDecodeError as e:
    print(f"\n  OSHIBKA: Nekorrektny JSON v {INPUT_FILE}: {e}")
    print("  Ubedites chto v fayle tolko JSON (bez lishnego teksta)")
    sys.exit(1)
except Exception as e:
    print(f"\n  OSHIBKA pri chtenii {INPUT_FILE}: {e}")
    sys.exit(1)

if not isinstance(raw_cookies, list):
    print("\n  OSHIBKA: JSON dolzhen byt massivom [ ... ]")
    sys.exit(1)

playwright_cookies = []
for c in raw_cookies:
    name  = c.get("name", "")
    value = c.get("value", "")
    if not name or not value:
        continue

    domain  = c.get("domain", "")
    expires = c.get("expirationDate", -1)

    # sameSite mapping Cookie-Editor -> Playwright
    same_site_map = {
        "no_restriction": "None",
        "lax":            "Lax",
        "strict":         "Strict",
        "unspecified":    "Lax",
    }
    same_site_raw = (c.get("sameSite") or "lax").lower()
    same_site = same_site_map.get(same_site_raw, "Lax")

    playwright_cookies.append({
        "name":     name,
        "value":    value,
        "domain":   domain,
        "path":     c.get("path", "/"),
        "expires":  float(expires) if expires and float(expires) > 0 else -1,
        "httpOnly": bool(c.get("httpOnly", False)),
        "secure":   bool(c.get("secure", False)),
        "sameSite": same_site,
    })

storage_state = {"cookies": playwright_cookies, "origins": []}

with open(SESSION_FILE, "w", encoding="utf-8") as f:
    json.dump(storage_state, f, indent=2, ensure_ascii=False)

print()
print(f"  [OK] Importirovano {len(playwright_cookies)} cookies")
print(f"  [OK] Sokhraneno -> {SESSION_FILE}")
print()
print("  Teper zapustite: python main.py")
print("=" * 55)
