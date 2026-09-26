#!/usr/bin/env python3
"""Compatibility CLI: ESD uses the shared v2 engine; old result bytes stay immutable."""
import runpy
import sys
from pathlib import Path

if __name__ != "__main__":
    raise RuntimeError("Import publication/engine/pub.py; this is an ESD CLI compatibility entry")
engine = Path(__file__).resolve().parents[2] / "publication/engine"
if "--profile" in sys.argv:
    raise SystemExit("Use publication/engine/pub.py to choose a product profile")
if "--from-preview" in sys.argv:
    i = sys.argv.index("--from-preview") + 1
    if i < len(sys.argv) and not sys.argv[i].startswith("publication/build/preview/"):
        raise SystemExit("v1 records are immutable and are not converted; use the repository-relative v2 preview path")
sys.path.insert(0, str(engine))
sys.argv[0] = str(engine / "pub.py")
sys.argv.extend(["--profile", "esd"])
runpy.run_path(str(engine / "pub.py"), run_name="__main__")
