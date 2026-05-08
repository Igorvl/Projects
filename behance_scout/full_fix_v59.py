"""
full_fix_v59.py
Iteratively finds and fixes ALL syntax errors in GEN_v59.txt
using @babel/parser via node subprocess.
Outputs: _build_cache/GEN_v59_fixed.txt
"""
import sys, io, re, subprocess, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SRC   = r'C:\Projects\Business\Web_projects_NEW\behance_scout\GEN_v59.txt'
OUT   = r'C:\Projects\Business\Web_projects_NEW\behance_scout\_build_cache\GEN_v59_fixed.txt'
STRIP = r'C:\Projects\Business\Web_projects_NEW\behance_scout\_build_cache\strip_and_fix.js'

# ── Node.js helper that tries to parse and returns the first error ────────────
node_tester = r"""
const fs = require('fs');
const babel = require('@babel/core');

const code = fs.readFileSync(process.argv[2], 'utf8');
try {
  babel.parseSync(code, {
    presets: [['@babel/preset-react', { runtime: 'classic' }]],
    filename: 'test.jsx',
  });
  console.log(JSON.stringify({ ok: true }));
} catch(e) {
  console.log(JSON.stringify({
    ok: false,
    line: e.loc ? e.loc.line : null,
    col: e.loc ? e.loc.column : null,
    msg: e.message.substring(0, 200)
  }));
}
"""

with open(STRIP, 'w', encoding='utf-8') as f:
    f.write(node_tester)

# ── Read original source ──────────────────────────────────────────────────────
with open(SRC, 'r', encoding='utf-8-sig', errors='replace') as f:
    code = f.read()

# ── Strip import/export ───────────────────────────────────────────────────────
code = re.sub(r'^\s*import\s+React[^\n]+\n?', '', code, flags=re.MULTILINE)
code = re.sub(r'^\s*export\s+default\s+App;\s*$', '', code, flags=re.MULTILINE)
code = code.replace('M?ller', 'Müller')

# ── Write initial version ─────────────────────────────────────────────────────
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(code)

# ── Iterative fix loop ────────────────────────────────────────────────────────
MAX_ITERS = 50
for iteration in range(MAX_ITERS):
    result = subprocess.run(
        ['node', STRIP, OUT],
        cwd=r'C:\Projects\Business\Web_projects_NEW\behance_scout',
        capture_output=True, text=True, encoding='utf-8'
    )
    try:
        info = json.loads(result.stdout.strip())
    except Exception:
        print(f'Node error: {result.stdout[:200]} | {result.stderr[:200]}')
        break

    if info.get('ok'):
        print(f'\n✅ PARSE OK after {iteration} fixes!')
        break

    line_no = info.get('line')
    col = info.get('col')
    msg = info.get('msg', '')
    print(f'[{iteration+1}] Error at line {line_no} col {col}: {msg[:80]}')

    # Read current code as lines
    with open(OUT, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if line_no is None or line_no > len(lines):
        print('  Cannot locate error line, stopping.')
        break

    err_line = lines[line_no - 1]  # 0-indexed
    prev_line = lines[line_no - 2] if line_no > 1 else ''

    fixed = False

    # Strategy 1: Line ends with } } { ... (two objects merged, no comma/newline)
    # Fix: replace } }  spaces  { with },\n      {
    m = re.search(r'\} \}\s+(\{ id:)', err_line)
    if m and not fixed:
        new_err = err_line[:m.start()] + ' },\n      ' + err_line[m.start(1):]
        lines[line_no - 1] = new_err
        print(f'  Strategy 1: split merged objects on line {line_no}')
        fixed = True

    # Strategy 2: Previous line ends with } without comma, current starts with {
    if not fixed:
        prev_stripped = prev_line.rstrip()
        cur_stripped = err_line.lstrip()
        if re.search(r'\}\s*$', prev_stripped) and not re.search(r',\s*$', prev_stripped):
            if cur_stripped.startswith('{'):
                lines[line_no - 2] = prev_stripped + ',\n'
                print(f'  Strategy 2: add comma to end of line {line_no-1}')
                fixed = True

    # Strategy 3: Line ends with } } { on same line (variant without space after first })
    if not fixed:
        m2 = re.search(r'\}\}\s*(\{)', err_line)
        if m2:
            new_err = err_line[:m2.start()] + '}, ' + err_line[m2.start(1):]
            lines[line_no - 1] = new_err
            print(f'  Strategy 3: insert comma between }}{{ on line {line_no}')
            fixed = True

    # Strategy 4: Object has no closing } before next {
    # Look for unmatched braces in the error line
    if not fixed:
        open_b = err_line.count('{')
        close_b = err_line.count('}')
        if open_b > close_b:
            # Add missing closing braces
            diff = open_b - close_b
            lines[line_no - 1] = err_line.rstrip('\n') + ''.join(['}'] * diff) + ',\n'
            print(f'  Strategy 4: add {diff} closing braces to line {line_no}')
            fixed = True

    if not fixed:
        print(f'  No strategy matched for line {line_no}, manual fix needed.')
        print(f'  Line content: {repr(err_line[:120])}')
        break

    with open(OUT, 'w', encoding='utf-8') as f:
        f.writelines(lines)

else:
    print('Max iterations reached.')

print(f'\nOutput: {OUT}')
