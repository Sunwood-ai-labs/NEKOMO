import ast
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'public-manifest.json').read_text(encoding='utf-8-sig'))
published_paths = {entry['path'] for entry in manifest['files']} | {'public-manifest.json'}
failures = []
link_count = 0
archive_count = 0
for entry in manifest['files']:
    path = (root / entry['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        failures.append({'path': entry['path'], 'check': 'file location'})
        continue
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != entry['sha256']:
        failures.append({'path': entry['path'], 'check': 'SHA-256'})
    if len(content) >= 100 * 1024 * 1024:
        failures.append({'path': entry['path'], 'check': 'file size'})
    if path.suffix.lower() in ('.fcstd', '.3mf'):
        with zipfile.ZipFile(path) as archive:
            names = {name.lower() for name in archive.namelist()}
            required = 'document.xml' if path.suffix.lower() == '.fcstd' else '3d/3dmodel.model'
            if required not in names:
                failures.append({'path': entry['path'], 'check': 'CAD or 3MF structure'})
            archive_count += 1
    if path.suffix.lower() == '.json':
        json.loads(content.decode('utf-8-sig'))
    if path.suffix.lower() == '.py':
        ast.parse(content.decode('utf-8-sig'), filename=entry['path'])
    if path.suffix.lower() != '.md':
        continue
    text = re.sub(r'```.*?```', '', content.decode('utf-8-sig'), flags=re.S)
    for target in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)', text):
        target = target.strip().strip('<>')
        parsed = urlsplit(target)
        if parsed.scheme in ('http', 'https', 'mailto') or target.startswith('#'):
            continue
        linked = (path.parent / unquote(parsed.path)).resolve()
        relative = linked.relative_to(root).as_posix() if linked.is_relative_to(root) else ''
        in_snapshot = relative in published_paths or (linked.is_dir() and any(name.startswith(relative + '/') for name in published_paths))
        if parsed.scheme or not linked.is_relative_to(root) or not linked.exists() or not in_snapshot:
            failures.append({'path': entry['path'], 'check': 'local link', 'target': target})
        link_count += 1

statuses = json.loads((root / 'docs/data/bus-review-status.json').read_text(encoding='utf-8'))
for required in ('README.md', 'docs/バスの版一覧.md', 'docs/人間のレビュー記録.md',
                 'docs/NEKOMO-concept-and-quality.md', 'docs/data/bus-review-status.json',
                 'docs/data/bus-agent-reviews.json', 'docs/data/bus-versions.json'):
    if required not in published_paths:
        failures.append({'path': required, 'check': 'required published file'})
expected_variants = {'v01・大型一体', 'v02・大型3部品', 'v03・60mm組立', 'v04・60mm一体',
                     'v05・底面開口候補', 'v06・40mmシンプル', 'v06・60mm空洞', 'v06・赤タイヤ',
                     'v07・40mm床なし', 'v08・写真型', 'v09・傾斜ボンネット'}
if len(statuses['rows']) != 11 or {row['label'] for row in statuses['rows']} != expected_variants:
    failures.append({'check': 'eleven review variants'})
printed = [row['label'] for row in statuses['rows'] if row['print_completed'] == 'recorded']
if set(printed) != {'v06・赤タイヤ', 'v09・傾斜ボンネット'}:
    failures.append({'check': 'two printed variants'})
agents = json.loads((root / 'docs/data/bus-agent-reviews.json').read_text(encoding='utf-8'))
if set(agents['rows']) != expected_variants:
    failures.append({'check': 'eleven agent review variants'})
if any(entry['stages']['DR3'] != 'なし' for entry in agents['rows'].values()):
    failures.append({'check': 'DR3 evidence state'})
summary = {'ok': not failures, 'files_checked': len(manifest['files']), 'local_links_checked': link_count,
           'cad_archives_checked': archive_count, 'printed_count': len(printed), 'failures': failures}
print(json.dumps(summary, ensure_ascii=True))
sys.exit(0 if summary['ok'] else 1)
