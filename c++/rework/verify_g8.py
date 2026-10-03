#!/usr/bin/env python3
"""Extract G8's reviewed C/C++ files; preserve old inputs and separate evidence kinds."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = "e035f594a19e3e3c2674cfbee1f6d15bf88e0ac4"
HELPER = HERE.parent / "learning/verify_g.py"
spec = importlib.util.spec_from_file_location("g8_process", HELPER)
process = importlib.util.module_from_spec(spec)
spec.loader.exec_module(process)
CHAPTERS = ["g08-binary-contracts.md", "g08-c-boundary-and-ownership.md",
            "g08-loading-and-evolution.md"]
BLOCK = re.compile(r"\*\*[^*\n]*`([a-z][a-z0-9-]*\.(?:cpp|c|h))`[^*\n]*\*\*\n\n```(cpp|c)\n(.*?)\n```", re.S)
EXPECTED_FILES = {"abi-types.h", "abi-probe.h", "abi-sum.c", "abi-provider.cpp",
    "abi-caller.cpp", "abi-missing.cpp", "layout-observer.cpp", "reading-api.h",
    "reading-engine.cpp", "contract-suite.h", "contract-consumer.c",
    "reading-plugin.h", "reading-plugin.cpp", "plugin-host.c", "boundary-layout.c"}
NORMAL = "C consumer checked complete values and boundary contracts\n"
HOST = "unchanged host consumed the provider and destroyed every handle\n"
REJECT = "unsupported negotiation rejected without publishing a table\n"
FAULTS = {
    "create": ("RE_FAIL_CREATE", "--create-fails",
               "controlled create failure left no owned handle\n"),
    "prepare": ("RE_FAIL_PREPARE", "--prepare-fails",
                "controlled preparation failure preserved every output field\n"),
}
SAN = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
       "-fno-omit-frame-pointer"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, why):
    if not ok:
        raise ValueError(why)


def extract():
    sources, documents = {}, {}
    for name in CHAPTERS:
        payload = (HERE / name).read_bytes()
        documents[name] = sha(payload)
        text = payload.decode()
        matches = BLOCK.findall(text)
        require(len(matches) == len(re.findall(r"^```(?:cpp|c)$", text, re.M)),
                "Unbound source block: " + name)
        for filename, language, body in matches:
            require(filename not in sources, "Duplicate file: " + filename)
            require(language == ("cpp" if filename.endswith(".cpp") else "c"),
                    "Wrong language identity: " + filename)
            sources[filename] = body + "\n"
    require(set(sources) == EXPECTED_FILES, "Unexpected source set")
    return sources, documents


def matches(record, code=0, stdout="", diagnostic=None):
    if not process.clean_exit(record, code) or record["stdout"] != stdout:
        return False
    return (not record["stderr"] if diagnostic is None else
            all(re.search(p, record["stderr"]) for p in diagnostic))


def link_negative(record):
    return (not record["timed_out"] and record["returncode"] > 0 and
            re.search(r"[Uu]ndefined", record["stderr"]) is not None and
            "native_sum" in record["stderr"])


def selftests():
    good = dict(returncode=0, timed_out=False, stdout="ok\n", stderr="")
    missing = dict(good, returncode=10, stdout="", stderr="OPEN_REJECTED: missing.dylib")
    link = dict(good, returncode=1, stdout="", stderr="Undefined symbols: native_sum(int, int)")
    tests = {
        "exact_result": matches(good, stdout="ok\n"),
        "wrong_stdout_rejected": not matches(good, stdout="other\n"),
        "stderr_rejected": not matches(dict(good, stderr="unexpected"), stdout="ok\n"),
        "timeout_rejected": not matches(dict(good, timed_out=True), stdout="ok\n"),
        "crash_not_mutation_rejection": not matches(dict(good, returncode=-11), 12, "ok\n"),
        "mutation_exit_required": not matches(good, 12, "ok\n"),
        "loader_target_diagnostic": matches(missing, 10, diagnostic=["OPEN_REJECTED", "missing.dylib"]),
        "unrelated_loader_failure_rejected": not matches(dict(missing, stderr="other failure"),
                                                         10, diagnostic=["OPEN_REJECTED"]),
        "link_target_diagnostic": link_negative(link),
        "unrelated_link_failure_rejected": not link_negative(dict(link, stderr="Undefined: other")),
        "compile_success_not_link_negative": not link_negative(dict(link, returncode=0)),
        "link_timeout_rejected": not link_negative(dict(link, timed_out=True)),
    }
    require(all(tests.values()), "Oracle selftest failure")
    return tests


def protected_binding():
    entries = subprocess.check_output(["git", "ls-tree", "-r", "-z", BASE], cwd=ROOT)
    excluded = {"c++/README.md", "c++/rework/README.md"}
    count = 0
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        meta, raw_name = entry.split(b"\t", 1)
        name = raw_name.decode()
        if name in excluded:
            continue
        mode, kind, identity = meta.split()
        path = ROOT / name
        require(kind == b"blob" and path.is_file() and not path.is_symlink(),
                "Unsupported or missing protected input: " + name)
        data = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(blob == identity.decode(), "Protected input changed: " + name)
        count += 1
    return dict(base=BASE, unchanged_tracked_files=count, status="UNCHANGED",
                excluded_navigation=sorted(excluded), historical_rerun="NOT RUN")


class Suite:
    def __init__(self, report, sources, root, cc, cxx, nm, label):
        self.report, self.sources, self.root = report, sources, root
        self.cc, self.cxx, self.nm, self.label = cc, cxx, nm, label
        self.src = root / "source"
        self.src.mkdir(parents=True)
        for name, body in sources.items():
            (self.src / name).write_text(body, encoding="utf-8")
        self.env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0",
                        UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=0")

    def invoke(self, args, cwd=None, sanitized=False):
        rec = process.command(args, cwd or self.root, timeout=60,
                              env=self.env if sanitized else None)
        rec["toolchain"] = self.label
        self.report["commands"].append(rec)
        return len(self.report["commands"]) - 1, rec

    def build(self, args):
        index, rec = self.invoke(args)
        require(process.clean_exit(rec), "Build failed at command " + str(index))
        if "-o" in args:
            self.bind(Path(args[args.index("-o") + 1]))
        return index

    def bind(self, path):
        self.report["artifacts"][str(path)] = sha(path.read_bytes())

    def folder(self, name):
        path = self.root / name
        path.mkdir()
        return path

    def compile(self, name, out, flags, extra=(), source=None):
        compiler, std = (self.cc, "c11") if name.endswith(".c") else (self.cxx, "c++23")
        return self.build([compiler, "-std=" + std, "-Wall", "-Wextra", "-Wpedantic",
            "-I" + str(self.src), *flags, *extra, str(source or self.src / name), "-o", str(out)])

    def result(self, name, category, cmd, code=0, output="", diagnostic=None, builds=(), sanitized=False):
        index, rec = self.invoke(cmd, sanitized=sanitized)
        ok = matches(rec, code, output, diagnostic)
        status = ("CLEAN_OBSERVED" if sanitized else
                  "REJECTED_AS_EXPECTED" if category == "mutation" else "PASS") if ok else "FAIL"
        entry = dict(id=name, category=category, toolchain=self.label, status=status,
                     build_commands=list(builds), run_command=index, expected_exit=code,
                     expected_stdout=output, diagnostic_patterns=diagnostic)
        self.report["cases"].append(entry)
        print(self.label, name, status, flush=True)
        return entry

    def library(self, directory, flags, defines=(), plugin=False, source=None):
        path = directory / "libreading.dylib"
        args = [self.cxx, "-std=c++23", "-Wall", "-Wextra", "-Wpedantic",
                "-I" + str(self.src), *flags, "-fvisibility=hidden", *defines,
                "-dynamiclib", str(source or self.src / "reading-engine.cpp")]
        if plugin:
            args.append(str(self.src / "reading-plugin.cpp"))
        index = self.build(args + ["-Wl,-install_name,@rpath/libreading.dylib", "-o", str(path)])
        return path, index

    def direct(self, name, flags, defines=(), argument=None, output=NORMAL, code=0,
               category="contract", sanitized=False, source=None):
        folder = self.folder(name)
        obj, exe = folder / "consumer.o", folder / "consumer"
        builds = [self.compile("contract-consumer.c", obj, flags, ["-c"])]
        library, index = self.library(folder, flags, defines, source=source)
        builds.append(index)
        builds.append(self.build([self.cxx, *flags, str(obj), str(library),
                                  "-Wl,-rpath,@loader_path", "-o", str(exe)]))
        self.result(name, category, [str(exe)] + ([argument] if argument else []),
                    code, output, builds=builds, sanitized=sanitized)
        return library

    def probes(self):
        for opt in ("-O0", "-O2"):
            folder = self.folder("binary" + opt)
            objects, builds = {}, []
            for source in ("abi-sum.c", "abi-provider.cpp", "abi-caller.cpp", "abi-missing.cpp"):
                obj = folder / (source + ".o")
                builds.append(self.compile(source, obj, [opt], ["-c"]))
                objects[source] = obj
            exe = folder / "caller"
            builds.append(self.build([self.cxx, str(objects["abi-caller.cpp"]),
                str(objects["abi-provider.cpp"]), str(objects["abi-sum.c"]), "-o", str(exe)]))
            self.result("separate-call" + opt, "contract", [str(exe)],
                        output="separate callers agree on values and call boundaries\n", builds=builds)
            index, rec = self.invoke([self.cxx, str(objects["abi-missing.cpp"]),
                str(objects["abi-sum.c"]), "-o", str(folder / "missing")])
            self.report["cases"].append(dict(id="missing-C-linkage" + opt, category="link_negative",
                toolchain=self.label, status="PASS" if link_negative(rec) else "FAIL",
                build_commands=builds[:4], link_command=index,
                diagnostic_patterns=["[Uu]ndefined", "native_sum"]))
            observation = dict(kind="symbols_and_lowering", toolchain=self.label, mode=opt,
                               status="OBSERVED", commands=[], assembly={})
            for name, obj in objects.items():
                for options in ([], ["--demangle"]):
                    index, result = self.invoke([self.nm, *options, str(obj)])
                    observation["commands"].append(index)
                    require(process.clean_exit(result), "nm observation failed")
            for name in ("abi-caller.cpp", "abi-provider.cpp"):
                asm = folder / (name + ".s")
                index = self.compile(name, asm, [opt], ["-S"])
                observation["commands"].append(index)
                observation["assembly"][str(asm)] = asm.read_text()
            self.report["observations"].append(observation)
        folder = self.folder("layout")
        exe = folder / "layout"
        build = self.compile("layout-observer.cpp", exe, ["-O0"])
        index, rec = self.invoke([str(exe)])
        pattern = (r"ReadingV1 size=\d+ align=\d+ value_offset=\d+\n"
                   r"ReadingV2 size=\d+ align=\d+ time_offset=\d+\n"
                   r"OwnerV1 size=\d+ align=\d+\nOwnerV2 size=\d+ align=\d+\n")
        require(process.clean_exit(rec) and not rec["stderr"] and re.fullmatch(pattern, rec["stdout"]),
                "Incomplete layout observation")
        self.report["observations"].append(dict(kind="layout", toolchain=self.label,
            status="OBSERVED", build_command=build, run_command=index, fixed_size_oracle=False))

    def dynamic(self):
        folder = self.folder("dynamic")
        layouts = []
        layout_steps = []
        for compiler, language, std in ((self.cc, "c", "c11"), (self.cxx, "c++", "c++23")):
            exe = folder / ("layout-" + language)
            layout_steps.append(self.build([compiler, "-std=" + std, "-x", language,
                "-Wall", "-Wextra", "-Wpedantic", "-I" + str(self.src),
                str(self.src / "boundary-layout.c"), "-o", str(exe)]))
            index, rec = self.invoke([str(exe)])
            layout_steps.append(index)
            require(process.clean_exit(rec) and not rec["stderr"], "Public layout probe failed")
            layouts.append(rec["stdout"])
        require(layouts[0] == layouts[1] and len(layouts[0].splitlines()) == 16,
                "C/C++ public layout mismatch or incomplete observation")
        self.report["observations"].append(dict(kind="C_and_CPP_public_layout", toolchain=self.label,
            status="OBSERVED", relation="MATCH", commands=layout_steps, fixed_size_oracle=False))
        host = folder / "host"
        build = self.compile("plugin-host.c", host, ["-O2"])
        before = sha(host.read_bytes())
        libraries = []
        for version in (1, 2):
            target = self.folder("provider" + str(version))
            library, lib_build = self.library(target, ["-O2"], ["-DRE_IMPLEMENTATION=" + str(version)], True)
            libraries.append(library)
            self.result("old-host-impl" + str(version), "compatibility", [str(host), str(library)],
                        output=HOST, builds=[build, lib_build])
            for mode in ("--wrong-version", "--wrong-size"):
                self.result("impl" + str(version) + mode, "negotiation",
                            [str(host), str(library), mode], output=REJECT, builds=[build, lib_build])
            indices = []
            for cmd in ([self.nm, "--defined-only", "--extern-only", str(library)],
                        ["/usr/bin/otool", "-L", str(library)], ["/usr/bin/otool", "-D", str(library)]):
                index, rec = self.invoke(cmd)
                require(process.clean_exit(rec), "Library observation failed")
                if cmd[0] == self.nm:
                    defined = set(re.findall(r"\b_re_[a-z_]+\b", rec["stdout"]))
                    require(defined == {"_re_create", "_re_destroy", "_re_process", "_re_get_api"},
                            "Product export surface changed")
                indices.append(index)
            self.report["observations"].append(dict(kind="product_exports_and_dependencies",
                status="OBSERVED", toolchain=self.label, implementation=version, commands=indices))
        missing = folder / "not-present.dylib"
        require(not missing.exists(), "Missing-library fixture exists")
        self.result("missing-library", "loading_negative", [str(host), str(missing)], 10,
                    diagnostic=["OPEN_REJECTED", "not-present.dylib"], builds=[build])
        library, lib_build = self.library(self.folder("no-entry"), ["-O2"], ["-DRE_OMIT_ENTRY"], True)
        self.result("missing-entry", "loading_negative", [str(host), str(library)], 11,
                    diagnostic=["LOOKUP_REJECTED", "re_get_api"], builds=[build, lib_build])
        # Compile a separate provider with a missing version guard; never edit the source corpus.
        target = self.folder("mutation-version")
        old = "if (requested != 1) return RE_VERSION;"
        require(self.sources["reading-plugin.cpp"].count(old) == 1, "Version mutation drift")
        mutant = target / "reading-plugin.cpp"
        mutant.write_text(self.sources["reading-plugin.cpp"].replace(old, "(void)requested;"))
        self.report["mutation_sources"][str(mutant)] = sha(mutant.read_bytes())
        library = target / "libreading.dylib"
        lib_build = self.build([self.cxx, "-std=c++23", "-O2", "-fvisibility=hidden",
            "-I" + str(self.src), "-dynamiclib", str(self.src / "reading-engine.cpp"), str(mutant),
            "-o", str(library)])
        self.result("accept-unknown-api-version", "mutation",
                    [str(host), str(library), "--wrong-version"], 21, builds=[build, lib_build])
        after = sha(host.read_bytes())
        require(before == after, "Old host changed while replacing providers")
        self.report["compatibility_binding"].append(dict(toolchain=self.label,
            host=str(host), before_sha256=before, after_sha256=after,
            providers={str(p): sha(p.read_bytes()) for p in libraries},
            public_headers={n: sha(self.sources[n].encode()) for n in ("reading-api.h", "reading-plugin.h")},
            status="UNCHANGED_HOST", scope="one provider per process; same platform and runtime family"))

    def run(self):
        self.probes()
        for opt in ("-O0", "-O2"):
            self.direct("direct" + opt, [opt])
        for name, (macro, argument, output) in FAULTS.items():
            self.direct("fault-" + name, ["-O2"], ["-D" + macro], argument, output, category="fault_contract")
        for name, old, new, code in (
            ("accept-unknown-config", "if (config->abi_version != 1) return RE_VERSION;",
             "if (config->abi_version == 0) return RE_VERSION;", 2),
            ("ignore-capacity", "if (capacity < count) return RE_SMALL;", "// Incorrect: ignore capacity.", 12),
            ("omit-written", "*written = count;", "*written = 0;", 14)):
            require(self.sources["reading-engine.cpp"].count(old) == 1, "Mutation drift: " + name)
            path = self.src / (name + ".cpp")
            path.write_text(self.sources["reading-engine.cpp"].replace(old, new))
            self.report["mutation_sources"][str(path)] = sha(path.read_bytes())
            self.direct(name, ["-O2"], output="", code=code, category="mutation", source=path)
        self.dynamic()
        probe = self.src / "sanitizer-probe.cpp"
        probe.write_text(self.report["harness_sources"]["sanitizer-probe.cpp"])
        exe = self.root / "sanitizer-probe"
        index, rec = self.invoke([self.cxx, "-std=c++23", *SAN, str(probe), "-o", str(exe)])
        available = process.clean_exit(rec)
        steps = [index]
        if available:
            self.bind(exe)
            index, rec = self.invoke([str(exe)], sanitized=True)
            steps.append(index)
            available = matches(rec)
        self.report["sanitizer_probes"].append(dict(toolchain=self.label, commands=steps,
            status="AVAILABLE" if available else "UNAVAILABLE", positive_control="NOT RUN"))
        if not available:
            self.report["cases"].append(dict(id="sanitized-direct-and-faults", category="sanitizer",
                toolchain=self.label, status="SKIP", reason="Sanitizer runtime probe unavailable"))
        else:
            self.direct("sanitized-direct", SAN, ["-DRE_IMPLEMENTATION=2"], category="sanitizer", sanitized=True)
            for name, (macro, argument, output) in FAULTS.items():
                self.direct("sanitized-" + name, SAN, ["-D" + macro, "-DRE_IMPLEMENTATION=2"],
                            argument, output, category="sanitizer", sanitized=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--toolchain", action="append", nargs=2, metavar=("CC", "CXX"), required=True)
    parser.add_argument("--nm", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Choose a new output; never overwrite evidence")
    require(platform.system() == "Darwin" and platform.machine() == "arm64",
            "SKIP: runner currently qualifies macOS arm64 only")
    sources, documents = extract()
    work = Path(tempfile.mkdtemp(prefix="kb-g8-rework-"))
    report = dict(started_at_utc=datetime.now(timezone.utc).isoformat(), base=BASE,
        platform=platform.platform(), macOS=platform.mac_ver()[0], machine=platform.machine(),
        python=platform.python_version(), documents=documents,
        source_sha256={n: sha(s.encode()) for n, s in sources.items()},
        runner_sha256=sha(Path(__file__).read_bytes()), helper_sha256=sha(HELPER.read_bytes()),
        temp_directory=str(work), protected_before=protected_binding(), oracle_selftests=selftests(),
        commands=[], cases=[], observations=[], artifacts={}, mutation_sources={}, toolchains=[],
        compatibility_binding=[], sanitizer_probes=[], status="RUNNING",
        performance="NOT RUN", concurrency_dynamic="NOT RUN", cross_platform="NOT ESTABLISHED",
        pdf="NOT BUILT / NOT VALIDATED", leak_sanitizer="DISABLED",
        asan_positive_control="NOT RUN", arbitrary_pointer_validation="NOT PROVIDED",
        harness_sources={"identity.cpp": "#include <version>\n",
            "sanitizer-probe.cpp": "int main() { volatile int n = 7; return n == 7 ? 0 : 1; }\n"})
    try:
        for number, (cc, cxx) in enumerate(args.toolchain):
            label = "toolchain-" + str(number)
            suite = Suite(report, sources, work / label, cc, cxx, args.nm, label)
            identity = {"id": label, "cc": cc, "cxx": cxx, "commands": []}
            for cmd in ([cc, "--version"], [cxx, "--version"], [cxx, "-print-target-triple"],
                        [args.nm, "--version"], ["/usr/bin/xcrun", "--show-sdk-path"],
                        ["/usr/bin/xcrun", "--show-sdk-version"]):
                index, rec = suite.invoke(cmd)
                require(process.clean_exit(rec), "Toolchain identity failed")
                identity["commands"].append(index)
            probe = suite.src / "identity.cpp"
            probe.write_text(report["harness_sources"]["identity.cpp"])
            index, rec = suite.invoke([cxx, "-std=c++23", "-dM", "-E", str(probe)])
            require(process.clean_exit(rec), "Standard library identity failed")
            identity["macro_command"] = index
            identity["library_macros"] = [line for line in rec["stdout"].splitlines()
                if re.match(r"#define (?:_LIBCPP_VERSION|__GLIBCXX__|__cplusplus) ", line)]
            report["toolchains"].append(identity)
            report["sanitizer_environment"] = {k: suite.env[k] for k in ("ASAN_OPTIONS", "UBSAN_OPTIONS")}
            suite.run()
        require(extract() == (sources, documents), "Sources changed during execution")
        report["protected_after"] = protected_binding()
        require(all(sha(Path(path).read_bytes()) == digest for path, digest in report["artifacts"].items()),
                "A recorded build artifact changed during execution")
        report["status"] = "FAILED" if any(c["status"] == "FAIL" for c in report["cases"]) else "COMPLETED"
    except KeyboardInterrupt:
        report["status"] = "CANCELLED"
        report["error"] = "Interrupted; active child process group terminated by process helper"
    except Exception as error:
        report["status"] = "FAILED"
        report["error"] = repr(error)
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["case_counts"] = {category: dict(Counter(c["status"] for c in report["cases"] if c["category"] == category))
                             for category in sorted({c["category"] for c in report["cases"]})}
    with args.output.open("x", encoding="utf-8") as target:
        json.dump(report, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps({k: report[k] for k in ("status", "case_counts", "temp_directory")}, indent=2))
    if "error" in report:
        print(report["error"], file=sys.stderr)
    return 0 if report["status"] == "COMPLETED" else 130 if report["status"] == "CANCELLED" else 1


if __name__ == "__main__":
    sys.exit(main())
