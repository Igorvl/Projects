"""
smart_fix_v59.py  
Smart fixer: for each data-array line, counts braces and adds missing closing ones.
Operates on _build_cache/GEN_v59_fixed.txt
"""
import sys, io, re, subprocess, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FIXED = r'C:\Projects\Business\Web_projects_NEW\behance_scout\_build_cache\GEN_v59_fixed.txt'
TESTER = r'C:\Projects\Business\Web_projects_NEW\behance_scout\_build_cache\strip_and_fix.js'

def test_parse(path):
    """Returns (ok, line, col, msg)"""
    r = subprocess.run(
        ['node', TESTER, path],
        cwd=r'C:\Projects\Business\Web_projects_NEW\behance_scout',
        capture_output=True, text=True, encoding='utf-8'
    )
    try:
        info = json.loads(r.stdout.strip())
        return info.get('ok', False), info.get('line'), info.get('col'), info.get('msg','')
    except:
        return False, None, None, r.stdout[:100]

def count_braces(s):
    """Count net open braces in a string (ignoring strings)."""
    # Simple count (good enough for our data)
    return s.count('{') - s.count('}')

# ── Fix loop ──────────────────────────────────────────────────────────────────
MAX = 60
for i in range(MAX):
    ok, line_no, col, msg = test_parse(FIXED)
    if ok:
        print(f'\n✅ ALL SYNTAX ERRORS FIXED after {i} iterations!')
        break

    print(f'[{i+1}] line {line_no} col {col}: {msg[:80]}')

    with open(FIXED, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if not line_no or line_no > len(lines):
        print('  Cannot locate, stopping.')
        break

    err_line = lines[line_no - 1]
    prev_line = lines[line_no - 2] if line_no > 1 else ''

    fixed = False

    # ── Strategy A: Line has unbalanced braces (more { than }) ───────────────
    net = count_braces(err_line)
    if net > 0 and not fixed:
        closing = '}' * net
        stripped = err_line.rstrip('\n\r')
        # If line ends with }, or } — add closing braces before comma
        if stripped.endswith(','):
            lines[line_no - 1] = stripped[:-1] + closing + ',\n'
        elif stripped.endswith('}'):
            lines[line_no - 1] = stripped + closing + ',\n'
        else:
            lines[line_no - 1] = stripped + closing + ',\n'
        print(f'  Strategy A: added {net} closing braces to line {line_no}')
        fixed = True

    # ── Strategy B: Previous line ends with no comma, current line starts { ──
    if not fixed:
        prev = prev_line.rstrip('\n\r')
        if prev.endswith('}') and not prev.endswith(','):
            lines[line_no - 2] = prev + ',\n'
            print(f'  Strategy B: added comma to line {line_no - 1}')
            fixed = True

    # ── Strategy C: Line contains } followed by spaces then { (same line) ────
    if not fixed:
        m = re.search(r'(\})\s{2,}(\{)', err_line)
        if m:
            new_line = err_line[:m.start(1)+1] + ',\n      ' + err_line[m.start(2):]
            lines[line_no - 1] = new_line
            print(f'  Strategy C: split merged objects on line {line_no}')
            fixed = True

    if not fixed:
        print(f'  !! No strategy matched. Line: {repr(err_line[:100])}')
        # Last resort: check PREVIOUS line for unclosed braces
        prev = prev_line.rstrip('\n\r')
        net_prev = count_braces(prev)
        if net_prev > 0:
            closing = '}' * net_prev
            if prev.endswith(','):
                lines[line_no - 2] = prev[:-1] + closing + ',\n'
            elif prev.endswith('}'):
                lines[line_no - 2] = prev + closing + ',\n'
            else:
                lines[line_no - 2] = prev + closing + ',\n'
            print(f'  Strategy D (prev line {line_no-1}): added {net_prev} closing braces')
            fixed = True

    if not fixed:
        print(f'  GIVING UP on line {line_no}')
        break


    with open(FIXED, 'w', encoding='utf-8') as f:
        f.writelines(lines)

else:
    print('Max iterations reached.')

print(f'\nDone. Fixed file: {FIXED}')
