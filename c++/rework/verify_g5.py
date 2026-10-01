#!/usr/bin/env python3
"""Extract G5 experiments and distinguish diagnostics, execution and artifact observations."""

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
BASE = "c4c74736de7dcfa6cc286f32866aa593384f3744"
HELPER = HERE.parent / "learning/verify_g.py"
spec = importlib.util.spec_from_file_location("g_process_helpers", HELPER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
CHAPTERS = ["g05-call-and-deduction.md", "g05-constraints-and-instantiation.md",
            "g05-constant-evaluation-and-codegen.md"]
FILE_BLOCK = re.compile(r"\*\*[^*\n]*`([a-z][a-z0-9-]*\.(?:cpp|hpp))`[^*\n]*\*\*\n\n```cpp\n(.*?)\n```", re.S)
OUTPUTS = {
    "sort-capabilities.cpp": "sort requires traversal and writable ordering capabilities\n",
    "deduction.cpp": "deduction preserves information according to the parameter pattern\n",
    "forwarding.cpp": "forwarding preserves the caller binding choice\n",
    "return-types.cpp": "return deduction chooses a value or a borrowed element\n",
    "snapshot.cpp": "one input pass produces an independent sorted snapshot\n",
    "requirement-kinds.cpp": "expression validity and required truth are different checks\n",
    "overload-selection.cpp": "shared named constraints order the eligible overloads\n",
    "member-instantiation.cpp": "using one member does not validate every dependent body\n",
    "constant-evaluation.cpp": "constant configuration and runtime readings share one rule\n",
    "count-elements.cpp": "each specialization instantiates its applicable counting branch\n",
}
DIAGNOSTICS = {
    "deduction-conflict.cpp": [r"error:.*choose_value", r"deduced conflicting types"],
    "fixed-rvalue.cpp": [r"error:.*(?:rvalue reference|expects an rvalue|cannot bind)", r"set"],
    "constraint-failure.cpp": [r"error:.*sorted_snapshot", r"constraints not satisfied", r"ReadingInput"],
    "body-failure.cpp": [r"error:.*no member named 'missing_value'", r"unchecked_first"],
    "ambiguous-constraints.cpp": [r"error:.*select_integer.*ambiguous"],
    "invalid-limits.cpp": [r"not a constant expression", r"checked_limits", r"throw"],
    "runtime-immediate.cpp": [r"not a constant expression", r"checked_limits", r"argc"],
    "ordinary-if.cpp": [r"error:.*(?:no matching|constraints)", r"(?:__size|ranges::size)", r"bad_count"],
}
HEADERS = {"reading.hpp", "reading-snapshot.hpp", "reading-limits.hpp", "positive-count.hpp"}
MULTI = {"positive-count.cpp", "count-client.cpp", "count-missing.cpp"}
LINK_DIAGNOSTICS = [r"(?:Undefined|undefined)", r"count_positive<float>"]
CLIENT_OUTPUT = "the provider supplies the requested int specialization\n"
SAN_FLAGS = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             "-fno-omit-frame-pointer"]
MUTATIONS = [
    ("move-left-input", "forwarding.cpp", "forwarding.cpp", 1,
     "return accept(std::forward<T>(value));", "return accept(std::move(value));"),
    ("omit-snapshot-sort", "snapshot.cpp", "reading-snapshot.hpp", 1,
     "std::ranges::sort(result, {}, &Reading::id);", "// Incorrect: return insertion order."),
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
        text = data.decode()
        blocks = FILE_BLOCK.findall(text)
        require(text.count("```cpp\n") == len(blocks), "Unbound C++ block: " + name)
        for filename, body in blocks:
            require(filename not in sources, "Duplicate filename: " + filename)
            sources[filename] = body + "\n"
    require(set(sources) == set(OUTPUTS) | set(DIAGNOSTICS) | HEADERS | MULTI,
            "Unexpected source set")
    return sources, documents


def execution_matches(record, code, output):
    return helpers.clean_exit(record, code) and record["stdout"] == output and not record["stderr"]


def diagnosed(record, patterns):
    return (not record["timed_out"] and record["returncode"] > 0 and
            all(re.search(p, record["stdout"] + record["stderr"]) for p in patterns))


def oracle_selftests():
    clean = dict(timed_out=False, returncode=0, stdout="ok\n", stderr="")
    bad = dict(clean, returncode=1, stdout="",
               stderr="error: call to select_integer is ambiguous")
    link = dict(bad, stderr="Undefined symbols: count_positive<float>")
    tests = {
        "exact_output": execution_matches(clean, 0, "ok\n"),
        "wrong_output_rejected": not execution_matches(clean, 0, "different\n"),
        "stderr_rejected": not execution_matches(dict(clean, stderr="error"), 0, "ok\n"),
        "timeout_rejected": not execution_matches(dict(clean, timed_out=True), 0, "ok\n"),
        "mutation_exit_required": not execution_matches(clean, 1, "ok\n"),
        "crash_not_rejection": not execution_matches(dict(clean, returncode=-11), 1, "ok\n"),
        "target_diagnostic": diagnosed(bad, DIAGNOSTICS["ambiguous-constraints.cpp"]),
        "wrong_diagnostic_rejected": not diagnosed(dict(bad, stderr="fatal error: header missing"),
                                                    DIAGNOSTICS["ambiguous-constraints.cpp"]),
        "successful_compile_rejected": not diagnosed(dict(bad, returncode=0),
                                                       DIAGNOSTICS["ambiguous-constraints.cpp"]),
        "negative_timeout_rejected": not diagnosed(dict(bad, timed_out=True),
                                                     DIAGNOSTICS["ambiguous-constraints.cpp"]),
        "negative_signal_rejected": not diagnosed(dict(bad, returncode=-6),
                                                    DIAGNOSTICS["ambiguous-constraints.cpp"]),
        "target_link_diagnostic": diagnosed(link, LINK_DIAGNOSTICS),
        "wrong_specialization_rejected": not diagnosed(dict(link,
            stderr="Undefined symbols: count_positive<int>"), LINK_DIAGNOSTICS),
        "link_timeout_rejected": not diagnosed(dict(link, timed_out=True), LINK_DIAGNOSTICS),
    }
    require(all(tests.values()), "Oracle selftest failed")
    return tests


def protected_binding():
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT).decode().splitlines()
    selected = [p for p in paths if
        re.match(r"c\+\+/rework/g0[0-4]-", p) or
        re.fullmatch(r"c\+\+/rework/verify_g[0-4]\.py", p) or
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
    parser.add_argument("--nm", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Choose a new path; do not overwrite historical evidence")
    sources, documents = extract()
    temp = Path(tempfile.mkdtemp(prefix="kb-g5-rework-"))
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "macOS": platform.mac_ver()[0],
        "machine": platform.machine(), "python": platform.python_version(),
        "documents": documents, "source_sha256": {n: sha(s.encode()) for n, s in sources.items()},
        "runner_sha256": sha(Path(__file__).read_bytes()), "process_helper": str(HELPER.relative_to(ROOT)),
        "helper_sha256": sha(HELPER.read_bytes()), "protected_binding": protected_binding(),
        "oracle_selftests": oracle_selftests(), "temp_directory": str(temp),
        "toolchains": [], "results": [], "artifact_observations": [], "mutations": [],
        "performance": "NOT RUN", "concurrency": "NOT RUN", "pdf": "NOT BUILT / NOT VALIDATED",
        "allocation_failure_injection": "NOT RUN", "asan_positive_control": "NOT RUN",
        "leak_sanitizer": "DISABLED", "cross_platform": "NOT ESTABLISHED"}
    nm_version = helpers.command([args.nm, "--version"], temp)
    require(helpers.clean_exit(nm_version), "nm identity unavailable")
    report["nm_identity"] = nm_version
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

        def run_case(name, mode, flags, cwd=folder, code=0, output=None):
            target = cwd / (name.removesuffix(".cpp") + "-" + mode)
            result = dict(source=name, mode=mode, compiler=compiler, status="FAIL", steps=[])
            command = common + flags + (["-c"] if mode == "compile_fail" else []) + [name, "-o", str(target)]
            build = helpers.command(command, cwd)
            result["steps"].append(build)
            if mode == "compile_fail":
                result["expected_diagnostic_patterns"] = DIAGNOSTICS[name]
                if diagnosed(build, DIAGNOSTICS[name]): result["status"] = "PASS"
            elif helpers.clean_exit(build):
                execution = helpers.command([str(target)], cwd, env=env)
                result["steps"].append(execution)
                result.update(expected_exit=code, expected_stdout=output)
                if execution_matches(execution, code, output):
                    result["status"] = ("CLEAN_OBSERVED" if mode == "sanitized" else
                        "REJECTED_AS_EXPECTED" if mode == "mutation" else "PASS")
            print(Path(compiler).parent, name, mode, result["status"], flush=True)
            return result

        for mode, flags in (("O0", ["-O0", "-g"]), ("O2", ["-O2"])):
            for name, output in OUTPUTS.items():
                report["results"].append(run_case(name, mode, flags, output=output))
            objects, steps = {}, []
            for name in sorted(MULTI):
                obj = folder / (name.removesuffix(".cpp") + "-" + mode + ".o")
                step = helpers.command(common + flags + ["-c", name, "-o", str(obj)], folder)
                steps.append(step)
                if helpers.clean_exit(step): objects[name] = obj
            multi_ok = len(objects) == len(MULTI)
            positive = dict(source="count-client.cpp", mode="multifile_" + mode, compiler=compiler,
                            status="FAIL", steps=list(steps), expected_stdout=CLIENT_OUTPUT, expected_exit=0)
            negative = dict(source="count-missing.cpp", mode="link_fail_" + mode, compiler=compiler,
                            status="FAIL", steps=list(steps), expected_diagnostic_patterns=LINK_DIAGNOSTICS)
            observation = dict(compiler=compiler, mode=mode, status="SKIP", objects={}, steps=[],
                               reason="Object compilation did not complete")
            if multi_ok:
                exe = folder / ("count-client-" + mode)
                link = helpers.command([compiler, str(objects["count-client.cpp"]),
                    str(objects["positive-count.cpp"]), "-o", str(exe)], folder)
                positive["steps"].append(link)
                if helpers.clean_exit(link):
                    run = helpers.command([str(exe)], folder)
                    positive["steps"].append(run)
                    if execution_matches(run, 0, CLIENT_OUTPUT): positive["status"] = "PASS"
                missing = helpers.command([compiler, str(objects["count-missing.cpp"]),
                    str(objects["positive-count.cpp"]), "-o", str(folder / ("missing-" + mode))], folder)
                negative["steps"].append(missing)
                if diagnosed(missing, LINK_DIAGNOSTICS): negative["status"] = "PASS"
                observation.update(status="OBSERVED", reason="No fixed size, spelling or symbol-count oracle")
                for name, obj in objects.items():
                    nm = helpers.command([args.nm, "--demangle", str(obj)], folder)
                    observation["steps"].append(nm)
                    if not helpers.clean_exit(nm): observation["status"] = "FAIL"
                    observation["objects"][name] = {"path": str(obj), "bytes": obj.stat().st_size,
                                                   "sha256": sha(obj.read_bytes())}
            report["results"].extend([positive, negative])
            report["artifact_observations"].append(observation)
            print(Path(compiler).parent, "multifile", mode, positive["status"],
                  negative["status"], observation["status"], flush=True)
        for name in DIAGNOSTICS:
            report["results"].append(run_case(name, "compile_fail", ["-O0"]))
        build = helpers.command(common + SAN_FLAGS + ["probe.cpp", "-o", "probe"], folder)
        probe = helpers.command([str(folder / "probe")], folder, env=env) if helpers.clean_exit(build) else None
        ready = probe is not None and execution_matches(probe, 0, "")
        report.setdefault("sanitizer_probes", []).append({"compiler": compiler, "compile": build,
            "run": probe, "status": "AVAILABLE" if ready else "UNAVAILABLE"})
        for name, output in OUTPUTS.items():
            report["results"].append(run_case(name, "sanitized", SAN_FLAGS, output=output) if ready else
                dict(source=name, mode="sanitized", compiler=compiler, status="SKIP", reason="Probe unavailable"))
        for label, name, changed, code, before, after in MUTATIONS:
            require(sources[changed].count(before) == 1, "Mutation target drifted: " + label)
            variant = folder / label
            variant.mkdir()
            modified = dict(sources)
            modified[changed] = modified[changed].replace(before, after)
            for filename, body in modified.items(): (variant / filename).write_text(body)
            result = run_case(name, "mutation", ["-O0", "-g"], cwd=variant, code=code, output="")
            result.update(name=label, replacement={"path": changed, "before": before, "after": after},
                          source_sha256={n: sha(s.encode()) for n, s in modified.items()})
            report["mutations"].append(result)
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["result_counts"] = dict(Counter(r["mode"] + ":" + r["status"] for r in report["results"]))
    report["mutation_counts"] = dict(Counter(r["status"] for r in report["mutations"]))
    report["artifact_counts"] = dict(Counter(r["status"] for r in report["artifact_observations"]))
    report["status"] = "COMPLETE" if (all(r["status"] in {"PASS", "CLEAN_OBSERVED"} for r in report["results"])
        and all(r["status"] == "REJECTED_AS_EXPECTED" for r in report["mutations"])
        and all(r["status"] == "OBSERVED" for r in report["artifact_observations"])) else "INCOMPLETE"
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(report["status"], "Evidence:", args.output, "Temporary sources:", temp)
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
