import re

with open('r4_utf8.txt', 'r', encoding='utf-8') as f:
    r4 = f.read()

with open('db_utf8.txt', 'r', encoding='utf-8') as f:
    db = f.read()

# Strip import and export
r4 = re.sub(r"import React.*?['\"]react['\"];?", "const { useState, useEffect, useMemo, useCallback, useRef } = React;", r4, count=1)
r4 = re.sub(r"export default App;", "", r4)

# Replace the Lucide icons if any exist in the code, though it looks like it uses raw SVGs or something else.
# Looking at the code: it has some SVGs or might use lucide-react. We'll include lucide script just in case.

html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Strips Pro Gen NEW — Behance Scout</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;900&display=swap" rel="stylesheet" />
  <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
</head>
<body>
<div id="root">
  <div style="padding: 20px; color: #666; font-family: sans-serif;">
    Loading Generator... (If this stays white, check console or script errors)
  </div>
</div>

<script>
  window.onerror = function(msg, url, line, col, error) {{
    document.getElementById('root').innerHTML = `
      <div style="padding: 20px; color: #ff4444; font-family: monospace; background: #fff0f0; border: 1px solid #ffcccc;">
        <b>JS Error:</b> ${{msg}}<br>
        <b>File:</b> ${{url}}<br>
        <b>Line:</b> ${{line}}:${{col}}
      </div>
    `;
    return false;
  }};
</script>

<script type="text/babel" data-presets="react">
{r4}

// --- DATABASE EXPANSION ---
{db}

// --- MERGE LOGIC ---
if(typeof NEW_CATEGORY_8_MATERIALS !== 'undefined') CATEGORIES[8].items.push(...NEW_CATEGORY_8_MATERIALS);
if(typeof NEW_CATEGORY_10_TRIGGERS !== 'undefined') CATEGORIES[10].items.push(...NEW_CATEGORY_10_TRIGGERS);
if(typeof NEW_CATEGORY_6_GRAPHICS !== 'undefined') CATEGORIES[6].items.push(...NEW_CATEGORY_6_GRAPHICS);
if(typeof NEW_CATEGORY_5_STRUCTURE !== 'undefined') CATEGORIES[5].items.push(...NEW_CATEGORY_5_STRUCTURE);
if(typeof NEW_CATEGORY_3_COLORS !== 'undefined') CATEGORIES[3].items.push(...NEW_CATEGORY_3_COLORS);
if(typeof NEW_CATEGORY_2_DNA !== 'undefined') CATEGORIES[2].items.push(...NEW_CATEGORY_2_DNA);

if(typeof EXT_CATEGORY_2_DNA !== 'undefined') CATEGORIES[2].items.push(...EXT_CATEGORY_2_DNA);
if(typeof EXT_CATEGORY_3_COLORS !== 'undefined') CATEGORIES[3].items.push(...EXT_CATEGORY_3_COLORS);
if(typeof EXT_CATEGORY_5_STRUCTURE !== 'undefined') CATEGORIES[5].items.push(...EXT_CATEGORY_5_STRUCTURE);
if(typeof EXT_CATEGORY_6_GRAPHICS !== 'undefined') CATEGORIES[6].items.push(...EXT_CATEGORY_6_GRAPHICS);
if(typeof EXT_CATEGORY_8_MATERIALS !== 'undefined') CATEGORIES[8].items.push(...EXT_CATEGORY_8_MATERIALS);
if(typeof EXT_CATEGORY_10_TRIGGERS !== 'undefined') CATEGORIES[10].items.push(...EXT_CATEGORY_10_TRIGGERS);
if(typeof EXT_CATEGORY_1_SCHOOLS !== 'undefined') CATEGORIES[1].items.push(...EXT_CATEGORY_1_SCHOOLS);
if(typeof EXT_CATEGORY_7_SUPERGRAPHICS !== 'undefined') CATEGORIES[7].items.push(...EXT_CATEGORY_7_SUPERGRAPHICS);
if(typeof EXT_CATEGORY_9_OPTICS !== 'undefined') CATEGORIES[9].items.push(...EXT_CATEGORY_9_OPTICS);
if(typeof EXT_CATEGORY_11_LIGHT !== 'undefined') CATEGORIES[11].items.push(...EXT_CATEGORY_11_LIGHT);

// --- MAY 3 DATA MERGE ---
if(typeof MAY_3_STRUCTURE !== 'undefined') CATEGORIES[5].items.push(...MAY_3_STRUCTURE);
if(typeof MAY_3_COLORS !== 'undefined') CATEGORIES[3].items.push(...MAY_3_COLORS);
if(typeof MAY_3_GRAPHICS !== 'undefined') CATEGORIES[6].items.push(...MAY_3_GRAPHICS);
if(typeof MAY_3_MATERIALS !== 'undefined') CATEGORIES[8].items.push(...MAY_3_MATERIALS);
if(typeof MAY_3_TRIGGERS !== 'undefined') CATEGORIES[10].items.push(...MAY_3_TRIGGERS);

if(typeof LEGACY_COLORS_31_60 !== 'undefined') CATEGORIES[3].items.push(...LEGACY_COLORS_31_60);

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
</script>
</body>
</html>
"""

with open('dashboard/templates/strips.html', 'w', encoding='utf-8') as f:
    f.write(html_template)

print('dashboard/templates/strips.html updated successfully!')
