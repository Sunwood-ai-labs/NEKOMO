"""Reject retired branding in current entry points; inventory historical references."""
import argparse
import json
import re
from pathlib import Path


CURRENT_FILES = (
    'README.md', 'AGENTS.md', 'docs/README.md', 'docs/reproduce.md',
    'docs/brand/identity.md', 'docs/brand/README.md',
    'docs/NEKONEKO-INDUSTRIES-concept-and-quality.md',
    'NEKONEKO-INDUSTRIES-concept-and-quality.md',
    'designs/nkm-c01-lynx/README.md', 'designs/nkm-c01-lynx/DESIGN.md',
    'quality/support-removal-preflight.py', 'quality/support_contact_lint.py',
)
SKILLS = ('nekoneko-dr-review', 'nekoneko-development-codename', 'nekoneko-logo-marking')
OLD_SKILL = re.compile(r'nekomo-(?:dr-review|development-codename|logo-marking)', re.I)
OLD_BRAND = re.compile(r'(?<![A-Za-z0-9_/-])NEKOMO(?![A-Za-z0-9_/-])|ネコモ', re.I)
HISTORY_WORDS = ('旧名', '旧名称', '過去', '履歴', '互換', 'legacy', 'historical')


def check(root):
    failures = []
    paths = {root / name for name in CURRENT_FILES if (root / name).is_file()}
    skill_root = root / '.agents/skills'
    if skill_root.exists():
        paths.update(p for p in skill_root.rglob('*') if p.suffix in ('.md', '.yaml', '.yml'))
    note_root = root / 'docs/note'
    if note_root.exists():
        paths.update(note_root.glob('*.md'))
    for name in SKILLS:
        if not (skill_root / name / 'SKILL.md').is_file():
            failures.append({'path': str(skill_root / name), 'reason': 'current skill missing'})
    for path in sorted(paths):
        for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            if OLD_SKILL.search(line):
                failures.append({'path': path.relative_to(root).as_posix(), 'line': number,
                                 'reason': 'retired skill name or link'})
            # Filenames, archived IDs and explicit old-name history are not live branding.
            prose = re.sub(r'`[^`]*`', '', line)
            prose = re.sub(r'\]\([^)]+\)', ']', prose)
            if OLD_BRAND.search(prose) and not any(word in line for word in HISTORY_WORDS):
                failures.append({'path': path.relative_to(root).as_posix(), 'line': number,
                                 'reason': 'retired brand used as a current name'})
    for old in ('NEKOMO-concept-and-quality.md', 'docs/NEKOMO-concept-and-quality.md'):
        if (root / old).exists():
            failures.append({'path': old, 'reason': 'retired current document filename'})
    return {'ok': not failures, 'current_files_checked': len(paths), 'failures': failures,
            'scope': 'Current naming and skill routing; archived CAD, G-code, evidence IDs and workspace paths are retained for traceability.'}


def inventory(root):
    records = []
    suffixes = {'.md', '.py', '.json', '.yaml', '.yml', '.toml', '.csv', '.svg'}
    for path in root.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        rel = path.relative_to(root)
        if any(part in ('.git', '.venv', 'node_modules', '__pycache__', '.yomiyasu') for part in rel.parts):
            continue
        if path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding='utf-8-sig')
        except UnicodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if 'nekomo' in line.lower() or 'ネコモ' in line:
                records.append({'path': rel.as_posix(), 'line': number})
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--inventory', type=Path, help='Write old-name occurrence locations, including ignored local records.')
    args = parser.parse_args()
    root = args.root.resolve()
    result = check(root)
    if args.inventory:
        records = inventory(root)
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        args.inventory.write_text(json.dumps({'occurrences': records, 'count': len(records)}, ensure_ascii=False, indent=2), encoding='utf-8')
        result['old_name_inventory_occurrences'] = len(records)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['ok'] else 1)
