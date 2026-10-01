#!/usr/bin/env python3
"""G6: separate semantic checks, resource observations and paired timing data."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = "baeeadf58a75f68555c587f317f382f49b0ba2fc"
HELPER = HERE.parent / "learning/verify_g.py"
spec = importlib.util.spec_from_file_location("g_process_helpers", HELPER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
CHAPTERS = ["g06-layout-and-access.md", "g06-allocation-and-measurement.md"]
FILE_BLOCK = re.compile(r"\*\*[^*\n]*`([a-z][a-z0-9-]*\.(?:cpp|hpp))`[^*\n]*\*\*\n\n```cpp\n(.*?)\n```", re.S)
FILES = {"layout.cpp", "readings.hpp", "scan.cpp", "scan-contract.cpp",
         "counting-resource.hpp", "reuse.cpp", "arena.cpp", "benchmark.cpp"}
NORMAL = ["scan-contract.cpp", "reuse.cpp", "arena.cpp"]
SAN_FLAGS = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             "-fno-omit-frame-pointer"]
MUTATIONS = [
    ("omit-last-value", "scan-contract.cpp", "scan.cpp", 3,
     "i < values.size()", "i + 1 < values.size()"),
    ("corrupt-record-id", "scan-contract.cpp", "readings.hpp", 2,
     "columns.ids.push_back(reading.id);", "columns.ids.push_back(reading.id + 1);"),
    ("omit-clear", "reuse.cpp", "reuse.cpp", 2,
     "data.clear();", "// Incorrect: retain the previous batch."),
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
            require(filename not in sources, "Duplicate source: " + filename)
            sources[filename] = body + "\n"
    require(set(sources) == FILES, "Unexpected source set")
    return sources, documents


def protected_binding():
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE], cwd=ROOT).decode().splitlines()
    selected = [p for p in paths if
        re.match(r"c\+\+/rework/g0[0-5]-", p) or
        re.fullmatch(r"c\+\+/rework/verify_g[0-5]\.py", p) or
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


def clean(record, code=0):
    return helpers.clean_exit(record, code) and not record["stderr"]


def observation(name, text):
    if name == "scan-contract.cpp":
        require(text == "complete records and both scans agree\n", "Wrong contract output")
        return None
    data = json.loads(text)
    require(isinstance(data, dict), "Expected an observation object")
    if name == "arena.cpp":
        require(set(data) == {"upstream_requests", "retained_before_release", "live_after_release",
                "constructed", "destroyed", "bounded_exhaustion"}, "Arena keys")
        require(data["bounded_exhaustion"] is True, "Exhaustion was not observed")
        numbers = {k: v for k, v in data.items() if k != "bounded_exhaustion"}
        require(all(type(v) is int and v >= 0 for v in numbers.values()), "Arena numeric fields")
        require(data["upstream_requests"] > 0 and data["retained_before_release"] > 0 and
                data["live_after_release"] == 0 and data["constructed"] == data["destroyed"] == 16,
                "Arena lifecycle mismatch")
    elif name == "reuse.cpp":
        require(set(data) == {"fresh_requests", "reused_requests", "fresh_bytes", "reused_bytes",
                             "fresh_peak", "reused_peak"}, "Resource keys")
        require(all(type(v) is int and v > 0 for v in data.values()), "Resource numeric fields")
        require(data["fresh_peak"] <= data["fresh_bytes"] and
                data["reused_peak"] <= data["reused_bytes"], "Resource cumulative/peak mismatch")
    elif name == "layout.cpp":
        require(set(data) == {"size", "alignment", "id_offset", "value_offset", "valid_offset",
                             "int_size", "bool_size"}, "Layout keys")
        require(all(type(v) is int and v >= 0 for v in data.values()), "Layout numeric fields")
        require(all(data[k] > 0 for k in ("size", "alignment", "int_size", "bool_size")), "Zero size")
        require(data["id_offset"] < data["value_offset"] < data["valid_offset"] < data["size"],
                "Member order mismatch")
    else:
        raise ValueError("Unknown observation: " + name)
    return data


def timing_rows(text):
    rows = [json.loads(line) for line in text.splitlines()]
    expected = [(n, shuffled, trial, order, layout)
        for n in (4096, 65536, 1048576) for shuffled in (0, 1) for trial in range(7)
        for order, layout in enumerate(("aos", "soa") if trial % 2 == 0 else ("soa", "aos"))]
    require(len(rows) == len(expected), "Incomplete timing matrix")
    for row, key in zip(rows, expected):
        require(set(row) == {"n", "shuffled", "trial", "order", "layout", "passes", "ns", "checksum"},
                "Timing schema mismatch")
        require(all(type(row[k]) is int for k in row if k != "layout"), "Non-integer timing field")
        require(tuple(row[k] for k in ("n", "shuffled", "trial", "order", "layout")) == key,
                "Timing identity/order mismatch")
        n = row["n"]
        passes = {4096: 64, 65536: 8, 1048576: 2}[n]
        # All selected half-sizes are multiples of 1024. Whole-record shuffling preserves this sum.
        total = (n // 2 // 1024) * (1023 * 1024 // 2)
        require(row["passes"] == passes and row["checksum"] == total * passes, "Wrong timed value")
        require(row["ns"] > 0, "Non-positive timing interval")
    return rows


def rejected(function, *args):
    try:
        function(*args)
    except (ValueError, TypeError, KeyError):
        return True
    return False


def selftests():
    rows = []
    for n in (4096, 65536, 1048576):
        passes = {4096: 64, 65536: 8, 1048576: 2}[n]
        for shuffled in (0, 1):
            for trial in range(7):
                for order, layout in enumerate(("aos", "soa") if trial % 2 == 0 else ("soa", "aos")):
                    rows.append(dict(n=n, shuffled=shuffled, trial=trial, order=order, layout=layout,
                        passes=passes, ns=100, checksum=(n // 2048) * 523776 * passes))
    encode = lambda values: "\n".join(json.dumps(x) for x in values)
    tests = {"complete_matrix": len(timing_rows(encode(rows))) == 84,
             "missing_row_rejected": rejected(timing_rows, encode(rows[:-1])),
             "duplicate_row_rejected": rejected(timing_rows, encode([rows[1]] + rows[1:])),
             "wrong_checksum_rejected": rejected(timing_rows, encode([dict(rows[0], checksum=0)] + rows[1:])),
             "wrong_passes_rejected": rejected(timing_rows, encode([dict(rows[0], passes=1)] + rows[1:])),
             "zero_interval_rejected": rejected(timing_rows, encode([dict(rows[0], ns=0)] + rows[1:])),
             "boolean_interval_rejected": rejected(timing_rows, encode([dict(rows[0], ns=True)] + rows[1:])),
             "invalid_json_rejected": rejected(timing_rows, "not-json"),
             "speed_order_not_an_oracle": len(timing_rows(encode([
                 dict(r, ns=1000000 if r["layout"] == "soa" else 1) for r in rows]))) == 84,
             "wrong_text_rejected": rejected(observation, "scan-contract.cpp", "success\n")}
    record = dict(returncode=0, timed_out=False, stdout="", stderr="")
    tests.update(timeout_rejected=not clean(dict(record, timed_out=True)),
                 crash_not_mutation=not clean(dict(record, returncode=-11), 3),
                 stderr_rejected=not clean(dict(record, stderr="diagnostic")),
                 wrong_exit_rejected=not clean(record, 3))
    require(all(tests.values()), "Oracle selftest failed")
    return tests


def summaries(processes):
    groups = defaultdict(list)
    for process in processes:
        if process["status"] != "OBSERVED":
            continue
        for row in process["rows"]:
            groups[(process["compiler"], process["process"], row["n"], row["shuffled"], row["layout"])].append(
                row["ns"] / row["passes"])
    result = []
    for (compiler, process, n, shuffled, layout), values in groups.items():
        quartiles = statistics.quantiles(values, n=4, method="inclusive")
        result.append(dict(compiler=compiler, process=process, n=n, shuffled=shuffled, layout=layout,
            observations=len(values), unit="ns per scan", min=min(values), median=statistics.median(values),
            max=max(values), q1=quartiles[0], q3=quartiles[2]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", action="append", required=True)
    parser.add_argument("--nm", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Use a new output path; historical evidence is immutable")
    sources, documents = extract()
    temp = Path(tempfile.mkdtemp(prefix="kb-g6-rework-"))
    report = dict(started_at_utc=datetime.now(timezone.utc).isoformat(), platform=platform.platform(),
        macOS=platform.mac_ver()[0], machine=platform.machine(), python=platform.python_version(),
        documents=documents, source_sha256={n: sha(s.encode()) for n, s in sources.items()},
        runner_sha256=sha(Path(__file__).read_bytes()), helper_sha256=sha(HELPER.read_bytes()),
        process_helper=str(HELPER.relative_to(ROOT)), protected_binding=protected_binding(),
        oracle_selftests=selftests(), temp_directory=str(temp), toolchains=[], results=[],
        layout_observations=[], codegen_observations=[], performance=[], mutations=[], sanitizer_probes=[],
        status="INCOMPLETE", concurrency="NOT RUN", pdf="NOT BUILT / NOT VALIDATED",
        cpu_sampling="NOT RUN", hardware_counters="NOT RUN", allocation_timing="NOT RUN",
        end_to_end_timing="NOT RUN", asan_positive_control="NOT RUN", leak_sanitizer="DISABLED",
        frequency_and_affinity_control="NOT SET", cross_platform="NOT ESTABLISHED")
    report["cpu_identity_query"] = helpers.command(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"], temp)
    report["nm_identity"] = helpers.command([args.nm, "--version"], temp)
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0",
               UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=0")
    report["sanitizer_environment"] = {k: env[k] for k in ("ASAN_OPTIONS", "UBSAN_OPTIONS")}
    try:
        require(helpers.clean_exit(report["nm_identity"]), "nm identity unavailable")
        for index, compiler in enumerate(args.compiler):
            folder = temp / str(index)
            folder.mkdir()
            for name, body in sources.items():
                (folder / name).write_text(body)
            (folder / "identity.cpp").write_text("#include <version>\n")
            (folder / "probe.cpp").write_text("int main() { return 0; }\n")
            version = helpers.command([compiler, "--version"], folder)
            macros = helpers.command([compiler, "-std=c++23", "-dM", "-E", "identity.cpp"], folder)
            require(helpers.clean_exit(version) and helpers.clean_exit(macros), "Tool identity failed")
            report["toolchains"].append(dict(compiler=compiler, version=version,
                identity_command=macros["command"], library_macros=[line for line in macros["stdout"].splitlines()
                    if re.match(r"#define (?:_LIBCPP_VERSION|__GLIBCXX__|__cplusplus) ", line)]))
            common = [compiler, "-std=c++23", "-Wall", "-Wextra", "-Wpedantic"]

            def run_case(name, mode, flags, cwd=folder, code=0):
                target = cwd / (name.removesuffix(".cpp") + "-" + mode)
                inputs = [name, "scan.cpp"] if name == "scan-contract.cpp" else [name]
                build = helpers.command(common + flags + inputs + ["-o", str(target)], cwd)
                result = dict(source=name, mode=mode, compiler=compiler, status="FAIL", steps=[build])
                if helpers.clean_exit(build):
                    result["executable_sha256"] = sha(target.read_bytes())
                    execution = helpers.command([str(target)], cwd, env=env)
                    result["steps"].append(execution)
                    if clean(execution, code):
                        try:
                            if mode == "mutation":
                                require(execution["stdout"] == "", "Unexpected mutation output")
                                result["status"] = "REJECTED_AS_EXPECTED"
                            else:
                                result["observation"] = observation(name, execution["stdout"])
                                result["status"] = ("CLEAN_OBSERVED" if mode == "sanitized" else
                                    "OBSERVED" if name == "layout.cpp" else "PASS")
                        except (ValueError, TypeError, KeyError) as error:
                            result["oracle_error"] = str(error)
                print(Path(compiler).parent, name, mode, result["status"], flush=True)
                return result

            for mode, flags in (("O0", ["-O0", "-g"]), ("O2", ["-O2"])):
                for name in NORMAL:
                    report["results"].append(run_case(name, mode, flags))
                report["layout_observations"].append(run_case("layout.cpp", mode, flags))
            build = helpers.command(common + SAN_FLAGS + ["probe.cpp", "-o", "probe"], folder)
            probe = helpers.command([str(folder / "probe")], folder, env=env) if helpers.clean_exit(build) else None
            ready = probe is not None and clean(probe) and probe["stdout"] == ""
            report["sanitizer_probes"].append(dict(compiler=compiler, compile=build, run=probe,
                                                  status="AVAILABLE" if ready else "UNAVAILABLE"))
            for name in NORMAL:
                report["results"].append(run_case(name, "sanitized", SAN_FLAGS) if ready else
                    dict(source=name, compiler=compiler, mode="sanitized", status="SKIP", reason="Probe unavailable"))
            for label, name, changed, code, before, after in MUTATIONS:
                require(sources[changed].count(before) == 1, "Mutation target drifted: " + label)
                variant = folder / label
                variant.mkdir()
                modified = dict(sources)
                modified[changed] = modified[changed].replace(before, after)
                for filename, body in modified.items():
                    (variant / filename).write_text(body)
                result = run_case(name, "mutation", ["-O0", "-g"], cwd=variant, code=code)
                result.update(name=label, expected_exit=code,
                    replacement=dict(path=changed, before=before, after=after),
                    source_sha256={n: sha(s.encode()) for n, s in modified.items()})
                report["mutations"].append(result)

            steps, objects = [], []
            for name in ("scan.cpp", "benchmark.cpp"):
                target = folder / (name + ".o")
                flags = ["-O3", "-fno-lto"]
                if name == "scan.cpp":
                    flags += ["-Rpass=loop-vectorize", "-Rpass-missed=loop-vectorize",
                              "-Rpass-analysis=loop-vectorize"]
                step = helpers.command(common + flags + ["-c", name, "-o", str(target)], folder)
                steps.append(step)
                if helpers.clean_exit(step):
                    objects.append(target)
            require(len(objects) == 2, "Measurement compilation failed: " + repr(steps))
            exe = folder / "benchmark"
            link = helpers.command([compiler, "-fno-lto", *map(str, objects), "-o", str(exe)], folder)
            steps.append(link)
            require(helpers.clean_exit(link), "Measurement link failed")
            asm = folder / "scan.s"
            assembly = helpers.command(common + ["-O3", "-fno-lto", "-S", "scan.cpp", "-o", str(asm)], folder)
            symbols = [helpers.command([args.nm, "--demangle", str(obj)], folder) for obj in objects]
            require(helpers.clean_exit(assembly) and all(helpers.clean_exit(x) for x in symbols), "Codegen observation failed")
            report["codegen_observations"].append(dict(compiler=compiler, status="OBSERVED", steps=steps,
                assembly_command=assembly, assembly=asm.read_text(), assembly_sha256=sha(asm.read_bytes()),
                symbols=symbols, objects={obj.name: dict(bytes=obj.stat().st_size, sha256=sha(obj.read_bytes()))
                    for obj in objects}, executable_sha256=sha(exe.read_bytes()),
                boundary="No vector-width or instruction-count oracle; not CPU profiling"))
            for process in range(3):
                execution = helpers.command([str(exe)], folder, timeout=90)
                result = dict(compiler=compiler, process=process, status="FAIL", execution=execution,
                              executable_sha256=sha(exe.read_bytes()))
                if clean(execution):
                    try:
                        result["rows"] = timing_rows(execution["stdout"])
                        result["status"] = "OBSERVED"
                    except (ValueError, TypeError, KeyError) as error:
                        result["oracle_error"] = str(error)
                report["performance"].append(result)
                print(Path(compiler).parent, "benchmark process", process, result["status"], flush=True)
        report["protected_binding_after"] = protected_binding()
        report["status"] = "COMPLETE" if (
            all(r["status"] in {"PASS", "CLEAN_OBSERVED"} for r in report["results"]) and
            all(r["status"] == "REJECTED_AS_EXPECTED" for r in report["mutations"]) and
            all(r["status"] == "OBSERVED" for key in ("layout_observations", "codegen_observations", "performance")
                for r in report[key])) else "INCOMPLETE"
    except KeyboardInterrupt:
        report["status"] = "CANCELLED"
    except Exception as error:
        report["error"] = repr(error)
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["result_counts"] = dict(Counter(r["mode"] + ":" + r["status"] for r in report["results"]))
    report["mutation_counts"] = dict(Counter(r["status"] for r in report["mutations"]))
    report["performance_summary"] = summaries(report["performance"])
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(report["status"], "Evidence:", args.output, "Sources:", temp)
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
