#!/usr/bin/env python3
"""B1-A tests use disposable Git/text fixtures, never a real PDF toolchain."""
import hashlib
import importlib.util
import errno
import io
import json
import os
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(SCRIPTS))
import pub
LEGACY = ("build.sh", "preflight.sh", "render-verify.sh", "compare-renders.sh",
          "write-manifest.py", "render-pdfium.py")


def tree_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kb-b1a-test-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.root = self.repo.resolve()
        self.patch_root = mock.patch.object(pub, "ROOT", self.root)
        self.patch_root.start()
        self.addCleanup(self.patch_root.stop)
        shutil.copytree(SCRIPTS, self.root / "publication/engine", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(SCRIPTS.parent / "latex", self.root / "publication/latex")
        shutil.copytree(SCRIPTS.parent / "profiles/esd", self.root / "publication/profiles/fixture")
        (self.root / "scripts").mkdir()
        for name in LEGACY:
            shutil.copyfile(SCRIPTS.parents[1] / "design/scripts" / name, self.root / "scripts" / name)
        (self.root / ".gitignore").write_text("/publication/build/\n/tmp/\n__pycache__/\n")
        for number in range(6):
            (self.root / f"{number:02d}-fixture.md").write_text(f"# Draft {number}\n\n不得发布。\n")
        profile_path = self.root / "publication/profiles/fixture/profile.json"
        config = json.loads(profile_path.read_text())
        config.update(id="fixture", dependencies=["fonts.lock"],
                      sources=[{"id": f"TEST-{n}", "path": f"{n:02}-fixture.md", "revision": "WORKTREE"} for n in range(6)])
        config["views"] = [{"id": f"TEST-{n}", "documents": [f"TEST-{n}"]} for n in range(6)] + [
            dict(next(v for v in config["views"] if v['id']=='ESD-HANDBOOK'), documents=[f"TEST-{n}" for n in range(6)])]
        profile_path.write_text(json.dumps(config))
        (self.root / "publication/profiles/fixture/table-layouts.json").write_text('{"tables":[]}')
        (self.root / "fonts.lock").write_text("fixture dependency declaration\\n")
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
        return subprocess.run([sys.executable, "-B", str(self.root / "publication/engine" / "pub.py"), "--profile", "fixture", *args],
                              cwd=self.repo, capture_output=True, text=True, env=env)

    def prepared(self):
        result = pub.prepare(self.root, "fixture")
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
        for name in ("00-fixture.md", "publication/profiles/fixture/template.tex", "fonts.lock", "publication/engine/links.py"):
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
        for name in ("00-fixture.md", "fonts.lock", "publication/profiles/fixture/template.tex"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.unlink()
                self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
                self.assertFalse((self.root / "publication/build").exists())
                path.write_bytes(original)

    def test_duplicate_numbered_source_rejected(self):
        path = self.root / "publication/profiles/fixture/profile.json"
        config = json.loads(path.read_text())
        config["sources"].append(config["sources"][0])
        path.write_text(json.dumps(config))
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
        self.assertFalse((self.root / "publication/build").exists())

    def test_symlink_inputs_and_directories_rejected(self):
        for name in ("00-fixture.md", "publication/profiles/fixture/template.tex", "fonts.lock", "publication/engine/links.py"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.unlink()
                path.symlink_to(self.dist / "history.bin")
                self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
                path.unlink()
                path.write_bytes(original)
        (self.root / "publication/profiles/fixture" / "linked-directory").symlink_to(self.dist, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
        self.assertFalse((self.root / "publication/build").exists())

    def test_fifo_input_rejected_without_blocking(self):
        path = self.root / "fonts.lock"
        path.unlink()
        os.mkfifo(path)
        completed = subprocess.run([sys.executable, "-B", str(self.root / "publication/engine/pub.py"),
                                    "preview", "--prepare-only", "--profile", "fixture"], capture_output=True, timeout=5)
        self.assertNotEqual(completed.returncode, 0)

    def test_build_symlink_to_dist_rejected(self):
        (self.root / "publication/build").symlink_to(self.dist, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)

    def test_preview_symlink_to_dist_rejected(self):
        (self.root / "publication/build").mkdir()
        (self.root / "publication/build/preview").symlink_to(self.dist, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)

    def test_build_id_symlink_rejected(self):
        with pub.root_handle(self.root) as fd:
            snapshot = pub.input_snapshot(fd, "fixture")
            value = pub.identity(snapshot, pub.git_context(self.root), pub.runtime_identity())
            value["publication"] = json.loads(snapshot["source-set.json"])
        build_id = pub.digest(pub.canonical(value))
        (self.root / "publication/build/preview").mkdir(parents=True)
        (self.root / "publication/build/preview" / build_id).symlink_to(self.dist, target_is_directory=True)
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)

    def test_file_in_place_of_output_directory_rejected(self):
        (self.root / "publication/build").write_bytes(b"do not replace")
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
        self.assertEqual((self.root / "publication/build").read_bytes(), b"do not replace")

    def test_external_output_symlink_target_unchanged(self):
        external = self.repo / "outside-output"
        external.mkdir()
        (external / "sentinel").write_bytes(b"keep")
        (self.root / "publication/build").symlink_to(external, target_is_directory=True)
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
            pub.prepare(self.root, "fixture")
        results = list((self.root / "publication/build").rglob("result.json"))
        self.assertEqual(len(results), 1)
        self.assertEqual(json.loads(results[0].read_text())["status"], "FAILED")

    def test_write_failure_reports_failed(self):
        original = pub.write_bytes

        def fail(fd, name, data):
            if name.startswith("inputs/"):
                raise OSError("injected write failure")
            original(fd, name, data)

        with mock.patch.object(pub, "write_bytes", side_effect=fail), self.assertRaises(OSError):
            pub.prepare(self.root, "fixture")
        result = next((self.root / "publication/build").rglob("result.json"))
        self.assertEqual(json.loads(result.read_text())["status"], "FAILED")

    def test_no_result_when_diagnostics_also_fail(self):
        original = pub.write_bytes

        def fail(fd, name, data):
            if name != "run.json":
                raise OSError("injected full output device")
            original(fd, name, data)

        with mock.patch.object(pub, "write_bytes", side_effect=fail), self.assertRaises(OSError):
            pub.prepare(self.root, "fixture")
        self.assertEqual(list((self.root / "publication/build").rglob("result.json")), [])

    def test_closed_operations_and_redirects_do_not_write(self):
        cases = [[name] for name in ("build", "check", "render", "candidate", "publish")]
        cases += [["publish", "--prepare-only"], ["preview", "--prepare-only", "--output", str(self.dist)],
                  ["preview", "--prepare-only", "--root", str(self.dist)]]
        for args in cases:
            with self.subTest(args=args):
                completed = self.cli(*args)
                self.assertEqual(completed.returncode, 2)
                self.assertFalse((self.root / "publication/build").exists())

    def test_environment_does_not_redirect_outputs(self):
        env = dict(os.environ, TMPDIR=str(self.dist), PUB_OUTPUT=str(self.dist),
                   BUILD_DIR=str(self.dist), DIST_DIR=str(self.dist))
        completed = self.cli("preview", "--prepare-only", env=env)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["path"].startswith(str(self.root.resolve() / "publication/build/preview") + "/"))

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

    def configure_filter(self, kind="clean"):
        helper = self.repo / "filter-helper.py"
        helper.write_text(
            "import pathlib, sys\n"
            f"p = pathlib.Path({str(self.dist / 'history.bin')!r})\n"
            "p.write_bytes(p.read_bytes() + b'FILTER EXECUTED\\n')\n"
            + ("sys.stdout.buffer.write(sys.stdin.buffer.read())\n" if kind == "clean" else "sys.exit(1)\n")
        )
        command = shlex.join([sys.executable, "-B", str(helper)])
        self.git("config", f"filter.fixture.{kind}", command)
        (self.root / ".gitattributes").write_text("00-fixture.md filter=fixture\n")
        source = self.root / "00-fixture.md"
        previous = source.stat()
        source.write_bytes(source.read_bytes().replace("不得".encode(), "可以".encode()))
        # Same size, different bytes/stat: force content examination, not a size-only shortcut.
        os.utime(source, (previous.st_atime, previous.st_mtime - 2))
        return command

    def test_clean_filter_rejected_before_helper_executes(self):
        self.configure_filter()
        completed = self.cli("preview", "--prepare-only")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unsupported Git filter configuration", completed.stderr)
        self.assertFalse((self.root / "publication/build").exists())
        self.assertEqual(tree_bytes(self.dist), self.dist_before)

    def test_process_filter_rejected_before_helper_executes(self):
        self.configure_filter("process")
        completed = self.cli("preview", "--prepare-only")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unsupported Git filter configuration", completed.stderr)
        self.assertFalse((self.root / "publication/build").exists())

    def test_included_filter_configuration_rejected(self):
        command = self.configure_filter()
        self.git("config", "--unset", "filter.fixture.clean")
        included = self.repo / "included.gitconfig"
        self.git("config", "--file", str(included), "filter.fixture.clean", command)
        self.git("config", "include.path", str(included))
        with self.assertRaisesRegex(pub.PreparationError, "unsupported Git filter configuration"):
            pub.git_context(self.root)
        self.assertFalse((self.root / "publication/build").exists())

    def test_conditional_filter_configuration_rejected(self):
        command = self.configure_filter("process")
        self.git("config", "--unset", "filter.fixture.process")
        included = self.repo / "conditional.gitconfig"
        self.git("config", "--file", str(included), "filter.fixture.process", command)
        branch = self.git("symbolic-ref", "--short", "HEAD").decode().strip()
        self.git("config", f"includeIf.onbranch:{branch}.path", str(included))
        with self.assertRaisesRegex(pub.PreparationError, "unsupported Git filter configuration"):
            pub.git_context(self.root)

    def test_global_xdg_filter_configuration_rejected(self):
        command = self.configure_filter()
        self.git("config", "--unset", "filter.fixture.clean")
        xdg = self.repo / "xdg-fixture"
        (xdg / "git").mkdir(parents=True)
        self.git("config", "--file", str(xdg / "git/config"), "filter.fixture.clean", command)
        completed = self.cli("preview", "--prepare-only", env=dict(os.environ, XDG_CONFIG_HOME=str(xdg)))
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unsupported Git filter configuration", completed.stderr)
        self.assertFalse((self.root / "publication/build").exists())

    def test_empty_unused_and_smudge_filters_rejected(self):
        for kind in ("clean", "process", "smudge"):
            with self.subTest(kind=kind):
                self.git("config", f"filter.unused.{kind}", "")
                with self.assertRaisesRegex(pub.PreparationError, "unsupported Git filter configuration"):
                    pub.git_context(self.root)
                self.git("config", "--unset", f"filter.unused.{kind}")

    def test_filter_detection_precedes_every_status_probe(self):
        self.configure_filter()
        original = pub.subprocess.check_output
        with mock.patch.object(pub.subprocess, "check_output", wraps=original) as calls:
            with self.assertRaises(pub.PreparationError):
                pub.git_context(self.root)
        self.assertFalse(any("status" in call.args[0] for call in calls.call_args_list))

    def test_invalid_git_configuration_fails_closed(self):
        with (self.repo / ".git/config").open("a") as stream:
            stream.write("\n[invalid section syntax\n")
        self.assertNotEqual(self.cli("preview", "--prepare-only").returncode, 0)
        self.assertFalse((self.root / "publication/build").exists())

    def test_submodule_gitlinks_outside_design_are_rejected(self):
        commit = self.git("rev-parse", "HEAD").decode().strip()
        self.git("update-index", "--add", "--cacheinfo", f"160000,{commit},outside-design-submodule")
        completed = self.cli("preview", "--prepare-only")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unsupported Git submodule index entries", completed.stderr)
        self.assertFalse((self.root / "publication/build").exists())

    def test_success_record_fsync_failure_never_commits_prepared(self):
        original = pub.os.fsync
        injected = []

        def fail_success_sync(fd):
            info = os.fstat(fd)
            for path in (self.root / "publication/build").rglob("*"):
                if path.name.startswith(("result.json", ".result-")) and path.is_file():
                    file_info = path.stat()
                    if (file_info.st_dev, file_info.st_ino) == (info.st_dev, info.st_ino):
                        if json.loads(path.read_text())["status"] == "PREPARED" and not injected:
                            injected.append(True)
                            raise OSError(errno.EIO, "injected final-record fsync failure")
            return original(fd)

        stderr = io.StringIO()
        with mock.patch.object(pub, "ROOT", self.root), mock.patch.object(pub.os, "fsync", side_effect=fail_success_sync):
            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                code = pub.main(["preview", "--prepare-only", "--profile", "fixture"])
        self.assertEqual(code, 1)
        self.assertEqual(injected, [True])
        self.assertIn("injected final-record fsync failure", stderr.getvalue())
        for path in (self.root / "publication/build").rglob("result.json"):
            self.assertNotEqual(json.loads(path.read_text())["status"], "PREPARED")

    def test_result_link_failure_does_not_commit_prepared(self):
        original = pub.os.link
        injected = []

        def fail_link(source, target, **kwargs):
            if not injected:
                injected.append(True)
                raise OSError(errno.EIO, "injected commit link failure")
            return original(source, target, **kwargs)

        with mock.patch.object(pub.os, "link", side_effect=fail_link), self.assertRaises(OSError):
            pub.prepare(self.root, "fixture")
        records = list((self.root / "publication/build").rglob("result.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(json.loads(records[0].read_text())["status"], "FAILED")

    def test_committed_result_is_not_overwritten(self):
        with pub.root_handle(self.root) as fd:
            first = pub.ResultCommit(fd)
            first.commit(pub.result("CANCELLED"))
            before = (self.root / "result.json").read_bytes()
            second = pub.ResultCommit(fd)
            with self.assertRaises(FileExistsError):
                second.commit(pub.result("PREPARED"))
            self.assertTrue(first.is_committed())
            self.assertFalse(second.is_committed())
            self.assertEqual((self.root / "result.json").read_bytes(), before)

    def test_error_immediately_after_link_preserves_committed_prepared(self):
        original = pub.os.link

        def after_link(source, target, **kwargs):
            original(source, target, **kwargs)
            raise OSError(errno.EIO, "injected post-commit error")

        with mock.patch.object(pub.os, "link", side_effect=after_link):
            outcome = pub.prepare(self.root, "fixture")
        self.assertEqual(outcome["status"], "PREPARED")
        records = list(Path(outcome["path"]).glob(".result-*.pending"))
        self.assertEqual(len(records), 1)  # No contradictory FAILED staging attempt.
        final = Path(outcome["path"]) / "result.json"
        self.assertEqual(final.stat().st_ino, records[0].stat().st_ino)
        self.assertEqual(json.loads(final.read_text())["status"], "PREPARED")

    def check_signal(self, signum, checkpoint="run.json"):
        # Test-only pauses around the real link commit; no production test switches.
        script = '''
import importlib.util, signal, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("fixture_pub", sys.argv[1])
p = importlib.util.module_from_spec(spec)
sys.modules["fixture_pub"] = p
sys.path.insert(0, str(__import__("pathlib").Path(sys.argv[1]).parent))
spec.loader.exec_module(p)
checkpoint = sys.argv[2]
original = p.write_bytes
link = p.os.link
paused = False
def wait_once():
    global paused
    if not paused:
        paused = True
        print("READY", flush=True)
        signal.pause()
def pause(fd, name, data):
    original(fd, name, data)
    if checkpoint == "run.json" and name == "run.json":
        wait_once()
def pause_link(source, target, **kwargs):
    if checkpoint == "before_commit":
        wait_once()
    link(source, target, **kwargs)
    if checkpoint == "after_commit":
        wait_once()
p.write_bytes = pause
p.os.link = pause_link
raise SystemExit(p.main(["preview", "--prepare-only", "--profile", "fixture"]))
'''
        child = subprocess.Popen([sys.executable, "-B", "-c", script, str(self.root / "publication/engine/pub.py"), checkpoint],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([child.stdout], [], [], 10)
            self.assertTrue(ready, "child did not reach the preparation checkpoint")
            self.assertEqual(child.stdout.readline().strip(), "READY")
            child.send_signal(signum)
            _, stderr = child.communicate(timeout=10)
            expected = -signal.SIGKILL if signum == signal.SIGKILL else (0 if checkpoint == "after_commit" else 128 + signum)
            self.assertEqual(child.returncode, expected, stderr)
            records = list((self.root / "publication/build").rglob("result.json"))
            if signum == signal.SIGKILL and checkpoint != "after_commit":
                self.assertEqual(records, [])
            else:
                self.assertEqual(len(records), 1)
                expected_state = "PREPARED" if checkpoint == "after_commit" else "CANCELLED"
                self.assertEqual(json.loads(records[0].read_text())["status"], expected_state)
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

    def test_sigterm_before_commit_has_no_prepared(self):
        self.check_signal(signal.SIGTERM, "before_commit")

    def test_sigkill_before_commit_has_no_final_result(self):
        self.check_signal(signal.SIGKILL, "before_commit")

    def test_sigterm_after_commit_keeps_prepared(self):
        self.check_signal(signal.SIGTERM, "after_commit")

    def test_sigint_after_commit_keeps_prepared(self):
        self.check_signal(signal.SIGINT, "after_commit")

    def test_sigkill_after_commit_keeps_prepared(self):
        self.check_signal(signal.SIGKILL, "after_commit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
