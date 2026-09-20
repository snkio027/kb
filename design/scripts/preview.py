#!/usr/bin/env python3
"""One-engine, macOS sandboxed draft PDF preview pipeline. No publication API."""
import copy
import ctypes
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, quote


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text(node):
    if isinstance(node, list):
        return "".join(map(text, node))
    if not isinstance(node, dict):
        return ""
    tag, value = node.get("t"), node.get("c")
    if tag in ("Str", "MetaString"):
        return value
    if tag in ("Space", "SoftBreak", "LineBreak"):
        return " "
    if tag in ("Code", "CodeBlock", "Math"):
        return value[-1]
    if tag == "Header":
        return text(value[2])
    if tag in ("Link", "Image", "Span"):
        return text(value[1])
    return text(value)


def walk(node):
    if isinstance(node, dict):
        yield node
        yield from walk(node.get("c"))
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def s(value):
    return {"t": "Str", "c": value}


def para(value):
    return {"t": "Para", "c": [s(value)]}


def raw(value):
    return {"t": "RawBlock", "c": ["latex", value]}


def escape(value):
    return "".join({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
                    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
                    "^": r"\textasciicircum{}"}.get(ch, ch) for ch in value)


def anchor(doc_id, identifier):
    return doc_id + "-" + hashlib.sha256(identifier.encode()).hexdigest()[:16]


def normalize(value):
    # Pandoc renders the unchecked ballot-box as the equivalent math square.
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value).replace("\u00ad", "").replace("☐", "□"))


def preflight():
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise RuntimeError("PDF preview requires macOS sandbox-exec; no unsandboxed fallback")
    try:
        import pypdf
    except ImportError as error:
        raise RuntimeError("PDF preview needs pypdf; use a Python environment with publication/requirements-preview.txt installed") from error
    missing = [name for name in ("pandoc", "lualatex", "pdftoppm") if not shutil.which(name)]
    if missing:
        raise RuntimeError("missing PDF tools on PATH: " + ", ".join(missing))


def command(args, cwd, log=None):
    with subprocess.Popen(list(map(str, args)), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as child:
        if log:
            dump(str(log) + ".command.json", {"argv": list(map(str, args)), "pid": child.pid, "started": time.time()})
        output, _ = child.communicate()
        completed = subprocess.CompletedProcess(args, child.returncode, output)
    if log:
        Path(log).write_bytes(completed.stdout)
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {args[0]}; " + completed.stdout.decode(errors="replace")[-2500:])
    return completed.stdout


def verify_sandbox(work, origin):
    if sys.platform != "darwin":
        raise RuntimeError("This preview release requires the tested macOS Seatbelt backend")
    check = ctypes.CDLL("/usr/lib/libsandbox.1.dylib").sandbox_check
    check.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    check.restype = ctypes.c_int
    def access(path):
        return check(os.getpid(), b"file-write-data", 1, ctypes.c_char_p(os.fsencode(path)))
    if access(work) != 0 or access(origin / "README.md") != 1 or access(origin / "dist") != 1:
        raise RuntimeError("worker requires verified write confinement; do not invoke --worker directly")


def tables_to_records(blocks, doc_id, ledger):
    output = []
    table_number = 0
    for block in blocks:
        if block["t"] != "Table":
            output.append(block)
            continue
        table_number += 1
        attr, caption, specs, head, bodies, foot = block["c"]
        rows = [row for body in bodies for row in body[2] + body[3]]
        headings = head[1][0][1] if head[1] else []
        if len(head[1]) > 1 or foot[1] or any(cell[2:4] != [1, 1] for row in head[1] + rows for cell in row[1]):
            raise RuntimeError("unsupported spanning table; requires explicit layout review")
        if len(specs) <= 3:
            # Fixed generous widths; long prose goes into records instead.
            lengths = [max([len(text(row[1][i][4])) for row in rows] + [len(text(headings[i][4]))]) for i in range(len(specs))]
            long_token = any(re.search(r"[A-Za-z0-9_/–—-]{26}", text(cell[4])) for row in rows for cell in row[1])
            if max(lengths, default=0) < 100 and not long_token:
                weights = [max(14, min(n, 55)) for n in lengths]
                block["c"][2] = [[spec[0], {"t": "ColWidth", "c": w / sum(weights)}] for spec, w in zip(specs, weights)]
                output.append(block)
                ledger.append({"table": f"{doc_id}-T{table_number:02}", "layout": "matrix", "row_text": ["".join(text(c[4]) for c in row[1]) for row in rows]})
                continue
        table_id = f"{doc_id}-T{table_number:02}"
        output.append(para(f"表 {table_number} · 字段记录视图（列名与原单元格逐项对应）"))
        if caption[1]:
            output.extend(caption[1])
        if not rows:
            output.append(para("空表模板 · 保留以下全部字段："))
            for cell in headings:
                output.extend(copy.deepcopy(cell[4]))
        mapping = []
        for number, row in enumerate(rows, 1):
            output.append(raw(r"\begin{PreviewRecordBox}{" + escape(f"{table_id} / 记录 {number}") + "}"))
            for column, cell in enumerate(row[1]):
                label = [s(text(headings[column][4]))] if headings else [s(f"字段 {column+1}")]
                output.append({"t": "Para", "c": [{"t": "Strong", "c": label}]})
                output.append(raw(r"\nopagebreak"))
                values = copy.deepcopy(cell[4])
                output.extend(values)
                assert values == cell[4]  # Field identity and full original block structure.
                mapping.append({"row": number, "column": column + 1, "label": text(label), "value": text(cell[4])})
            output.append(raw(r"\end{PreviewRecordBox}"))
        row_text = [table_id + f" / 记录 {n}" + "".join(c["label"] + c["value"] for c in mapping if c["row"] == n) for n in range(1, len(rows) + 1)]
        ledger.append({"table": table_id, "layout": "records", "cells": mapping, "row_text": row_text})
    return output


def compose(documents, selected, combined, source_commit):
    blocks, ledger = [], []
    by_file = {d["path"].name: d for d in documents}
    for doc in selected:
        meta, doc_id = doc["meta"], doc["id"]
        # Clear the preceding page before updating its running identity.
        blocks += [raw(r"\clearpage\PreviewSetIdentity{" + escape(doc_id) + "}{" + escape(meta["version"]) + "}{" + escape(meta["status"]) + "}")]
        body = copy.deepcopy(doc["ast"]["blocks"])
        code_number = 0
        for item in walk(body):
            tag = item.get("t")
            if tag in ("RawBlock", "RawInline"):
                raise RuntimeError("raw source markup needs explicit review")
            if tag == "Header":
                original = item["c"][1][0]
                item["c"][1][0] = doc["anchors"][original]
                item["c"][1][1].append("unnumbered")
            elif tag == "Link":
                target = item["c"][2][0]
                filename, _, fragment = unquote(target).partition("#")
                dest = by_file.get(Path(filename).name) if filename else doc
                if dest:
                    dest_id = dest["anchors"].get(fragment) if fragment else dest["first_anchor"]
                    if not dest_id:
                        raise RuntimeError("missing local reference: " + target)
                    if combined or dest is doc:
                        item["c"][2][0] = "#" + dest_id
                    else:
                        base = dest.get("source_href", f"https://github.com/snkio027/kb/blob/{source_commit}/design/" + quote(dest["path"].name))
                        item["c"][2][0] = base + ("#" + quote(fragment) if fragment else "")
                elif not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                    item["c"][2][0] = f"https://github.com/snkio027/kb/blob/{source_commit}/design/" + quote(filename)
            elif tag == "CodeBlock":
                code_number += 1
                code = item["c"][1]
                width = max((sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in line) for line in code.splitlines()), default=0)
                is_flow = any(ch in code for ch in "│┌┐└┘├┤┬┴┼↓→") or " -> " in code
                # Long schema/text records can wrap; spatial diagrams never do.
                spatial = any(ch in code for ch in "│┌┐└┘├┤┬┴┼") or (is_flow and width <= 94)
                if spatial and width > 94:
                    raise RuntimeError("spatial diagram exceeds readable portrait width")
                item["c"][0][2].append(["preview-flow", str(spatial).lower()])
                item["c"][0][2].append(["preview-code-id", f"{doc_id}-C{code_number:02}"])
        body = tables_to_records(body, doc_id, ledger)
        blocks.extend(body)
    if combined:
        blocks.append(raw(r"\clearpage\PreviewSetIdentity{ESD-HANDBOOK}{preview.1}{DRAFT / COMBINED WORKING VIEW}"))
        blocks.append({"t": "Header", "c": [1, ["generated-requirement-index", ["unnumbered"], []], [s("条款定位索引（生成导航）")]]})
        for doc in selected:
            blocks.append(para(doc["id"] + " · " + doc["meta"]["title"]))
            for header in (x for x in walk(doc["ast"]["blocks"]) if x.get("t") == "Header" and "-REQ-" in text(x)):
                dest = doc["anchors"][header["c"][1][0]]
                blocks.append({"t": "Para", "c": [{"t": "Link", "c": [["", [], []], copy.deepcopy(header["c"][2]), ["#" + dest, ""]]}]})
    return blocks, ledger


def build_view(view, documents, work, inputs, tools, record):
    combined = view == "ESD-HANDBOOK"
    selected = documents if combined else [d for d in documents if d["id"] == view]
    title = "系统设计与工程保证工作手册" if combined else selected[0]["meta"]["title"]
    meta = {"title": title, "subtitle": "六篇完整草案 · 合订工作版" if combined else selected[0]["meta"].get("subtitle", "完整草案阅读版"),
            "document_id": view, "version": "preview.1" if combined else selected[0]["meta"]["version"],
            "status": "DRAFT / COMBINED WORKING VIEW" if combined else selected[0]["meta"]["status"],
            "owner": selected[0]["meta"].get("owner", ""), "source_commit": record["identity"]["source"]["commit"],
            "build_short": record["build_id"][:24]}
    meta["subject"] = f'{view} | v{meta["version"]} | {meta["status"]} | PREVIEW'
    meta["keywords"] = ", ".join(d["id"] + " " + d["meta"]["version"] + " " + d["meta"]["status"] for d in selected)
    meta["composition"] = "\n\n".join(d["id"] + " · v" + d["meta"]["version"] + " · " + d["meta"]["status"] for d in selected)
    blocks, ledger = compose(documents, selected, combined, meta["source_commit"])
    ast = {"pandoc-api-version": selected[0]["ast"]["pandoc-api-version"], "meta": {k: {"t": "MetaString", "c": v} for k, v in meta.items()}, "blocks": blocks}
    folder = work / "typeset" / view
    folder.mkdir(parents=True)
    dump(folder / "composed.json", ast)
    dump(folder / "table-map.json", ledger)
    command([tools["pandoc"], folder / "composed.json", "-f", "json", "-t", "latex", "--standalone", "--top-level-division=chapter",
             "--no-highlight", "--wrap=none", "--template", inputs / "publication/preview.tex", "--lua-filter", inputs / "publication/filters/preview.lua", "-o", folder / "document.tex"], work, folder / "pandoc.log")
    for attempt in range(3):
        command([tools["lualatex"], "--no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-recorder", "document.tex"], folder, folder / f"compile-{attempt}.txt")
    log = (folder / "document.log").read_text(errors="replace")
    fatal = [line for line in log.splitlines() if re.search(r"Missing character|destination with the same identifier|Undefined control sequence|LaTeX Error", line)]
    if fatal:
        raise RuntimeError(view + " typesetting diagnostics: " + "\n".join(fatal[:12]))
    pdf = work / "output/pdf" / (view + "-draft.pdf")
    shutil.copyfile(folder / "document.pdf", pdf)
    from pypdf import PdfReader
    reader = PdfReader(pdf)
    if reader.metadata.title != title or reader.metadata.subject != meta["subject"] or not reader.outline:
        raise RuntimeError(view + " metadata/bookmark failure")
    body_text = []
    page_identity_text = []
    for page in reader.pages:
        furniture = []
        def capture(value, cm, tm, font, size):
            # Exclude only generated running furniture by its physical band.
            y = tm[5] * cm[3] + cm[5]
            if 52 < y < 782:
                body_text.append(value)
            else:
                furniture.append(value)
        complete = page.extract_text(visitor_text=capture)
        page_identity_text.append(normalize(complete if not page_identity_text else "".join(furniture)))
    all_text = "\n".join(body_text)
    (folder / "extracted.txt").write_text(all_text, encoding="utf-8")
    extracted = normalize(all_text)
    ignored_labels = []
    for item in walk(blocks):
        if item.get("t") == "CodeBlock":
            code_id = dict(item["c"][0][2])["preview-code-id"]
            for suffix in (" · 续", " · 原文代码／流程"):
                label = code_id + suffix
                if any(label in text(d["ast"]["blocks"]) for d in selected):
                    raise RuntimeError("generated/source label collision")
                extracted = extracted.replace(normalize(label), "")
                ignored_labels.append(label)
    for table in ledger:
        if table["layout"] == "records":
            for number in range(1, len(table["row_text"]) + 1):
                label = table["table"] + f" / 记录 {number} · 续"
                if any(label in text(d["ast"]["blocks"]) for d in selected):
                    raise RuntimeError("generated/source label collision")
                extracted = extracted.replace(normalize(label), "")
                ignored_labels.append(label)
    missing = []
    for doc in selected:
        for item in walk(doc["ast"]["blocks"]):
            if item.get("t") in ("Header", "Para", "Plain", "CodeBlock"):
                sample = normalize(text(item))
                if sample and sample not in extracted:
                    missing.append({"document": doc["id"], "type": item["t"], "text": text(item)})
    missing_rows = [{"table": table["table"], "row": n} for table in ledger for n, row in enumerate(table["row_text"], 1) if normalize(row) not in extracted]
    # Font embedding and link destination integrity are checked in the artifact, not logs alone.
    names = reader.named_destinations
    for doc in selected:
        if not set(doc["anchors"].values()) <= set(names):
            raise RuntimeError("source heading missing from PDF destinations")
    identity_changes = {0: meta}
    for doc in selected:
        identity_changes[reader.get_destination_page_number(names[doc["first_anchor"]])] = doc["meta"]
    if combined:
        identity_changes[reader.get_destination_page_number(names["generated-requirement-index"])] = meta
    expected = meta
    for number, page_text in enumerate(page_identity_text):
        expected = identity_changes.get(number, expected)
        if any(normalize(expected[k]) not in page_text for k in ("document_id", "version", "status")):
            raise RuntimeError(f"{view} page {number+1}: running identity mismatch")
    links = 0
    for page in reader.pages:
        for ref in page.get("/Annots", []):
            annotation = ref.get_object()
            target = annotation.get("/Dest") or annotation.get("/A", {}).get("/D")
            if isinstance(target, str) and target not in names:
                raise RuntimeError("unresolved PDF destination: " + target)
            links += annotation.get("/Subtype") == "/Link"
        for font_ref in page["/Resources"].get("/Font", {}).values():
            font = font_ref.get_object()
            if "/DescendantFonts" in font:
                font = font["/DescendantFonts"][0].get_object()
            descriptor = font.get("/FontDescriptor")
            if descriptor and not any(k in descriptor.get_object() for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                raise RuntimeError("unembedded font")
    # Render every page at review resolution; key pages can be re-rendered at 144 dpi.
    render = work / "renders" / view
    render.mkdir(parents=True)
    command([tools["pdftoppm"], "-png", "-r", "72", pdf, render / "page"], work, folder / "render.log")
    overfull = re.findall(r"Overfull \\hbox \(([0-9.]+)pt", log)
    audit = {"view": view, "pages": len(reader.pages), "pdf": str(pdf.relative_to(work)), "sha256": sha(pdf), "links": links,
             "named_destinations": len(names), "metadata": meta, "missing_text_blocks": missing,
             "identity_pages_checked": len(page_identity_text),
             "missing_table_row_relations": missing_rows, "table_rows_checked": sum(len(t["row_text"]) for t in ledger),
             "extraction_policy": {"body_band_pt": [52, 782], "normalization": "NFKC + whitespace + soft hyphen removal; unchecked ballot/square equivalence", "ignored_generated_labels": ignored_labels},
             "overfull_hbox_pt": [float(n) for n in overfull], "rendered_pages": len(list(render.glob("page-*.png"))),
             "visual_review": "REQUIRED; automated checks are not visual approval"}
    dump(folder / "audit.json", audit)
    print(f'{view}: {len(reader.pages)} pages, {len(missing)} text blocks requiring review', flush=True)
    return audit


def worker(run, origin):
    work, inputs = run / "work", run / "inputs"
    verify_sandbox(work, origin)
    expected_parent = int(os.environ["PREVIEW_PARENT_PID"])
    def parent_watchdog():
        while True:
            if os.getppid() != expected_parent:
                os.killpg(os.getpgrp(), signal.SIGKILL)
            time.sleep(.25)
    threading.Thread(target=parent_watchdog, daemon=True).start()
    record = json.loads((run / "run.json").read_text())
    for item in record["identity"]["inputs"]:
        if sha(inputs / item["path"]) != item["sha256"]:
            raise RuntimeError("frozen input mismatch")
    for name in ("output/pdf", "output/source", "source-ast", "cache", "tmp", "typeset", "renders"):
        (work / name).mkdir(parents=True, exist_ok=True)
    os.environ.update(TEXMFVAR=str(work / "cache"), TEXMFCACHE=str(work / "cache"),
                      TEXINPUTS=str(inputs / "publication") + "//:", openout_any="p", shell_escape="f")
    # TeX selects its format from argv[0]; resolving lualatex to luahbtex loses it.
    tools = {name: shutil.which(name) for name in ("pandoc", "lualatex", "pdftoppm")}
    if not all(tools.values()):
        raise RuntimeError("pandoc, lualatex and pdftoppm are required")
    tool_identity = {name: {"path": file, "sha256": sha(file), "version": command([file, "-v" if name == "pdftoppm" else "--version"], work).decode(errors="replace").splitlines()[0]} for name, file in tools.items()}
    documents = []
    for source in sorted(inputs.glob("*.md")):
        ast = json.loads(command([tools["pandoc"], source, "-f", "markdown-smart", "-t", "json"], work))
        meta = {key: text(value) for key, value in ast["meta"].items()}
        if "DRAFT" not in meta["status"] or not meta["document_id"]:
            raise RuntimeError("this entry only produces draft previews")
        headers = [node for node in walk(ast["blocks"]) if node.get("t") == "Header"]
        ids = [h["c"][1][0] for h in headers]
        if len(ids) != len(set(ids)):
            raise RuntimeError("duplicate source header anchor")
        doc_id = meta["document_id"]
        if not re.fullmatch(r"[A-Z][A-Z0-9-]+", doc_id) or doc_id == "ESD-HANDBOOK" or not ids:
            raise RuntimeError("invalid/reserved document identity or no source heading")
        anchors = {item: anchor(doc_id, item) for item in ids}
        # Raw Git object lookup is read-only, inside the sandbox, without textconv.
        commit = record["identity"]["source"]["commit"]
        committed = subprocess.run(["git", "--no-pager", "-C", str(origin), "cat-file", "blob", commit + ":design/" + source.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        matches_commit = committed.returncode == 0 and committed.stdout == source.read_bytes()
        source_href = f"https://github.com/snkio027/kb/blob/{commit}/design/" + quote(source.name) if matches_commit else "../source/" + quote(source.name)
        shutil.copyfile(source, work / "output/source" / source.name)
        dump(work / "source-ast" / (doc_id + ".json"), ast)
        documents.append({"path": source, "ast": ast, "meta": meta, "id": doc_id, "anchors": anchors, "first_anchor": anchors[ids[0]], "source_href": source_href, "source_matches_commit": matches_commit})
    if len({d["id"] for d in documents}) != len(documents):
        raise RuntimeError("duplicate document ID")
    views = [d["id"] for d in documents] + ["ESD-HANDBOOK"]
    dump(work / "source-catalog.json", [{"path": d["path"].name, "metadata": d["meta"], "anchors": d["anchors"], "source_href": d["source_href"], "source_matches_commit": d["source_matches_commit"]} for d in documents])
    with ThreadPoolExecutor(max_workers=2) as pool:
        audits = list(pool.map(lambda view: build_view(view, documents, work, inputs, tools, record), views))
    dependencies = {}
    for fls in (work / "typeset").glob("*/document.fls"):
        for line in fls.read_text(errors="replace").splitlines():
            if line.startswith("INPUT "):
                file = Path(line[6:])
                if file.is_absolute() and file.is_file() and not file.is_relative_to(run):
                    dependencies[str(file)] = sha(file)
    import pypdf
    package_root = Path(pypdf.__file__).parent
    python_library = {"version": pypdf.__version__, "files": {str(p.relative_to(package_root)): sha(p) for p in sorted(package_root.rglob("*.py"))}}
    if any(sha(file) != tool_identity[name]["sha256"] for name, file in tools.items()):
        raise RuntimeError("tool executable changed during preview")
    execution_identity = {"preparation_id": record["build_id"], "tools": tool_identity, "pypdf": python_library, "tex_input_sha256": dependencies}
    execution_id = hashlib.sha256(json.dumps(execution_identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    report = {"status": "BUILT_FOR_REVIEW", "source_build_id": record["build_id"], "views": audits,
              "execution_id": execution_id, "execution_identity": execution_identity,
              "official_release": False, "pdf_ua_claim": None}
    dump(work / "preview-audit.json", report)
    if any(a["missing_text_blocks"] or a["missing_table_row_relations"] or a["rendered_pages"] != a["pages"] or any(w > 2 for w in a["overfull_hbox_pt"]) for a in audits):
        raise RuntimeError("review blockers: inspect work/preview-audit.json before accepting this run")
    index = "# ESD 草案阅读预览\n\nPREVIEW / DRAFT，不是发布批准。请优先使用合订版进行跨篇阅读。\n\n"
    for a in audits:
        index += f'- [{a["metadata"]["title"]}](pdf/{Path(a["pdf"]).name}) — {a["pages"]} 页\n'
    index += "\n独立版的跨篇源链接：源字节与 commit 相同时使用固定 Git 链接，否则指向随附 source/ 快照，请保留完整 output 目录。\n\n"
    index += f'准备标识：`{record["build_id"]}`\n\n实际执行身份：`{execution_id}`\n\n检查记录在 `../preview-audit.json`；页面渲染在 `../renders/`。\n'
    (work / "output/README.md").write_text(index, encoding="utf-8")


def run_preview(prepared, origin, pub):
    run = Path(prepared["path"])
    with pub.root_handle(run) as fd:
        with pub.directory(fd, "work", create=True):
            pass
        work = run / "work"
        # Only work is writable; frozen inputs, attempt terminal records and dist are not.
        profile = '(version 1)(allow default)(deny network*)(deny file-write* (require-all (require-not (subpath ' + json.dumps(str(work)) + ')) (require-not (literal "/dev/null"))))'
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "TEX", "LUA", "XCRUN_", "PYTHON"))}
        env.update(TMPDIR=str(work), XDG_CACHE_HOME=str(work / "cache"), PYTHONDONTWRITEBYTECODE="1", PREVIEW_PARENT_PID=str(os.getpid()))
        argv = ["/usr/bin/sandbox-exec", "-p", profile, sys.executable, "-B", str(run / "inputs/scripts/preview.py"), "--worker", str(run), str(origin)]
        terminal = pub.ResultCommit(fd, "preview-result.json")
        child = None
        try:
            with (work / "worker.log").open("xb") as log:
                child = subprocess.Popen(argv, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                code = child.wait()
            if code:
                raise RuntimeError(f"preview worker exited {code}; see {work / 'worker.log'}")
            report = json.loads((work / "preview-audit.json").read_text())
            for artifact in report["views"]:
                if sha(work / artifact["pdf"]) != artifact["sha256"]:
                    raise RuntimeError("output digest changed before completion")
            terminal.commit({"schema_version": 1, "commit_protocol": pub.POLICY["result_commit_policy"], "status": "PREVIEW_READY", "execution_id": report["execution_id"], "audit_sha256": sha(work / "preview-audit.json"), "meaning": "Draft reading artifacts; not formal publication or visual approval",
                             "checks": "See work/preview-audit.json", "artifacts": {a["pdf"]: a["sha256"] for a in report["views"]}})
            return {"status": "PREVIEW_READY", "path": str(work / "output/pdf"), "audit": str(work / "preview-audit.json")}
        except BaseException as error:
            if terminal.is_committed():
                return {"status": "PREVIEW_READY", "path": str(work / "output/pdf"), "notice": "committed result retained"}
            try:
                pub.ResultCommit(fd, "preview-result.json").commit({"status": "CANCELLED" if isinstance(error, (pub.Cancelled, KeyboardInterrupt)) else "FAILED", "diagnostic": str(error)})
            except (OSError, pub.Cancelled, KeyboardInterrupt):
                pass
            raise
        finally:
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--worker":
        raise SystemExit("Use pub.py preview; this is an internal sandboxed worker")
    worker(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
