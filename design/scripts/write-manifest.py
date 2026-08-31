#!/usr/bin/env python3
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SOURCES = [
    "01-优秀系统设计与工程保证方法论-v1.1.0.md",
    "02-优秀系统设计-从约束不变量到证据-v1.1.0.md",
]
PDFS = [name.removesuffix(".md") + ".pdf" for name in SOURCES]
HASHED_SOURCES = [
    "publication/esdbook.cls",
    "publication/esd-theme.sty",
    "publication/template.tex",
    "publication/filters/normalize-headings.lua",
    "publication/filters/semantic-blocks.lua",
    "publication/filters/tables.lua",
    "publication/filters/code-blocks.lua",
    "publication/filters/cross-references.lua",
    "publication/filters/pdf-metadata.lua",
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def first_line(command: list[str]) -> str:
    output = subprocess.check_output(command, text=True)
    return output.splitlines()[0].strip()


def latex_kernel() -> str:
    logs = sorted((ROOT / "build").glob("*.log"))
    if not logs:
        return "unknown"
    match = re.search(r"LaTeX2e <([^>]+)>", logs[0].read_text(errors="replace"))
    return match.group(1) if match else "unknown"


epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "1788134400"))
manifest = {
    "schema_version": 1,
    "generated_at": datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z"),
    "source_date_epoch": epoch,
    "profile": "Professional Release",
    "source_of_truth": "Markdown",
    "sources": SOURCES,
    "artifacts": {name: digest(DIST / name) for name in PDFS},
    "toolchain": {
        "pandoc": first_line(["pandoc", "--version"]),
        "lualatex": first_line(["lualatex", "--version"]),
        "latex_kernel": latex_kernel(),
        "latexmk": first_line(["latexmk", "-v"]),
    },
    "publication_source_sha256": {
        name: digest(ROOT / name) for name in HASHED_SOURCES
    },
    "locks": ["package-lock.txt", "texlive.profile", "fonts.lock"],
    "pdf_ua_claim": None,
    "accessibility_status": "UNKNOWN / NOT RELEASE-QUALIFIED",
}
(DIST / "build-manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
