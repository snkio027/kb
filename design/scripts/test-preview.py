#!/usr/bin/env python3
"""Compatibility test command; runs the migrated v2 regression suite."""
import runpy
import sys
from pathlib import Path
target = Path(__file__).resolve().parents[2] / "publication/tests/test-preview.py"
sys.argv[0] = str(target)
runpy.run_path(str(target), run_name="__main__")
