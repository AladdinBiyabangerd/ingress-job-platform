"""Run one collector pass, list stored jobs, or repeat the pass every hour."""

from __future__ import annotations

import sys

from worker.runner import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
