#!/usr/bin/env python3
"""Extract and verify reviewed G0–G4 Markdown labs; write only to a fresh temp tree."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
LAB = re.compile(r'<!-- g-lab (\{[^\n]+\}) -->')
FILE = re.compile(r'<!-- g-file (\{[^\n]+\}) -->\n```cpp\n(.*?)\n```', re.S)
MODES = {'run', 'link', 'compile_fail', 'asan_negative'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract(documents):
    labs = []
    seen = set()
    for path, text in documents:
        markers = list(LAB.finditer(text))
        if text.count('<!-- g-lab ') != len(markers):
            raise ValueError(f'malformed lab marker: {path}')
        file_count = 0
        for index, marker in enumerate(markers):
            info = json.loads(marker.group(1))
            lab_id = info.get('id', '')
            if not re.fullmatch(r'G[0-4]-L[1-9][0-9]*', lab_id) or lab_id in seen:
                raise ValueError(f'invalid or duplicate lab: {lab_id}')
            seen.add(lab_id)
            if info.get('mode') not in MODES:
                raise ValueError(f'unsupported mode: {lab_id}')
            if info['mode'] in {'run', 'link'} and 'stdout' not in info:
                raise ValueError(f'missing output oracle: {lab_id}')
            if info['mode'] != 'run':
                if not info.get('diagnostic'):
                    raise ValueError(f'missing diagnostic oracle: {lab_id}')
                re.compile(info['diagnostic'])
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            files = {}
            for file_marker in FILE.finditer(text, marker.end(), end):
                name = json.loads(file_marker.group(1))['path']
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*\.(?:cpp|hpp)', name):
                    raise ValueError(f'unsafe or unsupported filename: {name}')
                if name in files:
                    raise ValueError(f'duplicate file: {lab_id}/{name}')
                files[name] = file_marker.group(2) + '\n'
                file_count += 1
            if 'main.cpp' not in files:
                raise ValueError(f'missing main.cpp: {lab_id}')
            labs.append(dict(info, document=path, files=files))
        if text.count('<!-- g-file ') != file_count:
            raise ValueError(f'orphan or malformed file marker: {path}')
    if not labs:
        raise ValueError('no labs found')
    return labs


def command(args, cwd, timeout=45, env=None):
    """Capture every child; timeout/cancel is never a successful negative test."""
    record = {'command': [str(a) for a in args], 'cwd': str(cwd)}
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               start_new_session=True, env=env)
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        record['timed_out'] = False
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        record['timed_out'] = True
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    record.update(returncode=process.returncode, stdout=stdout, stderr=stderr)
    return record


def clean_exit(record, code=0):
    return not record['timed_out'] and record['returncode'] == code


def diagnosed(record, pattern):
    return (not record['timed_out'] and record['returncode'] > 0 and
            re.search(pattern, record['stdout'] + record['stderr']) is not None)


def mutations(labs):
    """Two small oracle checks, not a general mutation framework."""
    cases = [
        ('G3-L1', 'truncate-copy', 'auto copy = source;',
         'auto copy = source; copy.resize(1);', 1),
        ('G4-L1', 'accept-next-key',
         'if (it == samples_.end() || it->signal_id != id)',
         'if (it == samples_.end())', 3),
    ]
    result = []
    by_id = {lab['id']: lab for lab in labs}
    for original, name, old, new, code in cases:
        lab = by_id[original]
        source = lab['files']['main.cpp']
        if source.count(old) != 1:
            raise ValueError(f'mutation target drifted: {original}/{name}')
        result.append(dict(lab, id=f'{original}-{name}',
                           kind='mutation-rejected', expected_exit=code, stdout='',
                           files={'main.cpp': source.replace(old, new)}))
    return result


def verify(lab, compiler, folder):
    folder.mkdir()
    for name, content in lab['files'].items():
        (folder / name).write_text(content, encoding='utf-8')
    result = {key: value for key, value in lab.items() if key != 'files'}
    result.update(status='FAIL', steps=[],
                  source_sha256={name: sha(content.encode())
                                 for name, content in lab['files'].items()})
    flags = [compiler, '-std=c++23', '-O1', '-g', '-Wall', '-Wextra', '-Wpedantic']

    def run(args, env=None):
        step = command(args, folder, env=env)
        result['steps'].append(step)
        return step

    mode = lab['mode']
    if mode == 'link':
        objects = []
        for name in lab['files']:
            if name.endswith('.cpp'):
                obj = Path(name).with_suffix('.o').name
                if not clean_exit(run(flags + ['-c', name, '-o', obj])):
                    return result
                objects.append(obj)
        if not diagnosed(run([compiler, 'main.o', '-o', 'missing']), lab['diagnostic']):
            return result
        if not clean_exit(run([compiler, *objects, '-o', 'demo'])):
            return result
    elif mode == 'asan_negative':
        flags = [compiler, '-std=c++23', '-O0', '-g', '-fsanitize=address',
                 '-fno-omit-frame-pointer']
        # Disable external symbolizers; use a deliberate, testable failure code.
        env = dict(os.environ, ASAN_OPTIONS=(
            'detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0'))
        (folder / 'asan_probe.cpp').write_text('int main() { return 0; }\n')
        if not clean_exit(run(flags + ['asan_probe.cpp', '-o', 'asan_probe'])):
            result.update(status='SKIP', reason='ASan probe could not compile')
            return result
        if not clean_exit(run([str(folder / 'asan_probe')], env)):
            result.update(status='SKIP', reason='ASan probe could not run normally')
            return result
        if not clean_exit(run(flags + ['main.cpp', '-o', 'demo'])):
            return result
        observed = run([str(folder / 'demo')], env)
        if clean_exit(observed, 86) and diagnosed(observed, lab['diagnostic']):
            result['status'] = 'PASS'
        return result
    elif mode == 'compile_fail':
        # No linker: the target claim concerns compilation constraints.
        if diagnosed(run(flags + ['-c', 'main.cpp', '-o', 'main.o']), lab['diagnostic']):
            result['status'] = 'PASS'
        return result
    elif not clean_exit(run(flags + ['main.cpp', '-o', 'demo'])):
        return result
    execution = run([str(folder / 'demo')])
    if (clean_exit(execution, lab.get('expected_exit', 0)) and
            execution['stdout'] == lab['stdout'] and not execution['stderr']):
        result['status'] = 'PASS'
    return result


def main(argv):
    if not argv:
        raise SystemExit('usage: verify_g.py CXX [CXX ...]')
    documents = [(path.name, path.read_text(encoding='utf-8'))
                 for path in sorted(ROOT.glob('g0[0-4]-*.md'))]
    if len(documents) != 5:
        raise ValueError('expected five G0–G4 documents')
    labs = extract(documents)
    all_cases = labs + mutations(labs)
    temp = Path(tempfile.mkdtemp(prefix='kb-g-learning-'))
    report = {'schema': 1, 'scope': 'G0-G4 targeted learning labs, not full technical acceptance',
              'source_documents_sha256': {name: sha(text.encode()) for name, text in documents},
              'runner_sha256': sha(Path(__file__).read_bytes()), 'toolchains': [],
              'temp_directory': str(temp), 'results': []}
    print(f'Evidence: {temp}', flush=True)
    try:
        for index, requested in enumerate(argv):
            compiler = shutil.which(requested)
            if compiler is None:
                report['results'].append({'compiler': requested, 'status': 'SKIP',
                                          'reason': 'compiler not found'})
                continue
            compiler = str(Path(compiler).absolute())
            tool_dir = temp / f'toolchain-{index}'
            tool_dir.mkdir()
            version = command([compiler, '--version'], tool_dir)
            if not clean_exit(version):
                report['results'].append({'compiler': compiler, 'status': 'FAIL',
                                          'reason': 'compiler identity check failed',
                                          'steps': [version]})
                continue
            # Read compiler/library macros; record the library family separately.
            probe = tool_dir / 'identity.cpp'
            probe.write_text('#include <version>\n', encoding='utf-8')
            macros = command([compiler, '-std=c++23', '-dM', '-E', str(probe)], tool_dir)
            if not clean_exit(macros):
                report['results'].append({'compiler': compiler, 'status': 'FAIL',
                                          'reason': 'standard library identity check failed',
                                          'steps': [macros]})
                continue
            report['toolchains'].append({'compiler': compiler, 'version': version,
                'identity_command': macros['command'],
                'library_macros': [line for line in macros['stdout'].splitlines()
                                   if re.match(r'#define (?:_LIBCPP_VERSION|__GLIBCXX__|_MSVC_STL_VERSION|__cplusplus) ', line)]})
            for lab in all_cases:
                result = verify(lab, compiler, tool_dir / lab['id'])
                result['compiler'] = compiler
                report['results'].append(result)
                print(f"{Path(compiler).parent}: {lab['id']} {result['status']}", flush=True)
        report['status'] = ('PASS' if report['results'] and
                            all(item['status'] == 'PASS' for item in report['results']) else 'INCOMPLETE')
    except BaseException as error:
        report.update(status='INCOMPLETE', error=repr(error))
        raise
    finally:
        # Diagnostic evidence, not a transactional publication or approval record.
        (temp / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                                         encoding='utf-8')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
