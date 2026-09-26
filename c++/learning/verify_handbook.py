#!/usr/bin/env python3
"""G5–G7 evidence, separated by claim; all generated files go to a fresh temp tree."""

import json
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tempfile

from verify_g import command, clean_exit, diagnosed, sha

ROOT = Path(__file__).resolve().parents[1]
LAB = re.compile(r'<!-- h-lab (\{[^\n]+\}) -->')
FILE = re.compile(r'<!-- h-file (\{[^\n]+\}) -->\n```cpp\n(.*?)\n```', re.S)
MODES = {'run', 'compile_fail', 'symbols', 'observation', 'benchmark',
         'concurrency', 'tsan_negative'}


def extract(documents):
    labs, seen = [], set()
    for name, text in documents:
        markers = list(LAB.finditer(text))
        if text.count('<!-- h-lab ') != len(markers):
            raise ValueError(f'malformed lab marker: {name}')
        count = 0
        for index, marker in enumerate(markers):
            info = json.loads(marker.group(1))
            identity = info.get('id', '')
            if not re.fullmatch(r'G[5-7]-[CMD][1-9][0-9]*', identity) or identity in seen:
                raise ValueError(f'invalid or duplicate lab: {identity}')
            seen.add(identity)
            if info.get('mode') not in MODES:
                raise ValueError(f'unsupported mode: {identity}')
            if info['mode'] == 'concurrency' and not isinstance(info.get('stdout'), str):
                raise ValueError(f'missing concurrency output oracle: {identity}')
            if info['mode'] in {'compile_fail', 'symbols'}:
                if not info.get('diagnostic'):
                    raise ValueError(f'missing diagnostic: {identity}')
                re.compile(info['diagnostic'])
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            files = {}
            for file_marker in FILE.finditer(text, marker.end(), end):
                filename = json.loads(file_marker.group(1))['path']
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*\.(?:cpp|hpp)', filename):
                    raise ValueError(f'unsafe filename: {filename}')
                if filename in files:
                    raise ValueError(f'duplicate file: {identity}/{filename}')
                files[filename] = file_marker.group(2) + '\n'
                count += 1
            if 'main.cpp' not in files:
                raise ValueError(f'missing main.cpp: {identity}')
            labs.append(dict(info, document=name, files=files))
        if text.count('<!-- h-file ') != count:
            raise ValueError(f'orphan or malformed file marker: {name}')
    if not labs:
        raise ValueError('no experiments')
    return labs


def tsan_detected(step):
    return (clean_exit(step, 66) and
            re.search(r'ThreadSanitizer: data race', step['stderr']) is not None)


def observations(identity, output):
    """Validate record identity/completeness, never a speed ranking or fixed ABI size."""
    rows = [json.loads(line) for line in output.splitlines()]
    if identity == 'G6-M1':
        if len(rows) != 1 or set(rows[0]) != {
                'size', 'align', 'id_offset', 'value_offset', 'reordered_size'}:
            raise ValueError('incomplete layout observation')
        r = rows[0]
        if not all(type(v) is int and v >= 0 for v in r.values()):
            raise ValueError('invalid layout values')
        if r['align'] == 0 or r['size'] == 0 or r['size'] % r['align']:
            raise ValueError('invalid size/alignment')
        if not (0 < r['id_offset'] < r['value_offset'] < r['size']):
            raise ValueError('invalid member offsets')
    elif identity == 'G6-M2':
        if len(rows) != 1 or set(rows[0]) != {
                'allocations', 'deallocations', 'requested_bytes'}:
            raise ValueError('incomplete allocation observation')
        r = rows[0]
        if not all(type(v) is int and v > 0 for v in r.values()):
            raise ValueError('invalid allocation values')
        if r['allocations'] != r['deallocations']:
            raise ValueError('resource imbalance')
    elif identity == 'G6-M3':
        wanted = {(n, trial, layout) for n in (1024, 65536, 1048576)
                  for trial in range(7) for layout in ('aos', 'soa')}
        seen = set()
        for r in rows:
            if set(r) != {'n', 'trial', 'layout', 'elapsed_ns', 'checksum'}:
                raise ValueError('incomplete benchmark row')
            key = r['n'], r['trial'], r['layout']
            if key not in wanted or key in seen:
                raise ValueError('duplicate/unexpected benchmark identity')
            if type(r['elapsed_ns']) is not int or r['elapsed_ns'] < 0:
                raise ValueError('invalid duration')
            n = r['n']
            q, remainder = divmod(n, 251)
            expected = q * (250 * 251 // 2) + remainder * (remainder - 1) // 2
            if r['checksum'] != expected:
                raise ValueError('incorrect full-data checksum')
            seen.add(key)
        if seen != wanted:
            raise ValueError('missing benchmark rows')
    else:
        raise ValueError(f'unknown observation contract: {identity}')
    return rows


def verify(lab, compiler, folder, tsan):
    folder.mkdir()
    for name, content in lab['files'].items():
        (folder / name).write_text(content, encoding='utf-8')
    result = {k: v for k, v in lab.items() if k != 'files'}
    result.update(compiler=compiler, steps=[], evidence=[],
                  source_sha256={n: sha(s.encode()) for n, s in lab['files'].items()})

    def run(args, env=None):
        step = command(args, folder, env=env)
        result['steps'].append(step)
        return step

    def record(category, status, claim, **fields):
        result['evidence'].append(dict(category=category, status=status, claim=claim, **fields))

    mode = lab['mode']
    flags = [compiler, '-std=c++23', '-Wall', '-Wextra', '-Wpedantic', '-pthread']
    if mode == 'compile_fail':
        step = run(flags + ['-fsyntax-only', 'main.cpp'])
        record('compile', 'PASS' if diagnosed(step, lab['diagnostic']) else 'FAIL',
               'target diagnostic, not timeout/signal/unrelated failure')
        return result
    if mode == 'tsan_negative':
        if not tsan['available']:
            record('concurrency', 'SKIP', 'known-race positive control', reason=tsan['reason'])
            return result
        build = run(flags + ['-O1', '-g', '-fsanitize=thread', 'main.cpp', '-o', 'race'])
        record('compile', 'PASS' if clean_exit(build) else 'FAIL', 'TSan negative fixture compiled')
        if clean_exit(build):
            step = run([str(folder / 'race')], tsan['env'])
            record('concurrency', 'DETECTED' if tsan_detected(step) else 'FAIL',
                   'TSan reports data race and exits 66')
        return result
    if mode in {'symbols', 'benchmark'}:
        flags += ['-O0', '-fno-inline'] if mode == 'symbols' else ['-O3']
        objects = []
        for name in lab['files']:
            if name.endswith('.cpp'):
                obj = Path(name).with_suffix('.o').name
                step = run(flags + ['-c', name, '-o', obj])
                if not clean_exit(step):
                    record('compile', 'FAIL', f'compile {name}')
                    return result
                objects.append(obj)
        selected = [o for o in objects if o != 'missing.o']
        build = run([compiler, *selected, '-o', 'demo'])
    else:
        build = run(flags + ['-O1', '-g', 'main.cpp', '-o', 'demo'])
    record('compile', 'PASS' if clean_exit(build) else 'FAIL', 'complete positive program compiled/linked')
    if not clean_exit(build):
        return result
    if mode == 'symbols':
        missing = run([compiler, 'missing.o', 'scale.o', '-o', 'missing'])
        record('compile', 'PASS' if diagnosed(missing, lab['diagnostic']) else 'FAIL',
               'unsupported specialization rejected at link, after successful compile')
        nm = shutil.which('nm')
        if nm:
            step = run([nm, '-C', 'scale.o'])
            record('compile', 'OBSERVED' if clean_exit(step) else 'FAIL', 'target symbol table')
        else:
            record('compile', 'SKIP', 'target symbol table', reason='nm unavailable')
    step = run([str(folder / 'demo')])
    if mode in {'observation', 'benchmark'}:
        try:
            if not clean_exit(step) or step['stderr']:
                raise ValueError('measurement process failed')
            rows = observations(lab['id'], step['stdout'])
            record('performance', 'OBSERVED', 'recorded values; no performance threshold', rows=rows)
        except (ValueError, TypeError, KeyError) as error:
            record('performance', 'FAIL', 'observation contract', reason=str(error))
        if mode == 'benchmark':
            assembly = run(flags + ['-S', 'kernel.cpp', '-o', 'kernel.s'])
            record('performance', 'OBSERVED' if clean_exit(assembly) else 'FAIL',
                   'generated assembly, not CPU profile',
                   artifact=str(folder / 'kernel.s'),
                   sha256=sha((folder / 'kernel.s').read_bytes()) if clean_exit(assembly) else None)
        return result
    correct = clean_exit(step) and not step['stderr'] and step['stdout'] == lab.get('stdout', '')
    category = 'concurrency' if mode == 'concurrency' else 'compile'
    record(category, ('CLEAN_OBSERVED' if mode == 'concurrency' else 'PASS') if correct else 'FAIL',
           'finite native execution with explicit invariants/output')
    if mode == 'concurrency':
        if not tsan['available']:
            record('concurrency', 'SKIP', 'instrumented execution', reason=tsan['reason'])
        else:
            build = run(flags + ['-O1', '-g', '-fsanitize=thread', 'main.cpp', '-o', 'instrumented'])
            record('compile', 'PASS' if clean_exit(build) else 'FAIL', 'TSan positive fixture compiled')
            if clean_exit(build):
                step = run([str(folder / 'instrumented')], tsan['env'])
                correct = clean_exit(step) and not step['stderr'] and step['stdout'] == lab['stdout']
                record('concurrency', 'CLEAN_OBSERVED' if correct else 'FAIL',
                       'invariants and no TSan diagnostic in this execution; not a protocol proof')
    return result


def main(argv):
    if not argv:
        raise SystemExit('usage: verify_handbook.py CXX [CXX ...]')
    documents = [(p.name, p.read_text(encoding='utf-8')) for p in sorted(ROOT.glob('g0[5-7]-*.md'))]
    if len(documents) != 3:
        raise ValueError('expected G5–G7')
    labs = extract(documents)
    temp = Path(tempfile.mkdtemp(prefix='kb-handbook-'))
    report = {'schema': 1, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'platform': platform.platform(), 'machine': platform.machine(),
              'scope': 'G5–G7 targeted claims, not cross-platform or complete technical acceptance',
              'pdf': 'NOT BUILT / NOT VALIDATED',
              'source_documents_sha256': {n: sha(t.encode()) for n, t in documents},
              'runner_sha256': sha(Path(__file__).read_bytes()),
              'helper_sha256': sha((ROOT / 'learning/verify_g.py').read_bytes()),
              'temp_directory': str(temp), 'toolchains': [], 'results': [],
              'not_run': ['CPU sampling profile', 'hardware counters', 'PDF',
                          'formal model checking', 'Zig/Rust compilation']}
    print(f'Evidence: {temp}', flush=True)
    try:
        sysctl = shutil.which('sysctl')
        report['machine_queries'] = [command([sysctl, key], temp) for key in
            ('hw.machine', 'hw.pagesize', 'hw.cachelinesize')] if sysctl else []
        if not sysctl:
            report['machine_queries'] = [dict(status='SKIP', category='performance',
                reason='sysctl unavailable; no cache-line/page-size observation')]
        for query in report['machine_queries']:
            if 'returncode' in query:
                query.update(category='performance',
                             status='OBSERVED' if clean_exit(query) else 'SKIP',
                             reason='' if clean_exit(query) else 'optional machine query unavailable')
        for index, requested in enumerate(argv):
            compiler = shutil.which(requested)
            if not compiler:
                report['toolchains'].append({'requested': requested, 'status': 'SKIP',
                                             'reason': 'compiler unavailable'})
                continue
            folder = temp / f'toolchain-{index}'
            folder.mkdir()
            version = command([compiler, '--version'], folder)
            probe = folder / 'identity.cpp'
            probe.write_text('#include <version>\n', encoding='utf-8')
            macros = command([compiler, '-std=c++23', '-dM', '-E', str(probe)], folder)
            identity = {'compiler': compiler, 'version': version, 'identity_command': macros['command'],
                        'library_macros': [l for l in macros['stdout'].splitlines() if re.match(
                            r'#define (?:_LIBCPP_VERSION|__GLIBCXX__|_MSVC_STL_VERSION|__cplusplus) ', l)]}
            if not clean_exit(version) or not clean_exit(macros):
                identity.update(status='FAIL', reason='toolchain identity failed')
                report['toolchains'].append(identity)
                continue
            probe = folder / 'tsan_probe.cpp'
            probe.write_text('#include <thread>\nint main(){ std::thread t([]{}); t.join(); }\n')
            binary = folder / 'tsan_probe'
            build = command([compiler, '-std=c++23', '-O1', '-g', '-pthread', '-fsanitize=thread',
                             str(probe), '-o', str(binary)], folder)
            env = dict(os.environ, TSAN_OPTIONS='halt_on_error=1:abort_on_error=0:exitcode=66:symbolize=0')
            steps = [build]
            if clean_exit(build):
                steps.append(command([str(binary)], folder, env=env))
            available = len(steps) == 2 and clean_exit(steps[-1]) and not steps[-1]['stderr']
            tsan = {'available': available, 'env': env,
                    'reason': '' if available else 'TSan compile/run probe unavailable; see raw diagnostics'}
            identity.update(status='IDENTIFIED', tsan_probe=steps, tsan_available=available,
                            tsan_options=env['TSAN_OPTIONS'])
            report['toolchains'].append(identity)
            for lab in labs:
                result = verify(lab, compiler, folder / lab['id'], tsan)
                report['results'].append(result)
                print(lab['id'] + ': ' + ', '.join(
                    e['category'] + '=' + e['status'] for e in result['evidence']), flush=True)
        report['summary_by_category'] = {}
        for result in report['results']:
            for e in result['evidence']:
                group = report['summary_by_category'].setdefault(e['category'], {})
                group[e['status']] = group.get(e['status'], 0) + 1
        for query in report['machine_queries']:
            group = report['summary_by_category'].setdefault(query['category'], {})
            group[query['status']] = group.get(query['status'], 0) + 1
        statuses = [e['status'] for r in report['results'] for e in r['evidence']]
        statuses += [t['status'] for t in report['toolchains']]
        statuses += [q['status'] for q in report['machine_queries']]
        report['execution'] = 'FAILED' if 'FAIL' in statuses else 'INCOMPLETE' if 'SKIP' in statuses else 'RECORDED'
    except BaseException as error:
        report.update(execution='INTERRUPTED_OR_FAILED', error=repr(error))
        raise
    finally:
        (temp / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if report['execution'] == 'RECORDED' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
