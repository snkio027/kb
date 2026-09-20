#!/usr/bin/env python3
"""Closed legacy release-manifest writer; no PDF tooling or writes."""
import sys

print("DISABLED: legacy manifest overwrote dist. Publication remains closed; use pub.py preview --prepare-only for input records.", file=sys.stderr)
raise SystemExit(2)
