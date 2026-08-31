#!/usr/bin/env python3
import sys
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader


def dereference(value):
    return value.get_object() if hasattr(value, "get_object") else value


def audit(path: Path) -> list[str]:
    errors = []
    reader = PdfReader(path)
    root = dereference(reader.trailer["/Root"])

    if root.get("/Lang") != "zh-CN":
        errors.append("catalog /Lang must be zh-CN")
    if "/JavaScript" in dereference(root.get("/Names", {})):
        errors.append("JavaScript name tree is not allowed")
    if "/EmbeddedFiles" in dereference(root.get("/Names", {})):
        errors.append("embedded files are not allowed")
    if not reader.outline:
        errors.append("bookmark outline is empty")

    internal_links = 0
    external_links = 0
    for number, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if abs(width - 595.276) > 0.75 or abs(height - 841.89) > 0.75:
            errors.append(f"page {number} is not A4")

        for annotation_ref in page.get("/Annots", []):
            annotation = dereference(annotation_ref)
            if annotation.get("/Subtype") != "/Link":
                continue
            if "/Dest" in annotation:
                internal_links += 1
                continue
            action = dereference(annotation.get("/A", {}))
            action_type = action.get("/S")
            if action_type == "/GoTo":
                internal_links += 1
            elif action_type == "/URI":
                target = str(action.get("/URI", ""))
                scheme = urlparse(target).scheme.lower()
                if scheme not in {"", "https", "mailto"}:
                    errors.append(f"page {number} uses disallowed URI scheme: {scheme}")
                external_links += 1
            elif action_type == "/GoToR":
                target = dereference(action.get("/F", ""))
                if isinstance(target, dict):
                    target = target.get("/F", "")
                if isinstance(target, bytes):
                    try:
                        target = target.decode("utf-8")
                    except UnicodeDecodeError:
                        errors.append(f"page {number} has a non-UTF-8 remote document target")
                        target = ""
                target_path = Path(str(target))
                if target_path.is_absolute() or ".." in target_path.parts or target_path.suffix.lower() != ".pdf":
                    errors.append(f"page {number} uses unsafe remote document target: {target}")
                external_links += 1
            elif action_type == "/JavaScript":
                errors.append(f"page {number} contains JavaScript")
            elif action_type:
                errors.append(f"page {number} uses unsupported link action: {action_type}")

    if internal_links == 0:
        errors.append("no internal TOC links found")

    print(
        f"{path.name}: pages={len(reader.pages)} bookmarks=yes "
        f"internal_links={internal_links} external_links={external_links} lang=zh-CN"
    )
    return errors


failed = False
for argument in sys.argv[1:]:
    pdf = Path(argument)
    problems = audit(pdf)
    for problem in problems:
        print(f"ERROR: {pdf.name}: {problem}", file=sys.stderr)
    failed = failed or bool(problems)

raise SystemExit(1 if failed else 0)
