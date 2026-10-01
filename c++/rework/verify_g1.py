#!/usr/bin/env python3
"""Verify the three reworked G1 units; preserve historical execution records."""

import argparse
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
BASE = "d45f9a7020c2888dda15445e63b64478d5c09ec4"
CHAPTERS = ["g01-storage-and-lifetime.md", "g01-borrowing-and-invalidation.md",
            "g01-representation-and-typed-access.md"]
FILE_BLOCK = re.compile(r"\*\*文件 `([^`]+)`\*\*\n\n```cpp\n(.*?)\n```", re.S)
OUTPUTS = {
    "lifecycle.cpp": "raw live=0\nconstructed live=1 value=42\ndestroyed live=0\n"
                     "rebuilt live=1 sequence=2\nfinal live=0 constructed=2 destroyed=2\n",
    "constructor-failure.cpp": "rejected outer-destroyed=0 member-destroyed=1\n"
                               "retry outer-destroyed=1 member-destroyed=2\n",
    "reference-lifetime.cpp": "direct live=1\nforwarded live=0\n",
    "array-span.cpp": "array sum=105\nmiddle sum=55\n",
    "vector-borrows.cpp": "append owner-size=3 borrowed-size=2\n"
                          "reallocated owner-alive size=3\ncleared size=0; capacity-retained\n",
    "erase-position.cpp": "after erase next=30 old-index-now=40\n",
    "representation-copy.cpp": "view tracks source; snapshot restores value\n",
    "representation-value.cpp": "numeric=1; restored=1.5\nsource=2.5; restored=1.5\n",
}
SAN_FLAGS = ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
             "-fno-omit-frame-pointer"]
ASAN_FLAGS = ["-O0", "-g", "-fsanitize=address", "-fno-omit-frame-pointer"]
ASAN_OPTIONS = "detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def extract():
    sources = {}
    documents = {}
    for name in CHAPTERS:
        data = (HERE / name).read_bytes()
        documents[name] = sha(data)
        blocks = FILE_BLOCK.findall(data.decode())
        require(data.decode().count("```cpp\n") == len(blocks), "Unbound C++ block: " + name)
        for filename, body in blocks:
            require(re.fullmatch(r"[a-z][a-z0-9-]*\.(?:cpp|hpp)", filename), "Unsafe filename")
            require(filename not in sources, "Duplicate filename")
            sources[filename] = body + "\n"
    require(set(sources) == set(OUTPUTS) | {"reading.hpp", "const-access.cpp", "stale-borrow.cpp"},
            "Unexpected source set")
    return sources, documents


def g0_binding():
    relative = "c++/rework/g00-native-toolchain.md"
    old = subprocess.check_output(["git", "show", f"{BASE}:{relative}"], cwd=ROOT)
    new = (ROOT / relative).read_bytes()
    fences = lambda data: re.findall(rb"^```([^\n]*)\n(.*?)^```[ \t]*$", data, re.M | re.S)
    require(fences(old) == fences(new), "G0 fenced payload changed")
    old_code = dict(FILE_BLOCK.findall(old.decode()))
    new_code = dict(FILE_BLOCK.findall(new.decode()))
    require(old_code == new_code, "G0 extracted source changed")
    history_path = "c++/rework/g00-results.json"
    history = (ROOT / history_path).read_bytes()
    require(history == subprocess.check_output(["git", "show", f"{BASE}:{history_path}"], cwd=ROOT),
            "Historical G0 evidence was changed")
    require(json.loads(history)["chapter_sha256"] == sha(old), "Historical G0 text binding mismatch")
    return {"historical_commit": BASE, "old_chapter_sha256": sha(old),
            "current_chapter_sha256": sha(new), "fenced_blocks_unchanged": len(fences(old)),
            "source_files_unchanged": len(old_code), "execution_rerun": "NOT RUN",
            "historical_result_sha256": sha(history)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Output already exists; choose a new record path")
    sources, documents = extract()
    temp = Path(tempfile.mkdtemp(prefix="kb-g1-rework-"))
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "macOS": platform.mac_ver()[0],
              "machine": platform.machine(), "python": platform.python_version(),
              "documents": documents, "source_sha256": {n: sha(s.encode()) for n, s in sources.items()},
              "runner_sha256": sha(Path(__file__).read_bytes()),
              "process_helper": str(HELPER.relative_to(ROOT)), "helper_sha256": sha(HELPER.read_bytes()),
              "g0_editorial_binding": g0_binding(), "temp_directory": str(temp),
              "toolchains": [], "results": [], "performance": "NOT RUN",
              "concurrency": "NOT RUN", "pdf": "NOT BUILT / NOT VALIDATED"}
    env = dict(os.environ, ASAN_OPTIONS=ASAN_OPTIONS, UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=0")
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

        def run_case(name, mode, flags, expected_stdout=None):
            result = {"source": name, "mode": mode, "compiler": compiler, "status": "FAIL", "steps": []}
            report["results"].append(result)
            output = folder / (name.removesuffix(".cpp") + "-" + mode)
            command = common + flags + (["-c"] if mode == "compile_fail" else []) + [name, "-o", str(output)]
            compilation = helpers.command(command, folder)
            result["steps"].append(compilation)
            if mode == "compile_fail":
                pattern = r"cannot assign to (?:variable|non-static data member).*const-qualified"
                result["expected_diagnostic"] = pattern
                if helpers.diagnosed(compilation, pattern):
                    result["status"] = "PASS"
            elif helpers.clean_exit(compilation):
                execution = helpers.command([str(output)], folder, env=env)
                result["steps"].append(execution)
                if mode == "asan_negative":
                    result.update(expected_exit=86, expected_diagnostic="AddressSanitizer: heap-use-after-free")
                    if helpers.clean_exit(execution, 86) and helpers.diagnosed(execution, result["expected_diagnostic"]):
                        result["status"] = "DETECTED_AS_EXPECTED"
                else:
                    result["expected_stdout"] = expected_stdout
                    if (helpers.clean_exit(execution) and execution["stdout"] == expected_stdout
                            and not execution["stderr"]):
                        result["status"] = "CLEAN_OBSERVED" if mode == "sanitized" else "PASS"
            print(Path(compiler).parent, name, mode, result["status"], flush=True)
            return result

        for mode, flags in (("O0", ["-O0", "-g"]), ("O2", ["-O2"])):
            for name, output in OUTPUTS.items():
                run_case(name, mode, flags, output)
        run_case("const-access.cpp", "compile_fail", ["-O0"])
        for mode, flags in (("sanitized", SAN_FLAGS), ("asan_negative", ASAN_FLAGS)):
            probe_build = helpers.command(common + flags + ["probe.cpp", "-o", "probe"], folder)
            probe_run = helpers.command([str(folder / "probe")], folder, env=env) if helpers.clean_exit(probe_build) else None
            ready = probe_run is not None and helpers.clean_exit(probe_run)
            report.setdefault("sanitizer_probes", []).append({"compiler": compiler, "mode": mode,
                "status": "AVAILABLE" if ready else "UNAVAILABLE", "compile": probe_build, "run": probe_run})
            selected = OUTPUTS if mode == "sanitized" else {"stale-borrow.cpp": None}
            for name, output in selected.items():
                if ready:
                    run_case(name, mode, flags, output)
                else:
                    report["results"].append({"source": name, "mode": mode, "compiler": compiler,
                                              "status": "SKIP", "reason": "Sanitizer probe unavailable"})
    report["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    accepted = {"PASS", "CLEAN_OBSERVED", "DETECTED_AS_EXPECTED"}
    report["status"] = "COMPLETE" if all(r["status"] in accepted for r in report["results"]) else "INCOMPLETE"
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(report["status"], "Evidence:", args.output, "Temporary sources:", temp)
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
