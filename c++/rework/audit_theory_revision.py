#!/usr/bin/env python3
"""Audit this prose revision; never run C++, rewrite old evidence or build PDFs."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = "b052f59f58582d7675e15ba96fed48f086744cec"
BODY = sorted(p for p in HERE.glob("g0[0-7]-*.md") if "verification" not in p.name)
FENCES = re.compile(r"^```[^\n]*\n.*?^```[ \t]*$", re.M | re.S)
FILES = re.compile(r"\*\*[^*\n]*`([a-z][a-z0-9-]*\.(?:cpp|hpp))`[^*\n]*\*\*\n\n```cpp\n(.*?)\n```", re.S)
GATE = re.compile(r"^#{2,3} \d+(?:\.\d+)? (?:用新情形检查理解|用变化后的条件检验模型|迁移题)", re.M)
EXTRA = {"c++/README.md", "c++/editorial-profile.md", "c++/rework/README.md",
         "c++/rework/audit_theory_revision.py", "c++/rework/theory-terminology-audit.json",
         "c++/rework/theory-terminology-revision.md"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", "-c", "core.fsmonitor=false", *args], cwd=ROOT,
                          check=True, capture_output=True, timeout=60).stdout


def tree_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from tree_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from tree_nodes(child)


def structure(text):
    process = subprocess.run(["pandoc", "-f", "gfm", "-t", "json"], input=text,
                             text=True, capture_output=True, check=True, timeout=30)
    nodes = list(tree_nodes(json.loads(process.stdout)))
    headers = [n["c"] for n in nodes if n.get("t") == "Header"]
    ids = [h[1][0] for h in headers] + re.findall(r'<a\s+id="([^"]+)"\s*>', text)
    errors = []
    if sum(h[0] == 1 for h in headers) != 1:
        errors.append("H1 count")
    previous = 0
    for level, attr, _ in headers:
        if level > 3 or level > previous + 1:
            errors.append("heading hierarchy: " + attr[0])
        previous = level
    if len(ids) != len(set(ids)):
        errors.append("duplicate anchor")
    if re.search(r"<\s*/?\s*(?:details|summary)\b", text, re.I):
        errors.append("HTML folding")
    # All source blocks in this fixed corpus use unindented triple backticks.
    if len(re.findall(r"^```", text, re.M)) != 2 * len(FENCES.findall(text)):
        errors.append("unbalanced fences")
    return set(ids), errors


def compare(old, new):
    errors = []
    if FENCES.findall(old) != FENCES.findall(new):
        errors.append("fenced payload changed")
    old_gate, new_gate = GATE.search(old), GATE.search(new)
    if not old_gate or not new_gate or old[old_gate.start():] != new[new_gate.start():]:
        errors.append("Gate/answers/end matter changed")
    # Bind the visible source identity as well as the code bytes.
    marker = re.compile(r"^\*\*[^\n]*`[^`]+\.(?:cpp|hpp)`[^\n]*\*\*$", re.M)
    if marker.findall(old) != marker.findall(new):
        errors.append("file identity changed")
    before, _ = structure(old)
    after, structural_errors = structure(new)
    errors.extend(structural_errors)
    missing = sorted(before - after)
    if missing:
        errors.append("old anchors missing: " + ", ".join(missing))
    return errors


def selftests(old):
    fence = FENCES.search(old)
    gate = GATE.search(old)
    marker = next(FILES.finditer(old))
    variants = {
        "prose_allowed": (old.replace("\n\n", "\n\n普通论述校准。\n\n", 1), False),
        "code_rejected": (old[:fence.end() - 3] + "// mutation\n" + old[fence.end() - 3:], True),
        "gate_rejected": (old[:gate.start()] + old[gate.start():] + "\n错误答案。\n", True),
        "anchor_rejected": (old.replace(old.splitlines()[0], "# Changed identity", 1), True),
        "filename_rejected": (old[:marker.start(1)] + "changed.hpp" + old[marker.end(1):], True),
    }
    result = {name: bool(compare(old, text)) == expected
              for name, (text, expected) in variants.items()}
    if not all(result.values()):
        raise ValueError("Audit selftest failed: " + repr(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New report; never overwrites an existing file")
    args = parser.parse_args()
    if not shutil.which("pandoc"):
        raise SystemExit("SKIP: pandoc required; no audit PASS")
    if len(BODY) != 18:
        raise SystemExit("FAIL: expected exactly 18 body documents")
    report = {"base": BASE, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "audit_sha256": sha(Path(__file__).read_bytes()),
              "python": sys.version.split()[0],
              "pandoc": subprocess.check_output(["pandoc", "--version"], text=True).splitlines()[0],
              "documents": {}, "historical_binding": {}, "errors": [],
              "cpp_rerun": "NOT RUN", "performance_rerun": "NOT RUN",
              "concurrency_dynamic_rerun": "NOT RUN", "pdf": "NOT BUILT / NOT VALIDATED"}
    current_sources = {}
    for path in BODY:
        rel = path.relative_to(ROOT).as_posix()
        old_bytes = git("show", BASE + ":" + rel)
        new_bytes = path.read_bytes()
        old, new = old_bytes.decode(), new_bytes.decode()
        errors = compare(old, new)
        report["errors"].extend(rel + ": " + e for e in errors)
        old_gate, new_gate = GATE.search(old), GATE.search(new)
        report["documents"][rel] = {
            "base_sha256": sha(old_bytes), "current_sha256": sha(new_bytes),
            "fences_unchanged": len(FENCES.findall(old)) if not errors else None,
            "old_anchors_retained": len(structure(old)[0]) if not errors else None,
            "gate_to_eof_unchanged": bool(old_gate and new_gate and
                                           old[old_gate.start():] == new[new_gate.start():]),
        }
        group = path.name[:3]
        sources = current_sources.setdefault(group, {})
        for filename, body in FILES.findall(new):
            if filename in sources:
                raise ValueError("Duplicate source in " + group + ": " + filename)
            sources[filename] = sha((body + "\n").encode())
    for group, sources in sorted(current_sources.items()):
        history = HERE / ("g01-review-results.json" if group == "g01" else group + "-results.json")
        data = json.loads(history.read_bytes())
        match = sources == data["source_sha256"]
        if not match:
            report["errors"].append(group + ": historical source mapping mismatch")
        report["historical_binding"][group] = {
            "path": history.relative_to(ROOT).as_posix(), "sha256": sha(history.read_bytes()),
            "original_document_sha256": data.get("documents", {data.get("chapter"): data.get("chapter_sha256")}),
            "source_sha256": sources, "binding": "MATCH" if match else "MISMATCH",
        }
    allowed = {p.relative_to(ROOT).as_posix() for p in BODY} | EXTRA
    protected = []
    outside = []
    entries = git("ls-tree", "-r", "-z", BASE)
    for entry in entries.split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, identity = meta.split()
        rel = name.decode()
        if rel in allowed:
            continue
        path = ROOT / rel
        if kind != b"blob" or path.is_symlink() or not path.is_file():
            outside.append(rel)
            continue
        payload = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
        if blob != identity.decode():
            outside.append(rel)
        protected.append(rel)
    report["protected_tracked_files"] = len(protected)
    report["outside_scope_changes"] = outside
    report["errors"].extend("outside scope: " + p for p in outside)
    report["audit_selftests"] = selftests(git("show", BASE + ":c++/rework/g00-native-toolchain.md").decode())
    report["counts"] = {
        "body_documents": len(BODY), "named_sources": sum(map(len, current_sources.values())),
        "fenced_payloads": sum(v["fences_unchanged"] or 0 for v in report["documents"].values()),
        "old_anchors": sum(v["old_anchors_retained"] or 0 for v in report["documents"].values()),
        "gate_regions": sum(v["gate_to_eof_unchanged"] for v in report["documents"].values()),
    }
    report["status"] = "PASS" if not report["errors"] else "FAIL"
    if args.output:
        with args.output.open("x", encoding="utf-8") as file:
            file.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "counts", "audit_selftests", "protected_tracked_files", "errors")},
                     ensure_ascii=False, indent=2))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
