#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT / "01-优秀系统设计与工程保证方法论-v1.1.0.md",
    ROOT / "02-优秀系统设计-从约束不变量到证据-v1.1.0.md",
]

def walk(value, counts):
    if isinstance(value, dict):
        tag = value.get("t")
        if tag in counts:
            counts[tag] += 1
        for child in value.values():
            walk(child, counts)
    elif isinstance(value, list):
        for child in value:
            walk(child, counts)

for source in SOURCES:
    raw = subprocess.check_output(["pandoc", str(source), "-t", "json"])
    doc = json.loads(raw)
    counts = {"Header": 0, "Table": 0, "CodeBlock": 0, "BlockQuote": 0}
    walk(doc, counts)
    tex = (ROOT / "build" / f"{source.stem}.tex").read_text(encoding="utf-8")
    generated = {
        "Header": len(re.findall(r"^\\(?:chapter|section|subsection|subsubsection)(?:\[[^]]*\])?\{", tex, re.MULTILINE)),
        "Table": len(re.findall(r"^\\begin\{(?:ESDTable|ESDWideTable)\}", tex, re.MULTILINE)),
        "CodeBlock": len(re.findall(r"^\\begin\{(?:ESDCode|ESDFlow|ESDTemplate)\}", tex, re.MULTILINE)),
    }
    expected = {
        "Header": counts["Header"] - 2,
        "Table": counts["Table"],
        "CodeBlock": counts["CodeBlock"],
    }
    if generated != expected:
        raise SystemExit(
            f"content parity failed for {source.name}: expected={expected}, generated={generated}"
        )
    print(
        source.name,
        json.dumps(
            {"source": counts, "generated": generated, "status": "PASS"},
            ensure_ascii=False,
            sort_keys=True,
        ),
    )
