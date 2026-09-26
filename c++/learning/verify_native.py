#!/usr/bin/env python3
"""G8/G9 native experiments; Markdown source, output in a fresh temp tree."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import sys
import tempfile

from verify_g import command, clean_exit, diagnosed, sha

ROOT = Path(__file__).resolve().parents[1]
LAB = re.compile(r'<!-- n-lab (\{[^\n]+\}) -->')
FENCE = chr(96) * 3
FILE = re.compile(r'<!-- n-file (\{[^\n]+\}) -->\n' + FENCE +
                  r'(?:cpp|c|cmake|json|text)\n(.*?)\n' + FENCE, re.S)
MODES = {'G8-B1': 'symbols', 'G8-B2': 'c_shared', 'G9-P1': 'package', 'G9-P2': 'codegen'}


def extract(documents):
    labs, seen = [], set()
    for name, text in documents:
        markers = list(LAB.finditer(text))
        if text.count('<!-- n-lab ') != len(markers):
            raise ValueError('malformed lab marker')
        count = 0
        for i, marker in enumerate(markers):
            info = json.loads(marker[1])
            identity = info.get('id')
            if identity not in MODES or identity in seen or info.get('mode') != MODES[identity]:
                raise ValueError('invalid/duplicate lab or mode')
            seen.add(identity)
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            files = {}
            for match in FILE.finditer(text, marker.end(), end):
                path = json.loads(match[1])['path']
                parts = PurePosixPath(path).parts
                if (not re.fullmatch(r'[A-Za-z0-9_./-]+', path) or not parts or
                        path.startswith('/') or '..' in parts or
                        str(PurePosixPath(path)) != path or path in files):
                    raise ValueError('unsafe or duplicate path')
                files[path] = match[2] + '\n'
                count += 1
            if not files:
                raise ValueError('empty lab')
            labs.append(dict(info, document=name, files=files))
        if count != text.count('<!-- n-file '):
            raise ValueError('orphan or malformed file marker')
    if not labs:
        raise ValueError('no labs')
    return labs


def runtime(step, stdout='', code=0):
    return clean_exit(step, code) and step['stdout'] == stdout and not step['stderr']


def ctest_ok(step):
    return (clean_exit(step) and
            re.search(r'100% tests passed(?:, 0 tests failed)? out of [1-9][0-9]*',
                      step['stdout']) is not None)


def environment():
    # Reduce accidental search help; not a hermetic sandbox.
    result = dict(os.environ)
    for key in list(result):
        if (key.startswith(('CMAKE_', 'DYLD_', 'LD_')) or
                key in {'CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH',
                        'CC', 'CXX', 'CFLAGS', 'CXXFLAGS', 'LDFLAGS', 'SDKROOT'}):
            result.pop(key)
    return result


def verify(lab, compiler, folder, tools):
    folder.mkdir()
    for name, source in lab['files'].items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
    result = {k: v for k, v in lab.items() if k != 'files'}
    result.update(compiler=compiler, source_sha256={
        n: sha(s.encode()) for n, s in lab['files'].items()}, steps=[], evidence=[])
    env = environment()

    def run(args, cwd=folder):
        step = command([str(a) for a in args], cwd, timeout=60, env=env)
        result['steps'].append(step)
        return step

    def check(ok, claim, category='compile_link_consumer', status='PASS'):
        result['evidence'].append(dict(category=category, claim=claim,
                                       status=status if ok else 'FAIL'))
        return ok

    def build(args, label, cwd=folder):
        return check(clean_exit(run(args, cwd)), label)

    cc = str(Path(compiler).with_name('clang'))
    flags = [compiler, '-std=c++23', '-O0', '-Wall', '-Wextra', '-Wpedantic']
    cflags = [cc, '-std=c11', '-Wall', '-Wextra', '-Wpedantic']
    mode = lab['mode']
    if mode == 'symbols':
        for args in [cflags + ['-c', 'sum.c', '-o', 'sum.o'],
                     flags + ['-c', 'overloads.cpp', '-o', 'overloads.o'],
                     flags + ['-c', 'main.cpp', '-o', 'main.o'],
                     flags + ['-c', 'missing.cpp', '-o', 'missing.o']]:
            if not build(args, 'separate translation unit compiled'):
                return result
        if not build([compiler, 'main.o', 'sum.o', 'overloads.o', '-o', 'demo'],
                     'C/C++ positive linked'):
            return result
        check(runtime(run([folder / 'demo'])), 'positive values, complete checks')
        negative = run([compiler, 'missing.o', 'sum.o', '-o', 'missing'])
        check(diagnosed(negative, r'(?is)undefined.*native_sum|native_sum.*undefined'),
              'missing C linkage rejected by target symbol diagnostic')
        raw = run([tools['nm'], '-g', 'sum.o', 'overloads.o'])
        pretty = run([tools['nm'], '-g', '-C', 'sum.o', 'overloads.o'])
        check(clean_exit(raw) and clean_exit(pretty) and
              'native_sum' in raw['stdout'] and 'add(int, int)' in pretty['stdout'] and
              'add(double, double)' in pretty['stdout'],
              'raw and demangled symbols observed', 'binary_observation', 'OBSERVED')
    elif mode == 'c_shared':
        if not build(cflags + ['-c', 'consumer.c', '-o', 'consumer.o'], 'C11 consumer compiled'):
            return result
        if not build(flags + ['-fvisibility=hidden', '-dynamiclib', 'decoder.cpp',
                    '-Wl,-install_name,@rpath/libdecoder.dylib', '-o', 'libdecoder.dylib'],
                    'C++ shared provider compiled/linked'):
            return result
        if not build([compiler, 'consumer.o', '-L.', '-ldecoder',
                      '-Wl,-rpath,@loader_path', '-o', 'consumer'], 'C consumer linked'):
            return result
        expected_code = 4 if lab.get('mutation') else 0
        expected_text = '' if lab.get('mutation') else 'c-abi-contract-ok\n'
        check(runtime(run([folder / 'consumer']), expected_text, expected_code),
              'truncated output rejected with exit 4' if lab.get('mutation') else
              'C caller validates complete output, failure state and callbacks')
        exported = run([tools['nm'], '-gU', 'libdecoder.dylib'])
        dependencies = run([tools['otool'], '-L', 'consumer'])
        names = set(re.findall(r'\b_?(dec_[A-Za-z0-9_]+)$', exported['stdout'], re.M))
        check(clean_exit(exported) and names == {'dec_create', 'dec_destroy', 'dec_decode'} and
              clean_exit(dependencies) and '@rpath/libdecoder.dylib' in dependencies['stdout'],
              'named C exports and relative install name observed',
              'binary_observation', 'OBSERVED')
    elif mode == 'package':
        cmake, ctest = tools['cmake'], tools['ctest']
        producer, binary, prefix = folder / 'producer', folder / 'build', folder / 'install'
        common = [f'-DCMAKE_CXX_COMPILER={compiler}', '-DCMAKE_BUILD_TYPE=Debug',
                  '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', '-DCMAKE_INSTALL_LIBDIR=lib']
        if not build([cmake, '-S', producer, '-B', binary, '-G', 'Ninja', *common],
                     'producer configured'):
            return result
        if not build([cmake, '--build', binary, '--verbose'], 'producer built'):
            return result
        if not check(ctest_ok(run([ctest, '--test-dir', binary, '--output-on-failure', '--no-tests=error'])),
                     'producer CTest executed nonempty suite'):
            return result
        if not build([cmake, '--install', binary, '--prefix', prefix], 'temporary package installed'):
            return result
        moved = folder / 'relocated'
        prefix.rename(moved)
        producer.rename(folder / 'producer-hidden')
        binary.rename(folder / 'build-hidden')
        configs = list(moved.rglob('*.cmake'))
        clean = bool(configs) and all(str(producer) not in p.read_text() and
                                      str(binary) not in p.read_text() for p in configs)
        check(clean, 'installed CMake metadata has no producer/build paths')
        consumer_args = [cmake, '-S', folder / 'consumer', '-G', 'Ninja',
                         f'-DCMAKE_CXX_COMPILER={compiler}',
                         f'-DHandbookNative_DIR={moved}/lib/cmake/HandbookNative',
                         '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF',
                         '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF',
                         '-DCMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH=OFF']
        consumer_build = folder / 'consumer-build'
        if not build(consumer_args + ['-B', consumer_build], 'relocated consumer configured'):
            return result
        if not build([cmake, '--build', consumer_build, '--verbose'], 'relocated consumer built'):
            return result
        check(ctest_ok(run([ctest, '--test-dir', consumer_build, '--output-on-failure', '--no-tests=error'])),
              'installed consumer executed and retained helper dependency')
        wrong = run(consumer_args + ['-B', folder / 'wrong-version', '-DREQUESTED_VERSION=2'])
        check(diagnosed(wrong, r'(?s)HandbookNative.*compatible.*requested version "2"'),
              'incompatible requested major rejected during configure')
    elif mode == 'codegen':
        cmake, ctest = tools['cmake'], tools['ctest']
        if not build([cmake, '--preset', 'dev', f'-DCMAKE_CXX_COMPILER={compiler}'],
                     'dev preset configured'):
            return result
        if not build([cmake, '--build', '--preset', 'dev', '--verbose'], 'dev preset built'):
            return result
        if not check(ctest_ok(run([ctest, '--preset', 'dev', '--no-tests=error'])), 'test preset ran initial value check'):
            return result
        executable = folder / 'build/dev/generated_value'
        check(runtime(run([executable, '7']), '7\n'), 'initial generated value observed')
        source = folder / 'value.txt'
        source.write_text('19\n')
        header_time = (folder / 'build/dev/generated.hpp').stat().st_mtime_ns
        stamp = max(source.stat().st_mtime_ns, header_time + 1_000_000_000)
        os.utime(source, ns=(stamp, stamp))
        if not build([cmake, '--build', '--preset', 'dev', '--verbose'], 'incremental build completed'):
            return result
        observed = run([executable, '19'])
        check(runtime(observed, '7\n', 4) if lab.get('mutation') else runtime(observed, '19\n'),
              'missing dependency rejected with stale value and exit 4' if lab.get('mutation') else
              'input change regenerated value without manual reconfigure')
        result['input_edit'] = dict(path='value.txt', before='7\n', after='19\n')
    return result


def mutations(labs):
    result = []
    for identity, path, before, after, name in [
        ('G8-B2', 'decoder.cpp', '*count = size;', '*count = size ? 1 : 0;', 'truncated-count'),
        ('G9-P2', 'CMakeLists.txt', 'DEPENDS value.txt generate.cmake',
         'DEPENDS generate.cmake', 'missing-input-dependency')]:
        item = copy.deepcopy(next(l for l in labs if l['id'] == identity))
        if item['files'][path].count(before) != 1:
            raise ValueError('mutation site drift')
        item['files'][path] = item['files'][path].replace(before, after)
        item['mutation'] = name
        result.append(item)
    return result


def main(argv):
    if not argv:
        raise SystemExit('usage: verify_native.py /path/to/clang++ [...]')
    documents = [(p.name, p.read_text()) for p in sorted(ROOT.glob('g0[89]-*.md'))]
    labs = extract(documents)
    if {l['id'] for l in labs} != set(MODES):
        raise ValueError('incomplete experiment set')
    folder = Path(tempfile.mkdtemp(prefix='kb-native-'))
    report = dict(date=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
                  machine=platform.machine(), temp_directory=str(folder),
                  source_documents_sha256={n: sha(t.encode()) for n, t in documents},
                  runner_sha256=sha(Path(__file__).read_bytes()),
                  helper_sha256=sha((ROOT / 'learning/verify_g.py').read_bytes()),
                  tools={}, toolchains=[], results=[],
                  not_run=['PDF', 'performance measurement', 'concurrency dynamic detection',
                           'cross compilation', 'GCC/libstdc++/MSVC/Windows/Linux',
                           'Rust/Zig FFI', 'historical ABI upgrade', 'dlopen/unload lifecycle',
                           'PCH/Unity/LTO/modules', 'package-manager downloads'])
    print(f'Evidence: {folder}', flush=True)
    try:
        names = ['cmake', 'ctest', 'ninja', 'nm', 'otool']
        paths = {n: shutil.which(n) for n in names}
        for name, path in paths.items():
            report['tools'][name] = dict(path=path, status='FOUND' if path else 'SKIP')
            if path and name in {'cmake', 'ctest', 'ninja'}:
                report['tools'][name]['version'] = command([path, '--version'], folder)
        if platform.system() != 'Darwin' or not all(paths.values()):
            report.update(execution='INCOMPLETE',
                          reason='Darwin Clang/Mach-O only; tools missing or unsupported OS')
            return 1
        for index, requested in enumerate(argv):
            compiler = shutil.which(requested)
            if not compiler or not Path(compiler).with_name('clang').exists():
                report['toolchains'].append(dict(requested=requested, status='SKIP',
                                                 reason='Clang C/C++ pair unavailable'))
                continue
            work = folder / f'toolchain-{index}'
            work.mkdir()
            probe = work / 'identity.cpp'
            probe.write_text('#include <version>\n')
            version = command([compiler, '--version'], work)
            macros = command([compiler, '-std=c++23', '-dM', '-E', probe], work)
            report['toolchains'].append(dict(compiler=compiler, version=version,
                macro_command=macros['command'], library_macros=[l for l in macros['stdout'].splitlines()
                if re.match(r'#define (?:_LIBCPP_VERSION|__GLIBCXX__|__cplusplus) ', l)],
                status='IDENTIFIED' if clean_exit(version) and clean_exit(macros) else 'FAIL'))
            if not clean_exit(version) or not clean_exit(macros):
                continue
            for lab in labs + mutations(labs):
                suffix = '-' + lab['mutation'] if lab.get('mutation') else ''
                item = verify(lab, compiler, work / (lab['id'] + suffix), paths)
                report['results'].append(item)
                print(lab['id'] + suffix + ': ' + ','.join(e['status'] for e in item['evidence']), flush=True)
        report['summary_by_category'] = {}
        for item in report['results']:
            for evidence in item['evidence']:
                group = report['summary_by_category'].setdefault(evidence['category'], {})
                group[evidence['status']] = group.get(evidence['status'], 0) + 1
        statuses = [e['status'] for r in report['results'] for e in r['evidence']]
        statuses += [t['status'] for t in report['toolchains']]
        report['execution'] = 'FAILED' if 'FAIL' in statuses else 'INCOMPLETE' if 'SKIP' in statuses else 'RECORDED'
    except BaseException as error:
        report.update(execution='INTERRUPTED_OR_FAILED', error=repr(error))
        raise
    finally:
        (folder / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return 0 if report['execution'] == 'RECORDED' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
