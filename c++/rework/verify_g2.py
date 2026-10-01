#!/usr/bin/env python3
"""Extract the two G2 units and record local execution evidence, never old results."""

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


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HELPER = HERE.parent / "learning/verify_g.py"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("g_verification_helpers", HELPER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
BASE = "d071bf44fe2713034741197fb3ed7e89d4385cab"
CHAPTERS = ["g02-resource-lifecycle.md", "g02-ownership-and-handoff.md"]
FILE_BLOCK = re.compile(r"\*\*文件 `([^`]+)`\*\*\n\n```cpp\n(.*?)\n```", re.S)
OUTPUTS = {
    "cleanup-paths.cpp": "normal/return/throw closed; failed acquire owns nothing\n",
    "member-failure.cpp": "members cleaned; completed Session destructors=1\n",
    "owner-transfer.cpp": "move transfers; assignment closes old; source becomes empty\n",
    "close-failure.cpp": "explicit close reports failure; fallback does not retry\n",
    "unique-handoff.cpp": "borrow does not own; transfer consumes even on failure\n",
    "shared-lifetime.cpp": "shared object; weak lock retains; member alias retains owner\n",
    "deferred-work.cpp": "owned task retains; discarded task releases; weak task may skip\n",
    "ownership-cycle.cpp": "strong callback cycle observed and broken; weak edge releases\n",
}
COPY_DIAGNOSTIC = r"call to deleted constructor of 'TempFile'"
SAN_FLAGS = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             "-fno-omit-frame-pointer"]


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
        blocks = FILE_BLOCK.findall(data.decode())
        require(data.decode().count("```cpp\n") == len(blocks), "Unbound C++ block: " + name)
        for filename, body in blocks:
            require(re.fullmatch(r"[a-z][a-z0-9-]*\.(?:cpp|hpp)", filename), "Unsafe filename")
            require(filename not in sources, "Duplicate filename")
            sources[filename] = body + "\n"
    require(set(sources) == set(OUTPUTS) | {
        "file-api.hpp", "temp-file.hpp", "batch.hpp", "owner-copy.cpp"}, "Unexpected source set")
    return sources, documents


def execution_matches(record, code, stdout):
    return helpers.clean_exit(record, code) and record["stdout"] == stdout and not record["stderr"]


def oracle_selftests():
    clean = dict(timed_out=False, returncode=0, stdout="ok\n", stderr="")
    tests = {
        "expected_output_accepted": execution_matches(clean, 0, "ok\n"),
        "wrong_output_rejected": not execution_matches(clean, 0, "other\n"),
        "stderr_rejected": not execution_matches(dict(clean, stderr="error"), 0, "ok\n"),
        "timeout_rejected": not execution_matches(dict(clean, timed_out=True), 0, "ok\n"),
        "crash_not_mutation_rejection": not execution_matches(dict(clean, returncode=-11), 2, "ok\n"),
        "wrong_exit_not_mutation_rejection": not execution_matches(clean, 2, "ok\n"),
        "wrong_compile_diagnostic_rejected": not helpers.diagnosed(
            dict(clean, returncode=1, stderr="missing header"), COPY_DIAGNOSTIC),
        "expected_compile_diagnostic_accepted": helpers.diagnosed(
            dict(clean, returncode=1, stderr="call to deleted constructor of 'TempFile'"),
            COPY_DIAGNOSTIC),
    }
    require(all(tests.values()), "Oracle selftest failed")
    return tests


def protected_binding():
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT).decode().splitlines()
    selected = [p for p in paths if
                p.startswith("c++/rework/g00-") or p.startswith("c++/rework/g01-") or
                p in {"c++/rework/verify_g1.py", "c++/learning/verify_g.py"} or
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Choose a new output path; historical results are immutable")
    sources, documents = extract()
    temp = Path(tempfile.mkdtemp(prefix="kb-g2-rework-"))
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "macOS": platform.mac_ver()[0],
              "machine": platform.machine(), "python": platform.python_version(),
              "documents": documents, "source_sha256": {n: sha(s.encode()) for n, s in sources.items()},
              "runner_sha256": sha(Path(__file__).read_bytes()),
              "process_helper": str(HELPER.relative_to(ROOT)), "helper_sha256": sha(HELPER.read_bytes()),
              "protected_binding": protected_binding(), "oracle_selftests": oracle_selftests(),
              "temp_directory": str(temp), "toolchains": [], "results": [], "mutations": [],
              "performance": "NOT RUN", "concurrency": "NOT RUN",
              "pdf": "NOT BUILT / NOT VALIDATED", "physical_io_faults": "NOT INJECTED",
              "asan_positive_control": "NOT RUN", "leak_sanitizer": "DISABLED"}
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=0")
    report["sanitizer_environment"] = {k: env[k] for k in ("ASAN_OPTIONS", "UBSAN_OPTIONS")}
    for index, compiler in enumerate(args.compiler):
        folder = temp / str(index)
        folder.mkdir()
        for name, body in sources.items():
            (folder / name).write_text(body)
        (folder / "identity.cpp").write_text("#include <version>\n")
        (folder / "probe.cpp").write_text("int main() { volatile int n = 7; return n == 7 ? 0 : 1; }\n")
        version = helpers.command([compiler, "--version"], folder)
        macros = helpers.command([compiler, "-std=c++23", "-dM", "-E", "identity.cpp"], folder)
        require(helpers.clean_exit(version) and helpers.clean_exit(macros), "Toolchain identity failed")
        report["toolchains"].append({"compiler": compiler, "version": version,
            "identity_command": macros["command"], "library_macros": [line for line in macros["stdout"].splitlines()
                if re.match(r"#define (?:_LIBCPP_VERSION|__GLIBCXX__|__cplusplus) ", line)]})
        common = [compiler, "-std=c++23", "-Wall", "-Wextra", "-Wpedantic"]

        def run_case(name, mode, flags, cwd=folder, expected_exit=0, expected_stdout=None):
            result = {"source": name, "mode": mode, "compiler": compiler, "status": "FAIL", "steps": []}
            target = cwd / (name.removesuffix(".cpp") + "-" + mode)
            command = common + flags + (["-c"] if mode == "compile_fail" else []) + [name, "-o", str(target)]
            compilation = helpers.command(command, cwd)
            result["steps"].append(compilation)
            if mode == "compile_fail":
                result["expected_diagnostic"] = COPY_DIAGNOSTIC
                if helpers.diagnosed(compilation, COPY_DIAGNOSTIC):
                    result["status"] = "PASS"
            elif helpers.clean_exit(compilation):
                execution = helpers.command([str(target)], cwd, env=env)
                result["steps"].append(execution)
                result.update(expected_exit=expected_exit, expected_stdout=expected_stdout)
                if execution_matches(execution, expected_exit, expected_stdout):
                    result["status"] = {"sanitized": "CLEAN_OBSERVED", "mutation": "REJECTED_AS_EXPECTED"}.get(mode, "PASS")
            print(Path(compiler).parent, name, mode, result["status"], flush=True)
            return result

        for mode, flags in (("O0", ["-O0", "-g"]), ("O2", ["-O2"])):
            for name, output in OUTPUTS.items():
                report["results"].append(run_case(name, mode, flags, expected_stdout=output))
        report["results"].append(run_case("owner-copy.cpp", "compile_fail", ["-O0"]))
        probe_build = helpers.command(common + SAN_FLAGS + ["probe.cpp", "-o", "probe"], folder)
        probe_run = helpers.command([str(folder / "probe")], folder, env=env) if helpers.clean_exit(probe_build) else None
        ready = probe_run is not None and execution_matches(probe_run, 0, "")
        report.setdefault("sanitizer_probes", []).append({"compiler": compiler,
            "status": "AVAILABLE" if ready else "UNAVAILABLE", "compile": probe_build, "run": probe_run})
        for name, output in OUTPUTS.items():
            if ready:
                report["results"].append(run_case(name, "sanitized", SAN_FLAGS, expected_stdout=output))
            else:
                report["results"].append({"source": name, "mode": "sanitized", "compiler": compiler,
                    "status": "SKIP", "reason": "Sanitizer probe unavailable"})

        variants = [
            ("omit-destructor-close", "cleanup-paths.cpp", 2,
             "~TempFile() noexcept { (void)close(); }", "~TempFile() noexcept {}"),
            ("swallow-close-error", "close-failure.cpp", 1,
             "return FileApi::close(file);", "(void)FileApi::close(file); return 0;"),
        ]
        for label, name, code, before, after in variants:
            require(sources["temp-file.hpp"].count(before) == 1, "Mutation target drifted: " + label)
            variant = folder / label
            variant.mkdir()
            modified = dict(sources, **{"temp-file.hpp": sources["temp-file.hpp"].replace(before, after)})
            for filename, body in modified.items():
                (variant / filename).write_text(body)
            result = run_case(name, "mutation", ["-O0", "-g"], cwd=variant,
                              expected_exit=code, expected_stdout="")
            result.update(name=label, replacement={"path": "temp-file.hpp", "before": before, "after": after},
                          source_sha256={n: sha(s.encode()) for n, s in modified.items()})
            report["mutations"].append(result)

    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["result_counts"] = dict(Counter(r["mode"] + ":" + r["status"] for r in report["results"]))
    report["mutation_counts"] = dict(Counter(r["status"] for r in report["mutations"]))
    report["status"] = "COMPLETE" if (all(r["status"] in {"PASS", "CLEAN_OBSERVED"} for r in report["results"])
        and all(r["status"] == "REJECTED_AS_EXPECTED" for r in report["mutations"])) else "INCOMPLETE"
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(report["status"], "Evidence:", args.output, "Temporary sources:", temp)
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
