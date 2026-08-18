#!/usr/bin/env python3
"""Prepare files before uploading/publishing.

This bumps cache-busting versions in the normal multi-file app, then rebuilds
the single-file offline artifact.

Usage:
    python tools/prepare_publish.py
    python tools/prepare_publish.py 20260818-1
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    version_args = sys.argv[1:]
    python = sys.executable

    run([python, "tools/bump_cache_version.py", *version_args])
    run([python, "tools/build_offline_html.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
