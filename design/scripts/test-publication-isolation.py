#!/usr/bin/env python3
"""B1-A tests use disposable Git/text fixtures, never a real PDF toolchain."""
import hashlib
import importlib.util
import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("pub", SCRIPTS / "pub.py")
pub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pub)
LEGACY = ("build.sh", "preflight.sh", "render-verify.sh", "compare-renders.sh",
          "write-manifest.py", "render-pdfium.py")


def tree_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kb-b1a-test-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.root = self.repo / "design"
        self.root.mkdir()
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / ".gitignore").write_text("/build/\n/tmp/\n__pycache__/\n")
        for number in range(6):
            (self.root / f"{number:02d}-fixture.md").write_text(f"# Draft {number}\n\n不得发布。\n")
        (self.root / "publication" / "profiles").mkdir(parents=True)
        (self.root / "publication" / "template.tex").write_text("fixture, not TeX\n")
        (self.root / "publication" / "profiles" / "release.yaml").write_text("status: draft\n")
        for name in pub.LOCKS:
            (self.root / name).write_text("fixture dependency declaration\n")
        self.dist = self.root / "dist"
        self.dist.mkdir()
        (self.dist / "history.bin").write_bytes(b"historical artifact sentinel\x00")
        (self.dist / "build-manifest.json").write_text('{"historical": true}\n')
        (self.dist / "sha256sums.txt").write_text("historical checksum sentinel\n")
        self.dist_before = tree_bytes(self.dist)
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=B1-A Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                 "commit", "-qm", "fixture")

    def tearDown(self):
        self.assertEqual(tree_bytes(self.dist), self.dist_before, "historical dist changed")

    def git(self, *args):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.PIPE, env=env)

    def cli(self, *args, env=None):
        return subprocess.run([sys.executable, "-B", str(self.root / "scripts" / "pub.py"), *args],
                              cwd=self.repo, capture_output=True, text=True, env=env)

    def prepared(self):
        result = pub.prepare(self.root)
        path = Path(result["path"])
        run = json.loads((path / "run.json").read_text())
        self.assertEqual(result["build_id"], pub.digest(pub.canonical(run["identity"])))
        self.assertEqual(json.loads((path / "result.json").read_text())["status"], "PREPARED")
        for item in run["identity"]["inputs"]:
            data = (path / "inputs" / item["path"]).read_bytes()
            self.assertEqual(item["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(item["bytes"], len(data))
        self.assertFalse(list(path.rglob("*.pdf")))
        return result, run

    def test_success_records_exact_snapshot_and_not_run_checks(self):
        result, run = self.prepared()
        self.assertFalse(run["identity"]["source"]["dirty"])
        self.assertEqual(run["channel"], "PREVIEW")
        checks = json.loads((Path(result["path"]) / "result.json").read_text())["checks"]
        self.assertEqual(set(checks.values()), {"NOT_RUN"})

    def test_cli_success_from_another_working_directory(self):
        completed = self.cli("preview", "--prepare-only")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "PREPARED")

    def test_repeated_inputs_get_separate_attempts(self):
        first, _ = self.prepared()
        old = tree_bytes(Path(first["path"]))
        second, _ = self.prepared()
        self.assertEqual(first["build_id"], second["build_id"])
        self.assertNotEqual(first["path"], second["path"])
        self.assertEqual(tree_bytes(Path(first["path"])), old)

    def test_same_commit_input_changes_change_identity(self):
        previous, _ = self.prepared()
        commit = self.git("rev-parse", "HEAD")
        for name in ("00-fixture.md", "publication/template.tex", "fonts.lock", "scripts/build.sh"):
            with self.subTest(name=name):
                path = self.root / name
                path.write_bytes(path.read_bytes() + b"changed\n")
                current, run = self.prepared()
                self.assertNotEqual(current["build_id"], previous["build_id"])
                self.assertTrue(run["identity"]["source"]["dirty"])
                self.assertEqual(self.git("rev-parse", "HEAD"), commit)
                previous = current

    def test_runtime_identity_is_part_of_build_id(self):
        first, _ = self.prepared()
        runtime = pub.runtime_identity()
        runtime["python"]["sha256"] = "test-only-different-runtime"
        with mock.patch.object(pub, "runtime_identity", return_value=runtime):
            second, _ = self.prepared()
        self.assertNotEqual(first["build_id"], second["build_id"])

    def test_source_commit_not_only_identity(self):
        source = {"commit": "same", "dirty": True}
        first = pub.identity({"source": b"one"}, source, {})
        second = pub.identity({"source": b"two"}, source, {})
        self.assertNotEqual(pub.digest(pub.canonical(first)), pub.digest(pub.canonical(second)))

    def test_missing_required_input_fails_before_output(self):
        for name in ("00-fixture.md", "fonts.lock", "publication/template.tex"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.unlink()
                self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
                self.assertFalse((self.root / "build").exists())
                path.write_bytes(original)

    def test_duplicate_numbered_source_rejected(self):
        (self.root / "00-duplicate.md").write_text("duplicate")
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
        self.assertFalse((self.root / "build").exists())

    def test_symlink_inputs_and_directories_rejected(self):
        for name in ("00-fixture.md", "publication/template.tex", "fonts.lock", "scripts/build.sh"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.unlink()
                path.symlink_to(self.dist / "history.bin")
                self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
                path.unlink()
                path.write_bytes(original)
        (self.root / "publication" / "linked-directory").symlink_to(self.dist, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
        self.assertFalse((self.root / "build").exists())

    def test_fifo_input_rejected_without_blocking(self):
        path = self.root / "fonts.lock"
        path.unlink()
        os.mkfifo(path)
        completed = subprocess.run([sys.executable, "-B", str(self.root / "scripts/pub.py"),
                                    "preview", "--prepare-only"], capture_output=True, timeout=5)
        self.assertNotEqual(completed.returncode, 0)

    def test_build_symlink_to_dist_rejected(self):
        (self.root / "build").symlink_to(self.dist, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)

    def test_preview_symlink_to_dist_rejected(self):
        (self.root / "build").mkdir()
        (self.root / "build/preview").symlink_to(self.dist, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)

    def test_build_id_symlink_rejected(self):
        with pub.root_handle(self.root) as fd:
            value = pub.identity(pub.input_snapshot(fd), pub.git_context(self.root), pub.runtime_identity())
        build_id = pub.digest(pub.canonical(value))
        (self.root / "build/preview").mkdir(parents=True)
        (self.root / "build/preview" / build_id).symlink_to(self.dist, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)

    def test_file_in_place_of_output_directory_rejected(self):
        (self.root / "build").write_bytes(b"do not replace")
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
        self.assertEqual((self.root / "build").read_bytes(), b"do not replace")

    def test_external_output_symlink_target_unchanged(self):
        external = self.repo / "outside-output"
        external.mkdir()
        (external / "sentinel").write_bytes(b"keep")
        (self.root / "build").symlink_to(external, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
        self.assertEqual(tree_bytes(external), {"sentinel": b"keep"})

    def test_path_escape_and_existing_file_never_written(self):
        with pub.root_handle(self.root) as fd:
            for path in ("../outside", "/absolute", "../dist/new"):
                with self.subTest(path=path), self.assertRaises(pub.PreparationError):
                    pub.write_bytes(fd, path, b"bad")
            with self.assertRaises(FileExistsError):
                pub.write_bytes(fd, "dist/history.bin", b"bad")

    def test_input_drift_fails_without_prepared_result(self):
        original = pub.write_bytes

        def drift(fd, name, data):
            original(fd, name, data)
            if name == "run.json":
                (self.root / "01-fixture.md").write_text("changed while copying")

        with mock.patch.object(pub, "write_bytes", side_effect=drift), self.assertRaises(pub.PreparationError):
            pub.prepare(self.root)
        results = list((self.root / "build").rglob("result.json"))
        self.assertEqual(len(results), 1)
        self.assertEqual(json.loads(results[0].read_text())["status"], "FAILED")

    def test_write_failure_reports_failed(self):
        original = pub.write_bytes

        def fail(fd, name, data):
            if name.startswith("inputs/"):
                raise OSError("injected write failure")
            original(fd, name, data)

        with mock.patch.object(pub, "write_bytes", side_effect=fail), self.assertRaises(OSError):
            pub.prepare(self.root)
        result = next((self.root / "build").rglob("result.json"))
        self.assertEqual(json.loads(result.read_text())["status"], "FAILED")

    def test_no_result_when_diagnostics_also_fail(self):
        original = pub.write_bytes

        def fail(fd, name, data):
            if name != "run.json":
                raise OSError("injected full output device")
            original(fd, name, data)

        with mock.patch.object(pub, "write_bytes", side_effect=fail), self.assertRaises(OSError):
            pub.prepare(self.root)
        self.assertEqual(list((self.root / "build").rglob("result.json")), [])

    def test_closed_operations_and_redirects_do_not_write(self):
        cases = [[name] for name in ("preview", "build", "check", "render", "candidate", "publish")]
        cases += [["publish", "--prepare-only"], ["preview", "--prepare-only", "--output", str(self.dist)],
                  ["preview", "--prepare-only", "--root", str(self.dist)]]
        for args in cases:
            with self.subTest(args=args):
                completed = self.cli(*args)
                self.assertEqual(completed.returncode, 2)
                self.assertFalse((self.root / "build").exists())

    def test_environment_does_not_redirect_outputs(self):
        env = dict(os.environ, TMPDIR=str(self.dist), PUB_OUTPUT=str(self.dist),
                   BUILD_DIR=str(self.dist), DIST_DIR=str(self.dist))
        completed = self.cli("preview", "--prepare-only", env=env)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["path"].startswith(str(self.root.resolve() / "build/preview") + "/"))

    def test_all_legacy_entry_points_reject_before_tool_invocation(self):
        env = dict(os.environ, TMPDIR=str(self.dist), PYTHON_BIN="/nonexistent", PATH="/nonexistent")
        before = tree_bytes(self.root)
        for name in LEGACY:
            for args in ([], [str(self.dist / "history.bin"), str(self.dist), "180"]):
                with self.subTest(name=name, args=args):
                    tool = "/bin/bash" if name.endswith(".sh") else sys.executable
                    completed = subprocess.run([tool, str(self.root / "scripts" / name), *args],
                                               cwd=self.repo, env=env, capture_output=True, text=True)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn("DISABLED", completed.stderr)
        self.assertEqual(tree_bytes(self.root), before)

    def check_signal(self, signum):
        # Pause after run.json via a test-only wrapper, then deliver a real OS signal.
        script = '''
import importlib.util, signal, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("fixture_pub", sys.argv[1])
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
original = p.write_bytes
def pause(fd, name, data):
    original(fd, name, data)
    if name == "run.json":
        print("READY", flush=True)
        signal.pause()
p.write_bytes = pause
raise SystemExit(p.main(["preview", "--prepare-only"]))
'''
        child = subprocess.Popen([sys.executable, "-B", "-c", script, str(self.root / "scripts/pub.py")],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([child.stdout], [], [], 10)
            self.assertTrue(ready, "child did not reach the preparation checkpoint")
            self.assertEqual(child.stdout.readline().strip(), "READY")
            child.send_signal(signum)
            _, stderr = child.communicate(timeout=10)
            expected = -signal.SIGKILL if signum == signal.SIGKILL else 128 + signum
            self.assertEqual(child.returncode, expected, stderr)
            records = list((self.root / "build").rglob("result.json"))
            if signum == signal.SIGKILL:
                self.assertEqual(records, [])
            else:
                self.assertEqual(len(records), 1)
                self.assertEqual(json.loads(records[0].read_text())["status"], "CANCELLED")
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate()

    def test_sigint_is_cancelled(self):
        self.check_signal(signal.SIGINT)

    def test_sigterm_is_cancelled(self):
        self.check_signal(signal.SIGTERM)

    def test_sigkill_has_no_success_result(self):
        self.check_signal(signal.SIGKILL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
