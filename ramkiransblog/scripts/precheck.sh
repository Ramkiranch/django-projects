#!/usr/bin/env bash
# Tier 1 precheck — run before every push.
#
# Catches:
#   1. Django config / import errors (manage.py check)
#   2. Test regressions (manage.py test)
#   3. Templates that fail to compile
#   4. Multi-line `{# ... #}` Django comments (Django's `{# %}` is
#      single-line ONLY — multi-line ones leak as visible text. Has
#      bitten this project four times. Now blocked at precheck time.)
#
# Usage:
#   ./scripts/precheck.sh
#
# Exits non-zero on any failure so you can chain with `&& git push`.

set -euo pipefail
cd "$(dirname "$0")/.."

VENV_PY=".venv/bin/python"
DJANGO_DIR="ramkiransblog"

if [[ ! -x "$VENV_PY" ]]; then
  echo "Expected venv at $VENV_PY — run: python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt"
  exit 1
fi

# 1. Django check
echo "==> django check"
DEBUG=True "$VENV_PY" "$DJANGO_DIR/manage.py" check

# 2. Tests (force SQLite + DEBUG=True to avoid prod env / Postgres dependence)
echo ""
echo "==> tests"
# Explicit app list — Django's auto-discovery doesn't see local apps when
# manage.py is invoked from the repo root.
DEBUG=True \
  DATABASE_URL="sqlite:///$PWD/$DJANGO_DIR/precheck.sqlite3" \
  "$VENV_PY" "$DJANGO_DIR/manage.py" test posts sitepages subscribers --verbosity=1
rm -f "$DJANGO_DIR/precheck.sqlite3"

# 3 + 4. Template compile + multi-line {# %} guard, in one Python invocation
echo ""
echo "==> templates compile + no multi-line {# %} comments"
"$VENV_PY" - <<'PY'
import os, re, sys
from pathlib import Path

sys.path.insert(0, 'ramkiransblog')
os.environ['DJANGO_SETTINGS_MODULE'] = 'ramkiransblog.settings'
os.environ.setdefault('SECRET_KEY', 'precheck')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')

import django
django.setup()
from django.template.loader import get_template

templates_root = Path('ramkiransblog')
all_html = list(templates_root.rglob('*.html'))

# Step 3: compile every template Django can resolve by name
compile_fails = []
compiled = 0
for p in all_html:
    parts = p.parts
    if 'templates' not in parts:
        continue
    idx = parts.index('templates')
    name = '/'.join(parts[idx + 1:])
    try:
        get_template(name)
        compiled += 1
    except Exception as e:
        compile_fails.append(f'{p}: {type(e).__name__}: {e}')

print(f'compiled {compiled} templates')
for f in compile_fails:
    print(f'COMPILE FAIL: {f}')

# Step 4: scan every .html for multi-line {# %} comments — Django parses
# these as literal text and they render visibly on the page.
comment_fails = []
for p in all_html:
    text = p.read_text(encoding='utf-8')
    for m in re.finditer(r'\{#.*?#\}', text, re.DOTALL):
        if '\n' in m.group():
            line = text[:m.start()].count('\n') + 1
            comment_fails.append(f'{p}:{line}: multi-line {{# ... #}} — use {{% comment %}}...{{% endcomment %}}')

for f in comment_fails:
    print(f'COMMENT FAIL: {f}')

if compile_fails or comment_fails:
    sys.exit(1)
print('all templates OK')
PY

echo ""
echo "==> ALL GREEN"
