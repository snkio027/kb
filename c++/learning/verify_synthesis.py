#!/usr/bin/env python3
"""G10/G11 integrated experiments; G12 is a review protocol, not another runner."""
import copy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import sys
import tempfile

from verify_g import command, clean_exit, sha
from verify_handbook import extract as handbook_extract
from verify_native import environment, ctest_ok

ROOT = Path(__file__).resolve().parents[1]
FENCE = chr(96) * 3
LAB = re.compile(r'<!-- s-lab (\{[^\n]+\}) -->')
FILE = re.compile(r'<!-- s-file (\{[^\n]+\}) -->\n' + FENCE +
                  r'(?:cpp|c|cmake|json|text)\n(.*?)\n' + FENCE, re.S)
MODES = {'G10-R1': 'runtime', 'G11-C1': 'control'}
EXPECTED = {'runtime': 'runtime protocols verified\n',
            'control': 'control verified; tracked_cpp_allocations=0\n'
                       'snapshot generations verified\n'}


def extract(documents):
    result, seen = [], set()
    for name, text in documents:
        markers = list(LAB.finditer(text))
        if len(markers) != text.count('<!-- s-lab '):
            raise ValueError('malformed lab')
        count = 0
        for i, marker in enumerate(markers):
            info = json.loads(marker[1])
            identity = info.get('id')
            if identity not in MODES or identity in seen or info.get('mode') != MODES[identity]:
                raise ValueError('unknown/duplicate lab')
            seen.add(identity)
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            files = {}
            for match in FILE.finditer(text, marker.end(), end):
                path = json.loads(match[1])['path']
                parts = PurePosixPath(path).parts
                if (not re.fullmatch(r'[A-Za-z0-9_./-]+', path) or not parts or
                        path.startswith('/') or '..' in parts or
                        str(PurePosixPath(path)) != path or path in files):
                    raise ValueError('unsafe/duplicate source path')
                files[path] = match[2] + '\n'
                count += 1
            if not files:
                raise ValueError('empty lab')
            result.append(dict(info, document=name, files=files))
        if count != text.count('<!-- s-file '):
            raise ValueError('orphan/malformed source')
    if seen != set(MODES):
        raise ValueError('expected exactly G10-R1 and G11-C1')
    return result


def mutation(lab, name, path, before, after, code):
    result = copy.deepcopy(lab)
    if result['files'][path].count(before) != 1:
        raise ValueError('mutation target must match once')
    result['files'][path] = result['files'][path].replace(before, after)
    result.update(mutation=name, expected_code=code,
                  change={'path': path, 'before': before, 'after': after})
    return result


def mutations(labs):
    runtime, control = (next(x for x in labs if x['mode'] == m)
                        for m in ('runtime', 'control'))
    return [
        mutation(runtime, 'close-output-early', 'src/runtime.cpp',
                 '    impl_->input.close();',
                 '    impl_->output.close();\n    impl_->input.close();', 10),
        mutation(control, 'accept-stale', 'control.hpp',
                 "            && now - s.sensor_ns <= 5'000'000\n"
                 "            && now - s.command_ns <= 50'000'000\n", '', 21),
        mutation(control, 'mixed-generation', 'control.hpp',
                 '        value_ = value;', '        value_ = value;\n        ++value_.position;', 31),
        mutation(control, 'allocate-in-step', 'control.hpp',
                 '        if (mode_ != Mode::active) return 0;',
                 '        void* p = ::operator new(1);\n        ::operator delete(p);\n'
                 '        if (mode_ != Mode::active) return 0;', 30)
    ]


def exact(step, stdout, code=0, stderr=''):
    return clean_exit(step, code) and step['stdout'] == stdout and step['stderr'] == stderr


def sanitizer_environment(base, kind):
    env = {k: v for k, v in base.items()
           if k not in {'ASAN_OPTIONS', 'UBSAN_OPTIONS', 'TSAN_OPTIONS', 'LSAN_OPTIONS'}}
    common = 'halt_on_error=1:abort_on_error=0:symbolize=0:'
    if kind in {'asan', 'asan_ubsan'}:
        env['ASAN_OPTIONS'] = common + 'exitcode=86:detect_leaks=0'
    if kind == 'asan_ubsan':
        env['UBSAN_OPTIONS'] = common + 'exitcode=86:print_stacktrace=0'
    if kind == 'ubsan':
        env['UBSAN_OPTIONS'] = common + 'exitcode=1:print_stacktrace=0'
    if kind == 'tsan':
        env['TSAN_OPTIONS'] = common + 'exitcode=66'
    return env


def mutation_rejected(step, lab):
    code = lab['expected_code']
    prefix = 'invariant=' if lab['mode'] == 'runtime' else 'control invariant='
    # Mixed-generation fails after the allocation result was printed.
    stdout = ('control verified; tracked_cpp_allocations=0\n'
              if lab['mutation'] == 'mixed-generation' else '')
    return exact(step, stdout, code, prefix + str(code) + '\n')


def runtime_observation(output):
    rows, seen = [], set()
    wanted = {(w, c, r) for w in (1, 2, 4) for c in (1, 16) for r in range(3)}
    for line in output.splitlines():
        w, c, trial, n, seconds, checksum = line.split(',')
        key = int(w), int(c), int(trial)
        seconds = float(seconds)
        if (key not in wanted or key in seen or int(n) != 2000 or
                int(checksum) != 384000 or not math.isfinite(seconds) or seconds <= 0):
            raise ValueError('invalid runtime observation')
        seen.add(key)
        rows.append(dict(workers=key[0], capacity=key[1], repeat=key[2], items=int(n),
                         seconds=seconds, checksum=int(checksum), items_per_second=int(n) / seconds))
    if seen != wanted:
        raise ValueError('incomplete runtime sweep')
    return rows


def timing_observation(output):
    lines = output.splitlines()
    if len(lines) != 1001 or not lines[0].startswith('position='):
        raise ValueError('expected plant value and 1000 ticks')
    position = float(lines[0].split('=')[1])
    if not math.isfinite(position):
        raise ValueError('nonfinite plant')
    wake, execution, misses = [], [], 0
    for i, line in enumerate(lines[1:]):
        tick, w, e, missed = map(int, line.split(','))
        if tick != i or e < 0 or missed not in (0, 1):
            raise ValueError('bad timing record')
        if missed != int(w + e > 1_000_000):
            raise ValueError('deadline flag inconsistent with timestamps')
        wake.append(w)
        execution.append(e)
        misses += missed

    def stats(values):
        ordered = sorted(values)
        return dict(min=ordered[0], p50=ordered[499], p99=ordered[989], max=ordered[-1])
    return dict(cycles=1000, period_ns=1_000_000, final_position=position,
                release_offset_ns=stats(wake), execution_ns=stats(execution),
                deadline_misses=misses, guarantee='timing observation on this machine')


class Session:
    def __init__(self, folder, compiler, identity):
        self.folder, self.compiler = folder, compiler
        self.env = environment()
        self.result = dict(identity, compiler=compiler, steps=[], evidence=[])

    def run(self, args, cwd=None, env=None):
        step = command([str(a) for a in args], cwd or self.folder,
                       timeout=60, env=env or self.env)
        step['sanitizer_options'] = {k: v for k, v in (env or self.env).items()
                                     if k in {'ASAN_OPTIONS', 'UBSAN_OPTIONS', 'TSAN_OPTIONS'}}
        self.result['steps'].append(step)
        return step

    def check(self, ok, claim, category='cpp_validation', status='PASS', **fields):
        self.result['evidence'].append(dict(category=category, claim=claim,
                                            status=status if ok else 'FAIL', **fields))
        return ok

    def build(self, args, claim):
        return self.check(clean_exit(self.run(args)), claim)


def controls(compiler, folder, race_source):
    folder.mkdir()
    s = Session(folder, compiler, {'id': 'instrumentation-controls'})
    sources = {
        'clean.cpp': '#include <thread>\nint main(){std::jthread t([]{});t.join();}\n',
        'asan.cpp': '#include <cstdlib>\nint main(){auto*p=new int[1];delete[]p;'
                    'volatile int n=*p;return n;}\n',
        'ubsan.cpp': '#include <climits>\nint main(){volatile int x=INT_MAX;'
                     'volatile int y=x+1;return y;}\n',
        'race.cpp': race_source}
    s.result['source_sha256'] = {n: sha(t.encode()) for n, t in sources.items()}
    s.result['fixture_sources'] = sources
    for name, text in sources.items():
        (folder / name).write_text(text)
    available = {}
    for kind, flags, filename, code, diagnostic in [
        ('asan', ['-fsanitize=address'],
         'asan.cpp', 86, r'AddressSanitizer: heap-use-after-free'),
        ('ubsan', ['-fsanitize=undefined', '-fno-sanitize-recover=all'],
         'ubsan.cpp', 1, r'runtime error: signed integer overflow'),
        ('tsan', ['-fsanitize=thread'], 'race.cpp', 66, r'ThreadSanitizer: data race')]:
        env = sanitizer_environment(s.env, kind)
        base = [compiler, '-std=c++23', '-O1', '-g', '-pthread', *flags]
        clean = folder / (kind + '-clean')
        target = folder / (kind + '-control')
        category = 'concurrency_dynamic' if kind == 'tsan' else 'cpp_validation'
        if not s.build(base + ['clean.cpp', '-o', clean], kind + ' clean probe compiled'):
            available[kind] = False
            continue
        step = s.run([clean], env=env)
        if not s.check(exact(step, ''), kind + ' runtime startup probe', category):
            available[kind] = False
            continue
        if not s.build(base + [filename, '-o', target], kind + ' known-fault control compiled'):
            available[kind] = False
            continue
        step = s.run([target], env=env)
        detected = (clean_exit(step, code) and not step['stdout'] and
                    re.search(diagnostic, step['stderr']) is not None)
        available[kind] = s.check(detected, kind + ' target diagnostic and controlled exit',
                                   category, 'DETECTED')
    s.result['available'] = available
    return s.result


def verify(lab, compiler, folder, tools, available):
    folder.mkdir()
    for path, source in lab['files'].items():
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding='utf-8')
    s = Session(folder, compiler, {k: v for k, v in lab.items() if k != 'files'})
    s.result['source_sha256'] = {p: sha(t.encode()) for p, t in lab['files'].items()}
    flags = [compiler, '-std=c++23', '-O1', '-g', '-Wall', '-Wextra', '-Wpedantic', '-pthread']
    inputs = (['-Iinclude', 'src/runtime.cpp', 'tests/runtime_test.cpp']
              if lab['mode'] == 'runtime' else ['control_test.cpp', 'allocations.cpp'])
    target = folder / 'native'
    if not s.build(flags + inputs + ['-o', target], 'native complete module compiled/linked'):
        return s.result
    step = s.run([target])
    if lab.get('mutation'):
        s.check(mutation_rejected(step, lab), 'compiled wrong implementation rejected by target invariant')
        return s.result
    if not s.check(exact(step, EXPECTED[lab['mode']]), 'native functional/protocol invariants'):
        return s.result
    for kind, options in [('asan_ubsan', ['-fsanitize=address,undefined',
                                         '-fno-sanitize-recover=all']),
                          ('tsan', ['-fsanitize=thread'])]:
        category = 'concurrency_dynamic' if kind == 'tsan' else 'cpp_validation'
        supported = (available.get('asan') and available.get('ubsan')
                     if kind == 'asan_ubsan' else available.get(kind))
        if not supported:
            s.result['evidence'].append(dict(category=category, status='SKIP',
                claim=kind + ' module execution', reason='instrumentation control unavailable/failed'))
            continue
        target = folder / kind
        if s.build(flags + options + inputs + ['-o', target], kind + ' complete module compiled'):
            env = sanitizer_environment(s.env, kind)
            step = s.run([target], env=env)
            s.check(exact(step, EXPECTED[lab['mode']]), kind + ' invariants and no diagnostic',
                    category, 'CLEAN_OBSERVED')
    if lab['mode'] == 'runtime':
        cmake, ctest = tools['cmake'], tools['ctest']
        source, build, prefix = folder, folder / 'build', folder / 'prefix'
        args = [cmake, '-S', source, '-B', build, '-G', 'Ninja',
                '-DCMAKE_CXX_COMPILER=' + compiler, '-DCMAKE_BUILD_TYPE=Release']
        if not s.build(args, 'runtime package configured'):
            return s.result
        if not s.build([cmake, '--build', build], 'runtime package built'):
            return s.result
        s.check(ctest_ok(s.run([ctest, '--test-dir', build, '--output-on-failure',
                               '--no-tests=error'])), 'nonempty runtime CTest suite')
        if not s.build([cmake, '--install', build, '--prefix', prefix], 'runtime installed'):
            return s.result
        step = s.run([build / 'runtime_bench'])
        try:
            if not exact(step, step['stdout']):
                raise ValueError('benchmark process failed')
            rows = runtime_observation(step['stdout'])
            s.check(True, 'worker/capacity sweep; no speed threshold',
                    'performance_observation', 'OBSERVED', rows=rows)
        except ValueError as error:
            s.check(False, 'runtime measurement records', 'performance_observation', reason=str(error))
        # Hide only generated trees within this fresh attempt; never rename repository paths.
        consumer = folder.parent / (folder.name + '-external-consumer')
        shutil.copytree(folder / 'consumer', consumer)
        moved = folder.parent / (folder.name + '-installed')
        prefix.rename(moved)
        hidden = folder.with_name(folder.name + '-hidden')
        folder.rename(hidden)
        s.folder = hidden
        cb = consumer / 'build'
        configure = [cmake, '-S', consumer, '-B', cb, '-G', 'Ninja',
                     '-DCMAKE_CXX_COMPILER=' + compiler,
                     '-DCMAKE_C_COMPILER=' + str(Path(compiler).with_name('clang')),
                     '-DCMAKE_PREFIX_PATH=' + str(moved),
                     '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF',
                     '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF']
        if s.build(configure, 'independent C/C++ consumer configured after relocation'):
            if s.build([cmake, '--build', cb], 'independent C/C++ consumer built'):
                s.check(ctest_ok(s.run([ctest, '--test-dir', cb, '--output-on-failure',
                    '--no-tests=error'])), 'independent C/C++ consumer nonempty CTest suite')
    else:
        target = folder / 'timing'
        if s.build([compiler, '-std=c++23', '-O2', '-pthread', 'timing.cpp', '-o', target],
                   'timing observer compiled separately without sanitizer'):
            step = s.run([target])
            try:
                if not exact(step, step['stdout']):
                    raise ValueError('timing process failed')
                summary = timing_observation(step['stdout'])
                s.check(True, '1 kHz simulated loop; no deadline acceptance threshold',
                        'performance_observation', 'OBSERVED', summary=summary)
            except ValueError as error:
                s.check(False, 'timing observation contract', 'performance_observation', reason=str(error))
    return s.result


def main(argv):
    if not argv:
        raise SystemExit('usage: verify_synthesis.py CXX [CXX ...]')
    documents = [(p.name, p.read_text()) for p in sorted(ROOT.glob('g1[01]-*.md'))]
    labs = extract(documents)
    g7 = ROOT / 'g07-concurrency-and-memory-model.md'
    race = next(x for x in handbook_extract([(g7.name, g7.read_text())])
                if x['id'] == 'G7-D3')['files']['main.cpp']
    folder = Path(tempfile.mkdtemp(prefix='kb-synthesis-'))
    report = dict(schema=1, started_at_utc=datetime.now(timezone.utc).isoformat(),
        base='4d7158a023aee00b54e565a57cda953fac3a5b48',
        platform=platform.platform(), machine=platform.machine(), temp_directory=str(folder),
        source_documents_sha256={n: sha(t.encode()) for n, t in documents},
        runner_sha256=sha(Path(__file__).read_bytes()),
        helpers_sha256={n: sha((ROOT / 'learning' / n).read_bytes())
                        for n in ('verify_g.py', 'verify_handbook.py', 'verify_native.py')},
        g7_control_document_sha256=sha(g7.read_bytes()),
        tools={}, toolchains=[], results=[], pdf='NOT BUILT / NOT VALIDATED',
        not_run=['formal protocol proof/model checking', 'CPU sampling profile',
                 'hardware counters/page faults', 'ROS/RMW/QoS', 'HIL/real hardware',
                 'hard-real-time or physical safety validation', 'Rust/Zig compilation',
                 'Linux/Windows/GCC/libstdc++', 'historical shared ABI compatibility',
                 'allocation failure/OS synchronization failure', 'unbounded service endurance'])
    print('Evidence: ' + str(folder), flush=True)
    try:
        tools = {n: shutil.which(n) for n in ('cmake', 'ctest', 'ninja')}
        for name, path in tools.items():
            report['tools'][name] = dict(path=path, status='FOUND' if path else 'SKIP',
                version=command([path, '--version'], folder) if path else None)
        if platform.system() != 'Darwin' or not all(tools.values()):
            report.update(execution='INCOMPLETE', reason='Darwin/Clang and CMake/CTest/Ninja required')
            return 1
        for index, requested in enumerate(argv):
            compiler = shutil.which(requested)
            if not compiler or not Path(compiler).with_name('clang').exists():
                report['toolchains'].append(dict(requested=requested, status='SKIP',
                                                 reason='Clang C/C++ pair unavailable'))
                continue
            work = folder / ('toolchain-' + str(index))
            work.mkdir()
            probe = work / 'identity.cpp'
            probe.write_text('#include <version>\n')
            version = command([compiler, '--version'], work)
            macros = command([compiler, '-std=c++23', '-dM', '-E', probe], work)
            identity = dict(compiler=compiler, version=version, macro_command=macros['command'],
                library_macros=[line for line in macros['stdout'].splitlines()
                    if re.match(r'#define (?:_LIBCPP_VERSION|__GLIBCXX__|__cplusplus) ', line)],
                status='IDENTIFIED' if clean_exit(version) and clean_exit(macros) else 'FAIL')
            report['toolchains'].append(identity)
            if identity['status'] == 'FAIL':
                continue
            control = controls(compiler, work / 'controls', race)
            report['results'].append(control)
            for lab in labs + mutations(labs):
                suffix = '-' + lab['mutation'] if lab.get('mutation') else ''
                result = verify(lab, compiler, work / (lab['id'] + suffix), tools, control['available'])
                report['results'].append(result)
                print(lab['id'] + suffix + ': ' +
                      ','.join(e['status'] for e in result['evidence']), flush=True)
        report['summary_by_category'] = {}
        statuses = [t['status'] for t in report['toolchains']]
        for result in report['results']:
            for evidence in result['evidence']:
                statuses.append(evidence['status'])
                category = report['summary_by_category'].setdefault(evidence['category'], {})
                category[evidence['status']] = category.get(evidence['status'], 0) + 1
        report['execution'] = ('FAILED' if 'FAIL' in statuses else
                               'INCOMPLETE' if 'SKIP' in statuses else 'RECORDED')
    except BaseException as error:
        report.update(execution='INTERRUPTED_OR_FAILED', error=repr(error))
        raise
    finally:
        (folder / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if report['execution'] == 'RECORDED' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
