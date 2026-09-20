#!/usr/bin/env bash
# B1-A: no legacy publishing or implicit forwarding.
printf '%s\n' 'DISABLED: legacy build wrote historical dist. Use pub.py preview --prepare-only; PDF build awaits B1-B.' >&2
exit 2
