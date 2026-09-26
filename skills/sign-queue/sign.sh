#!/bin/sh
# sign.sh — compatibility wrapper; the drain is signq.py (`make sign`). `sign.sh --list` == `signq.py list`.
exec python3 "$(dirname "$0")/signq.py" "$@"
