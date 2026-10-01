#!/usr/bin/env python3
"""Extract G3's complete files; keep execution, observations and mutations distinct."""

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
BASE = "9276e3e6054366cf1dc82367d0892c588aedd579"
CHAPTERS = ["g03-value-copy-and-move.md", "g03-expressions-and-return.md"]
FILE_BLOCK = re.compile(r"\*\*文件 `([^`]+)`\*\*\n\n```cpp\n(.*?)\n```", re.S)
OUTPUTS = {
    "memberwise-value.cpp": "member copy owns independent values; shared handle does not\n",
    "copy-value.cpp": "copy preserves complete value and independent storage\n",
    "copy-failure.cpp": "failed preparation preserves target; later copy succeeds\n",
    "move-state.cpp": "move transfers storage; source resets; self move preserves value\n",
    "parameter-value.cpp": "value parameter copies or takes storage; reference alone does not\n",
    "move-selection.cpp": "cast does not transfer; named reference and const can copy\n",
    "direct-result.cpp": "same-type prvalue constructs result without copy or move\n",
    "expression-model.cpp": "expression category selects references; traits do not prove semantics\n",
}
OBSERVATION = "return-observation.cpp"
OBSERVATION_PATTERN = r"direct_moves=0; named_moves=([01]); forced_moves=1\n"
DIAGNOSTICS = {
    "deleted-move.cpp": r"call to deleted constructor of 'Copyable'",
    "named-result-invalid.cpp": r"call to deleted constructor of 'PinnedBatch'",
}
SAN_FLAGS = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             "-fno-omit-frame-pointer"]
MUTATIONS = [
    ("truncate-copy", "copy-value.cpp", 1,
     "Batch(const Batch& other) : Batch(other.sequence_, other.values()) {}",
     "Batch(const Batch& other) : Batch(other.sequence_, "
     "other.values().first(other.size_ == 0 ? 0 : 1)) {}"),
    ("no-op-copy-assignment", "copy-value.cpp", 4,
     "Batch next(other);\n            swap(next);", "(void)other;"),
    ("commit-before-preparation", "copy-failure.cpp", 4,
     "Batch next(other);", "sequence_ = other.sequence_;\n            Batch next(other);"),
    ("leave-moved-length", "move-state.cpp", 2,
     "size_(std::exchange(other.size_, 0))", "size_(other.size_)"),
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
            require(re.fullmatch(r"[a-z][a-z0-9-]*\.(?:cpp|hpp)", filename), "Unsafe filename")
            require(filename not in sources, "Duplicate filename")
            sources[filename] = body + "\n"
    require(set(sources) == set(OUTPUTS) | set(DIAGNOSTICS) | {
        OBSERVATION, "batch-storage.hpp", "value-batch.hpp", "pinned-batch.hpp"},
        "Unexpected source set")
    return sources, documents


def execution_matches(record, code, stdout):
    return helpers.clean_exit(record, code) and record["stdout"] == stdout and not record["stderr"]


def observation_matches(record, no_elision=False):
    match = re.fullmatch(OBSERVATION_PATTERN, record["stdout"])
    return (helpers.clean_exit(record) and not record["stderr"] and match is not None
            and (not no_elision or match.group(1) == "1"))


def oracle_selftests():
    clean = dict(timed_out=False, returncode=0, stdout="ok\n", stderr="")
    observed = dict(clean, stdout="direct_moves=0; named_moves=0; forced_moves=1\n")
    tests = {
        "exact_output": execution_matches(clean, 0, "ok\n"),
        "wrong_output_rejected": not execution_matches(clean, 0, "other\n"),
        "stderr_rejected": not execution_matches(dict(clean, stderr="bad"), 0, "ok\n"),
        "timeout_rejected": not execution_matches(dict(clean, timed_out=True), 0, "ok\n"),
        "crash_not_mutation_rejection": not execution_matches(dict(clean, returncode=-11), 4, "ok\n"),
        "wrong_exit_rejected": not execution_matches(clean, 4, "ok\n"),
        "wrong_diagnostic_rejected": not helpers.diagnosed(
            dict(clean, returncode=1, stderr="missing header"), DIAGNOSTICS["deleted-move.cpp"]),
        "right_diagnostic": helpers.diagnosed(
            dict(clean, returncode=1, stderr="call to deleted constructor of 'Copyable'"),
            DIAGNOSTICS["deleted-move.cpp"]),
        "normal_nrvo_observation": observation_matches(observed),
        "disabled_nrvo_requires_move": not observation_matches(observed, True),
        "disabled_nrvo_observation": observation_matches(
            dict(observed, stdout="direct_moves=0; named_moves=1; forced_moves=1\n"), True),
        "extra_output_rejected": not observation_matches(dict(observed, stdout=observed["stdout"] + "noise")),
        "invalid_count_rejected": not observation_matches(
            dict(observed, stdout="direct_moves=0; named_moves=2; forced_moves=1\n")),
    }
    require(all(tests.values()), "Oracle selftest failed")
    return tests


def protected_binding():
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT).decode().splitlines()
    selected = [p for p in paths if
                re.match(r"c\+\+/rework/g0[012]-", p) or
                re.fullmatch(r"c\+\+/rework/verify_g[012]\.py", p) or
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
    temp = Path(tempfile.mkdtemp(prefix="kb-g3-rework-"))
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "macOS": platform.mac_ver()[0],
              "machine": platform.machine(), "python": platform.python_version(),
              "documents": documents, "source_sha256": {n: sha(s.encode()) for n, s in sources.items()},
              "runner_sha256": sha(Path(__file__).read_bytes()),
              "process_helper": str(HELPER.relative_to(ROOT)), "helper_sha256": sha(HELPER.read_bytes()),
              "protected_binding": protected_binding(), "oracle_selftests": oracle_selftests(),
              "temp_directory": str(temp), "toolchains": [], "results": [], "mutations": [],
              "performance": "NOT RUN", "concurrency": "NOT RUN", "pdf": "NOT BUILT / NOT VALIDATED",
              "allocation_failure": "DETERMINISTIC PRE-ALLOCATION INJECTION, NOT OS EXHAUSTION",
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
                result["expected_diagnostic"] = DIAGNOSTICS[name]
                if helpers.diagnosed(compilation, DIAGNOSTICS[name]):
                    result["status"] = "PASS"
            elif helpers.clean_exit(compilation):
                execution = helpers.command([str(target)], cwd, env=env)
                result["steps"].append(execution)
                if name == OBSERVATION:
                    result["expected_output_pattern"] = OBSERVATION_PATTERN
                    result["requires_named_move"] = mode == "no_elision"
                    accepted = observation_matches(execution, mode == "no_elision")
                    if accepted:
                        result["observed_named_moves"] = int(re.fullmatch(OBSERVATION_PATTERN, execution["stdout"])[1])
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
        for name in (OBSERVATION, "direct-result.cpp"):
            report["results"].append(run_case(name, "no_elision",
                ["-O0", "-g", "-fno-elide-constructors", "-DEXPECT_NO_ELISION"],
                expected_stdout=OUTPUTS.get(name)))
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
        for label, name, code, before, after in MUTATIONS:
            require(sources["value-batch.hpp"].count(before) == 1, "Mutation target drifted: " + label)
            variant = folder / label
            variant.mkdir()
            modified = dict(sources, **{"value-batch.hpp": sources["value-batch.hpp"].replace(before, after)})
            for filename, body in modified.items():
                (variant / filename).write_text(body)
            result = run_case(name, "mutation", ["-O0", "-g"], cwd=variant,
                              expected_exit=code, expected_stdout="")
            result.update(name=label, replacement={"path": "value-batch.hpp", "before": before, "after": after},
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
