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
    source_risks = []

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
        # Editorial Profile v1.0 applies to G0–G12; PDF is not rendered here.
        if path.parent == CPP and re.match(r'g(?:0[0-9]|1[0-2])-', path.name):
            if sum(header[0] == 1 for header in headers) != 1:
                errors.append(f'{path.name}: expected exactly one H1')
            previous = 0
            for header in headers:
                if header[0] > 3:
                    errors.append(f'{path.name}: heading deeper than H3: {header[1][0]}')
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
            if re.search(r'<\s*/?\s*(?:details|summary)\b', text, re.I):
                errors.append(f'{path.name}: content depends on HTML folding')
            lines = text.splitlines()
            start = None
            language = ''
            for index, line in enumerate(lines):
                if line.startswith('```'):
                    if start is None:
                        start, language = index, line[3:]
                        if language in {'cpp', 'c'}:
                            context = '\n'.join(lines[max(0, index - 7):index])
                            if not re.search(r'\[(?:完整实验|机制片段|反例)', context):
                                errors.append(f'{path.name}:{index + 1}: missing visible code identity')
                    else:
                        body = lines[start + 1:index]
                        longest = max((sum(2 if ord(c) > 127 else 1 for c in l)
                                       for l in body), default=0)
                        if len(body) > 32 or longest > 96:
                            source_risks.append(dict(file=path.name, line=start + 1,
                                kind='code_or_diagram_pagination', language=language,
                                lines=len(body), display_columns=longest))
                        start = None
                elif start is None:
                    if re.fullmatch(r'\s*(?:---+|\*\*\*+)\s*', line):
                        errors.append(f'{path.name}:{index + 1}: decorative horizontal rule')
                    if line.startswith('|') and index + 1 < len(lines) and re.match(
                            r'^\|[\s:|-]+\|$', lines[index + 1]):
                        rows = []
                        pos = index
                        while pos < len(lines) and lines[pos].startswith('|'):
                            rows.append(lines[pos])
                            pos += 1
                        cells = [re.split(r'(?<!\\)\|', row)[1:-1] for row in rows]
                        if max(map(len, cells)) > 4 or any(
                                sum(2 if ord(c) > 127 else 1 for c in cell.strip()) > 64
                                for row in cells for cell in row):
                            source_risks.append(dict(file=path.name, line=index + 1,
                                kind='table_width', columns=max(map(len, cells)), rows=len(rows)))
                    if re.match(r'^#{1,3} ', line):
                        next_content = next((s for s in lines[index + 1:] if s.strip()
                                             and not s.startswith('<a id=')), '')
                        level = len(line.split(' ')[0])
                        following = re.match(r'^(#{1,3}) ', next_content)
                        if not next_content or (following and len(following[1]) <= level):
                            errors.append(f'{path.name}:{index + 1}: heading without content')
    print(json.dumps({'markdown_files': len(paths), 'local_links': links,
                      'upgraded_hierarchy_files': 13, 'errors': errors,
                      'pdf': 'NOT BUILT / NOT VALIDATED',
                      'source_risks': source_risks},
                     ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
