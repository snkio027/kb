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
sys.path.insert(0, str(HERE))
import preview
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
        docs = []
        for i in range(2):
            ast = self.parse("# Same\n\n[other](01-test.md#same)\n")
            identity = f"TEST-{i}"
            docs.append({"path": Path(f"{i:02}-test.md"), "ast": ast, "id": identity,
                         "meta": {"version": "1", "status": "DRAFT", "title": "Same"},
                         "anchors": {"same": preview.anchor(identity, "same")}, "first_anchor": preview.anchor(identity, "same")})
        blocks, _ = preview.compose(docs, docs, True, "a" * 40)
        headers = [x["c"][1][0] for x in preview.walk(blocks) if x["t"] == "Header"]
        self.assertEqual(len(headers), len(set(headers)))
        targets = [x["c"][2][0] for x in preview.walk(blocks) if x["t"] == "Link"]
        self.assertTrue(all(t == "#" + docs[1]["first_anchor"] for t in targets))
        docs[1]["anchors"].clear()
        with self.assertRaisesRegex(RuntimeError, "missing local reference"):
            preview.compose(docs, docs, True, "a" * 40)

    def test_preview_terminal_fsync_failure_leaves_no_success(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder, pub.root_handle(Path(folder)) as fd:
            with mock.patch.object(pub.os, "fsync", side_effect=OSError("injected EIO")), self.assertRaises(OSError):
                pub.ResultCommit(fd, "preview-result.json").commit({"status": "PREVIEW_READY"})
            self.assertFalse((Path(folder) / "preview-result.json").exists())
            pub.ResultCommit(fd, "preview-result.json").commit({"status": "FAILED"})
            self.assertEqual(json.loads((Path(folder) / "preview-result.json").read_text())["status"], "FAILED")


class RealPreviewTests(unittest.TestCase):
    git = base.IsolationTests.git
    cli = base.IsolationTests.cli
    tearDown = base.IsolationTests.tearDown

    def setUp(self):
        base.IsolationTests.setUp(self)
        shutil.copytree(HERE.parent / "publication", self.root / "publication", dirs_exist_ok=True)
        for number in range(6):
            other = (number + 1) % 6
            (self.root / f"{number:02}-fixture.md").write_text(
                f'---\ndocument_id: "TEST-{number}"\nversion: "0.1.0"\ntitle: "测试文档 {number}"\nstatus: "DRAFT"\n---\n'
                f'# 测试文档 {number}\n\n## 1. 原文条件\n\n必须保留 `R0–R3` 与 `R2 — Core`。\n\n'
                f'[另一篇]({other:02}-fixture.md)\n\n'
                '| ID | 条件 | 判断 | 证据 |\n|---|---|---|---|\n|A|未知不得视为通过|UNKNOWN|保留原件|\n\n'
                '```yaml\nvalue: "' + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ|' * 5 + '"\n```\n', encoding="utf-8")
        self.template = self.root / "publication/preview.tex"
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
        child = subprocess.Popen([sys.executable, "-B", str(self.root / "scripts/pub.py"), "preview"],
                                 cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.children.append(child)
        return child

    def run_path(self):
        return next((self.root / "build/preview").glob("*/*"))

    def test_real_success_and_compiler_cannot_write_dist(self):
        target = str((self.dist / "history.bin").resolve())
        self.inject(r'\directlua{local f=io.open("' + target + r'","wb"); if f then f:write("BAD"); f:close(); error("sandbox failed") else texio.write_nl("SANDBOX_WRITE_DENIED") end}')
        child = self.start()
        out, err = child.communicate(timeout=240)
        self.assertEqual(child.returncode, 0, err + "\n" + (self.run_path() / "work/worker.log").read_text())
        self.assertEqual(json.loads(out)["status"], "PREVIEW_READY")
        report = json.loads((self.run_path() / "work/preview-audit.json").read_text())
        self.assertEqual(len(report["views"]), 7)
        self.assertTrue(all(not view["missing_text_blocks"] for view in report["views"]))
        log = self.run_path() / "work/typeset/TEST-0/document.log"
        self.assertIn("SANDBOX_WRITE_DENIED", log.read_text())

    def test_real_compile_failure_never_commits_ready(self):
        self.inject(r"\ThisCommandIntentionallyDoesNotExist")
        child = self.start()
        child.communicate(timeout=150)
        self.assertNotEqual(child.returncode, 0)
        self.assertEqual(json.loads((self.run_path() / "preview-result.json").read_text())["status"], "FAILED")
        self.assertTrue(list(self.run_path().glob("work/typeset/*/compile-0.txt.command.json")))

    def test_real_compiler_int_term_and_kill(self):
        self.inject(r"\loop\iftrue\repeat")
        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            with self.subTest(signal=signum):
                before = set((self.root / "build/preview").glob("*/*"))
                child = self.start()
                deadline = time.monotonic() + 90
                commands = []
                while time.monotonic() < deadline:
                    self.assertIsNone(child.poll(), "controller unexpectedly exited")
                    runs = set((self.root / "build/preview").glob("*/*")) - before
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
