#!/usr/bin/env python3
"""Run only the source-bound examples in the new G0; never build a PDF."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
CHAPTER = HERE / "g00-native-toolchain.md"
FLAGS = ["-std=c++23", "-O0", "-g", "-Wall", "-Wextra", "-Wpedantic"]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New JSON file; existing records are never overwritten")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    chapter = CHAPTER.read_bytes()
    matches = re.findall(r"\*\*文件 `([^`]+)`\*\*\n\n```cpp\n(.*?)\n```",
                         chapter.decode(), re.S)
    sources = {name: body + "\n" for name, body in matches}
    expected = {"calc.hpp", "calc.cpp", "main.cpp", "conflicting-return.cpp",
                "wrong-parameters.cpp", "header-definition.hpp", "aux.cpp",
                "single.cpp", "unused.cpp"}
    if set(sources) != expected or len(matches) != len(expected):
        raise SystemExit("Source extraction mismatch; no experiments run")
    root = Path(tempfile.mkdtemp(prefix="kb-g0-rework-"))
    llvm = Path("/opt/homebrew/opt/llvm/bin")
    commands = {name: shutil.which(name) or str(llvm / name)
                for name in ("llvm-nm", "llvm-objdump", "ar", "otool")}
    record = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
              "chapter": CHAPTER.name, "chapter_sha256": digest(chapter),
              "runner_sha256": digest(Path(__file__).read_bytes()),
              "platform": platform.platform(), "machine": platform.machine(),
              "macOS": platform.mac_ver()[0], "python": platform.python_version(),
              "source_sha256": {n: digest(s.encode()) for n, s in sources.items()},
              "workspace": str(root), "tool_paths": commands, "runs": [],
              "scope": "Local compiler/linker checks and binary observations only; "
                       "not performance, cross-platform, or PDF qualification"}

    for number, compiler in enumerate(args.compiler):
        directory = root / str(number)
        directory.mkdir()
        run = {"compiler": compiler, "checks": [], "observations": {}, "commands": []}
        record["runs"].append(run)
        current = "setup"

        def execute(argv, cwd=directory, expected_exit=0, diagnostic=None):
            argv = [str(x) for x in argv]
            log = {"argv": argv, "cwd": str(cwd)}
            run["commands"].append(log)
            try:
                result = subprocess.run(argv, cwd=cwd, capture_output=True,
                                        text=True, timeout=30)
            except subprocess.TimeoutExpired:
                log["status"] = "TIMEOUT"
                raise RuntimeError("Timeout is not an expected negative result")
            log.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
            if expected_exit is None:
                if result.returncode <= 0 or not diagnostic:
                    raise RuntimeError("Expected a diagnosed, nonsignal failure")
            elif result.returncode != expected_exit:
                raise RuntimeError(f"Expected exit {expected_exit}, got {result.returncode}")
            if diagnostic and not re.search(diagnostic, result.stdout + result.stderr, re.I | re.S):
                raise RuntimeError(f"Missing intended diagnostic: {diagnostic}")
            return result.stdout + result.stderr

        def compile_file(name, output, cwd=directory, flags=FLAGS):
            return execute([compiler, *flags, "-c", name, "-o", output], cwd=cwd)

        def passed():
            run["checks"].append({"name": current, "status": "PASS"})

        def observe(key, argv, cwd=directory):
            run["observations"][key] = {"status": "OBSERVED", "text": execute(argv, cwd=cwd)}
            return run["observations"][key]["text"]

        try:
            for name, source in sources.items():
                (directory / name).write_text(source)
            run["version"] = execute([compiler, "--version"])
            run["target"] = execute([compiler, "-dumpmachine"]).strip()
            for name in ("llvm-nm", "llvm-objdump"):
                observe(name + "-version", [commands[name], "--version"])

            current = "preprocess-and-semantic-check"
            execute([compiler, "-std=c++23", "-E", "-P", "main.cpp", "-o", "main.ii"])
            preprocessed = (directory / "main.ii").read_text()
            require("int add(int a, int b);" in preprocessed, "Declaration not in preprocessed file")
            require("int main()" in preprocessed and "return a + b;" not in preprocessed,
                    "Unexpected preprocessed definition set")
            run["observations"]["preprocessed"] = {"status": "OBSERVED", "text": preprocessed}
            execute([compiler, "-std=c++23", "-fsyntax-only", "main.cpp"])
            passed()

            current = "missing-definition-link-diagnostic"
            compile_file("main.cpp", "main.o")
            execute([compiler, "main.o", "-o", "missing-definition"], expected_exit=None,
                    diagnostic=r"(?:undefined symbols?|undefined reference).*add\(int, int\)")
            passed()

            current = "separate-translation-units-run"
            compile_file("calc.cpp", "calc.o")
            execute([compiler, "main.o", "calc.o", "-o", "demo"])
            execute([directory / "demo"])
            passed()
            observe("driver-plan", [compiler, "-###", "main.o", "calc.o", "-o", "planned"])
            for obj in ("main.o", "calc.o"):
                observe(obj + "-symbols-raw", [commands["llvm-nm"], obj])
                observe(obj + "-symbols-demangled", [commands["llvm-nm"], "--demangle", obj])
            observe("call-and-relocation", [commands["llvm-objdump"], "--disassemble", "--reloc", "main.o"])
            observe("linked-demo-disassembly", [commands["llvm-objdump"], "--disassemble", "demo"])

            current = "logic-mutation-is-not-a-link-error"
            mutated = sources["calc.cpp"].replace("return a + b;", "return a - b;")
            require(mutated != sources["calc.cpp"], "Mutation did not change source")
            run["mutation_sha256"] = digest(mutated.encode())
            (directory / "subtract.cpp").write_text(mutated)
            compile_file("subtract.cpp", "subtract.o")
            execute([compiler, "main.o", "subtract.o", "-o", "wrong-result"])
            execute([directory / "wrong-result"], expected_exit=1)
            passed()

            current = "return-type-conflict-compile-diagnostic"
            execute([compiler, *FLAGS, "-c", "conflicting-return.cpp", "-o", "conflict.o"],
                    expected_exit=None, diagnostic=r"(?:differ only in their return type|return type.*differs)")
            passed()

            current = "wrong-parameters-link-diagnostic"
            compile_file("wrong-parameters.cpp", "wrong-parameters.o")
            execute([compiler, "main.o", "wrong-parameters.o", "-o", "wrong-signature"],
                    expected_exit=None, diagnostic=r"(?:undefined symbols?|undefined reference).*add\(int, int\)")
            observe("wrong-parameters-symbols", [commands["llvm-nm"], "--demangle", "wrong-parameters.o"])
            passed()

            for inline in (False, True):
                current = "inline-header-run" if inline else "duplicate-header-link-diagnostic"
                variant = directory / ("inline" if inline else "duplicate")
                variant.mkdir()
                header = sources["header-definition.hpp"]
                if inline:
                    header = header.replace("int add(", "inline int add(")
                (variant / "calc.hpp").write_text(header)
                run.setdefault("header_variant_sha256", {})[variant.name] = digest(header.encode())
                for name in ("main.cpp", "aux.cpp"):
                    (variant / name).write_text(sources[name])
                    compile_file(name, name + ".o", cwd=variant)
                link = [compiler, "main.cpp.o", "aux.cpp.o", "-o", "demo"]
                if inline:
                    execute(link, cwd=variant)
                    execute([variant / "demo"], cwd=variant)
                else:
                    execute(link, cwd=variant, expected_exit=None,
                            diagnostic=r"(?:duplicate symbol|multiple definition).*add")
                passed()

            current = "optimized-single-translation-unit-run"
            for source, stem, level in (("main.cpp", "main-O0", "-O0"),
                                        ("main.cpp", "main-O2", "-O2"),
                                        ("single.cpp", "single-O2", "-O2")):
                execute([compiler, "-std=c++23", level, "-S", source, "-o", stem + ".s"])
                run["observations"][stem + "-assembly"] = {
                    "status": "OBSERVED", "text": (directory / (stem + ".s")).read_text()}
            compile_file("single.cpp", "single-O2.o", flags=["-std=c++23", "-O2"])
            execute([compiler, "single-O2.o", "-o", "single"])
            execute([directory / "single"])
            observe("single-O2-symbols", [commands["llvm-nm"], "--demangle", "single-O2.o"])
            passed()

            current = "static-archive-run-before-and-after-rename"
            compile_file("unused.cpp", "unused.o")
            execute([commands["ar"], "rcs", "libcalc.a", "calc.o", "unused.o"])
            observe("archive-members", [commands["ar"], "t", "libcalc.a"])
            execute([compiler, "main.o", "libcalc.a", "-Wl,-map,static-demo.map", "-o", "static-demo"])
            execute([directory / "static-demo"])
            observe("static-demo-symbols", [commands["llvm-nm"], "--demangle", "static-demo"])
            run["observations"]["static-link-map"] = {
                "status": "OBSERVED", "text": (directory / "static-demo.map").read_text()}
            (directory / "libcalc.a").rename(directory / "libcalc.a.saved")
            execute([directory / "static-demo"])
            observe("runtime-dylibs", [commands["otool"], "-L", "static-demo"])
            passed()

            current = "user-header-dependency-file"
            execute([compiler, "-std=c++23", "-MMD", "-MF", "main.d", "-c", "main.cpp", "-o", "dep.o"])
            dependency = (directory / "main.d").read_text()
            require("main.cpp" in dependency and "calc.hpp" in dependency,
                    "Dependency file is missing source or user header")
            run["observations"]["dependency-file"] = {"status": "OBSERVED", "text": dependency}
            passed()
            run["status"] = "PASS"
        except FileNotFoundError as error:
            run["status"] = "SKIP"
            run["checks"].append({"name": current, "status": "SKIP", "detail": str(error)})
        except (RuntimeError, OSError) as error:
            run["status"] = "FAIL"
            run["checks"].append({"name": current, "status": "FAIL", "detail": str(error)})

    record["status"] = "PASS" if all(r["status"] == "PASS" for r in record["runs"]) else "INCOMPLETE"
    record["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(record, output, ensure_ascii=False, indent=2)
        output.write("\n")
    for run in record["runs"]:
        print(run["compiler"], run["status"], len(run["checks"]), "checks")
        for check in run["checks"]:
            if check["status"] != "PASS":
                print(check)
    print("Evidence:", args.output, "Temporary artifacts:", root)
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
