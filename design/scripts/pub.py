#!/usr/bin/env python3
"""B1-A only: prepare isolated inputs; all PDF and release operations stay closed."""

import argparse
import hashlib
import json
import os
import platform
import signal
import stat
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LOCKS = ("fonts.lock", "package-lock.txt", "texlive.profile")
REQUIRED_PUBLICATION = ("publication/template.tex", "publication/profiles/release.yaml")
POLICY = {
    "schema_version": 1,
    "operation": "PREVIEW_INPUT_PREPARATION",
    "pdf_build": "DISABLED_PENDING_B1B",
    "candidate": "DISABLED",
    "publish": "DISABLED",
    "output_policy": "build/preview/<build-id>/<attempt-id>",
}
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class PreparationError(Exception):
    pass


class Cancelled(Exception):
    def __init__(self, signum):
        super().__init__(f"received signal {signum}")
        self.signum = signum


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def parts(relative):
    path = Path(relative)
    if path.is_absolute() or not path.parts or any(p in {".", ".."} for p in path.parts):
        raise PreparationError("unsafe relative path: " + str(relative))
    return path.parts


@contextmanager
def directory(parent_fd, relative, create=False):
    """Traverse through no-follow directory handles, never resolved output strings."""
    current = os.dup(parent_fd)
    try:
        for name in parts(relative):
            if create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=current)
                except FileExistsError:
                    pass
            child = os.open(name, DIRECTORY_FLAGS, dir_fd=current)
            os.close(current)
            current = child
        yield current
    finally:
        os.close(current)


def regular_bytes(parent_fd, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise PreparationError("input is not a regular file: " + name)
        return stream.read()


def input_snapshot(root_fd):
    result = {}
    names = os.listdir(root_fd)
    for number in range(6):
        matches = [name for name in names if name.startswith(f"{number:02d}-") and name.endswith(".md")]
        if len(matches) != 1:
            raise PreparationError(f"expected exactly one {number:02d} Markdown source")
        result[matches[0]] = regular_bytes(root_fd, matches[0])
    for name in LOCKS:
        result[name] = regular_bytes(root_fd, name)

    def collect(fd, prefix):
        for name in sorted(os.listdir(fd)):
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            relative = prefix + "/" + name
            if stat.S_ISDIR(info.st_mode):
                with directory(fd, name) as child:
                    collect(child, relative)
            elif stat.S_ISREG(info.st_mode):
                result[relative] = regular_bytes(fd, name)
            else:
                raise PreparationError("unsupported or linked input: " + relative)

    with directory(root_fd, "publication") as publication_fd:
        collect(publication_fd, "publication")
    for name in REQUIRED_PUBLICATION:
        if name not in result:
            raise PreparationError("missing required input: " + name)
    with directory(root_fd, "scripts") as scripts_fd:
        for name in sorted(os.listdir(scripts_fd)):
            if name.endswith((".py", ".sh")):
                result["scripts/" + name] = regular_bytes(scripts_fd, name)
    if "scripts/pub.py" not in result:
        raise PreparationError("missing preparation entry point")
    return result


def git_context(root):
    # Metadata probes must not inherit temp/cache redirection into historical dist.
    # macOS /usr/bin/git can otherwise make xcrun write its cache into TMPDIR.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("GIT_", "XCRUN_")) and key not in {"TMPDIR", "TMP", "TEMP"}}
    env["GIT_OPTIONAL_LOCKS"] = "0"

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args], env=env,
            stderr=subprocess.PIPE,
        )

    if Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip()).resolve() != root.parent.resolve():
        raise PreparationError("design must belong to its parent Git repository")
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all")
    return {
        "commit": git("rev-parse", "HEAD").decode("ascii").strip(),
        "dirty": bool(status),
        "worktree_status_sha256": digest(status),
    }


def runtime_identity():
    executable = Path(sys.executable).resolve(strict=True)
    return {
        "python": {
            "path": str(executable), "sha256": digest(executable.read_bytes()),
            "version": sys.version, "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "pdf_toolchain": "NOT_PROBED / NOT_EXECUTED",
        "actual_fonts": "NOT_RESOLVED",
    }


def identity(snapshot, source, runtime):
    return {
        "policy": POLICY, "source": source, "runtime": runtime,
        "inputs": [
            {"path": name, "bytes": len(data), "sha256": digest(data)}
            for name, data in sorted(snapshot.items())
        ],
    }


def write_bytes(fd, relative, data):
    names = parts(relative)
    # All files are exclusive and read-only after creation; never replace an entry.
    def write(parent):
        target = os.open(names[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o400, dir_fd=parent)
        with os.fdopen(target, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    if len(names) == 1:
        write(fd)
    else:
        with directory(fd, "/".join(names[:-1]), create=True) as parent:
            write(parent)


def write_json(fd, name, value):
    write_bytes(fd, name, canonical(value) + b"\n")


def result(status, **details):
    return {
        "status": status, "finished_at": now(),
        "meaning": "Input preparation only; not a PDF or publication approval",
        "checks": {key: "NOT_RUN" for key in ("pdf", "content_fidelity", "visual", "reading")},
        **details,
    }


def prepare(root):
    with root_handle(root) as root_fd:
        source = git_context(root)
        snapshot = input_snapshot(root_fd)
        runtime = runtime_identity()
        description = identity(snapshot, source, runtime)
        build_id = digest(canonical(description))
        attempt_id = uuid.uuid4().hex
        relative = f"build/preview/{build_id}/{attempt_id}"
        with directory(root_fd, f"build/preview/{build_id}", create=True) as build_fd:
            # A collision is a failure, never permission to reuse an old attempt.
            os.mkdir(attempt_id, mode=0o700, dir_fd=build_fd)
            with directory(build_fd, attempt_id) as run_fd:
                try:
                    write_json(run_fd, "run.json", {
                        "status": "PREPARING", "channel": "PREVIEW", "started_at": now(),
                        "build_id": build_id, "attempt_id": attempt_id, "identity": description,
                    })
                    for name, data in sorted(snapshot.items()):
                        write_bytes(run_fd, "inputs/" + name, data)
                    if input_snapshot(root_fd) != snapshot or git_context(root) != source:
                        raise PreparationError("inputs or Git context changed during preparation")
                    if runtime_identity() != runtime:
                        raise PreparationError("preparation runtime changed during preparation")
                    write_json(run_fd, "result.json", result("PREPARED"))
                except (Exception, KeyboardInterrupt) as error:
                    status = "CANCELLED" if isinstance(error, (Cancelled, KeyboardInterrupt)) else "FAILED"
                    try:
                        write_json(run_fd, "result.json", result(status, diagnostic=str(error)))
                    except (OSError, Cancelled, KeyboardInterrupt):
                        pass  # Incomplete or malformed result is never success.
                    raise
        return {"status": "PREPARED", "build_id": build_id, "path": str(root / relative)}


@contextmanager
def root_handle(root):
    fd = os.open(root, DIRECTORY_FLAGS)
    try:
        yield fd
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preview", "build", "check", "render", "candidate", "publish"))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    if args.operation != "preview" or not args.prepare_only:
        parser.error("B1-A only permits preview --prepare-only; PDF operations and publication are disabled")

    def cancel(signum, _frame):
        raise Cancelled(signum)

    previous = {signum: signal.signal(signum, cancel) for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        print(json.dumps(prepare(ROOT), ensure_ascii=False))
        return 0
    except Cancelled as error:
        print("CANCELLED: input preparation interrupted", file=sys.stderr)
        return 128 + error.signum
    except KeyboardInterrupt:
        print("CANCELLED: input preparation interrupted", file=sys.stderr)
        return 130
    except (PreparationError, OSError, subprocess.SubprocessError) as error:
        print("FAILED: " + str(error), file=sys.stderr)
        return 1
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    raise SystemExit(main())
