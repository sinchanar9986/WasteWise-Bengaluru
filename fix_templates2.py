"""Fix malformed Jinja expressions produced by the regex replacement."""
import os, re

template_dir = os.path.join(os.path.dirname(__file__), 'templates')

# Fix patterns like {{ r.(created_at or '')[:10] if r.created_at else '—' }}
# Should be:         {{ (r.created_at or '')[:10] }}
BAD_PATTERN = re.compile(
    r"\{\{\s*(\w+)\.\((\w+) or ''\)\[([^\]]+)\]\s*if \1\.\2 else '.*?'\s*\}\}"
)
BAD_PATTERN2 = re.compile(
    r"\{\{\s*(\w+)\.\((\w+) or ''\)\[([^\]]+)\]\s*if \1\.\2 else ''\s*\}\}"
)
GOOD_REPL = r"{{ (\1.\2 or '')[\3] }}"

fixed = 0
for root, _, files in os.walk(template_dir):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        content = open(path, encoding='utf-8').read()
        new_content = BAD_PATTERN.sub(GOOD_REPL, content)
        new_content = BAD_PATTERN2.sub(GOOD_REPL, new_content)
        if new_content != content:
            open(path, 'w', encoding='utf-8').write(new_content)
            rel = os.path.relpath(path, template_dir)
            print(f'  Fixed: {rel}')
            fixed += 1

# Also fix report detail links: report_id=r.id -> report_id=r.report_id
# (only where the report object is a waste_report, not an allocation)
REPORT_ID_FIX = re.compile(r"url_for\('citizen\.report_detail',\s*report_id=r\.id\)")
for root, _, files in os.walk(template_dir):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        content = open(path, encoding='utf-8').read()
        new_content = REPORT_ID_FIX.sub("url_for('citizen.report_detail', report_id=r.report_id)", content)
        if new_content != content:
            open(path, 'w', encoding='utf-8').write(new_content)
            rel = os.path.relpath(path, template_dir)
            if os.path.join(root, fname) not in [os.path.join(template_dir, f) for f in []]:
                print(f'  Fixed report_id: {rel}')
            fixed += 1

print(f'Done. Fixed {fixed} template(s).')
