#!/usr/bin/env python3
"""This batch's read-only checks; outputs are evidence, not an approval."""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = 'a2195d9557f1c4e86b7f64c290844c63493b2f18'
ALLOWED = {'design/README.md', *(f'design/scripts/{n}.py' for n in (
    'pub', 'preview', 'candidate', 'preview_audit', 'test-candidate',
    'test-preview', 'test-publication-isolation'))}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for name in ('test-publication-isolation', 'test-candidate', 'test-products', 'test-preview'):
        command = [sys.executable, '-B', f'publication/tests/{name}.py']
        start = time.monotonic()
        done = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (args.output / f'{name}.log').write_bytes(done.stdout)
        results.append({'command': command, 'exit_code': done.returncode,
                        'seconds': round(time.monotonic() - start, 3),
                        'log': f'{name}.log', 'log_sha256': sha(done.stdout)})
        print(name, done.returncode, flush=True)
    files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', '-z', BASE], cwd=ROOT).decode().split('\0')
    protected = []
    for name in filter(None, files):
        if name in ALLOWED:
            continue
        original = subprocess.check_output(['git', 'show', f'{BASE}:{name}'], cwd=ROOT)
        path = ROOT / name
        current = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        protected.append({'path': name, 'bytes': len(original), 'base_sha256': sha(original),
                          'current_sha256': sha(current) if current is not None else None,
                          'unchanged': current == original})
    for command, logfile in (([sys.executable, '-B', 'c++/learning/check_docs.py'], 'check-docs.log'),
                             (['git', 'diff', '--check'], 'diff-check.log')):
        done = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (args.output / logfile).write_bytes(done.stdout)
        results.append({'command': command, 'exit_code': done.returncode,
                        'log': logfile, 'log_sha256': sha(done.stdout)})
    record = {'base': BASE, 'platform': platform.platform(), 'machine': platform.machine(),
              'python': sys.version, 'commands': results, 'protected_files': protected,
              'meaning': 'Local execution and byte comparison, not CI, publication approval or C++ experiment reruns.'}
    (args.output / 'checks.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return int(any(r['exit_code'] for r in results) or not all(p['unchanged'] for p in protected))


if __name__ == '__main__':
    raise SystemExit(main())
