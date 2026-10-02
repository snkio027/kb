#!/usr/bin/env python3
"""Extract G7 source; separate contracts, stress, logical negatives and TSan evidence."""

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
BASE = "c1e8ab7a33f450ef5663085ecdd00ce41ce1692a"
HELPER = HERE.parent / "learning/verify_g.py"
spec = importlib.util.spec_from_file_location("g_process_helpers", HELPER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
CHAPTERS = ["g07-shared-state-and-shutdown.md", "g07-atomics-and-publication.md"]
FILE_BLOCK = re.compile(r"\*\*[^*\n]*`([a-z][a-z0-9-]*\.(?:cpp|hpp))`[^*\n]*\*\*\n\n```cpp\n(.*?)\n```", re.S)
OUTPUTS = {
    "channel-contract.cpp": "channel contract verified\n",
    "worker-failure.cpp": "failure observed after join; delivered is not completed\n",
    "cas-counter.cpp": "cas count=2 verified\n",
    "slot-handoff.cpp": "slot generations=20000 verified\n",
    "channel-stress.cpp": "stress rounds=24 records=24000 verified\n",
}
FILES = set(OUTPUTS) | {"channel.hpp", "race-control.cpp"}
MUTATIONS = [
    ("accept-after-close", "channel-contract.cpp", "channel.hpp",
     "if (state_ != State::open) return false;", "if (state_ == State::aborted) return false;",
     3, "contract failure=3\n"),
    ("omit-discard-accounting", "channel-contract.cpp", "channel.hpp",
     "discarded_ += size_;", "// Incorrect: omit discarded work from accounting.",
     12, "contract failure=12\n"),
    ("wrong-slot-value", "slot-handoff.cpp", "slot-handoff.cpp",
     "payload = {id, id * 17U + 3U};", "payload = {id, id * 17U + 4U};",
     31, "slot value rejected\n"),
]
PROBE = """#include <thread>
int main() { int value = 0; std::jthread t([&] { value = 1; });
    t.join(); return value == 1 ? 0 : 1; }
"""
IDENTITY = """#include <version>
#include <iostream>
int main() {
    std::cout << "__cplusplus=" << __cplusplus << '\\n';
#ifdef _LIBCPP_VERSION
    std::cout << "_LIBCPP_VERSION=" << _LIBCPP_VERSION << '\\n';
#endif
#ifdef __GLIBCXX__
    std::cout << "__GLIBCXX__=" << __GLIBCXX__ << '\\n';
#endif
}
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def extract():
    sources, documents = {}, {}
    for name in CHAPTERS:
        data = (HERE / name).read_bytes()
        documents[name] = sha(data)
        text = data.decode()
        blocks = FILE_BLOCK.findall(text)
        require(text.count("```cpp\n") == len(blocks), "Unbound C++ block: " + name)
        for filename, body in blocks:
            require(filename not in sources, "Duplicate source: " + filename)
            sources[filename] = body + "\n"
    require(set(sources) == FILES, "Unexpected source set")
    return sources, documents


def protected_binding():
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT).decode().splitlines()
    selected = [p for p in paths if
        re.match(r"c\+\+/rework/g0[0-6]-", p) or
        re.fullmatch(r"c\+\+/rework/verify_g[0-6]\.py", p) or
        p == "c++/learning/verify_g.py" or
        re.match(r"c\+\+/g(?:0[0-9]|1[0-2])-.*\.md$", p) or
        re.match(r"c\+\+/failure-model/fm[0-9]-.*\.md$", p) or
        (p.startswith("publication/releases/") and p.endswith(".pdf"))]
    result = {}
    for path in selected:
        old = subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)
        require(old == (ROOT / path).read_bytes(), "Protected file changed: " + path)
        result[path] = sha(old)
    return {"base": BASE, "status": "UNCHANGED", "files_sha256": result,
            "historical_execution_rerun": "NOT RUN"}


def exact(record, stdout="", code=0):
    return helpers.clean_exit(record, code) and record["stdout"] == stdout and record["stderr"] == ""


def detected(record):
    return helpers.clean_exit(record, 66) and "ThreadSanitizer: data race" in record["stderr"]


def selftests():
    good = dict(returncode=0, timed_out=False, stdout="ok\n", stderr="")
    race = dict(returncode=66, timed_out=False, stdout="", stderr="WARNING: ThreadSanitizer: data race\n")
    tests = {
        "exact_output_accepted": exact(good, "ok\n"),
        "wrong_output_rejected": not exact(good, "wrong\n"),
        "timeout_rejected": not exact(dict(good, timed_out=True), "ok\n"),
        "stderr_rejected": not exact(dict(good, stderr="warning"), "ok\n"),
        "crash_not_logical_rejection": not exact(dict(good, returncode=-11), "ok\n", 21),
        "wrong_exit_rejected": not exact(good, "ok\n", 21),
        "target_race_accepted": detected(race),
        "missing_race_rejected": not detected(dict(race, stderr="")),
        "wrong_sanitizer_rejected": not detected(dict(race, stderr="AddressSanitizer: error")),
        "wrong_race_exit_rejected": not detected(dict(race, returncode=1)),
        "race_timeout_rejected": not detected(dict(race, timed_out=True)),
        "race_crash_rejected": not detected(dict(race, returncode=-6)),
        "clean_not_positive_control": not detected(good),
    }
    require(all(tests.values()), "Oracle selftest failed")
    return tests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Use a new output path; historical evidence is immutable")
    sources, documents = extract()
    temp = Path(tempfile.mkdtemp(prefix="kb-g7-rework-"))
    base_env = {k: v for k, v in os.environ.items()
                if k not in {"ASAN_OPTIONS", "UBSAN_OPTIONS", "TSAN_OPTIONS", "LSAN_OPTIONS"}}
    tsan_env = dict(base_env, TSAN_OPTIONS="halt_on_error=1:abort_on_error=0:exitcode=66:symbolize=0")
    report = dict(started_at_utc=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
        macOS=platform.mac_ver()[0], machine=platform.machine(), python=platform.python_version(),
        documents=documents, source_sha256={n: sha(s.encode()) for n, s in sources.items()},
        runner_sha256=sha(Path(__file__).read_bytes()), helper_sha256=sha(HELPER.read_bytes()),
        process_helper=str(HELPER.relative_to(ROOT)), protected_binding=protected_binding(),
        oracle_selftests=selftests(), temp_directory=str(temp), toolchains=[], results=[],
        fixtures={"probe.cpp": PROBE, "identity.cpp": IDENTITY},
        tsan_options=tsan_env["TSAN_OPTIONS"], status="INCOMPLETE",
        protocol_argument="MANUAL / NOT MACHINE-CHECKED", performance="NOT RUN",
        compile_negative="NOT RUN", asan_ubsan="NOT RUN", model_checker="NOT RUN",
        cross_platform="NOT ESTABLISHED", pdf="NOT BUILT / NOT VALIDATED")

    def run(args_, folder, env=base_env):
        return helpers.command(args_, folder, timeout=45, env=env)

    def build(compiler, folder, source, binary, flags):
        step = run([compiler, "-std=c++23", "-Wall", "-Wextra", "-Wpedantic", "-pthread",
                    *flags, source, "-o", binary], folder)
        if helpers.clean_exit(step) and (folder / binary).is_file():
            step["binary_sha256"] = sha((folder / binary).read_bytes())
        return step

    def record(compiler, category, name, status, **data):
        report["results"].append(dict(compiler=compiler, category=category, name=name, status=status, **data))
        print(f"{Path(compiler).name} {category} {name}: {status}", flush=True)

    try:
        for index, compiler in enumerate(args.compiler):
            folder = temp / f"toolchain-{index}"
            folder.mkdir()
            for name, body in dict(sources, **report["fixtures"]).items():
                (folder / name).write_text(body)
            version = run([compiler, "--version"], folder)
            identity_build = build(compiler, folder, "identity.cpp", "identity", ["-O0"])
            require(exact(identity_build), "Identity compile failed")
            identity_run = run([str(folder / "identity")], folder)
            require(helpers.clean_exit(version) and helpers.clean_exit(identity_run) and
                    not identity_run["stderr"] and
                    re.search(r"^__cplusplus=202302$", identity_run["stdout"], re.M),
                    "Toolchain identity failed")
            toolchain = dict(compiler=compiler, version=version, identity_build=identity_build,
                             identity_run=identity_run)
            report["toolchains"].append(toolchain)

            for source, expected in OUTPUTS.items():
                flags_list = ["-O2"] if source == "channel-stress.cpp" else ["-O0", "-O2"]
                for opt in flags_list:
                    binary = source.removesuffix(".cpp") + opt
                    compiled = build(compiler, folder, source, binary, [opt])
                    require(exact(compiled), f"Compile failed: {source} {compiled}")
                    repeats = 3 if source == "channel-stress.cpp" else 1
                    for repeat in range(repeats):
                        step = run([str(folder / binary)], folder)
                        category = "finite_stress" if repeats == 3 else "contract"
                        record(compiler, category, source, "PASS" if exact(step, expected) else "FAIL",
                               optimization=opt, process=repeat, compile=compiled, run=step)
                if source == "cas-counter.cpp":
                    step = run([str(folder / binary), "--broken"], folder)
                    record(compiler, "logical_negative", "atomic-lost-update",
                           "REJECTED_AS_EXPECTED" if exact(step, "lost update rejected\n", 21) else "FAIL",
                           compile=compiled, run=step)

            for name, main_source, changed, before, after, code, output in MUTATIONS:
                mutant = folder / name
                mutant.mkdir()
                require(sources[changed].count(before) == 1, "Mutation must have one exact target")
                mutated = dict(sources)
                mutated[changed] = sources[changed].replace(before, after)
                for filename, body in mutated.items():
                    (mutant / filename).write_text(body)
                compiled = build(compiler, mutant, main_source, "mutant", ["-O2"])
                require(exact(compiled), "Mutation did not compile")
                step = run([str(mutant / "mutant")], mutant)
                record(compiler, "mutation", name,
                       "REJECTED_AS_EXPECTED" if exact(step, output, code) else "FAIL",
                       changed_file=changed, before=before, after=after,
                       source_sha256={n: sha(s.encode()) for n, s in mutated.items()},
                       expected_exit=code, compile=compiled, run=step)

            flags = ["-O1", "-g", "-fsanitize=thread", "-fno-omit-frame-pointer"]
            probe_build = build(compiler, folder, "probe.cpp", "tsan-probe", flags)
            probe_run = run([str(folder / "tsan-probe")], folder, tsan_env) if exact(probe_build) else None
            available = exact(probe_build) and probe_run is not None and exact(probe_run)
            toolchain.update(tsan_probe_build=probe_build, tsan_probe_run=probe_run,
                             tsan_probe_available=available)
            if not available:
                for source in ["race-control.cpp", *OUTPUTS, "atomic-lost-update"]:
                    record(compiler, "tsan", source, "SKIP", reason="Safe TSan compile/run probe unavailable")
                continue
            compiled = build(compiler, folder, "race-control.cpp", "race-control-tsan", flags)
            require(exact(compiled), "Known race failed to compile")
            step = run([str(folder / "race-control-tsan")], folder, tsan_env)
            positive = detected(step)
            record(compiler, "tsan_positive_control", "race-control.cpp",
                   "DETECTED_AS_EXPECTED" if positive else "FAIL", compile=compiled, run=step)
            for source, expected in OUTPUTS.items():
                if not positive:
                    record(compiler, "tsan", source, "SKIP", reason="Known-race detection not qualified")
                    continue
                binary = source.removesuffix(".cpp") + "-tsan"
                compiled = build(compiler, folder, source, binary, flags)
                require(exact(compiled), "TSan compile failed: " + source)
                step = run([str(folder / binary)], folder, tsan_env)
                record(compiler, "tsan", source,
                       "CLEAN_OBSERVED" if exact(step, expected) else "FAIL", compile=compiled, run=step)
                if source == "cas-counter.cpp":
                    step = run([str(folder / binary), "--broken"], folder, tsan_env)
                    record(compiler, "tsan_logical_negative", "atomic-lost-update",
                           "LOGIC_REJECTED_CLEAN_OBSERVED" if exact(step, "lost update rejected\n", 21) else "FAIL",
                           compile=compiled, run=step)
            if not positive:
                record(compiler, "tsan_logical_negative", "atomic-lost-update", "SKIP",
                       reason="Known-race detection not qualified")

        require(protected_binding() == report["protected_binding"], "Protected inputs changed during run")
        current_sources, current_documents = extract()
        require(current_sources == sources and current_documents == documents, "Sources changed during run")
        report["status"] = "COMPLETED" if all(r["status"] not in {"FAIL", "SKIP"}
            for r in report["results"]) else "INCOMPLETE"
    except KeyboardInterrupt:
        report["status"] = "CANCELLED"
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = repr(exc)
    finally:
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        report["summary"] = {category: dict(Counter(r["status"] for r in report["results"]
            if r["category"] == category)) for category in sorted({r["category"] for r in report["results"]})}
        with args.output.open("x") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print(json.dumps({"status": report["status"], "summary": report["summary"],
                          "output": str(args.output)}, ensure_ascii=False), flush=True)
    return 0 if report["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
