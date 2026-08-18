#!/usr/bin/env python3
"""Build a single-file offline HTML artifact from index.html.

Usage:
    python tools/build_offline_html.py
    python tools/build_offline_html.py --output isaac-unlock-planner-offline.html
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "index.html"
DEFAULT_OUTPUT = ROOT / "isaac-unlock-planner-offline.html"


def local_path(url: str, base_dir: Path) -> Path | None:
    parts = urlsplit(url.strip())
    if parts.scheme or parts.netloc:
        return None
    path = unquote(parts.path)
    if not path:
        return None
    candidate = (base_dir / path).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        raise SystemExit(f"Refusing to inline path outside project: {url}")
    return candidate


def data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if not mime:
        mime = "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def strip_query_key(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return f"./{rel}"


CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)([^)'\"\s]+)\1\s*\)")


def inline_css_assets(css: str, css_path: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        quote = match.group(1) or '"'
        url = match.group(2)
        if url.startswith(("data:", "http:", "https:", "blob:")):
            return match.group(0)
        path = local_path(url, css_path.parent)
        if path is None or not path.exists():
            raise SystemExit(f"CSS asset not found: {url} referenced from {css_path}")
        return f"url({quote}{data_uri(path)}{quote})"

    return CSS_URL_RE.sub(replace, css)


def offline_asset_map() -> dict[str, str]:
    assets: dict[str, str] = {}
    for folder in (ROOT / "assets" / "character", ROOT / "assets" / "boss"):
        for path in sorted(folder.glob("*")):
            if path.is_file():
                assets[strip_query_key(path)] = data_uri(path)
    return assets


def patch_app_js_for_offline(js: str, assets: dict[str, str]) -> str:
    js = js.replace(
        "  'use strict';\n",
        "  'use strict';\n\n  const OFFLINE_ASSETS = window.ISAAC_OFFLINE_ASSETS || {};\n",
        1,
    )

    old_character = "  function characterLocalImage(character) {\n    return versionedLocalUrl(`./assets/character/${character.id}.png`);\n  }\n"
    new_character = "  function characterLocalImage(character) {\n    const url = `./assets/character/${character.id}.png`;\n    return OFFLINE_ASSETS[url] || versionedLocalUrl(url);\n  }\n"
    old_boss = "  function bossImage(boss) {\n    return [versionedLocalUrl(`./assets/boss/${boss.id}.png`)];\n  }\n"
    new_boss = "  function bossImage(boss) {\n    const url = `./assets/boss/${boss.id}.png`;\n    return [OFFLINE_ASSETS[url] || versionedLocalUrl(url)];\n  }\n"

    js = js.replace(old_character, new_character, 1)
    js = js.replace(old_boss, new_boss, 1)
    if old_character in js or old_boss in js or "OFFLINE_ASSETS" not in js:
        raise SystemExit("Failed to patch dynamic asset URLs in js/app.js")

    asset_json = json.dumps(assets, ensure_ascii=False, separators=(",", ":"))
    return f"window.ISAAC_OFFLINE_ASSETS={asset_json};\n{js}"


LINK_RE = re.compile(r"<link\b(?=[^>]*\brel=[\"']stylesheet[\"'])(?=[^>]*\bhref=[\"']([^\"']+)[\"'])[^>]*>", re.I)
SCRIPT_RE = re.compile(r"<script\b(?=[^>]*\bsrc=[\"']([^\"']+)[\"'])[^>]*>\s*</script>", re.I)


def build(input_path: Path, output_path: Path) -> None:
    html = input_path.read_text(encoding="utf-8")
    assets = offline_asset_map()

    def replace_link(match: re.Match[str]) -> str:
        href = match.group(1)
        path = local_path(href, input_path.parent)
        if path is None or not path.exists():
            raise SystemExit(f"Stylesheet not found: {href}")
        css = inline_css_assets(path.read_text(encoding="utf-8"), path)
        return f'<style data-offline-src="{href}">\n{css}\n</style>'

    def replace_script(match: re.Match[str]) -> str:
        src = match.group(1)
        path = local_path(src, input_path.parent)
        if path is None or not path.exists():
            raise SystemExit(f"Script not found: {src}")
        js = path.read_text(encoding="utf-8")
        if path.relative_to(ROOT).as_posix() == "js/app.js":
            js = patch_app_js_for_offline(js, assets)
        return f'<script data-offline-src="{src}">\n{js}\n</script>'

    html = LINK_RE.sub(replace_link, html)
    html = SCRIPT_RE.sub(replace_script, html)
    output_path.write_text(html, encoding="utf-8")
    print(f"Offline HTML -> {output_path.relative_to(ROOT)}")
    print(f"Embedded dynamic image assets: {len(assets)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a single-file offline HTML artifact.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.input.resolve(), args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
