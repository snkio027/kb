#!/usr/bin/env python3
"""Closed arbitrary-output renderer; no optional imports or writes."""
import sys

print("DISABLED: direct renderer accepts unchecked output paths. Run-scoped PDF rendering is not yet enabled.", file=sys.stderr)
raise SystemExit(2)
