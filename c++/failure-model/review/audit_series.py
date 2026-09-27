#!/usr/bin/env python3
"""Read-only FM series audit: editorial structure, legacy targets and C++ payloads.

This is a scoped editorial gate, not a language-correctness or PDF checker.
Requires Pandoc (GFM reader). JSON is emitted on stdout; no repository writes.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
FM = ROOT / 'c++/failure-model'
BASE = '3c6dce94144213e77be98508cceb9c2631113ad6'
TEST = re.compile(r'<!-- fm-test (\{[^\n]+\}) -->\n```cpp\n(.*?)\n```', re.S)
FENCE = re.compile(r'^(`{3,}|~{3,})([^\n]*)\n(.*?)^\1[ \t]*$', re.M | re.S)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def parse(text):
    proc = subprocess.run([shutil.which('pandoc'), '-f', 'gfm', '-t', 'json'],
                          input=text, text=True, capture_output=True,
                          check=True, timeout=30)
    nodes = list(walk(json.loads(proc.stdout)))
    headers = [n['c'] for n in nodes if n.get('t') == 'Header']
    outside = FENCE.sub(lambda m: '\n' * m[0].count('\n'), text)
    explicit = re.findall(r'<a\s+id="([^"]+)"\s*>', outside)
    ids = [h[1][0] for h in headers] + explicit
    return headers, ids, outside


def payload(text):
    cpp = [m[3] for m in FENCE.finditer(text) if m[2] == 'cpp']
    tests = [(json.loads(m[1]), m[2] + '\n') for m in TEST.finditer(text)]
    return cpp, tests


def protected_errors(old, new):
    errors = []
    a, b = payload(old), payload(new)
    if a[0] != b[0]:
        errors.append('C++ payload/order changed')
    if a[1] != b[1]:
        errors.append('test metadata/source/order changed')
    old_headers, old_ids, _ = parse(old)
    new_headers, new_ids, _ = parse(new)
    missing = sorted(set(old_ids) - set(new_ids))
    if missing:
        errors.append('legacy anchors missing: ' + ', '.join(missing))
    # Numbered sections remain stable even though H2 becomes H3.
    def numbered(headers):
        return [h[1][0] for h in headers if re.match(r'^\d+-', h[1][0])]
    # Old numbered subheadings (e.g. 2.1) are represented by explicit aliases.
    old_sections = [h[1][0] for h in old_headers
                    if h[0] == 2 and re.match(r'^\d+-', h[1][0])]
    new_sections = numbered(new_headers)
    if old_sections != new_sections:
        errors.append('numbered section identity/order changed')
    return errors


def selftests():
    sample = '# Demo\n\n## 0. Contract\n\nold prose\n\n' + (
        '<!-- fm-test {"id":"T00","mode":"run"} -->\n'
        '```cpp\nint main() { return 0; }\n```\n')
    variants = {
        'prose_allowed': (sample.replace('old prose', 'new prose'), False),
        'cpp_rejected': (sample.replace('return 0', 'return 1'), True),
        'oracle_rejected': (sample.replace('"run"', '"compile"'), True),
        'anchor_rejected': (sample.replace('0. Contract', '0. Changed'), True),
        'legacy_h1_alias_allowed': (
            sample.replace('# Demo', '<a id="demo"></a>\n\n# New title'), False),
    }
    results = {}
    for name, (changed, rejected) in variants.items():
        actual = bool(protected_errors(sample, changed))
        results[name] = actual == rejected
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', default=BASE)
    args = ap.parse_args()
    if not shutil.which('pandoc'):
        raise SystemExit('SKIP: pandoc required (not a PASS)')
    base = subprocess.check_output(['git', 'rev-parse', args.base + '^{commit}'],
                                   cwd=ROOT, text=True).strip()
    chapters = sorted(FM.glob('fm[0-9]-*.md'))
    if len(chapters) != 10:
        raise SystemExit('FAIL: expected exactly ten chapters')
    errors, records, risks = [], [], []
    for path in chapters:
        relative = path.relative_to(ROOT).as_posix()
        before = subprocess.check_output(['git', 'show', base + ':' + relative], cwd=ROOT)
        after = path.read_bytes()
        old, new = before.decode(), after.decode()
        errors.extend(relative + ': ' + e for e in protected_errors(old, new))
        old_headers, old_ids, _ = parse(old)
        headers, ids, outside = parse(new)
        if sum(h[0] == 1 for h in headers) != 1:
            errors.append(relative + ': expected one H1')
        previous = 0
        for h in headers:
            if h[0] > 3 or h[0] > previous + 1:
                errors.append(relative + ': invalid heading hierarchy: ' + h[1][0])
            previous = h[0]
        duplicates = [key for key, count in Counter(ids).items() if count > 1]
        if duplicates:
            errors.append(relative + ': duplicate targets: ' + ', '.join(duplicates))
        if re.search(r'^\s*---+\s*$', outside, re.M):
            errors.append(relative + ': decorative horizontal rule')
        if re.search(r'<\s*/?\s*(details|summary)\b', outside, re.I):
            errors.append(relative + ': hidden important content')
        if re.search(r'^(`{3,}|~{3,})', outside, re.M):
            errors.append(relative + ': unmatched/unsupported fence')
        for m in FENCE.finditer(new):
            lines = m[3].splitlines()
            width = max((sum(2 if ord(c) > 127 else 1 for c in line)
                         for line in lines), default=0)
            if len(lines) > 32 or width > 96:
                risks.append(dict(file=relative, line=new[:m.start()].count('\n') + 1,
                                  kind='code_or_diagram_pagination', language=m[2],
                                  lines=len(lines), display_columns=width))
        rows = new.splitlines()
        for i, line in enumerate(rows[:-1]):
            if line.startswith('|') and re.fullmatch(r'\|[\s:|\-]+\|', rows[i + 1]):
                table = []
                for row in rows[i:]:
                    if not row.startswith('|'):
                        break
                    table.append(re.split(r'(?<!\\)\|', row)[1:-1])
                if max(map(len, table)) > 4 or any(
                    sum(2 if ord(c) > 127 else 1 for c in cell.strip()) > 64
                    for row in table for cell in row):
                    risks.append(dict(file=relative, line=i + 1, kind='table_width',
                                      columns=max(map(len, table)), rows=len(table)))
        cpp, tests = payload(new)
        records.append(dict(file=relative, before_sha256=sha(before), after_sha256=sha(after),
                            before_lines=len(old.splitlines()), after_lines=len(rows),
                            before_h2=sum(h[0] == 2 for h in old_headers),
                            after_h2=sum(h[0] == 2 for h in headers),
                            legacy_anchor_count=len(set(old_ids)),
                            cpp_blocks=len(cpp), marked_cases=[meta['id'] for meta, _ in tests],
                            cpp_sha256=[sha(code.encode()) for code in cpp]))
    historical = []
    for name in ('verify_fm.py', 'fm-claims.md', 'fm-review-7869082.md',
                 'fm-verification-samples.md', 'fm-verification-results.json'):
        path = FM / 'review' / name
        relative = path.relative_to(ROOT).as_posix()
        before = subprocess.check_output(['git', 'show', base + ':' + relative], cwd=ROOT)
        actual = path.read_bytes()
        if before != actual:
            errors.append(relative + ': historical evidence changed')
        historical.append(dict(file=relative, sha256=sha(actual), unchanged=before == actual))
    allowed = {p.relative_to(ROOT).as_posix() for p in chapters}
    allowed.update('c++/failure-model/' + p for p in (
        'README.md', 'series-guide.md', 'review/series-revision.md',
        'review/audit_series.py', 'review/series-audit.json',
        'review/series-verification-results.json'))
    changed = subprocess.check_output(['git', 'diff', '--name-only', base, '--'],
                                      cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'],
                                        cwd=ROOT, text=True).splitlines()
    outside_scope = sorted((set(changed) | set(untracked)) - allowed)
    if outside_scope:
        errors.append('out of scope: ' + ', '.join(outside_scope))
    tests = selftests()
    if not all(tests.values()):
        errors.append('audit selftest failure')
    all_cases = [case for p in chapters + [FM / 'review/fm-verification-samples.md']
                 for case in payload(p.read_text(encoding='utf-8'))[1]]
    case_ids = sorted(meta['id'] for meta, _ in all_cases)
    if case_ids != [f'T{i:02}' for i in range(1, 21)]:
        errors.append('expected exactly T01 through T20')
    result_path = FM / 'review/series-verification-results.json'
    binding = {'status': 'MISSING'}
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding='utf-8'))
        input_paths = chapters + [FM / 'review/fm-verification-samples.md']
        current_inputs = {p.relative_to(FM).as_posix(): sha(p.read_bytes()) for p in input_paths}
        bound = result.get('source_files_sha256') == current_inputs
        bound = bound and result.get('runner_sha256') == sha((FM / 'review/verify_fm.py').read_bytes())
        toolchains = result.get('toolchains', [])
        bound = bound and bool(toolchains)
        for toolchain in toolchains:
            rows = toolchain.get('results', [])
            by_id = {row['id']: row for row in rows}
            bound = bound and sorted(row['id'] for row in rows) == case_ids
            for meta, source in all_cases:
                row = by_id.get(meta['id'], {})
                bound = bound and row.get('source_sha256') == sha(source.encode())
                bound = bound and all(row.get(k) == v for k, v in meta.items())
        binding = dict(status='MATCH' if bound else 'MISMATCH',
                       result_sha256=sha(result_path.read_bytes()),
                       input_documents=len(current_inputs),
                       recorded_execution_exit_code=result.get('exit_code'))
        if not bound:
            errors.append('execution record does not bind current inputs/runner/cases')
    else:
        errors.append('final execution record missing')
    report = dict(base=base, status='PASS' if not errors else 'FAIL',
                  scope='FM editorial structure / exact C++ payload / legacy targets',
                  script_sha256=sha(Path(__file__).read_bytes()),
                  chapters=records, cpp_blocks=sum(r['cpp_blocks'] for r in records),
                  legacy_anchors=sum(r['legacy_anchor_count'] for r in records),
                  experiments=[dict(metadata=meta, source_sha256=sha(code.encode()))
                               for meta, code in sorted(all_cases, key=lambda c: c[0]['id'])],
                  selftests=tests, historical_evidence=historical,
                  verification_binding=binding,
                  protected_outside_scope_changes=outside_scope, errors=errors,
                  source_risks=risks,
                  limits=['Not a proof of prose or C++ semantic correctness.',
                          'Legacy target existence does not automatically prove target meaning.',
                          'Text/Markdown diagrams and templates are deliberately editable.',
                          'C++ execution is separately recorded; no performance or TSan run here.',
                          'No FM PDF built or validated; G/publication artifacts are outside scope.'])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
