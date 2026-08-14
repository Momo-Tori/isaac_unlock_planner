#!/usr/bin/env python3
"""Bump cache-busting query strings before publishing to GitHub Pages.

Usage:
    python tools/bump_cache_version.py
    python tools/bump_cache_version.py 20260814-2

Without an explicit value, a local timestamp is used.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
STYLES = ROOT / "styles.css"


def main() -> int:
    version = sys.argv[1].strip() if len(sys.argv) > 1 else datetime.now().strftime("%Y%m%d%H%M%S")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise SystemExit("版本号只能包含字母、数字、点、下划线和连字符。")

    index = INDEX.read_text(encoding="utf-8")
    index, n1 = re.subn(r"([?&]v=)[A-Za-z0-9._-]+", rf"\g<1>{version}", index)
    index, n2 = re.subn(r"<!-- CACHE_VERSION: [^。<]+。", f"<!-- CACHE_VERSION: {version}。", index)
    INDEX.write_text(index, encoding="utf-8")

    styles = STYLES.read_text(encoding="utf-8")
    styles, n3 = re.subn(r"(Achievement_sprite\.jpg\?v=)[A-Za-z0-9._-]+", rf"\g<1>{version}", styles)
    STYLES.write_text(styles, encoding="utf-8")

    print(f"Cache version -> {version}")
    print(f"Updated index resource refs: {n1}")
    print(f"Updated index marker: {n2}")
    print(f"Updated sprite ref: {n3}")
    if n1 < 8 or n2 != 1 or n3 != 1:
        print("Warning: expected references were not all found; please inspect the files.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
