#!/usr/bin/env python3
"""G4 document experiments: semantic oracles, implementation observations and mutations."""

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
spec = importlib.util.spec_from_file_location("g_process_helpers", HELPER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
BASE = "c5d3b17cf66fd4bb6f6cfef705d0c7cf95e16af7"
CHAPTERS = ["g04-sequences-and-identity.md", "g04-algorithms-and-views.md",
            "g04-lookup-and-indexes.md"]
FILE_BLOCK = re.compile(r"\*\*[^*\n]*`([a-z][a-z0-9-]*\.(?:cpp|hpp))`[^*\n]*\*\*\n\n```cpp\n(.*?)\n```", re.S)
OUTPUTS = {
    "sequence-edit.cpp": "sequence edits preserve values and renew positions\n",
    "stable-storage.cpp": "target identity follows the chosen storage contract\n",
    "single-pass.cpp": "input is consumed once; stored values support repeated passes\n",
    "sort-identity.cpp": "stable ordering preserves ties, not selected positions\n",
    "compact-records.cpp": "compaction selects the prefix; erase changes container size\n",
    "lazy-and-owned.cpp": "view observes source; materialized values form a snapshot\n",
    "range-lifetime.cpp": "borrowed range concerns the wrapper, not immortal elements\n",
    "ordered-lookup.cpp": "ordered lookup checks both boundary and key equality\n",
    "map-operations.cpp": "lookup, conditional insertion and replacement are distinct\n",
    "hash-references.cpp": "rehash renews iterators but preserves element references\n",
    "indexed-replacement.cpp": "rows and index commit together; rejected input preserves old state\n",
}
OBSERVATION = "relocation-observation.cpp"
OBSERVATION_PATTERN = (r"nothrow copies=([0-9]+) moves=([0-9]+)\n"
                       r"potentially-throwing copies=([0-9]+) moves=([0-9]+)\n")
DIAGNOSTICS = {
    "dangling-result.cpp": [r"error:.*(?:indirection|invalid argument type).*dangling"],
    "sort-filter.cpp": [r"error:.*(?:no matching function|constraints not satisfied)",
                        r"random_access_(?:range|iterator)", r"sort"],
}
SAN_FLAGS = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             "-fno-omit-frame-pointer"]
MUTATIONS = [
    ("omit-tail-erasure", "compact-records.cpp", "compact-records.cpp", 3,
     "rows.erase(tail.begin(), tail.end());", "// Incorrect: leave the compacted tail in the container."),
    ("accept-next-key", "ordered-lookup.cpp", "ordered-lookup.cpp", 3,
     "it == rows.end() || it->id != id", "it == rows.end()"),
    ("omit-last-index-entry", "indexed-replacement.cpp", "indexed-batch.hpp", 2,
     "i < rows.size()", "i + 1 < rows.size()"),
    ("accept-duplicate-key", "indexed-replacement.cpp", "indexed-batch.hpp", 3,
     'if (!index.emplace(rows[i].id, i).second)\n                    throw std::invalid_argument("duplicate reading id");',
     "index.emplace(rows[i].id, i); // Incorrect: silently accept a duplicate."),
]


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
            require(filename not in sources, "Duplicate filename: " + filename)
            sources[filename] = body + "\n"
    require(set(sources) == set(OUTPUTS) | set(DIAGNOSTICS) | {
        OBSERVATION, "reading.hpp", "indexed-batch.hpp"}, "Unexpected source set")
    return sources, documents


def execution_matches(record, code, stdout):
    return helpers.clean_exit(record, code) and record["stdout"] == stdout and not record["stderr"]


def observation_matches(record):
    return (helpers.clean_exit(record) and not record["stderr"] and
            re.fullmatch(OBSERVATION_PATTERN, record["stdout"]) is not None)


def diagnostic_matches(record, patterns):
    return (not record["timed_out"] and record["returncode"] > 0 and
            all(re.search(p, record["stdout"] + record["stderr"]) for p in patterns))


def oracle_selftests():
    clean = dict(timed_out=False, returncode=0, stdout="ok\n", stderr="")
    observed = dict(clean, stdout="nothrow copies=0 moves=3\npotentially-throwing copies=3 moves=0\n")
    diagnostic = dict(clean, returncode=1, stdout="",
                      stderr="error: indirection requires pointer operand ('ranges::dangling' invalid)")
    tests = {
        "exact_output": execution_matches(clean, 0, "ok\n"),
        "wrong_output_rejected": not execution_matches(clean, 0, "other\n"),
        "stderr_rejected": not execution_matches(dict(clean, stderr="problem"), 0, "ok\n"),
        "timeout_rejected": not execution_matches(dict(clean, timed_out=True), 0, "ok\n"),
        "crash_not_mutation_rejection": not execution_matches(dict(clean, returncode=-11), 3, "ok\n"),
        "wrong_mutation_exit_rejected": not execution_matches(clean, 3, "ok\n"),
        "observation_format": observation_matches(observed),
        "different_counts_allowed": observation_matches(dict(observed,
            stdout="nothrow copies=3 moves=0\npotentially-throwing copies=0 moves=3\n")),
        "extra_observation_output_rejected": not observation_matches(dict(observed,
            stdout=observed["stdout"] + "noise")),
        "negative_count_rejected": not observation_matches(dict(observed,
            stdout=observed["stdout"].replace("copies=0", "copies=-1"))),
        "target_diagnostic": diagnostic_matches(diagnostic, DIAGNOSTICS["dangling-result.cpp"]),
        "missing_header_not_diagnostic": not diagnostic_matches(dict(diagnostic,
            stderr="fatal error: vector not found"), DIAGNOSTICS["dangling-result.cpp"]),
        "diagnostic_timeout_rejected": not diagnostic_matches(dict(diagnostic, timed_out=True),
            DIAGNOSTICS["dangling-result.cpp"]),
        "diagnostic_signal_rejected": not diagnostic_matches(dict(diagnostic, returncode=-6),
            DIAGNOSTICS["dangling-result.cpp"]),
    }
    require(all(tests.values()), "Oracle selftest failed")
    return tests


def protected_binding():
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT).decode().splitlines()
    selected = [p for p in paths if
                re.match(r"c\+\+/rework/g0[0-3]-", p) or
                re.fullmatch(r"c\+\+/rework/verify_g[0-3]\.py", p) or
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Choose a new output path; historical results are immutable")
    sources, documents = extract()
    temp = Path(tempfile.mkdtemp(prefix="kb-g4-rework-"))
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "macOS": platform.mac_ver()[0],
        "machine": platform.machine(), "python": platform.python_version(),
        "documents": documents, "source_sha256": {n: sha(s.encode()) for n, s in sources.items()},
        "runner_sha256": sha(Path(__file__).read_bytes()),
        "process_helper": str(HELPER.relative_to(ROOT)), "helper_sha256": sha(HELPER.read_bytes()),
        "protected_binding": protected_binding(), "oracle_selftests": oracle_selftests(),
        "temp_directory": str(temp), "toolchains": [], "results": [], "mutations": [],
        "performance": "NOT RUN", "concurrency": "NOT RUN", "pdf": "NOT BUILT / NOT VALIDATED",
        "allocation_failure_injection": "NOT RUN", "asan_positive_control": "NOT RUN",
        "leak_sanitizer": "DISABLED"}
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
                result["expected_diagnostic_patterns"] = DIAGNOSTICS[name]
                if diagnostic_matches(compilation, DIAGNOSTICS[name]):
                    result["status"] = "PASS"
            elif helpers.clean_exit(compilation):
                execution = helpers.command([str(target)], cwd, env=env)
                result["steps"].append(execution)
                if name == OBSERVATION:
                    result["expected_output_pattern"] = OBSERVATION_PATTERN
                    accepted = observation_matches(execution)
                    if accepted:
                        result["observed_counts"] = dict(zip(
                            ("nothrow_copies", "nothrow_moves", "potentially_throwing_copies", "potentially_throwing_moves"),
                            map(int, re.fullmatch(OBSERVATION_PATTERN, execution["stdout"]).groups())))
                else:
                    result.update(expected_exit=expected_exit, expected_stdout=expected_stdout)
                    accepted = execution_matches(execution, expected_exit, expected_stdout)
                if accepted:
                    result["status"] = ("CLEAN_OBSERVED" if mode == "sanitized" else
                        "REJECTED_AS_EXPECTED" if mode == "mutation" else
                        "OBSERVED" if name == OBSERVATION else "PASS")
            print(Path(compiler).parent, name, mode, result["status"], flush=True)
            return result

        for mode, flags in (("O0", ["-O0", "-g"]), ("O2", ["-O2"])):
            for name, output in OUTPUTS.items():
                report["results"].append(run_case(name, mode, flags, expected_stdout=output))
            report["results"].append(run_case(OBSERVATION, mode, flags))
        for name in DIAGNOSTICS:
            report["results"].append(run_case(name, "compile_fail", ["-O0"]))
        probe_build = helpers.command(common + SAN_FLAGS + ["probe.cpp", "-o", "probe"], folder)
        probe_run = helpers.command([str(folder / "probe")], folder, env=env) if helpers.clean_exit(probe_build) else None
        ready = probe_run is not None and execution_matches(probe_run, 0, "")
        report.setdefault("sanitizer_probes", []).append({"compiler": compiler,
            "status": "AVAILABLE" if ready else "UNAVAILABLE", "compile": probe_build, "run": probe_run})
        for name in [*OUTPUTS, OBSERVATION]:
            if ready:
                report["results"].append(run_case(name, "sanitized", SAN_FLAGS, expected_stdout=OUTPUTS.get(name)))
            else:
                report["results"].append({"source": name, "mode": "sanitized", "compiler": compiler,
                    "status": "SKIP", "reason": "Sanitizer probe unavailable"})
        for label, name, modified_file, code, before, after in MUTATIONS:
            require(sources[modified_file].count(before) == 1, "Mutation target drifted: " + label)
            variant = folder / label
            variant.mkdir()
            modified = dict(sources)
            modified[modified_file] = modified[modified_file].replace(before, after)
            for filename, body in modified.items():
                (variant / filename).write_text(body)
            result = run_case(name, "mutation", ["-O0", "-g"], cwd=variant,
                              expected_exit=code, expected_stdout="")
            result.update(name=label, replacement={"path": modified_file, "before": before, "after": after},
                          source_sha256={n: sha(s.encode()) for n, s in modified.items()})
            report["mutations"].append(result)
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["result_counts"] = dict(Counter(r["mode"] + ":" + r["status"] for r in report["results"]))
    report["mutation_counts"] = dict(Counter(r["status"] for r in report["mutations"]))
    report["status"] = "COMPLETE" if (all(r["status"] in {"PASS", "OBSERVED", "CLEAN_OBSERVED"} for r in report["results"])
        and all(r["status"] == "REJECTED_AS_EXPECTED" for r in report["mutations"])) else "INCOMPLETE"
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(report["status"], "Evidence:", args.output, "Temporary sources:", temp)
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
