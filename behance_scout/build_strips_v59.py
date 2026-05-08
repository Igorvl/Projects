"""
build_strips_v59.py
Embeds GEN_v59.txt (pure React/JSX) into an HTML standalone file.
"""
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC = r'C:\Projects\Business\Web_projects_NEW\behance_scout\GEN_v59.txt'
TPL = r'C:\Projects\Business\Web_projects_NEW\behance_scout\strips_template.html'
OUT = r'C:\Projects\Business\Web_projects_NEW\behance_scout\dashboard\templates\strips.html'

# ── HTML template ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>STRIPS PRO GEN — V59: FULL RESTORATION</title>
  <meta name="description" content="K.S.A.R. / P.S.D.N. Prompt Generator. V59 Full Restoration." />

  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', 'system-ui', 'sans-serif'],
            mono: ['"JetBrains Mono"', 'Menlo', 'monospace'],
            serif: ['Georgia', 'serif'],
          }
        }
      }
    }
  </script>

  <!-- Google Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

  <!-- React 18 UMD -->
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>

  <!-- Babel Standalone for JSX -->
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>

  <style>
    * { box-sizing: border-box; }
    body { margin: 0; padding: 0; background: #050608; }
    .custom-scrollbar::-webkit-scrollbar { width: 6px; }
    .custom-scrollbar::-webkit-scrollbar-track { background: #050608; }
    .custom-scrollbar::-webkit-scrollbar-thumb { background: #23262e; border-radius: 4px; }
    .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: #c8aa6e; }
    @media print {
      @page { margin: 0; size: A4; }
      body {
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
        background: white;
      }
    }
  </style>
</head>
<body>
  <div id="root"></div>

  <script type="text/babel">
    const { useState, useEffect, useMemo } = React;

INJECT_JS_HERE

    const rootEl = document.getElementById('root');
    ReactDOM.createRoot(rootEl).render(<App />);
  </script>
</body>
</html>"""

# ── Read source JS ────────────────────────────────────────────────────────────
with open(SRC, 'r', encoding='utf-8-sig', errors='replace') as f:  # utf-8-sig strips BOM
    js_code = f.read()

# Strip module declarations (handled by wrapper)
js_code = re.sub(
    r"^\s*import\s+React\s*,\s*\{[^}]+\}\s*from\s+['\"]react['\"];\s*\n?",
    '',
    js_code,
    flags=re.MULTILINE
)
js_code = re.sub(r"^\s*export\s+default\s+App;\s*$", '', js_code, flags=re.MULTILINE)

# Strip <style dangerouslySetInnerHTML> block (already in <style> tag above)
# We keep it - it won't hurt, just duplicates scrollbar CSS

print(f"JS code length after stripping: {len(js_code):,} chars")
print(f"Lines: {js_code.count(chr(10)):,}")

# Indent the JS code by 4 spaces for readability
js_indented = '\n'.join('    ' + l if l.strip() else '' for l in js_code.split('\n'))

# ── Assemble final HTML ───────────────────────────────────────────────────────
html = HTML_TEMPLATE.replace('INJECT_JS_HERE', js_indented, 1)

# ── Write output ──────────────────────────────────────────────────────────────
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)

size_kb = len(html.encode('utf-8')) / 1024
print(f"\nSUCCESS: strips.html written — {size_kb:.1f} KB")
print(f"Output: {OUT}")

# Quick sanity check
checks = {
    'text/babel': True,
    'tailwindcss': True,
    'const App': True,
    'generatePrompt': True,
    'ReactDOM.createRoot': True,
    'DEFAULT_PROTOCOLS': True,
    'CATEGORIES': True,
    'FILM_STOCKS': True,
    'COMPOSITIONS': True,
    'PLACEHOLDER_CODE': False,
    'import React': False,
    'export default App': False,
}
print("\n=== SANITY CHECKS ===")
all_ok = True
for marker, should_exist in checks.items():
    found = marker in html
    status = 'OK' if found == should_exist else 'FAIL'
    if status == 'FAIL':
        all_ok = False
    print(f"  {status}: {'FOUND' if found else 'MISSING'} [{marker}]")

if all_ok:
    print("\nAll checks passed!")
else:
    print("\nSome checks FAILED — review above")
