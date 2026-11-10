import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Update the snapshot manifest from Git-tracked paths.')
    parser.add_argument('--check', action='store_true', help='Check coverage without updating the manifest.')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    manifest_path = root / 'public-manifest.json'
    original = manifest_path.read_bytes().decode('utf-8')
    manifest = json.loads(original)
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
    paths = sorted(set(tracked) - {'', 'public-manifest.json'})

    if args.check:
        listed = [entry['path'] for entry in manifest['files']]
        missing = sorted(set(paths) - set(listed))
        extra = sorted(set(listed) - set(paths))
        if missing or extra or len(listed) != len(set(listed)):
            parser.exit(1, f'Manifest coverage mismatch. Missing: {missing}. Extra: {extra}. Entries: {len(listed)}.\n')
        print(f'Manifest covers {len(paths)} Git-tracked files.')
        return

    files = []
    for name in paths:
        data = (root / name).read_bytes()
        files.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    manifest['files'] = files
    newline = '\r\n' if '\r\n' in original else '\n'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline=newline)
    print(f'Updated manifest for {len(files)} Git-tracked files.')


if __name__ == '__main__':
    main()
