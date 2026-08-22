#!/usr/bin/env python3
"""Compatibility launcher for project-local and skill-based execution."""

import sys
from pathlib import Path

checkout_source = Path(__file__).resolve().parents[3] / "src"
if checkout_source.is_dir():
    sys.path.insert(0, str(checkout_source))

from agent_code_guard.code_guard import main


if __name__ == "__main__":
    raise SystemExit(main())
