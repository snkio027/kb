#!/usr/bin/env python3
"""Extract and run the 20 marked FM probes; write only to a new temp directory."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FLAGS = ["-std=c++23", "-O1", "-Wall", "-Wextra", "-pedantic", "-pthread"]
PATTERN = re.compile(r'<!-- fm-test (\{[^\n]+\}) -->\n```cpp\n(.*?)\n```', re.S)
MODES = {"run", "compile", "compile_fail", "death", "sanitizer_negative"}
PROBES = {
    "expected": '#include <expected>\n#if !defined(__cpp_lib_expected) || __cpp_lib_expected < 202202L\n#error expected_unavailable\n#endif\nstd::expected<int,int> x{1};\n',
    "expected-monadic": '#include <expected>\n#if !defined(__cpp_lib_expected) || __cpp_lib_expected < 202211L\n#error monadic_unavailable\n#endif\n',
    "posix": '#include <fcntl.h>\n#include <unistd.h>\nint main() { return 0; }\n',
    "ubsan": 'int main() { return 0; }\n',
}
IDENTITY = '''#include <iostream>
#include <version>
int main() {
#ifdef _LIBCPP_VERSION
    std::cout << "_LIBCPP_VERSION=" << _LIBCPP_VERSION << '\\n';
#endif
#ifdef __GLIBCXX__
    std::cout << "__GLIBCXX__=" << __GLIBCXX__ << '\\n';
#endif
#ifdef __cpp_lib_expected
    std::cout << "__cpp_lib_expected=" << __cpp_lib_expected << '\\n';
#endif
}
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def collect():
    paths = sorted(ROOT.glob("fm[0-9]-*.md")) + [ROOT / "review/fm-verification-samples.md"]
    cases, inputs = {}, {}
    for path in paths:
        data = path.read_bytes()
        inputs[str(path.relative_to(ROOT))] = sha(data)
        text = data.decode("utf-8")
        matches = list(PATTERN.finditer(text))
        if len(matches) != text.count("<!-- fm-test "):
            raise ValueError(f"Malformed sample marker in {path}")
        for match in matches:
            meta = json.loads(match[1])
            case_id = meta["id"]
            if not re.fullmatch(r"T\d{2}", case_id) or case_id in cases:
                raise ValueError(f"Invalid or duplicated sample: {case_id}")
            if meta["mode"] not in MODES:
                raise ValueError(f"Unknown mode: {meta}")
            if meta.get("feature") and meta["feature"] not in PROBES:
                raise ValueError(f"Unknown feature: {meta}")
            if meta["mode"] in {"compile_fail", "sanitizer_negative"} and not meta.get("diagnostics"):
                raise ValueError(f"Missing diagnostic oracle: {case_id}")
            for pattern in meta.get("diagnostics", []):
                re.compile(pattern)
            source = match[2] + "\n"
            cases[case_id] = dict(meta, source=source, source_sha256=sha(source.encode()),
                                  document=str(path.relative_to(ROOT)),
                                  marker_line=text.count("\n", 0, match.start()) + 1)
    if set(cases) != {f"T{i:02}" for i in range(1, 21)}:
        raise ValueError("Expected exactly T01 through T20")
    return [cases[k] for k in sorted(cases)], inputs


def invoke(command, cwd, timeout=30):
    process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    return dict(command=command, cwd=str(cwd), returncode=process.returncode,
                stdout=stdout, stderr=stderr, timeout=timed_out)


def diagnostics_match(case, text):
    return all(re.search(p, text, re.I) for p in case.get("diagnostics", []))


def classify(case, compile_result, run_result=None):
    if compile_result["timeout"] or (run_result and run_result["timeout"]):
        return "HARNESS_ERROR"
    rc = compile_result["returncode"]
    if rc < 0:
        return "HARNESS_ERROR"
    if case["mode"] == "compile_fail":
        if rc > 0 and diagnostics_match(case, compile_result["stderr"]):
            return "PASS"
        return "DIVERGENCE" if case["id"] == "T16" and rc == 0 else "FAIL"
    if rc != 0:
        return "FAIL"
    if case["mode"] == "compile":
        return "PASS"
    if run_result is None:
        return "HARNESS_ERROR"
    if case["mode"] == "sanitizer_negative":
        ok = run_result["returncode"] != 0 and diagnostics_match(case, run_result["stderr"])
    else:
        ok = run_result["returncode"] == case.get("exit_code", 0)
    return "PASS" if ok else "FAIL"


def run_compiler(compiler, folder, cases):
    folder.mkdir()
    path = shutil.which(compiler)
    if not path:
        return {"compiler": compiler, "available": False}, [dict(id=c["id"], status="SKIP", reason="compiler unavailable") for c in cases]
    path = str(Path(path).absolute())
    info = {"compiler": compiler, "path": path, "available": True,
            "version": invoke([path, "--version"], folder), "features": {}}
    source = folder / "identity.cpp"
    source.write_text(IDENTITY)
    binary = folder / "identity"
    compiled = invoke([path, *FLAGS, str(source), "-o", str(binary)], folder)
    info["identity_compile"] = compiled
    if compiled["returncode"] != 0 or compiled["timeout"]:
        return info, [dict(id=c["id"], status="HARNESS_ERROR", reason="C++23 compile/link probe failed") for c in cases]
    info["identity_run"] = invoke([str(binary)], folder, timeout=8)
    if info["identity_run"]["returncode"] != 0 or info["identity_run"]["timeout"]:
        return info, [dict(id=c["id"], status="HARNESS_ERROR", reason="toolchain runtime probe failed") for c in cases]
    for feature, code in PROBES.items():
        probe = folder / (feature + ".cpp")
        probe.write_text(code)
        command = [path, *FLAGS]
        if feature == "ubsan":
            command += ["-fsanitize=undefined", "-fno-sanitize-recover=all", str(probe), "-o", str(folder / "ubsan")]
        else:
            command += ["-fsyntax-only", str(probe)]
        result = invoke(command, folder)
        if feature == "ubsan" and result["returncode"] == 0 and not result["timeout"]:
            result = {"compile": result, "run": invoke([str(folder / "ubsan")], folder, timeout=8)}
            available = result["run"]["returncode"] == 0 and not result["run"]["timeout"]
        else:
            available = result["returncode"] == 0 and not result["timeout"]
        info["features"][feature] = {"available": available, "probe": result}
    rows = []
    for case in cases:
        row = {k: v for k, v in case.items() if k != "source"}
        feature = case.get("feature")
        if feature and not info["features"][feature]["available"]:
            row.update(status="SKIP", reason=f"{feature} preflight failed; inspect probe")
            rows.append(row)
            continue
        work = folder / case["id"]
        work.mkdir()
        source, binary = work / "sample.cpp", work / "sample"
        source.write_text(case["source"])
        command = [path, *FLAGS]
        if case["mode"] in {"compile", "compile_fail"}:
            command += ["-fsyntax-only", str(source)]
        else:
            if case["mode"] == "sanitizer_negative":
                command += ["-fsanitize=undefined", "-fno-sanitize-recover=all"]
            command += [str(source), "-o", str(binary)]
        row["compile"] = invoke(command, work)
        if row["compile"]["returncode"] == 0 and not row["compile"]["timeout"] and case["mode"] not in {"compile", "compile_fail"}:
            row["run"] = invoke([str(binary)], work, timeout=8)
        row["status"] = classify(case, row["compile"], row.get("run"))
        rows.append(row)
    return info, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("compilers", nargs="*", default=["clang++"])
    args = parser.parse_args()
    cases, inputs = collect()
    output = Path(tempfile.mkdtemp(prefix="fm-verification-"))
    report = dict(platform=platform.platform(), baseline="N4950 + LWG 3843",
                  source_base="786908271dfa479c0d4aeb2239b19bd15f90e768",
                  source_files_sha256=inputs, runner_sha256=sha(Path(__file__).read_bytes()),
                  scope="20 targeted samples; not corpus coverage", toolchains=[])
    try:
        for i, compiler in enumerate(args.compilers):
            info, results = run_compiler(compiler, output / f"compiler-{i}", cases)
            info["results"] = results
            info["counts"] = {s: sum(r["status"] == s for r in results) for s in ["PASS", "FAIL", "DIVERGENCE", "SKIP", "HARNESS_ERROR"]}
            report["toolchains"].append(info)
            print(compiler, json.dumps(info["counts"]), flush=True)
        statuses = {r["status"] for t in report["toolchains"] for r in t["results"]}
        code = 1 if statuses & {"FAIL", "DIVERGENCE", "HARNESS_ERROR"} else (2 if "SKIP" in statuses else 0)
        report["exit_code"] = code
        return code
    finally:
        (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print("Evidence:", output / "results.json", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
