#!/usr/bin/env python3
"""Real-engine preview regressions; disposable repositories, never historical PDFs."""
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "engine"))
import preview
import preview_audit
import candidate
import pub

spec = importlib.util.spec_from_file_location("isolation", HERE / "test-publication-isolation.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class CompositionTests(unittest.TestCase):
    def parse(self, source):
        return json.loads(subprocess.check_output(["pandoc", "-f", "markdown-smart", "-t", "json"], input=source.encode()))

    def test_table_fields_values_and_empty_headers_preserved(self):
        for source in ("|A|B|C|D|\n|-|-|-|-|\n|a|b|c|d|\n|e|f|g|h|\n", "|A|B|C|D|\n|-|-|-|-|\n"):
            ast = self.parse(source)
            ledger = []
            converted = preview.tables_to_records(ast["blocks"], "TEST", ledger)
            for node in preview.walk(ast["blocks"]):
                if node["t"] in ("Plain", "Para"):
                    self.assertIn(preview.text(node), preview.text(converted))
            if ledger[0]["cells"]:
                self.assertEqual([(c["row"], c["column"], c["label"], c["value"]) for c in ledger[0]["cells"]],
                                 [(r, c, label, value) for r, values in enumerate(("abcd", "efgh"), 1)
                                  for c, (label, value) in enumerate(zip("ABCD", values), 1)])

    def test_duplicate_titles_are_namespaced_and_broken_references_fail(self):
        from links import Resolver
        docs = []
        for i in range(2):
            ast = self.parse("# Same\n\n[other](01-test.md#same)\n")
            identity = f"TEST-{i}"
            docs.append({"path": Path(f"{i:02}-test.md"), "relative_path": f"{i:02}-test.md",
                         "ast": ast, "id": identity, "aliases": {},
                         "meta": {"version": "1", "status": "DRAFT", "title": "Same"},
                         "anchors": {"same": preview.anchor(identity, "same")}, "first_anchor": preview.anchor(identity, "same")})
        resolver = Resolver(docs, docs, "https://example.org/repo", None, {}, pub, preview.command, None, preview.walk)
        blocks, _ = preview.compose(docs, docs, {}, {}, resolver)
        headers = [x["c"][1][0] for x in preview.walk(blocks) if x["t"] == "Header"]
        self.assertEqual(len(headers), len(set(headers)))
        targets = [x["c"][2][0] for x in preview.walk(blocks) if x["t"] == "Link"]
        self.assertTrue(all(t == "#" + docs[1]["first_anchor"] for t in targets))
        docs[1]["anchors"].clear()
        with self.assertRaisesRegex(RuntimeError, "unresolved source anchor"):
            preview.compose(docs, docs, {}, {}, resolver)

    def test_preview_terminal_fsync_failure_leaves_no_success(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder, pub.root_handle(Path(folder)) as fd:
            with mock.patch.object(pub.os, "fsync", side_effect=OSError("injected EIO")), self.assertRaises(OSError):
                pub.ResultCommit(fd, "preview-result.json").commit({"status": "PREVIEW_READY"})
            self.assertFalse((Path(folder) / "preview-result.json").exists())
            pub.ResultCommit(fd, "preview-result.json").commit({"status": "FAILED"})
            self.assertEqual(json.loads((Path(folder) / "preview-result.json").read_text())["status"], "FAILED")

    def test_occurrence_scope_order_and_negative_word_regressions(self):
        for expected, actual in ((["不得忽略", "不得忽略"], "不得忽略"),
                                 (["第一条件", "第二条件"], "第二条件 第一条件"),
                                 (["不得发布"], "可以发布")):
            self.assertTrue(preview_audit.ordered_match(expected, actual, preview.normalize)[1])
        for section, actual in ((["A 的条件"], "B 的条件"), (["B 的条件"], "A 的条件")):
            self.assertTrue(preview_audit.ordered_match(section, actual, preview.normalize)[1])
        self.assertFalse(preview_audit.ordered_match(["相同", "相同"], "相同 相同", preview.normalize)[1])

    def test_inline_literals_cannot_lose_spaces(self):
        import re
        for literal in ('System Owner', 'cmd --flag "a b"', 'x  y', 'at-least-once delivery'):
            self.assertIsNotNone(re.search(preview_audit.literal_pattern(literal), literal))
            self.assertIsNone(re.search(preview_audit.literal_pattern(literal), literal.replace(' ', '')))
        self.assertIsNotNone(re.search(preview_audit.literal_pattern('CONDITIONALLY_CONFORMANT'), 'CONDITIONALLY_\nCONFORMANT'))

    def test_uri_classification_full_path_and_fragment(self):
        from links import Resolver
        doc = {"id": "TEST", "relative_path": "nested/01-core.md", "aliases": {},
               "anchors": {"s": "anchor-s"}, "first_anchor": "anchor-s"}
        resolver = Resolver([doc], [doc], "https://example.org/repo", None, {}, pub, preview.command, None, preview.walk)
        for url in ("https://example.org/history/01-core.md#s", "//example.org/01-core.md#s", "/archive/01-core.md#s", "01-core.md?version=old#s"):
            self.assertEqual(resolver.resolve(url, doc), url)
        self.assertEqual(resolver.resolve("./01-core.md#s", doc), "#anchor-s")
        with self.assertRaises(RuntimeError):
            resolver.resolve("../../outside.md", doc)

    def test_explicit_matrix_binding_and_drift(self):
        ast = self.parse('# 比较\n\n|A|B|C|D|\n|-|-|-|-|\n|a|b|c|d|\n')
        policy = {"document": "TEST", "section": "比较", "headers": list('ABCD'), "layout": "matrix"}
        ledger = []
        result = preview.tables_to_records(ast['blocks'], 'TEST', ledger, [policy])
        self.assertEqual(result[-1]['t'], 'Table')
        self.assertEqual(ledger[0]['selection'], 'explicit')
        policy['headers'] = list('ABCE')
        with self.assertRaisesRegex(RuntimeError, 'drifted'):
            preview.tables_to_records(ast['blocks'], 'TEST', [], [policy])


class RealPreviewTests(unittest.TestCase):
    git = base.IsolationTests.git
    cli = base.IsolationTests.cli
    tearDown = base.IsolationTests.tearDown

    def setUp(self):
        base.IsolationTests.setUp(self)
        for number in range(6):
            other = (number + 1) % 6
            (self.root / f"{number:02}-fixture.md").write_text(
                f'---\ndocument_id: "TEST-{number}"\nversion: "0.1.0"\ntitle: "测试文档 {number}"\nstatus: "DRAFT"\n---\n'
                f'# 测试文档 {number}\n\n# 1. 原文条件\n\n## TEST-REQ-001 条款\n\n必须保留 `R0–R3` 与 `R2 — Core`。\n\n'
                '`System Owner`、`cmd --flag "a b"`、`x  y`、`CONDITIONALLY_CONFORMANT`。\n\n'
                f'[另一篇]({other:02}-fixture.md)\n\n'
                '| ID | 条件 | 判断 | 证据 |\n|---|---|---|---|\n|A|未知不得视为通过|UNKNOWN|保留原件|\n\n'
                '```yaml\nvalue: "' + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ|' * 5 + '"\n```\n', encoding="utf-8")
        self.template = self.root / "publication/profiles/fixture/template.tex"
        self.children = []
        self.addCleanup(self.stop_children)

    def stop_children(self):
        for child in self.children:
            if child.poll() is None:
                child.terminate()
                try:
                    child.communicate(timeout=8)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.communicate()

    def inject(self, tex):
        self.template.write_text(self.template.read_text().replace(r"\begin{document}", r"\begin{document}" + "\n" + tex))

    def start(self):
        child = subprocess.Popen([sys.executable, "-B", str(self.root / "publication/engine/pub.py"), "preview", "--profile", "fixture"],
                                 cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.children.append(child)
        return child

    def run_path(self):
        return next((self.root / "publication/build/preview").glob("*/*"))

    def test_real_success_and_compiler_cannot_write_dist(self):
        target = str((self.dist / "history.bin").resolve())
        self.inject(r'\directlua{local f=io.open("' + target + r'","wb"); if f then f:write("BAD"); f:close(); error("sandbox failed") else texio.write_nl("SANDBOX_WRITE_DENIED") end}')
        child = self.start()
        out, err = child.communicate(timeout=240)
        audits = list(self.run_path().glob('work/typeset/*/section-audit.json'))
        details = [{k: v for k, v in json.loads(a.read_text()).items() if k.endswith('errors') or k == 'orphan_headings'} for a in audits]
        self.assertEqual(child.returncode, 0, err + "\n" + (self.run_path() / "work/worker.log").read_text() + '\n' + json.dumps(details, ensure_ascii=False))
        self.assertEqual(json.loads(out)["status"], "PREVIEW_READY")
        report = json.loads((self.run_path() / "work/preview-audit.json").read_text())
        self.assertEqual(len(report["views"]), 7)
        self.assertTrue(all(not view["missing_text_blocks"] for view in report["views"]))
        self.assertTrue(all(view['preface_page'] == 2 for view in report['views']))
        from pypdf import PdfReader
        pdf = PdfReader(self.run_path() / 'work/output/pdf/TEST-0-draft.pdf')
        all_text = '\n'.join(p.extract_text() for p in pdf.pages)
        for literal in ('System Owner', 'cmd --flag "a b"', 'x  y', 'CONDITIONALLY_CONFORMANT'):
            self.assertRegex(all_text, preview_audit.literal_pattern(literal))
        combined = PdfReader(self.run_path() / 'work/output/pdf/ESD-HANDBOOK-draft.pdf')
        self.assertEqual(len([entry for entry in combined.outline if isinstance(entry, dict)]), 8)
        self.assertIn('TEST-REQ-001', combined.pages[-1].extract_text())
        # Freeze precisely these successful bytes, with no compiler on this path.
        relative = str(self.run_path().relative_to(self.root))
        with mock.patch.object(preview, 'command', side_effect=AssertionError('candidate must not compile')):
            frozen = candidate.freeze(self.root, relative, pub, "fixture")
        target = Path(frozen['path'])
        self.assertEqual(frozen['status'], 'CANDIDATE_PREPARED_FOR_REVIEW')
        manifest = json.loads((target / 'candidate-manifest.json').read_text())
        self.assertFalse(manifest['formal_release'])
        for entry in manifest['identity']['files']:
            self.assertEqual(pub.digest((target / entry['path']).read_bytes()), entry['sha256'])
        old = base.tree_bytes(target)
        # Mutating the old preview must never silently refresh a frozen candidate.
        pdf_path = self.run_path() / 'work/output/pdf/TEST-0-draft.pdf'
        pdf_path.write_bytes(pdf_path.read_bytes() + b'changed')
        with self.assertRaisesRegex(pub.PreparationError, 'digest changed'):
            candidate.freeze(self.root, relative, pub, "fixture")
        self.assertEqual(old, base.tree_bytes(target))
        log = self.run_path() / "work/typeset/TEST-0/document.log"
        self.assertIn("SANDBOX_WRITE_DENIED", log.read_text())

    def test_real_compile_failure_never_commits_ready(self):
        self.inject(r"\ThisCommandIntentionallyDoesNotExist")
        child = self.start()
        child.communicate(timeout=150)
        self.assertNotEqual(child.returncode, 0)
        self.assertEqual(json.loads((self.run_path() / "preview-result.json").read_text())["status"], "FAILED")
        self.assertTrue(list(self.run_path().glob("work/typeset/*/compile-0.txt.command.json")))

    def test_real_pdf_missing_literal_spaces_is_rejected(self):
        self.inject(r'\renewcommand{\PreviewCodeSpace}{}')
        child = self.start()
        child.communicate(timeout=240)
        self.assertNotEqual(child.returncode, 0)
        report = json.loads((self.run_path() / 'work/preview-audit.json').read_text())
        self.assertTrue(all(view['inline_literal_errors'] for view in report['views']))
        self.assertEqual(json.loads((self.run_path() / 'preview-result.json').read_text())['status'], 'FAILED')

    def test_real_pdf_preface_target_on_cover_is_rejected(self):
        original = self.template.read_text()
        original = original.replace(r'\begin{document}', r'\begin{document}\hypertarget{generated-preface}{}')
        original = original.replace('{part}{generated-preface}{阅读与版本说明}', '{part}{wrong-preface}{阅读与版本说明}')
        self.template.write_text(original)
        child = self.start()
        child.communicate(timeout=240)
        self.assertNotEqual(child.returncode, 0)
        report = json.loads((self.run_path() / 'work/preview-audit.json').read_text())
        self.assertTrue(all(any(e['anchor'] == 'generated-preface' for e in view['section_errors']) for view in report['views']))

    def test_real_compiler_int_term_and_kill(self):
        self.inject(r"\loop\iftrue\repeat")
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            with self.subTest(signal=signum):
                before = set((self.root / "publication/build/preview").glob("*/*"))
                child = self.start()
                deadline = time.monotonic() + 90
                commands = []
                while time.monotonic() < deadline:
                    self.assertIsNone(child.poll(), "controller unexpectedly exited")
                    runs = set((self.root / "publication/build/preview").glob("*/*")) - before
                    if runs:
                        run = runs.pop()
                        commands = list(run.glob("work/typeset/*/compile-0.txt.command.json"))
                        if commands:
                            break
                    time.sleep(.1)
                self.assertTrue(commands, "real compiler did not start")
                pids = [json.loads(p.read_text())["pid"] for p in commands]
                child.send_signal(signum)
                child.communicate(timeout=12)
                self.assertNotEqual(child.returncode, 0)
                # Both parent-side process-group cleanup and worker parent-death watchdog.
                for pid in pids:
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        try:
                            os.kill(pid, 0)
                        except ProcessLookupError:
                            break
                        time.sleep(.1)
                    else:
                        self.fail(f"orphan compiler still alive: {pid}")
                terminal = run / "preview-result.json"
                if signum == signal.SIGKILL:
                    self.assertFalse(terminal.exists())
                else:
                    self.assertEqual(json.loads(terminal.read_text())["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
