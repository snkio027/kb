#!/usr/bin/env python3
"""Read-only release-preparation checks; never grants reader/release approval.

--record creates only a new checks.json beside this script, refusing overwrite.
No PDF builder, renderer, reader automation or publish command is invoked.
"""
import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = 'eb7f5672d1128607d4f34fa34217aefa9ba99b33'
PREFIX = 'publication/reviews/release-qualification/'
PDF = 'publication/reviews/full-handbook/cpp-handbook-full/output/pdf/CPP-HANDBOOK-draft.pdf'
DIGEST = '80aabc252ef41eccb04a67504af1401e3f89211a43a1a89d761980143b225b26'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(args):
    return subprocess.check_output(args, cwd=ROOT, timeout=60)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record', action='store_true')
    args = parser.parse_args()
    require(not args.record or not (HERE / 'checks.json').exists(), 'refuse record overwrite')
    require(sha(ROOT / PDF) == DIGEST, 'candidate digest mismatch')
    checksum = run(['shasum', '-a', '256', '-c', PREFIX + 'SHA256SUMS']).decode()
    old_command = [sys.executable, '-B', 'publication/reviews/full-handbook/verify-delivery.py']
    old_result = json.loads(run(old_command))

    # Raw Git blob hashing: no status, clean/process filters or worktree conversion.
    protected = []
    changed = []
    baseline_paths = set()
    for entry in run(['git', 'ls-tree', '-rz', BASE]).split(b'\0'):
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, kind, expected = meta.decode().split()
        path = raw_path.decode()
        baseline_paths.add(path)
        require(kind == 'blob' and mode in {'100644', '100755'}, 'unsupported baseline entry: ' + path)
        current = ROOT / path
        require(current.is_file() and not current.is_symlink(), 'missing/replaced file: ' + path)
        data = current.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if path == 'publication/README.md':
            if actual != expected:
                changed.append(path)
        else:
            require(actual == expected, 'protected bytes changed: ' + path)
            protected.append(path)

    current_paths = set(run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).decode().split('\0')) - {''}
    require(all(p.startswith(PREFIX) for p in current_paths - baseline_paths), 'unexpected new file outside scope')
    dist_expected = {p for p in baseline_paths if p.startswith('design/dist/')}
    dist_actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'design/dist').rglob('*') if p.is_file() or p.is_symlink()}
    require(dist_expected == dist_actual, 'historical dist file set changed')

    docs = [ROOT / 'publication/README.md', *sorted(HERE.glob('*.md'))]
    links = 0
    for path in docs:
        nodes = list(walk(json.loads(run(['pandoc', '-f', 'gfm', '-t', 'json', str(path)]))))
        headers = [n['c'] for n in nodes if n.get('t') == 'Header']
        require(sum(h[0] == 1 for h in headers) == 1, 'expected one H1: ' + str(path))
        previous = 0
        ids = []
        for level, identity, _ in headers:
            require(level <= 3 and level <= previous + 1, 'heading hierarchy: ' + str(path))
            ids.append(identity[0])
            previous = level
        require(len(ids) == len(set(ids)), 'duplicate headings: ' + str(path))
        for node in nodes:
            if node.get('t') not in {'Link', 'Image'}:
                continue
            url = urlsplit(node['c'][-1][0])
            if url.scheme or url.netloc:
                continue
            require(not url.fragment, 'fragment check not implemented: ' + str(path))
            target = path.parent / unquote(url.path) if url.path else path
            # checks.json is generated only after these checks succeed.
            require(target.exists() or (args.record and target.resolve() == HERE / 'checks.json'), 'missing link: ' + str(target))
            links += 1
    run(['git', 'diff', '--check'])
    inputs = [*docs, HERE / 'SHA256SUMS', Path(__file__).resolve()]
    report = {
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
        'base': BASE,
        'platform': platform.platform(),
        'python': sys.version,
        'result': 'MACHINE_CHECK_PASS',
        'candidate_sha256': DIGEST,
        'checksum_command': 'shasum -a 256 -c ' + PREFIX + 'SHA256SUMS',
        'checksum_output': checksum.strip(),
        'historical_delivery_command': old_command,
        'historical_delivery_result': old_result,
        'protected_baseline_files_unchanged': len(protected),
        'protected_pdfs_unchanged': sum(p.lower().endswith('.pdf') for p in protected),
        'dist_file_set_unchanged': True,
        'allowed_existing_changes': changed,
        'markdown_files': len(docs),
        'local_links_checked': links,
        'diff_check': 'PASS',
        'checked_inputs': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in inputs],
        'reader_compatibility': 'PARTIAL_NOT_QUALIFIED_SEE_READER_SMOKE',
        'pdf_build': 'NOT_RUN',
        'publication_regressions': 'NOT_RUN',
        'cpp_compile_performance_concurrency': 'NOT_RUN',
        'formal_release': False,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.record:
        with (HERE / 'checks.json').open('x', encoding='utf-8') as stream:
            stream.write(rendered)
    print(rendered, end='')


if __name__ == '__main__':
    main()
