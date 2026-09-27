#!/usr/bin/env python3
"""Read-only verifier for this exact authorized release, not a publisher."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = "4f8fe84a17429bc0a3b731461bfac5f0e1402cda"
PDF = "Modern-Cpp-Failure-Semantics-Handbook-v1.0.0.pdf"
DIGEST = "2957aab0ad153873307a83af9383f08dabcfb3caae8c5f27750a6f48ee3c4e9c"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main():
    paths = {PDF: HERE / "output/pdf" / PDF}
    paths.update({n: HERE / "distribution" / n for n in
                  ("release-manifest.json", "RELEASE-NOTES.md", "SHA256SUMS")})
    expected = {name: sha(path) for name, path in paths.items()}
    require(expected[PDF] == DIGEST, "PDF changed")
    lines = paths["SHA256SUMS"].read_text().splitlines()
    entries = [line.split("  ", 1) for line in lines]
    require(len(entries) == 3 and {n for _, n in entries} == set(paths) - {"SHA256SUMS"},
            "Checksum file-set mismatch")
    for digest, name in entries:
        require(expected[name] == digest, f"Checksum mismatch: {name}")
    manifest = json.loads(paths["release-manifest.json"].read_bytes())
    auth = json.loads((HERE / "authorization.json").read_bytes())
    candidate = json.loads((HERE / "output/pdf/release-manifest.json").read_bytes())
    require(manifest["payload_status"] == "AUTHORIZED_FOR_DISTRIBUTION", "Wrong payload status")
    require(auth["status"] == "PUBLISH_AUTHORIZED" and auth["user_message_verbatim"] == "批准发布",
            "Missing recorded authorization")
    require(manifest["pdf"] == candidate["pdf"] and auth["pdf_sha256"] == DIGEST,
            "Authorization/candidate identity mismatch")
    require(manifest["candidate_commit"] == auth["candidate_commit"] == BASE,
            "Candidate commit mismatch")
    require(manifest["candidate_id"] == candidate["candidate_id"] == auth["candidate_id"],
            "Candidate ID mismatch")
    for key, rel in (("candidate_release_manifest_sha256", "output/pdf/release-manifest.json"),
                     ("evidence_export_sha256", "evidence/export.json"),
                     ("reader_evidence_sha256", "evidence/reader-evidence.json")):
        require(manifest[key] == sha(HERE / rel), f"Evidence mismatch: {key}")
    allowed = {"publication/README.md", str((HERE / "README.md").relative_to(ROOT))}
    protected = 0
    tree = git("ls-tree", "-r", "-z", BASE).split(b"\0")
    for entry in filter(None, tree):
        meta, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode()
        if path in allowed:
            continue
        require((ROOT / path).read_bytes() == git("cat-file", "blob", meta.split()[2].decode()),
                f"Protected file changed: {path}")
        protected += 1
    old_dist = set(git("ls-tree", "-r", "--name-only", BASE, "design/dist").decode().splitlines())
    now_dist = {str(p.relative_to(ROOT)) for p in (ROOT / "design/dist").rglob("*") if p.is_file()}
    require(old_dist == now_dist, "Historical dist file set changed")
    if len(sys.argv) > 1:
        downloaded = Path(sys.argv[1]).resolve()
        require({p.name for p in downloaded.iterdir()} == set(paths), "Downloaded file set mismatch")
        for name, digest in expected.items():
            require(sha(downloaded / name) == digest, f"Downloaded bytes differ: {name}")
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    print(json.dumps({"status": "PACKAGE_AND_SCOPE_PASS", "pdf_sha256": DIGEST,
                      "asset_sha256": expected, "protected_files": protected,
                      "download_checked": len(sys.argv) > 1,
                      "publication_fact": "Not established by this offline verifier"}))


if __name__ == "__main__":
    main()
