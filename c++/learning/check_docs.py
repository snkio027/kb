#!/usr/bin/env python3
"""Read-only GFM parse/link checks for the C++ corpus and its incoming indexes."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[2]
CPP = ROOT / 'c++'


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def main():
    pandoc = shutil.which('pandoc')
    if not pandoc:
        raise SystemExit('SKIP: pandoc is required for GFM parsing')
    paths = sorted(CPP.rglob('*.md')) + [ROOT / 'README.md', ROOT / 'design/project/asset-register.md']
    cache = {}
    errors = []

    def parse(path):
        if path not in cache:
            text = path.read_text(encoding='utf-8')
            result = subprocess.run([pandoc, '-f', 'gfm', '-t', 'json', str(path)],
                                    text=True, capture_output=True, timeout=30, check=True)
            tree = json.loads(result.stdout)
            nodes = list(walk(tree))
            headers = [node['c'] for node in nodes if node.get('t') == 'Header']
            explicit = re.findall(r'<a\s+id="([^"]+)"\s*>', text)
            anchors = {header[1][0] for header in headers} | set(explicit)
            cache[path] = text, nodes, headers, anchors
        return cache[path]

    links = 0
    for path in paths:
        text, nodes, headers, anchors = parse(path)
        for node in nodes:
            if node.get('t') not in {'Link', 'Image'}:
                continue
            target = node['c'][-1][0]
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            links += 1
            destination = (path.parent / unquote(url.path)).resolve() if url.path else path
            if not destination.exists():
                errors.append(f'{path.relative_to(ROOT)}: missing {target}')
            elif url.fragment and destination.suffix == '.md':
                if unquote(url.fragment) not in parse(destination)[3]:
                    errors.append(f'{path.relative_to(ROOT)}: missing anchor {target}')
        # Only upgraded G0–G4 use this edition's hierarchy rules.
        if path.parent == CPP and re.match(r'g0[0-4]-', path.name):
            if sum(header[0] == 1 for header in headers) != 1:
                errors.append(f'{path.name}: expected exactly one H1')
            previous = 0
            for header in headers:
                if header[0] > previous + 1:
                    errors.append(f'{path.name}: skipped heading level at {header[1][0]}')
                previous = header[0]
            explicit = re.findall(r'<a\s+id="([^"]+)"\s*>', text)
            if len(explicit) != len(set(explicit)):
                errors.append(f'{path.name}: duplicate explicit anchors')
            fence = False
            for line in text.splitlines():
                if line.startswith('```'):
                    fence = not fence
            if fence:
                errors.append(f'{path.name}: unclosed fence')
            if text.count('<details>') != text.count('</details>'):
                errors.append(f'{path.name}: unbalanced details')
    print(json.dumps({'markdown_files': len(paths), 'local_links': links,
                      'upgraded_hierarchy_files': 5, 'errors': errors},
                     ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
