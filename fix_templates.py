"""Fix all .strftime() calls in templates — SQLite returns strings not datetime objects."""
import os, re

template_dir = os.path.join(os.path.dirname(__file__), 'templates')

# (pattern, replacement) pairs applied in order
RULES = [
    # now.strftime(...) if now is defined else 'just now'
    (r"now\.strftime\('[^']+'\) if now is defined else 'just now'", "'just now'"),
    # X.strftime('%Y-%m-%d') if X else ''
    (r"(\w+)\.strftime\('%Y-%m-%d'\) if \1 else ''", r"(\1 or '')[:10]"),
    # X.strftime('%d %b %Y at %H:%M') if X else ''
    (r"(\w+)\.strftime\('%d %b %Y at %H:%M'\) if \1 else ''", r"(\1 or '')[:16]"),
    # X.strftime('%d %b %Y, %H:%M:%S') if X else '—'
    (r"(\w+)\.strftime\('%d %b %Y, %H:%M:%S'\) if \1 else '.*?'", r"(\1 or '')[:19]"),
    # X.strftime('%d %b %Y, %H:%M') if X else '—' or ''
    (r"(\w+)\.strftime\('%d %b %Y, %H:%M'\) if \1 else '.*?'", r"(\1 or '')[:16]"),
    # X.strftime('%d %b, %H:%M') if X else ''
    (r"(\w+)\.strftime\('%d %b, %H:%M'\) if \1 else ''", r"(\1 or '')[5:16]"),
    # X.strftime('%d %b %Y') if X else '—' or ''
    (r"(\w+)\.strftime\('%d %b %Y'\) if \1 else '.*?'", r"(\1 or '')[:10]"),
    # collection_date.strftime('%d %b %Y') (no conditional)
    (r"(\w+)\.strftime\('%d %b %Y'\)", r"(\1 or '')[:10]"),
    # Catch-all for any remaining .strftime()
    (r"(\w+(?:\.\w+)*)\.strftime\('[^']+'\)", r"(\1 or '')[:19]"),
]

fixed = 0
for root, _, files in os.walk(template_dir):
    for fname in files:
        if not fname.endswith('.html'):
            continue
        path = os.path.join(root, fname)
        content = open(path, encoding='utf-8').read()
        new_content = content
        for pattern, repl in RULES:
            new_content = re.sub(pattern, repl, new_content)
        if new_content != content:
            open(path, 'w', encoding='utf-8').write(new_content)
            rel = os.path.relpath(path, template_dir)
            print(f'  Fixed: {rel}')
            fixed += 1

print(f'Done. Fixed {fixed} template(s).')
